"""``QueryPlan`` — the typed, governed query a natural-language question
becomes. Spec ``0080-nl-analytics-insights`` (REQ-001, REQ-002).

A ``QueryPlan`` can only name a governed metric (``0008``'s ``SemanticLayer``),
that metric's declared dimensions, filters on declared dimension values, a
time window, and an optional comparison or rank. There is deliberately no
field that can carry SQL, a code string, or an arbitrary expression — an
interpreter (``interpret.py``) can only ever produce values in this shape,
and :func:`validate_plan` is the single gate every interpreter's output must
pass before execution (REQ-003).

Standard library only.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from quantsmith.pipelines.metrics_semantic_layer import GovernanceError, SemanticLayer

COMPARISON_KINDS = ("prior_period", "prior_year", "prior_insight")
FILTER_OPS = ("eq", "in")
GRAINS = ("day", "week", "month", "quarter", "year")

MAX_DIMENSIONS = 2


class PlanError(ValueError):
    """Raised by :func:`validate_plan` when a plan is not governed (REQ-001)."""


@dataclass(frozen=True)
class Filter:
    """A filter on one declared dimension value. ``values`` is never empty."""

    dimension: str
    op: str
    values: Tuple[str, ...]

    def __post_init__(self) -> None:
        if self.op not in FILTER_OPS:
            raise PlanError(f"filter op {self.op!r} not in {FILTER_OPS}")
        if not self.values:
            raise PlanError(f"filter on {self.dimension!r} has no values")
        if self.op == "eq" and len(self.values) != 1:
            raise PlanError(f"filter op 'eq' on {self.dimension!r} takes exactly one value")


@dataclass(frozen=True)
class TimeWindow:
    """An inclusive period range at a stated grain. Periods are comparable ints."""

    start_period: int
    end_period: int
    grain: str

    def __post_init__(self) -> None:
        if self.grain not in GRAINS:
            raise PlanError(f"grain {self.grain!r} not in {GRAINS}")
        if self.start_period > self.end_period:
            raise PlanError("window start_period is after end_period")


@dataclass(frozen=True)
class Comparison:
    """A comparison against a prior period, prior year, or a named prior insight."""

    kind: str
    reference: Optional[str] = None

    def __post_init__(self) -> None:
        if self.kind not in COMPARISON_KINDS:
            raise PlanError(f"comparison kind {self.kind!r} not in {COMPARISON_KINDS}")
        if self.kind == "prior_insight" and not self.reference:
            raise PlanError("comparison kind 'prior_insight' needs a reference key")


@dataclass(frozen=True)
class QueryPlan:
    """The governed query a question becomes. No field can carry SQL or code.

    ``dimensions`` are the breakdowns requested (at most :data:`MAX_DIMENSIONS`
    — spec 0080's assumption of one metric per plan, up to a two-measure
    scatter). ``defaults_applied`` names every default value the interpreter
    filled in (REQ-002); ``interpreter`` records the name (and version, if the
    interpreter carries one) that produced this plan (REQ-013 audit trail).
    """

    metric: str
    dimensions: Tuple[str, ...]
    filters: Tuple[Filter, ...]
    window: TimeWindow
    comparison: Optional[Comparison]
    rank: Optional[int]
    defaults_applied: Tuple[str, ...]
    interpreter: str

    def __post_init__(self) -> None:
        if not self.metric:
            raise PlanError("a plan needs a metric")
        if len(self.dimensions) > MAX_DIMENSIONS:
            raise PlanError(f"a plan supports at most {MAX_DIMENSIONS} dimensions")
        if self.rank is not None and self.rank < 1:
            raise PlanError("rank must be a positive integer")

    def to_canonical_dict(self) -> Dict:
        """A JSON-safe, order-independent representation for hashing (NFR-001)."""
        return {
            "metric": self.metric,
            "dimensions": list(self.dimensions),
            "filters": [
                {"dimension": f.dimension, "op": f.op, "values": sorted(f.values)}
                for f in sorted(self.filters, key=lambda f: f.dimension)
            ],
            "window": {
                "start_period": self.window.start_period,
                "end_period": self.window.end_period,
                "grain": self.window.grain,
            },
            "comparison": (
                {"kind": self.comparison.kind, "reference": self.comparison.reference}
                if self.comparison is not None
                else None
            ),
            "rank": self.rank,
            "defaults_applied": sorted(self.defaults_applied),
            "interpreter": self.interpreter,
        }

    def canonical_json(self) -> str:
        return json.dumps(self.to_canonical_dict(), sort_keys=True, separators=(",", ":"))

    def content_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Clarification:
    """What comes back instead of a plan when the question does not resolve
    to exactly one valid interpretation (REQ-002).

    ``candidates`` names what the interpreter considered — metric names,
    ambiguous synonyms, or (after masking, see ``authorize.py``) only what
    the viewer's clearance permits.
    """

    reason: str
    candidates: Tuple[str, ...] = field(default_factory=tuple)
    question: str = ""


def validate_plan(plan: QueryPlan, layer: SemanticLayer, config: Optional[Dict] = None) -> None:
    """The one gate every interpreter's output passes before execution (REQ-003).

    Raises :class:`PlanError` for anything ungoverned: an undefined metric, an
    undeclared dimension (on the plan or in a filter), or (for ``prior_insight``)
    a comparison the config does not recognize as a known reference key.
    """
    config = config or {}
    try:
        defn = layer.definition(plan.metric)
    except GovernanceError as exc:
        raise PlanError(f"undefined metric: {plan.metric}") from exc

    declared = set(defn.dimensions)
    for d in plan.dimensions:
        if d not in declared:
            raise PlanError(f"dimension {d!r} is not declared for metric {plan.metric!r}")
    for f in plan.filters:
        if f.dimension not in declared:
            raise PlanError(f"filter dimension {f.dimension!r} is not declared for metric {plan.metric!r}")

    known_refs = config.get("known_prior_insight_keys")
    if (
        plan.comparison is not None
        and plan.comparison.kind == "prior_insight"
        and known_refs is not None
        and plan.comparison.reference not in known_refs
    ):
        raise PlanError(f"unknown prior-insight reference: {plan.comparison.reference}")


def describe_plan(plan: QueryPlan) -> str:
    """A plain-language echo of the plan: "how I read your question" (REQ-009)."""
    parts = [f"metric '{plan.metric}'"]
    if plan.dimensions:
        parts.append("by " + ", ".join(plan.dimensions))
    for f in plan.filters:
        parts.append(f"where {f.dimension} {f.op} {list(f.values)}")
    parts.append(f"for periods {plan.window.start_period}-{plan.window.end_period} ({plan.window.grain})")
    if plan.comparison is not None:
        ref = f" ({plan.comparison.reference})" if plan.comparison.reference else ""
        parts.append(f"compared to {plan.comparison.kind}{ref}")
    if plan.rank is not None:
        parts.append(f"top {plan.rank}")
    if plan.defaults_applied:
        parts.append("defaults applied: " + ", ".join(sorted(plan.defaults_applied)))
    return "; ".join(parts)
