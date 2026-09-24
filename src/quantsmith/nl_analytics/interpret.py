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

import re
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Protocol, Sequence, Tuple, runtime_checkable

from quantsmith.pipelines.metrics_semantic_layer import SemanticLayer

from .plan import Clarification, Comparison, Filter, QueryPlan, TimeWindow

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
