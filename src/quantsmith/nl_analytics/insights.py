"""Deterministic insight computation. Spec ``0080`` (REQ-007).

Every insight is computed arithmetic, never a model's guess: level, change,
per-group contribution to that change, trend direction, trailing-baseline
outliers, and concentration. Levels and trends use the semantic layer's own
ungrouped value, never a sum of groups; contribution and concentration only
appear for a metric whose groups add up, and a rate's change is reported in
basis points — all governed by the :class:`~.domain.MetricPolicy` (T-021). Each :class:`Insight` carries the exact numbers
it rests on in ``values``, so :mod:`narrate` can check a written sentence
against them number by number (REQ-008) instead of trusting prose.

Standard library only.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from .domain import MetricPolicy
from .execute import Result

INSIGHT_KINDS = ("level", "change", "contributor", "trend", "outlier", "concentration")


@dataclass(frozen=True)
class Insight:
    """One computed finding.

    ``statement`` is the fully-rendered English sentence for this insight
    (spec ``plan.md`` names this field ``statement_template``; it holds the
    rendered text rather than a fill-in-the-blanks template, since 0080 has
    no second templating layer — the numbers in ``values`` are what a
    narrative is checked against, not placeholders in this string).
    """

    kind: str
    statement: str
    values: Dict[str, object]


def _fmt(value: float, policy: MetricPolicy) -> str:
    unit = policy.display_unit
    if unit == "%":
        return f"{value:g}%"
    return f"{value:g} {unit}" if unit else f"{value:g}"


def _view(obj, policy: MetricPolicy) -> Tuple[float, Optional[int], Dict[Tuple[str, ...], float]]:
    """The (level, period it is as of, per-group values) a result stands for.

    The level is the semantic layer's own ungrouped value, never a sum of the
    groups — summing groups is only right for an additive metric, and a mean
    or ratio of the whole is not the sum of the parts (T-021). A metric that
    may not be summed over time (a stock or a rate) is read at the latest
    period rather than across the window. A persisted prior insight carries
    only ``values`` keyed ``()``, which is already its level.
    """
    period_totals = getattr(obj, "period_totals", None)
    if period_totals is None:
        values = dict(obj.values)
        level = values[()] if set(values) == {()} else sum(values.values())
        return level, None, values
    latest = obj.latest_period
    if not policy.sums_across_time and latest is not None and latest in period_totals:
        return period_totals[latest], latest, dict(obj.series[latest])
    return obj.total, None, dict(obj.values)


def compute_insights(
    result: Result,
    comparison: Optional[Result] = None,
    *,
    policy: Optional[MetricPolicy] = None,
    outlier_z_threshold: float = 2.5,
    outlier_min_baseline: int = 3,
) -> Tuple[Insight, ...]:
    """Compute the insight set for ``result`` (REQ-007).

    ``comparison`` is another :class:`Result` for the same plan over the
    comparison window (prior period, prior year, or a persisted prior
    insight's level) — change and contributor insights only appear when it is
    given.

    ``policy`` (from :func:`~quantsmith.nl_analytics.domain.resolve_policy`)
    carries the metric's unit and additivity and the insight kinds it must not
    produce (REQ-015, REQ-017). Without one the metric is treated as additive
    with no unit — ``answer()`` always passes one.
    """
    metric = result.plan.metric
    policy = policy or MetricPolicy(metric=metric)
    level, level_period, groups = _view(result, policy)
    # A grouped question about a metric whose groups do not add up (yields
    # by tenor, VaR by desk) has no meaningful total: report each group, and
    # never a cross-group sum (AC-023). Groups that do not reconcile to the
    # layer's own total (0008 NFR-003) are treated the same way even when the
    # policy calls the metric additive — a mean or ratio called without a
    # policy can then still never be decomposed into nonsense shares.
    reconciles = math.isclose(sum(groups.values()), level, rel_tol=1e-9, abs_tol=1e-9)
    per_group = bool(result.plan.dimensions) and not (policy.sums_across_dimensions and reconciles)
    if per_group:
        insights = [_group_levels(result, metric, groups, level_period, policy)]
    else:
        insights = [_level(result, metric, level, level_period, policy)]
    if comparison is not None and per_group:
        _, _, prior_groups = _view(comparison, policy)
        change = _group_changes(result, metric, groups, prior_groups, policy)
        if change is not None:
            insights.append(change)
    elif comparison is not None:
        prior, _, prior_groups = _view(comparison, policy)
        change = _change(metric, level, prior, policy)
        insights.append(change)
        if (
            policy.allows("contributor")
            and result.plan.dimensions
            and change.values["absolute"] != 0
        ):
            insights.append(_contributor(result, metric, groups, prior_groups, change.values["absolute"]))
    trend = _trend(result, metric, policy)
    if trend is not None:
        insights.append(trend)
    outlier = _outlier(result, metric, outlier_z_threshold, outlier_min_baseline, policy)
    if outlier is not None:
        insights.append(outlier)
    if policy.allows("concentration") and result.plan.dimensions and not per_group and len(groups) > 1:
        insights.append(_concentration(result, metric, groups))
    return tuple(i for i in insights if policy.allows(i.kind))


def _level(result: Result, metric: str, level: float, period: Optional[int], policy: MetricPolicy) -> Insight:
    as_of = result.as_of if period is None else period
    values = {"level": level, "as_of": result.as_of}
    if period is not None:
        values["period"] = period
    return Insight(
        kind="level", statement=f"{metric} is {_fmt(level, policy)} as of period {as_of}.",
        values=values,
    )


def _label(key: Tuple[str, ...]) -> str:
    return " / ".join(key) or "(total)"


def _group_levels(
    result: Result, metric: str, groups: Dict[Tuple[str, ...], float], period: Optional[int], policy: MetricPolicy
) -> Insight:
    as_of = result.as_of if period is None else period
    keys = sorted(groups)
    parts = ", ".join(f"{_label(k)} {_fmt(groups[k], policy)}" for k in keys)
    values: Dict[str, object] = {"levels": {"|".join(k) or "(total)": groups[k] for k in keys}, "as_of": result.as_of}
    if period is not None:
        values["period"] = period
    return Insight(
        kind="level",
        statement=f"{metric} by {' / '.join(result.plan.dimensions)} as of period {as_of}: {parts}.",
        values=values,
    )


def _group_changes(
    result: Result,
    metric: str,
    now: Dict[Tuple[str, ...], float],
    prior: Dict[Tuple[str, ...], float],
    policy: MetricPolicy,
) -> Optional[Insight]:
    keys = sorted(set(now) & set(prior))
    if not keys:
        return None
    absolute = {k: now[k] - prior[k] for k in keys}
    factor = policy.bps_factor
    values: Dict[str, object] = {
        "now": {"|".join(k): now[k] for k in keys},
        "prior": {"|".join(k): prior[k] for k in keys},
        "absolute": {"|".join(k): absolute[k] for k in keys},
    }
    if factor is not None:
        bps = {k: round(absolute[k] * factor, 9) for k in keys}
        values["bps"] = {"|".join(k): bps[k] for k in keys}
        parts = ", ".join(f"{_label(k)} {bps[k]:+g} bp" for k in keys)
    else:
        parts = ", ".join(f"{_label(k)} {absolute[k]:+g}" for k in keys)
    return Insight(
        kind="change",
        statement=f"{metric} by {' / '.join(result.plan.dimensions)} versus the comparison period: {parts}.",
        values=values,
    )


def _change(metric: str, now: float, prior: float, policy: MetricPolicy) -> Insight:
    absolute = now - prior
    direction = "up" if absolute > 0 else "down" if absolute < 0 else "unchanged"
    factor = policy.bps_factor
    if factor is not None:
        # A rate's move is reported in basis points; a percent change of a
        # rate (4.00% -> 4.20% is "+5%") is the classic misreading (AC-023).
        bps = round(absolute * factor, 9)
        return Insight(
            kind="change",
            statement=(
                f"{metric} is {direction} {abs(bps):g} bp ({bps:+g} bp, {_fmt(prior, policy)} to "
                f"{_fmt(now, policy)}) versus the comparison period."
            ),
            values={"now": now, "prior": prior, "absolute": absolute, "bps": bps, "percent": None},
        )
    pct = (absolute / prior) if prior != 0 else None
    pct_text = f" ({pct:+.1%})" if pct is not None else ""
    return Insight(
        kind="change",
        statement=f"{metric} is {direction} {abs(absolute):g}{pct_text} versus the comparison period.",
        values={"now": now, "prior": prior, "absolute": absolute, "percent": pct},
    )


def _contributor(
    result: Result,
    metric: str,
    now: Dict[Tuple[str, ...], float],
    prior: Dict[Tuple[str, ...], float],
    total_change: float,
) -> Insight:
    keys = sorted(set(now) | set(prior))
    diffs = {k: now.get(k, 0.0) - prior.get(k, 0.0) for k in keys}
    shares = {k: (d / total_change) for k, d in diffs.items()}
    ranked = sorted(keys, key=lambda k: abs(diffs[k]), reverse=True)
    top = ranked[0]
    return Insight(
        kind="contributor",
        statement=(
            f"{' / '.join(result.plan.dimensions)} = {' / '.join(top) or '(total)'} drove "
            f"{shares[top]:+.1%} of the change in {metric} ({diffs[top]:+g})."
        ),
        values={
            "dimensions": list(result.plan.dimensions),
            "diffs": {"|".join(k) or "(total)": v for k, v in diffs.items()},
            "shares": {"|".join(k) or "(total)": v for k, v in shares.items()},
            "top": "|".join(top) or "(total)",
        },
    )


def _trend(result: Result, metric: str, policy: MetricPolicy) -> Optional[Insight]:
    totals = result.period_totals
    if len(totals) < 2:
        return None
    periods = sorted(totals)
    first, last = totals[periods[0]], totals[periods[-1]]
    direction = "increasing" if last > first else "decreasing" if last < first else "flat"
    return Insight(
        kind="trend",
        statement=(
            f"{metric} is {direction} from {_fmt(first, policy)} (period {periods[0]}) "
            f"to {_fmt(last, policy)} (period {periods[-1]})."
        ),
        values={"first_period": periods[0], "first_value": first, "last_period": periods[-1], "last_value": last},
    )


def _outlier(
    result: Result, metric: str, z_threshold: float, min_baseline: int, policy: MetricPolicy
) -> Optional[Insight]:
    totals = result.period_totals
    if len(totals) <= min_baseline:
        return None
    periods = sorted(totals)
    flagged = []
    for i in range(min_baseline, len(periods)):
        baseline = [totals[p] for p in periods[:i]]
        mean = statistics.mean(baseline)
        std = statistics.pstdev(baseline)
        if std == 0:
            # A perfectly flat baseline has no scale to divide by. Any
            # departure from it is still meaningful, so fall back to a tiny
            # epsilon (relative to the baseline's own magnitude) rather than
            # skip the period outright — the alternative, silently never
            # flagging a flat series, is the wrong failure mode here.
            if totals[periods[i]] == mean:
                continue
            std = max(abs(mean), 1.0) * 1e-6
        z = (totals[periods[i]] - mean) / std
        if abs(z) >= z_threshold:
            flagged.append({"period": periods[i], "value": totals[periods[i]], "z": z})
    if flagged:
        worst = max(flagged, key=lambda f: abs(f["z"]))
        statement = (
            f"{metric} at period {worst['period']} ({_fmt(worst['value'], policy)}) is an outlier "
            f"against its trailing baseline (z = {worst['z']:+.2f})."
        )
    else:
        statement = f"{metric} shows no outlier against its trailing baseline (threshold z = {z_threshold:g})."
    return Insight(
        kind="outlier",
        statement=statement,
        values={"threshold": z_threshold, "baseline_size": min_baseline, "flagged": flagged},
    )


def _concentration(result: Result, metric: str, groups: Dict[Tuple[str, ...], float]) -> Insight:
    # Shares of a whole only exist for a metric whose groups add up to it;
    # compute_insights never calls this for one that does not.
    total = sum(groups.values())
    shares = {k: (v / total if total != 0 else 0.0) for k, v in groups.items()}
    hhi = sum(s * s for s in shares.values())
    top_key, top_share = max(shares.items(), key=lambda kv: kv[1])
    return Insight(
        kind="concentration",
        statement=(
            f"{' / '.join(result.plan.dimensions)} = {' / '.join(top_key) or '(total)'} holds "
            f"{top_share:.1%} of {metric} (HHI {hhi:.3f} across {len(shares)} groups)."
        ),
        values={
            "hhi": hhi, "top_share": top_share, "top_key": "|".join(top_key) or "(total)",
            "group_count": len(shares),
        },
    )
