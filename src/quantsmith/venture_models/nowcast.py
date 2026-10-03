"""Sector-funding nowcast baseline for spec 0095 (chain-ladder development).

Databases fill in late: a quarter's funding keeps rising as rounds are reported. The chain-ladder
method used in insurance reserving estimates how complete each reporting lag typically is from past
quarters and scales the partial recent figure up to an estimate of its eventual total. It must be
evaluated on **real-time vintages** (only what was known then), against naive baselines, or it will
look better than it is. Estimates are nowcasts with error, not facts.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .validation import require_min_n

Triangle = Sequence[Sequence[Optional[float]]]


def age_to_age_factors(triangle: Triangle) -> List[float]:
    """Volume-weighted development factors: sum of lag k+1 over sum of lag k, rows where both are known."""
    lags = max(len(r) for r in triangle)
    factors = []
    for k in range(lags - 1):
        num = den = 0.0
        for row in triangle:
            if k + 1 < len(row) and row[k] is not None and row[k + 1] is not None:
                num += row[k + 1]
                den += row[k]
        if den <= 0:
            raise ValueError(f"no data to estimate the factor from lag {k} to {k + 1}")
        factors.append(num / den)
    return factors


def completeness_curve(factors: Sequence[float]) -> List[float]:
    """Share of the eventual total reported at each lag (the last lag is 1.0)."""
    comp = [1.0] * (len(factors) + 1)
    prod = 1.0
    for k in range(len(factors) - 1, -1, -1):
        prod *= factors[k]
        comp[k] = 1.0 / prod
    return comp


def nowcast_ultimate(reported: float, lag: int, factors: Sequence[float]) -> float:
    """Eventual total for a quarter reported at ``reported`` after ``lag`` lags."""
    est = reported
    for k in range(lag, len(factors)):
        est *= factors[k]
    return est


def vintage(full: Triangle, as_of_quarter: int) -> List[List[Optional[float]]]:
    """The triangle as known at ``as_of_quarter``: entry (q, k) exists only if q + k <= as_of_quarter."""
    out: List[List[Optional[float]]] = []
    for q, row in enumerate(full):
        if q > as_of_quarter:
            break
        out.append([row[k] if q + k <= as_of_quarter else None for k in range(len(row))])
    return out


def backtest_nowcast(full: Triangle, burn_in: int = 6, min_targets: int = 6) -> Dict[str, Any]:
    """Real-time evaluation of nowcasting the final value of each quarter from its first report.

    For each target quarter T after ``burn_in``, factors come only from the vintage known at T. The
    chain-ladder estimate is compared with the true final value and with two baselines: the first report
    as is, and the most recent quarter that was already complete.
    """
    lags = len(full[0])
    finals = [row[-1] for row in full]
    errs: Dict[str, List[float]] = {"chain_ladder": [], "first_report_as_is": [], "last_complete_quarter": []}
    targets = 0
    for T in range(max(burn_in, lags), len(full)):
        v = vintage(full, T)
        factors = age_to_age_factors(v)
        first = v[T][0]
        truth = finals[T]
        if first is None or truth is None or truth == 0:
            continue
        targets += 1
        errs["chain_ladder"].append(abs(nowcast_ultimate(first, 0, factors) - truth) / truth)
        errs["first_report_as_is"].append(abs(first - truth) / truth)
        last_complete = finals[T - lags + 1]
        errs["last_complete_quarter"].append(abs(last_complete - truth) / truth)
    require_min_n(targets, min_targets, "nowcast backtest targets")
    mape = {k: sum(v) / len(v) for k, v in errs.items()}
    return {"n_targets": targets, "mape": mape,
            "beats_baselines": mape["chain_ladder"] < min(mape["first_report_as_is"], mape["last_complete_quarter"]),
            "note": "real-time vintages; synthetic data shows the arithmetic, not real accuracy"}
