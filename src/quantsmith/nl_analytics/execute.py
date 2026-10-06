"""Execute a validated plan over caller-injected rows. Spec ``0080`` (REQ-005).

No I/O lives here: ``reader`` is a caller-injected callable that returns
``Fact`` rows for a plan (a database read, a file load — anything). This
module only ever filters and aggregates what it is handed, and it never reads
a clock: the as-of bound is a value the caller passes in, so a question asked
"as of" an earlier date can never see a row written after that date
(NFR-002).

Standard library only.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Sequence, Tuple

from quantsmith.pipelines.metrics_semantic_layer import Fact, SemanticLayer

from .plan import Filter, QueryPlan

Reader = Callable[[QueryPlan], Sequence[Fact]]


@dataclass(frozen=True)
class Result:
    """The computed answer to a plan.

    ``values`` aggregates the whole window into one number per dimension-value
    tuple — "the current level" (an ungrouped plan has one entry keyed by
    ``()``). ``series`` is the same aggregation done separately per period, in
    ascending period order, so trend and outlier insights and a time-series
    chart have something to work from without a second read of the data.

    ``total`` and ``period_totals`` are the metric computed by the semantic
    layer over *all* the rows (whole window, and per period) with no grouping.
    For a summed metric they equal the sum of the groups; for a mean, ratio,
    or any other non-additive metric they do not, and summing ``values``
    across groups would be wrong — insights read these instead (T-021).
    ``content_hash`` covers the plan, ``values``, ``series``, and both totals,
    so two runs over identical inputs are provably identical (NFR-001).
    """

    plan: QueryPlan
    values: Dict[Tuple[str, ...], float]
    series: Dict[int, Dict[Tuple[str, ...], float]]
    row_count: int
    latest_period: Optional[int]
    as_of: int
    content_hash: str
    total: float = 0.0
    period_totals: Dict[int, float] = field(default_factory=dict)


def _row_matches(row: Fact, f: Filter) -> bool:
    value = row.dims.get(f.dimension)
    if f.op == "eq":
        return value == f.values[0]
    return value in f.values


def execute(plan: QueryPlan, layer: SemanticLayer, reader: Reader, as_of: int) -> Result:
    """Run a validated plan. Call :func:`plan.validate_plan` first."""
    raw = reader(plan)
    filtered = [
        r
        for r in raw
        if r.period <= as_of
        and plan.window.start_period <= r.period <= plan.window.end_period
        and all(_row_matches(r, f) for f in plan.filters)
    ]

    groups: Dict[Tuple[str, ...], list] = {}
    for r in filtered:
        key = tuple(r.dims.get(d, "") for d in plan.dimensions)
        groups.setdefault(key, []).append(r)
    if not groups:
        groups[tuple("" for _ in plan.dimensions)] = []
    values = {key: layer.compute(plan.metric, rows) for key, rows in groups.items()}

    by_period: Dict[int, list] = {}
    for r in filtered:
        by_period.setdefault(r.period, []).append(r)
    series: Dict[int, Dict[Tuple[str, ...], float]] = {}
    for period in sorted(by_period):
        period_groups: Dict[Tuple[str, ...], list] = {}
        for r in by_period[period]:
            key = tuple(r.dims.get(d, "") for d in plan.dimensions)
            period_groups.setdefault(key, []).append(r)
        series[period] = {key: layer.compute(plan.metric, rows) for key, rows in period_groups.items()}

    total = layer.compute(plan.metric, filtered)
    period_totals = {period: layer.compute(plan.metric, by_period[period]) for period in sorted(by_period)}

    latest_period = max((r.period for r in filtered), default=None)

    payload = {
        "plan": plan.to_canonical_dict(),
        "values": {"|".join(k): v for k, v in sorted(values.items())},
        "series": {
            str(period): {"|".join(k): v for k, v in sorted(vals.items())}
            for period, vals in sorted(series.items())
        },
        "total": total,
        "period_totals": {str(period): v for period, v in sorted(period_totals.items())},
        "row_count": len(filtered),
        "latest_period": latest_period,
        "as_of": as_of,
    }
    content_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    return Result(
        plan=plan,
        values=values,
        series=series,
        row_count=len(filtered),
        latest_period=latest_period,
        as_of=as_of,
        content_hash=content_hash,
        total=total,
        period_totals=period_totals,
    )
