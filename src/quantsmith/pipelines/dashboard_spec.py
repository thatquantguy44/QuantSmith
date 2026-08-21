"""Tool-agnostic dashboard spec — the code contract for `analytics/dashboard_design`.

Spec ``0014-data-analyst-storytelling`` defines a tool-agnostic dashboard spec that
BI-tool profiles render. This module makes that contract concrete so every profile
(Power BI first, others later) renders the *same* structure. Standard-library only.

A ``DashboardSpec`` is a governed design: each ``Panel`` names a governed metric (from
`metrics_semantic_layer`, `0008`) and a tool-agnostic chart type. Renderers map these
to a specific BI tool's payload; the spec itself is never tied to one tool.

Spec ``0047`` added ``SCHEMA_VERSION`` and ``check_schema_compatibility`` so a consumer
in a *separate repository* — can refuse
a payload it does not understand and show stale data, rather than crash. For a client
shipped through App Store review, "detect a breaking change by breaking" means days
without a fix.

**The limit of that guarantee, stated plainly:** ``SCHEMA_VERSION`` is a *declaration*,
not a derivation. Bumping it is a manual act, so a breaking change shipped without a
bump is undetectable from here. The honest guard is a contract test on the consumer's
side that decodes a real spec from the installed package; this module enables that test
but cannot enforce it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

# Tool-agnostic chart types a dashboard spec may use.
CHART_TYPES = ("bar", "line", "area", "scatter", "table", "kpi", "gauge", "map")

# MAJOR.MINOR of the rendering contract. A differing MAJOR is a breaking change;
# a higher MINOR adds fields a older consumer may safely ignore. Patch is absent
# by design: a patch cannot change payload shape.
SCHEMA_VERSION = "1.0"


class DashboardSpecError(ValueError):
    """Raised when a dashboard spec is malformed or ungoverned."""


@dataclass(frozen=True)
class Panel:
    """One panel: a governed metric shown with a tool-agnostic chart type."""

    title: str
    chart_type: str
    metric: str                      # a governed metric name (0008)
    dimensions: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.metric:
            raise DashboardSpecError(f"panel '{self.title}' has no governed metric")
        if self.chart_type not in CHART_TYPES:
            raise DashboardSpecError(
                f"panel '{self.title}' has unknown chart_type '{self.chart_type}' "
                f"(use one of {list(CHART_TYPES)})"
            )


@dataclass(frozen=True)
class DashboardSpec:
    """A tool-agnostic dashboard: ordered panels over a dataset, plus filters."""

    title: str
    dataset: str
    panels: Tuple[Panel, ...]
    filters: Dict[str, str] = field(default_factory=dict)
    page: str = "Overview"
    # Appended last with a default so existing positional construction and every
    # renderer built before spec 0047 are unaffected.
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.panels:
            raise DashboardSpecError("a dashboard spec needs at least one panel")

    def metrics(self) -> Tuple[str, ...]:
        """Governed metrics used, in first-seen order, de-duplicated."""
        seen: list = []
        for p in self.panels:
            if p.metric not in seen:
                seen.append(p.metric)
        return tuple(seen)

    def chart_types(self) -> Tuple[str, ...]:
        """Chart types used, in first-seen order, de-duplicated."""
        seen: list = []
        for p in self.panels:
            if p.chart_type not in seen:
                seen.append(p.chart_type)
        return tuple(seen)


# ---------------------------------------------------------------------------
# Consumer compatibility -- spec 0047
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Compatibility:
    compatible: bool
    reason: str
    payload_version: str
    consumer_version: str


def _parse(version: str) -> Tuple[int, int]:
    """Parse ``MAJOR.MINOR``; raises ``ValueError`` on anything else."""
    parts = str(version).strip().split(".")
    if len(parts) < 2:
        raise ValueError(f"expected MAJOR.MINOR, got {version!r}")
    return int(parts[0]), int(parts[1])


def check_schema_compatibility(
    payload_version: str,
    consumer_version: str = SCHEMA_VERSION,
) -> Compatibility:
    """Can a consumer on ``consumer_version`` render a ``payload_version`` spec?

    A differing MAJOR is a breaking change and is rejected. A payload with a
    higher MINOR within the same MAJOR is accepted with a caveat: it may carry
    fields this consumer does not know about, which it should ignore rather
    than treat as an error. Rejecting a newer minor would make every SDK minor
    release break every client until it upgraded — the opposite of the point.

    A version string that cannot be parsed is rejected with a reason; it is
    never silently accepted.
    """
    try:
        payload_major, payload_minor = _parse(payload_version)
    except ValueError as exc:
        return Compatibility(False, f"unreadable payload version: {exc}", str(payload_version), consumer_version)
    try:
        consumer_major, consumer_minor = _parse(consumer_version)
    except ValueError as exc:
        return Compatibility(False, f"unreadable consumer version: {exc}", str(payload_version), str(consumer_version))

    if payload_major != consumer_major:
        return Compatibility(
            False,
            f"major version {payload_major} is not compatible with consumer major "
            f"{consumer_major}; the rendering contract changed incompatibly",
            payload_version,
            consumer_version,
        )
    if payload_minor > consumer_minor:
        return Compatibility(
            True,
            f"payload minor {payload_minor} is newer than consumer minor "
            f"{consumer_minor}; unknown fields should be ignored, not treated as errors",
            payload_version,
            consumer_version,
        )
    return Compatibility(True, "", payload_version, consumer_version)
