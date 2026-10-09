"""Natural-language interpretation seam. Spec ``0080`` (REQ-002, REQ-003).

The baseline :class:`KeywordInterpreter` ships today; an LLM interpreter (via
``adapters/llm_runtime/``) plugs in later through :func:`register_interpreter`
without any caller change — both produce the same
:class:`~quantsmith.nl_analytics.plan.QueryPlan`, and both are checked by the
same :func:`~quantsmith.nl_analytics.plan.validate_plan` before execution
(REQ-003, AC-004). Ambiguity is resolved by asking, never by guessing
(REQ-002).

Standard library only.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import (
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Protocol,
    Tuple,
    runtime_checkable,
)

from quantsmith.pipelines.metrics_semantic_layer import SemanticLayer

from .plan import (
    COMPARISON_KINDS,
    FILTER_OPS,
    GRAINS,
    MAX_DIMENSIONS,
    Clarification,
    Comparison,
    Filter,
    PlanError,
    QueryPlan,
    TimeWindow,
    validate_plan,
)

_WORD_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class InterpretContext:
    """Caller-supplied context an interpreter reads (REQ-001).

    ``as_of`` and ``today_period`` are supplied by the caller, never read from
    a clock inside the interpreter (NFR-002 — no hidden "now").
    """

    today_period: int
    default_grain: str = "day"
    default_window_periods: Optional[int] = None  # e.g. 7 for "last 7 days" default
    known_metric_synonyms: Mapping[str, Tuple[str, ...]] = field(default_factory=dict)
    known_dimension_synonyms: Mapping[str, Tuple[str, ...]] = field(default_factory=dict)


@runtime_checkable
class Interpreter(Protocol):
    """The contract every interpretation backend implements (REQ-003)."""

    @property
    def name(self) -> str:  # pragma: no cover - trivial
        ...

    def interpret(self, question: str, layer: SemanticLayer, context: InterpretContext):
        """Return a :class:`QueryPlan` or a :class:`Clarification`. Never guess."""
        ...


_REGISTRY: Dict[str, Interpreter] = {}


def register_interpreter(interpreter: Interpreter) -> None:
    """Add an interpreter (e.g. an LLM backend) under its own ``name`` (REQ-003)."""
    _REGISTRY[interpreter.name] = interpreter


def get_interpreter(name: str) -> Interpreter:
    if name not in _REGISTRY:
        raise KeyError(f"no interpreter registered under {name!r}")
    return _REGISTRY[name]


def registered_interpreters() -> Tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


def _tokens(text: str) -> List[str]:
    return _WORD_RE.findall(text.lower())


_RELATIVE_WINDOWS = {
    "today": (0, 0),
    "yesterday": (1, 1),
    "this week": (0, 6),
    "last week": (7, 13),
    "this month": (0, 29),
    "mtd": (0, 29),
}


class KeywordInterpreter:
    """Deterministic baseline interpreter: metric/dimension synonyms plus a
    small set of relative-date phrases. Ships as the seam's reference
    implementation (REQ-003); an LLM interpreter is an upgrade, not a
    dependency.
    """

    name = "keyword"

    def interpret(
        self, question: str, layer: SemanticLayer, context: InterpretContext
    ):
        tokens = set(_tokens(question))
        candidates = self._match_metrics(tokens, layer, context)
        if len(candidates) == 0:
            return Clarification(reason="no known metric matched the question", question=question)
        if len(candidates) > 1:
            return Clarification(
                reason="more than one metric matched the question",
                candidates=tuple(sorted(candidates)),
                question=question,
            )
        metric = candidates[0]
        defn = layer.definition(metric)

        dims = tuple(
            d for d in defn.dimensions
            if d in tokens or any(s in question.lower() for s in context.known_dimension_synonyms.get(d, ()))
        )

        window, defaults = self._window(question, context)

        return QueryPlan(
            metric=metric,
            dimensions=dims,
            filters=(),
            window=window,
            comparison=self._comparison(question),
            rank=None,
            defaults_applied=defaults,
            interpreter=f"{self.name}/1",
        )

    def _match_metrics(self, tokens: set, layer: SemanticLayer, context: InterpretContext) -> List[str]:
        found = []
        for name in layer._defs:  # governed vocabulary only — no metric outside the registry
            names_to_try = {name.replace("_", " ")} | {
                s.lower() for s in context.known_metric_synonyms.get(name, ())
            }
            if name in tokens or any(_matches_phrase(phrase, tokens) for phrase in names_to_try):
                found.append(name)
        return found

    def _window(self, question: str, context: InterpretContext) -> Tuple[TimeWindow, Tuple[str, ...]]:
        q = question.lower()
        for phrase, (start_back, end_back) in _RELATIVE_WINDOWS.items():
            if phrase in q:
                return (
                    TimeWindow(
                        start_period=context.today_period - end_back,
                        end_period=context.today_period - start_back,
                        grain=context.default_grain,
                    ),
                    (),
                )
        if context.default_window_periods is None:
            raise _NoDefaultWindow()
        return (
            TimeWindow(
                start_period=context.today_period - context.default_window_periods + 1,
                end_period=context.today_period,
                grain=context.default_grain,
            ),
            ("window",),
        )

    @staticmethod
    def _comparison(question: str) -> Optional[Comparison]:
        q = question.lower()
        if "since yesterday" in q:
            return Comparison(kind="prior_insight", reference="yesterday")
        if "last week" in q and ("vs" in q or "compared" in q or "versus" in q):
            return Comparison(kind="prior_period")
        if "year over year" in q or "yoy" in q or "vs last year" in q:
            return Comparison(kind="prior_year")
        return None


# ---------------------------------------------------------------------------
# LLM interpreter (T-025, REQ-020, AC-029)
# ---------------------------------------------------------------------------

# ``complete(prompt, system) -> text``. The caller builds it — typically from
# ``quantsmith.adapters.llm_runtime`` — so this package never opens a
# connection (NFR-003, AC-019). It may raise anything; ``LookupError`` means
# "no model configured" (an ``api_style: none`` profile).
Completer = Callable[[str, str], str]

_PLAN_KEYS = {"metric", "dimensions", "filters", "window", "comparison", "rank"}

_INTERPRETER_SYSTEM = """You translate a business question into a governed query plan.
Use only the metrics, dimensions, grains, filter operators, and comparison kinds listed in the
vocabulary. Never invent a metric or dimension, never write SQL or code, never guess.
Reply with exactly one JSON object and nothing else, in one of two shapes:
  {"metric": str, "dimensions": [str], "filters": [{"dimension": str, "op": "eq"|"in", "values": [str]}],
   "window": {"start_period": int, "end_period": int, "grain": str} | null,
   "comparison": {"kind": str, "reference": str | null} | null, "rank": int | null}
  {"clarification": {"reason": str, "candidates": [metric names]}}
Periods are integers; today's period is today_period, and no window may end after it. Use null
for window when the question names no time range. Ask for clarification when the question could
mean more than one metric or names something outside the vocabulary."""


def _vocabulary(layer: SemanticLayer, context: InterpretContext) -> Dict[str, object]:
    metrics = []
    for name in sorted(layer._defs):  # governed vocabulary only
        d = layer.definition(name)
        metrics.append({
            "name": name, "kind": d.kind, "aggregation": d.agg, "grain": d.grain,
            "dimensions": list(d.dimensions),
            "synonyms": list(context.known_metric_synonyms.get(name, ())),
        })
    return {
        "metrics": metrics,
        "dimension_synonyms": {k: list(v) for k, v in sorted(context.known_dimension_synonyms.items())},
        "grains": list(GRAINS), "filter_ops": list(FILTER_OPS), "comparison_kinds": list(COMPARISON_KINDS),
        "max_dimensions": MAX_DIMENSIONS, "today_period": context.today_period,
        "default_grain": context.default_grain, "default_window_periods": context.default_window_periods,
    }


def _strict_json(text: str) -> Dict[str, object]:
    body = text.strip()
    if body.startswith("```"):  # tolerate one fenced block, nothing else
        lines = body.splitlines()
        if len(lines) < 2 or not lines[-1].strip().startswith("```"):
            raise ValueError("unterminated code fence")
        body = "\n".join(lines[1:-1]).strip()
    data = json.loads(body)
    if not isinstance(data, dict):
        raise ValueError("the reply is not a JSON object")  # noqa: TRY004 - an invalid reply, not a caller type error
    return data


def _str_list(value: object, field_name: str) -> Tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise PlanError(f"{field_name} must be a list of strings")
    return tuple(value)


class LLMInterpreter:
    """Interpret with a language model, through the same gate as the baseline (REQ-003, REQ-020).

    The model only ever proposes: its reply must be one JSON object with known
    fields, it becomes a :class:`QueryPlan` through the plan's own checks, and
    :func:`validate_plan` runs before anything executes. Malformed output, an
    ungoverned plan, or a model failure returns a :class:`Clarification`
    naming the reason — never a guess. When ``fallback`` is given (usually
    :class:`KeywordInterpreter`), it answers instead when no model is
    available, and the plan records which interpreter produced it.
    """

    def __init__(self, complete: Completer, *, name: str = "llm", version: str = "1",
                 fallback: Optional[Interpreter] = None) -> None:
        self._complete = complete
        self.name = name
        self.version = version
        self._fallback = fallback

    @property
    def label(self) -> str:
        return f"{self.name}/{self.version}"

    def prompt(self, question: str, layer: SemanticLayer, context: InterpretContext) -> str:
        return json.dumps({"vocabulary": _vocabulary(layer, context), "question": question},
                          sort_keys=True, ensure_ascii=False)

    def interpret(self, question: str, layer: SemanticLayer, context: InterpretContext):
        try:
            reply = self._complete(self.prompt(question, layer, context), _INTERPRETER_SYSTEM)
        except Exception as exc:  # noqa: BLE001 - any model failure becomes a clarification or the fallback, never a guess
            if self._fallback is not None:
                return self._fallback.interpret(question, layer, context)
            code = getattr(exc, "code", type(exc).__name__)
            return Clarification(reason=f"the language model could not interpret the question ({code})",
                                 question=question)
        try:
            data = _strict_json(reply)
        except ValueError as exc:
            return Clarification(reason=f"the language model's reply was not a valid plan ({exc})",
                                 question=question)
        if "clarification" in data:
            return self._clarification(data["clarification"], layer, question)
        try:
            plan = self._plan(data, context)
            validate_plan(plan, layer)
        except (PlanError, TypeError, ValueError) as exc:
            return Clarification(reason=f"the language model proposed a plan that is not governed: {exc}",
                                 question=question)
        return plan

    @staticmethod
    def _clarification(raw: object, layer: SemanticLayer, question: str) -> Clarification:
        if not isinstance(raw, dict) or not isinstance(raw.get("reason"), str) or not raw["reason"].strip():
            return Clarification(reason="the language model asked for clarification without a reason",
                                 question=question)
        names = raw.get("candidates") if isinstance(raw.get("candidates"), list) else []
        governed = tuple(sorted({c for c in names if isinstance(c, str) and c in layer._defs}))
        return Clarification(reason=raw["reason"].strip(), candidates=governed, question=question)

    def _plan(self, data: Dict[str, object], context: InterpretContext) -> QueryPlan:
        unknown = set(data) - _PLAN_KEYS
        if unknown:
            raise PlanError(f"unknown field(s) {sorted(unknown)}")
        metric = data.get("metric")
        if not isinstance(metric, str) or not metric:
            raise PlanError("metric must be a non-empty string")
        dims = _str_list(data.get("dimensions", []), "dimensions")
        filters = []
        for raw in data.get("filters") or []:
            if not isinstance(raw, dict) or set(raw) - {"dimension", "op", "values"}:
                raise PlanError("each filter is {dimension, op, values}")
            filters.append(Filter(dimension=str(raw.get("dimension", "")), op=str(raw.get("op", "")),
                                  values=_str_list(raw.get("values", []), "filter values")))
        defaults: Tuple[str, ...] = ()
        window_raw = data.get("window")
        if window_raw is None:
            if context.default_window_periods is None:
                raise PlanError("no time window in the question and no default window is configured")
            window = TimeWindow(start_period=context.today_period - context.default_window_periods + 1,
                                end_period=context.today_period, grain=context.default_grain)
            defaults = ("window",)
        else:
            if not isinstance(window_raw, dict) or set(window_raw) - {"start_period", "end_period", "grain"}:
                raise PlanError("window is {start_period, end_period, grain}")
            start, end = window_raw.get("start_period"), window_raw.get("end_period")
            if not all(isinstance(v, int) and not isinstance(v, bool) for v in (start, end)):
                raise PlanError("window periods must be integers")
            if end > context.today_period:
                raise PlanError(f"window ends at period {end}, after today ({context.today_period})")
            window = TimeWindow(start_period=start, end_period=end,
                                grain=str(window_raw.get("grain") or context.default_grain))
        comparison = None
        comp_raw = data.get("comparison")
        if comp_raw is not None:
            if not isinstance(comp_raw, dict) or set(comp_raw) - {"kind", "reference"}:
                raise PlanError("comparison is {kind, reference}")
            ref = comp_raw.get("reference")
            comparison = Comparison(kind=str(comp_raw.get("kind", "")), reference=ref if isinstance(ref, str) else None)
        rank = data.get("rank")
        if rank is not None and (not isinstance(rank, int) or isinstance(rank, bool)):
            raise PlanError("rank must be an integer or null")
        return QueryPlan(metric=metric, dimensions=dims, filters=tuple(filters), window=window,
                         comparison=comparison, rank=rank, defaults_applied=defaults, interpreter=self.label)


class _NoDefaultWindow(Exception):
    """Internal: no relative phrase matched and no default window is configured."""


def interpret(
    question: str,
    layer: SemanticLayer,
    context: InterpretContext,
    interpreter: Optional[Interpreter] = None,
):
    """Interpret ``question`` with ``interpreter`` (default: the keyword baseline).

    Wraps the "missing time window with no declared default" case (REQ-002)
    as a :class:`Clarification` rather than letting the interpreter raise.
    """
    engine = interpreter or KeywordInterpreter()
    try:
        return engine.interpret(question, layer, context)
    except _NoDefaultWindow:
        return Clarification(
            reason="no time window in the question and no default window is configured",
            question=question,
        )


def _matches_phrase(phrase: str, tokens: set) -> bool:
    words = phrase.split()
    return all(w in tokens for w in words)


register_interpreter(KeywordInterpreter())
