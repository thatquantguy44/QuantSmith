"""``answer()`` — the single entry point. Spec ``0080`` (REQ-009, NFR-006).

Composes every stage: interpret -> validate -> authorize -> execute -> chart
-> insights -> narrate -> the returned :class:`ChatResponse`. Every path,
including every way of *not* answering, returns a typed status and a
non-empty reason (NFR-006); a non-answer never carries a chart (AC-022).

Standard library only.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from typing import Callable, Dict, Mapping, Optional, Tuple

from quantsmith.pipelines.analytics_packs import PackSource
from quantsmith.pipelines.metrics_semantic_layer import SemanticLayer

from .authorize import AccessPolicy, authorize_clarification, authorize_plan
from .chart import ChartSpec, choose_chart, to_markdown_table, to_vega_lite
from .domain import (
    domain_caveats,
    extend_interpret_context,
    resolve_policy,
    select,
    term_conflict,
    writeback_refusal,
)
from .execute import Reader, execute
from .insights import Insight, compute_insights
from .interpret import Interpreter, InterpretContext, interpret
from .narrate import default_caveats, ground, template_narrative
from .plan import Clarification, PlanError, QueryPlan, TimeWindow, describe_plan, validate_plan
from .writeback import (
    WriteBackContract,
    WriteBackError,
    WriteBackOutcome,
    WriteBackWriter,
    build_records,
    publish,
)

RESPONSE_STATUSES = ("answered", "clarification_needed", "masked", "empty", "stale", "write_rejected")

# How many periods one year is, per grain — used to shift a window back a
# year for a "prior_year" comparison. Approximate for "day" (365, no leap-year
# adjustment); good enough for a comparison window, not for accrual math.
_PERIODS_PER_YEAR = {"day": 365, "week": 52, "month": 12, "quarter": 4, "year": 1}


class ResponseError(ValueError):
    """Raised by :class:`ChatResponse` when a non-answer status carries a chart,
    or any status carries no reason (NFR-006)."""


@dataclass(frozen=True)
class WriteBackRequest:
    """Opt-in end-to-end write-back for one answer (REQ-010, REQ-011, T-018).

    Set on :class:`AnswerContext` alongside ``run_id`` — the write-back's
    records are keyed by the same caller-assigned run id an envelope for
    this run would use, never a separately invented one. Publishing is
    dry-run unless both ``dry_run=False`` and (``approved=True`` or the
    contract's own ``auto_approve``) — the same rule ``writeback.publish``
    itself enforces; a refused commit becomes a ``write_rejected``
    :class:`ChatResponse`, never a raised exception (NFR-006).
    """

    contract: WriteBackContract
    writer: WriteBackWriter
    author_handle: str = "nl_analytics"
    dry_run: bool = True
    approved: bool = False
    # Caller-supplied, like every other timestamp in this package — never a
    # clock. Defaults to the request's own as_of when unset.
    created_at: Optional[int] = None


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
    writeback: Optional[WriteBackOutcome] = None
    # Analytics domain packs (0081) applied to this answer, by pack id; empty
    # means generic behavior (REQ-015, REQ-017).
    domain_packs: Tuple[str, ...] = ()
    # Where the applied packs' catalog came from (``PackSource.describe()``,
    # REQ-018); empty when no pack applied.
    domain_pack_source: str = ""

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
    # Returns anything with a ``.values`` mapping compute_insights can read —
    # typically a ``writeback.PriorInsight`` (T-013 not wired here; see
    # writeback.prior_insights and comparison_key()).
    prior_insight_lookup: Optional[Callable[[str, int], Optional[object]]] = None
    plan_config: Dict = field(default_factory=dict)
    # Opt-in 0070 envelope emission (REQ-013, T-014). Both or neither: a
    # request with envelope_dir set but no run_id is an error, since the
    # envelope needs a caller-assigned run id (the same convention every
    # other run/record id in this package follows) and this module never
    # invents one. Leaving both unset keeps the chat path free of side
    # effects, as documented in envelope.py.
    envelope_dir: Optional[str] = None
    run_id: Optional[str] = None
    envelope_actor_clearance: str = "public"
    envelope_interpreter_mode: str = "keyword/1"
    # Caller-declared classification of the dataset behind the question
    # (``contains_pii`` / ``contains_mnpi`` / ``contains_restricted_positions``
    # — NFR-004, AC-020); never inferred. Only consulted when an envelope is
    # emitted — see envelope.py's PRIVACY_FLAGS and redaction behavior.
    dataset_privacy: Dict[str, bool] = field(default_factory=dict)
    # Opt-in end-to-end write-back (REQ-010, REQ-011, T-018). Requires
    # ``run_id`` (shared with envelope emission, if both are requested);
    # unset by default, so asking a question never writes anywhere.
    writeback: Optional[WriteBackRequest] = None
    # The dataset's ``domain:`` tags (as declared in ``sources/*.yml``) and
    # the loaded analytics domain packs (``analytics_packs.load_packs``) to
    # select from (REQ-015). Both caller-supplied — this module reads no
    # files. No tags, or no pack matching them, means generic behavior,
    # stated in the response (REQ-017).
    dataset_domains: Tuple[str, ...] = ()
    domain_packs: Tuple[Mapping, ...] = ()
    # Where ``domain_packs`` came from — the ``PackSource`` that
    # ``analytics_packs.resolve_packs`` returns with them (REQ-018). When a
    # caller supplies packs without one, the response still identifies the
    # catalog by a hash of the packs it was given.
    domain_pack_source: Optional[PackSource] = None


def _refuse(status: str, reason: str, plan_echo: str = "") -> ChatResponse:
    return ChatResponse(
        status=status, reason=reason, headline="", insights=(), chart=None, vega_lite=None,
        markdown_table=None, plan_echo=plan_echo, caveats=(), citations=(),
    )


def _metric_definition_hash(layer: SemanticLayer, metric: str) -> str:
    canonical = json.dumps(asdict(layer.definition(metric)), sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def answer(question: str, context: AnswerContext) -> ChatResponse:
    """Answer ``question``, or say precisely why not (REQ-009, NFR-006)."""
    if context.dataset_domains and not context.domain_packs:
        # Tags with no catalog to select from would silently answer with
        # generic behavior; that is a configuration error (REQ-018).
        raise ResponseError(
            "dataset_domains is set but domain_packs is empty; load a catalog with "
            "analytics_packs.resolve_packs() and pass its packs and source"
        )
    selection = select(context.dataset_domains, context.domain_packs)

    # A term two selected packs map to different metrics is a clarification,
    # never a guess (REQ-015, AC-024) — checked before any interpretation.
    conflict = term_conflict(question, selection)
    if conflict is not None:
        masked = authorize_clarification(conflict, context.access_policy, context.viewer_clearance)
        candidates = f" Candidates: {', '.join(masked.candidates)}." if masked.candidates else ""
        return _refuse("clarification_needed", masked.reason + candidates)

    interpret_context = (
        extend_interpret_context(context.interpret_context, context.layer, selection)
        if selection.packs else context.interpret_context
    )
    interpreted = interpret(question, context.layer, interpret_context, context.interpreter)

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

    policy = resolve_policy(context.layer, plan.metric, selection)
    chart = choose_chart(
        result, context.layer, units=context.units or policy.display_unit,
        snapshot=not policy.sums_across_time,
    )
    insight_set = compute_insights(result, comparison_result, policy=policy)
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
    ) + domain_caveats(selection, policy, plan)
    citations = (
        f"{plan.metric} — owner: {context.layer.definition(plan.metric).owner}",
        f"as of period {context.as_of}",
    )
    pack_source = ""
    if selection.packs:
        pack_source = _pack_source(context).describe()
        citations += (f"domain packs: {pack_source}",)

    final = ChatResponse(
        # A pack may suppress any kind, the level included (``0081`` allows it);
        # the plan echo then stands in as the headline rather than crashing.
        status="answered", reason="", headline=insight_set[0].statement if insight_set else describe_plan(plan),
        insights=insight_set, chart=chart, vega_lite=to_vega_lite(chart),
        markdown_table=to_markdown_table(chart), plan_echo=describe_plan(plan),
        caveats=caveats, citations=citations, domain_packs=selection.pack_ids,
        domain_pack_source=pack_source,
    )

    if context.writeback is not None:
        if not context.run_id:
            raise ResponseError("writeback is set but run_id is not (a write-back record is keyed by a caller-assigned run id)")
        refusal = writeback_refusal(selection)
        if refusal is not None:
            # Write-back is eligible only when every applied pack is
            # reviewed (REQ-016, AC-025); refused before any record is built.
            return _refuse("write_rejected", refusal, describe_plan(plan))
        request = context.writeback
        records = build_records(
            plan, result, insight_set, run_id=context.run_id, question=question,
            metric_definition_hash=_metric_definition_hash(context.layer, plan.metric),
            author_handle=request.author_handle, interpreter_mode=plan.interpreter,
            created_at=request.created_at if request.created_at is not None else context.as_of,
        )
        try:
            outcome = publish(
                records, request.contract, request.writer,
                dry_run=request.dry_run, approved=request.approved,
            )
        except WriteBackError as exc:
            # A refused commit is a typed non-answer, never a raised
            # exception through the chat path (NFR-006) — the caller asked
            # a valid question but its write-back could not be committed.
            return _refuse("write_rejected", str(exc), describe_plan(plan))
        final = replace(final, run_id=context.run_id, writeback=outcome)

    if context.envelope_dir is not None:
        if not context.run_id:
            raise ResponseError("envelope_dir is set but run_id is not (REQ-013 needs a caller-assigned run id)")
        # Local import: envelope.py imports ChatResponse from this module, so
        # importing it at module level here would be circular. Emission is
        # opt-in and only ever reached when a caller actually asked for one.
        from .envelope import emit_answer_evidence

        envelope_path = emit_answer_evidence(
            question, plan, result, chart, insight_set, final, context.envelope_dir,
            run_id=context.run_id, actor_clearance=context.envelope_actor_clearance,
            interpreter_mode=context.envelope_interpreter_mode,
            dataset_privacy=context.dataset_privacy,
        )
        final = replace(final, envelope_uri=str(envelope_path))

    return final


def _pack_source(context: AnswerContext) -> PackSource:
    if context.domain_pack_source is not None:
        return context.domain_pack_source
    canonical = json.dumps(list(context.domain_packs), sort_keys=True, separators=(",", ":"))
    from quantsmith import __version__

    return PackSource(
        kind="caller-supplied", location="(in memory)", version=__version__,
        content_hash=f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}",
        pack_count=len(context.domain_packs),
    )


def comparison_key(plan: QueryPlan) -> str:
    """The identity key a persisted "prior insight" comparison matches on:
    what was asked (metric + declared dimensions), not the rolling window —
    see ``writeback.prior_insights``."""
    return "|".join((plan.metric, *plan.dimensions))


def _resolve_comparison(plan: QueryPlan, context: AnswerContext) -> Optional[object]:
    comp = plan.comparison
    if comp.kind == "prior_insight":
        if context.prior_insight_lookup is None:
            return None
        # "Yesterday" means strictly before today: exclude anything already
        # persisted today by looking up as of one period earlier, not the
        # current as-of itself (AC-016). A reference this module does not
        # recognize falls back to the current as-of unshifted.
        lookup_as_of = context.as_of - 1 if comp.reference == "yesterday" else context.as_of
        return context.prior_insight_lookup(comparison_key(plan), lookup_as_of)

    length = plan.window.end_period - plan.window.start_period + 1
    shift = length if comp.kind == "prior_period" else _PERIODS_PER_YEAR.get(plan.window.grain, 365)
    window = TimeWindow(
        start_period=plan.window.start_period - shift,
        end_period=plan.window.end_period - shift,
        grain=plan.window.grain,
    )
    comparison_plan = replace(plan, window=window, comparison=None)
    return execute(comparison_plan, context.layer, context.reader, context.as_of)
