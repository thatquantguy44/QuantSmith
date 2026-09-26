"""Deterministic insight computation. Spec ``0080`` (REQ-007).

Every insight is computed arithmetic, never a model's guess: level, change,
per-group contribution to that change, trend direction, trailing-baseline
outliers, and concentration. Each :class:`Insight` carries the exact numbers
it rests on in ``values``, so :mod:`narrate` can check a written sentence
against them number by number (REQ-008) instead of trusting prose.

Standard library only.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

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


def _period_totals(result: Result) -> Dict[int, float]:
    return {period: sum(vals.values()) for period, vals in result.series.items()}


def compute_insights(
    result: Result,
    comparison: Optional[Result] = None,
    *,
    outlier_z_threshold: float = 2.5,
    outlier_min_baseline: int = 3,
) -> Tuple[Insight, ...]:
    """Compute the insight set for ``result`` (REQ-007).

    ``comparison`` is another :class:`Result` for the same plan over the
    comparison window (prior period, prior year, or a persisted prior
    insight's level) — change and contributor insights only appear when it is
    given.
    """
    metric = result.plan.metric
    insights = [_level(result, metric)]
    if comparison is not None:
        change = _change(result, comparison, metric)
        insights.append(change)
        if result.plan.dimensions and change.values["absolute"] != 0:
            insights.append(_contributor(result, comparison, metric, change.values["absolute"]))
    trend = _trend(result, metric)
    if trend is not None:
        insights.append(trend)
    outlier = _outlier(result, metric, outlier_z_threshold, outlier_min_baseline)
    if outlier is not None:
        insights.append(outlier)
    if result.plan.dimensions and len(result.values) > 1:
        insights.append(_concentration(result, metric))
    return tuple(insights)


def _level(result: Result, metric: str) -> Insight:
    level = sum(result.values.values())
    return Insight(
        kind="level", statement=f"{metric} is {level:g} as of period {result.as_of}.",
        values={"level": level, "as_of": result.as_of},
    )


def _change(result: Result, comparison: Result, metric: str) -> Insight:
    now = sum(result.values.values())
    prior = sum(comparison.values.values())
    absolute = now - prior
    pct = (absolute / prior) if prior != 0 else None
    direction = "up" if absolute > 0 else "down" if absolute < 0 else "unchanged"
    pct_text = f" ({pct:+.1%})" if pct is not None else ""
    return Insight(
        kind="change",
        statement=f"{metric} is {direction} {abs(absolute):g}{pct_text} versus the comparison period.",
        values={"now": now, "prior": prior, "absolute": absolute, "percent": pct},
    )


def _contributor(result: Result, comparison: Result, metric: str, total_change: float) -> Insight:
    keys = sorted(set(result.values) | set(comparison.values))
    diffs = {k: result.values.get(k, 0.0) - comparison.values.get(k, 0.0) for k in keys}
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


def _trend(result: Result, metric: str) -> Optional[Insight]:
    totals = _period_totals(result)
    if len(totals) < 2:
        return None
    periods = sorted(totals)
    first, last = totals[periods[0]], totals[periods[-1]]
    direction = "increasing" if last > first else "decreasing" if last < first else "flat"
    return Insight(
        kind="trend",
        statement=f"{metric} is {direction} from {first:g} (period {periods[0]}) to {last:g} (period {periods[-1]}).",
        values={"first_period": periods[0], "first_value": first, "last_period": periods[-1], "last_value": last},
    )


def _outlier(
    result: Result, metric: str, z_threshold: float, min_baseline: int
) -> Optional[Insight]:
    totals = _period_totals(result)
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
            f"{metric} at period {worst['period']} ({worst['value']:g}) is an outlier "
            f"against its trailing baseline (z = {worst['z']:+.2f})."
        )
    else:
        statement = f"{metric} shows no outlier against its trailing baseline (threshold z = {z_threshold:g})."
    return Insight(
        kind="outlier",
        statement=statement,
        values={"threshold": z_threshold, "baseline_size": min_baseline, "flagged": flagged},
    )


def _concentration(result: Result, metric: str) -> Insight:
    total = sum(result.values.values())
    shares = {k: (v / total if total != 0 else 0.0) for k, v in result.values.items()}
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
