"""``answer()`` — the single entry point. Spec ``0080`` (REQ-009, NFR-006).

Composes every stage: interpret -> validate -> authorize -> execute -> chart
-> insights -> narrate -> the returned :class:`ChatResponse`. Every path,
including every way of *not* answering, returns a typed status and a
non-empty reason (NFR-006); a non-answer never carries a chart (AC-022).

Standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable, Dict, Optional, Tuple

from quantsmith.pipelines.metrics_semantic_layer import SemanticLayer

from .authorize import AccessPolicy, authorize_clarification, authorize_plan
from .chart import ChartSpec, choose_chart, to_markdown_table, to_vega_lite
from .execute import Reader, Result, execute
from .insights import Insight, compute_insights
from .interpret import Interpreter, InterpretContext, interpret
from .narrate import default_caveats, ground, template_narrative
from .plan import Clarification, PlanError, QueryPlan, TimeWindow, describe_plan, validate_plan

RESPONSE_STATUSES = ("answered", "clarification_needed", "masked", "empty", "stale", "write_rejected")

# How many periods one year is, per grain — used to shift a window back a
# year for a "prior_year" comparison. Approximate for "day" (365, no leap-year
# adjustment); good enough for a comparison window, not for accrual math.
_PERIODS_PER_YEAR = {"day": 365, "week": 52, "month": 12, "quarter": 4, "year": 1}


class ResponseError(ValueError):
    """Raised by :class:`ChatResponse` when a non-answer status carries a chart,
    or any status carries no reason (NFR-006)."""


@dataclass(frozen=True)
class ChatResponse:
    """The typed answer to a question — or the typed reason there is none."""

    status: str
    reason: str
    headline: str
    insights: Tuple[Insight, ...]
    chart: Optional[ChartSpec]
    vega_lite: Optional[Dict[str, object]]
    markdown_table: Optional[str]
    plan_echo: str
    caveats: Tuple[str, ...]
    citations: Tuple[str, ...]
    run_id: Optional[str] = None
    envelope_uri: Optional[str] = None
    writeback: Optional[object] = None

    def __post_init__(self) -> None:
        if self.status not in RESPONSE_STATUSES:
            raise ResponseError(f"status {self.status!r} not in {RESPONSE_STATUSES}")
        if self.status != "answered" and not self.reason:
            raise ResponseError(f"status {self.status!r} needs a non-empty reason (NFR-006)")
        if self.status != "answered" and self.chart is not None:
            raise ResponseError("a non-answer status must not carry a chart (AC-022)")


@dataclass(frozen=True)
class AnswerContext:
    """Everything ``answer()`` needs, all caller-supplied — no hidden clock,
    no hidden connection (NFR-002, NFR-003)."""

    layer: SemanticLayer
    reader: Reader
    as_of: int
    interpret_context: InterpretContext
    viewer_clearance: str = "public"
    access_policy: AccessPolicy = field(default_factory=AccessPolicy)
    interpreter: Optional[Interpreter] = None
    synthetic: bool = False
    min_sample_rows: int = 10
    staleness_caveat_periods: int = 2
    staleness_hard_periods: int = 30
    units: str = ""
    prior_insight_lookup: Optional[Callable[[str, int], Optional[Result]]] = None
    plan_config: Dict = field(default_factory=dict)


def _refuse(status: str, reason: str, plan_echo: str = "") -> ChatResponse:
    return ChatResponse(
        status=status, reason=reason, headline="", insights=(), chart=None, vega_lite=None,
        markdown_table=None, plan_echo=plan_echo, caveats=(), citations=(),
    )


def answer(question: str, context: AnswerContext) -> ChatResponse:
    """Answer ``question``, or say precisely why not (REQ-009, NFR-006)."""
    interpreted = interpret(question, context.layer, context.interpret_context, context.interpreter)

    if isinstance(interpreted, Clarification):
        masked = authorize_clarification(interpreted, context.access_policy, context.viewer_clearance)
        candidates = f" Candidates: {', '.join(masked.candidates)}." if masked.candidates else ""
        return _refuse("clarification_needed", masked.reason + candidates)

    plan: QueryPlan = interpreted
    try:
        validate_plan(plan, context.layer, context.plan_config)
    except PlanError as exc:
        return _refuse("clarification_needed", str(exc))

    authorized = authorize_plan(plan, context.access_policy, context.viewer_clearance)
    if isinstance(authorized, Clarification):
        return _refuse("masked", authorized.reason)
    plan = authorized

    result = execute(plan, context.layer, context.reader, context.as_of)

    if result.row_count == 0:
        return _refuse("empty", "no rows matched the plan", describe_plan(plan))

    if (
        result.latest_period is not None
        and (context.as_of - result.latest_period) > context.staleness_hard_periods
    ):
        return _refuse(
            "stale",
            f"the latest observed period ({result.latest_period}) is more than "
            f"{context.staleness_hard_periods} periods before as-of ({context.as_of})",
            describe_plan(plan),
        )

    comparison_result = _resolve_comparison(plan, context) if plan.comparison is not None else None

    chart = choose_chart(result, context.layer, units=context.units)
    insight_set = compute_insights(result, comparison_result)
    narrative = template_narrative(insight_set)
    grounding = ground(narrative, insight_set, result)
    if not grounding.ok:
        # Our own deterministic template failed to ground itself — a bug in
        # this module, not a fact about the data. Surface it rather than
        # deliver an unbacked number (RISK-002).
        raise ResponseError(f"template narrative is not grounded: {grounding.unbacked_numbers}")

    caveats = default_caveats(
        result, synthetic=context.synthetic, min_sample_rows=context.min_sample_rows,
        staleness_periods=context.staleness_caveat_periods,
    )
    citations = (
        f"{plan.metric} — owner: {context.layer.definition(plan.metric).owner}",
        f"as of period {context.as_of}",
    )

    return ChatResponse(
        status="answered", reason="", headline=insight_set[0].statement,
        insights=insight_set, chart=chart, vega_lite=to_vega_lite(chart),
        markdown_table=to_markdown_table(chart), plan_echo=describe_plan(plan),
        caveats=caveats, citations=citations,
    )


def _resolve_comparison(plan: QueryPlan, context: AnswerContext) -> Optional[Result]:
    comp = plan.comparison
    if comp.kind == "prior_insight":
        if context.prior_insight_lookup is None:
            return None
        return context.prior_insight_lookup(comp.reference, context.as_of)

    length = plan.window.end_period - plan.window.start_period + 1
    shift = length if comp.kind == "prior_period" else _PERIODS_PER_YEAR.get(plan.window.grain, 365)
    window = TimeWindow(
        start_period=plan.window.start_period - shift,
        end_period=plan.window.end_period - shift,
        grain=plan.window.grain,
    )
    comparison_plan = replace(plan, window=window, comparison=None)
    return execute(comparison_plan, context.layer, context.reader, context.as_of)
