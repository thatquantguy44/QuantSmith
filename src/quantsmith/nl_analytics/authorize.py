"""Clearance check before execution. Spec ``0080`` (REQ-004).

A plan is checked against the viewer's clearance before it ever reaches
``execute.py``. A metric, dimension, or dataset above the viewer's clearance
is masked out — never surfaced, never named — so asking about it is
indistinguishable from asking about something that does not exist (existence
masking, AC-005). This module contains no I/O: clearance resolution itself is
``0058``'s job; this module only applies an already-resolved clearance string.

Standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Tuple

from quantsmith.pipelines.access_control import access_level_allows

from .plan import Clarification, QueryPlan


@dataclass(frozen=True)
class AccessPolicy:
    """Which access level a metric, dimension, or dataset requires.

    Anything not named in ``metric_levels``/``dimension_levels`` falls back to
    ``default_level`` (``0058``'s own default is "see everything" when no
    clearance is resolved; a policy here is stricter only where it says so).
    """

    default_level: str = "public"
    metric_levels: Mapping[str, str] = field(default_factory=dict)
    dimension_levels: Mapping[str, str] = field(default_factory=dict)
    dataset_level: str = "public"

    def metric_allowed(self, metric: str, viewer_clearance: str) -> bool:
        level = self.metric_levels.get(metric, self.default_level)
        return access_level_allows(level, viewer_clearance)

    def dimension_allowed(self, dimension: str, viewer_clearance: str) -> bool:
        level = self.dimension_levels.get(dimension, self.default_level)
        return access_level_allows(level, viewer_clearance)

    def dataset_allowed(self, viewer_clearance: str) -> bool:
        return access_level_allows(self.dataset_level, viewer_clearance)


_METRIC_MASKED = Clarification(reason="no known metric matched the question")


def filter_candidates(
    candidates: Tuple[str, ...], policy: AccessPolicy, viewer_clearance: str
) -> Tuple[str, ...]:
    """Drop restricted metric names from a clarification's candidate list.

    A restricted metric must never appear as a candidate — that would reveal
    its existence even while refusing to answer about it directly (AC-005).
    """
    return tuple(c for c in candidates if policy.metric_allowed(c, viewer_clearance))


def authorize_plan(plan: QueryPlan, policy: AccessPolicy, viewer_clearance: str):
    """Check ``plan`` against the viewer's clearance (REQ-004).

    Returns the plan unchanged when everything on it is allowed. When the
    dataset or the metric itself is restricted, returns the same
    "unknown metric" clarification a truly nonexistent metric would produce —
    existence masking (AC-005). A restricted *dimension* the plan requested is
    silently dropped from the plan, as if the interpreter had never matched
    it, rather than surfaced as "you cannot see this."
    """
    if not policy.dataset_allowed(viewer_clearance):
        return _METRIC_MASKED
    if not policy.metric_allowed(plan.metric, viewer_clearance):
        return _METRIC_MASKED

    allowed_dims = tuple(d for d in plan.dimensions if policy.dimension_allowed(d, viewer_clearance))
    if allowed_dims == plan.dimensions:
        return plan
    from dataclasses import replace

    return replace(plan, dimensions=allowed_dims)


def authorize_clarification(
    clarification: Clarification, policy: AccessPolicy, viewer_clearance: str
) -> Clarification:
    """Mask restricted candidates out of a clarification (REQ-004, AC-005)."""
    masked = filter_candidates(clarification.candidates, policy, viewer_clearance)
    if masked == clarification.candidates:
        return clarification
    return Clarification(reason=clarification.reason, candidates=masked, question=clarification.question)
