"""Funding-flow anomaly baseline for spec 0095.

Flags sector-period funding totals that are unusual against their own seasonal history, using the
median and the median absolute deviation. The central venture trap is reporting lag: the latest
periods are incomplete in every database, so a low recent value is **not assessable**, never an
"anomalous drop". Output is an indicator for a human, not a finding.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from .emergence import MAD_SCALE, mad, median


def robust_z(value: float, history: Sequence[float], floor_fraction: float = 0.05) -> float:
    """(value - median) / robust scale, with the scale floored at a fraction of the median level."""
    if not history:
        raise ValueError("history is empty")
    m = median(history)
    scale = max(MAD_SCALE * mad(history), floor_fraction * abs(m), 1e-9)
    return (value - m) / scale


def flag_anomalies(series: Sequence[float], period: int = 4, lag_periods: int = 1, min_seasonal: int = 3,
                   z_threshold: float = 3.5, floor_fraction: float = 0.05) -> List[Dict[str, Any]]:
    """Per-period status for a series (oldest first).

    The last ``lag_periods`` are ``incomplete_period``. Other periods use same-season history when at
    least ``min_seasonal`` earlier same-season values exist, else all earlier values when there are at
    least ``min_seasonal`` of them, else are ``not_assessable``.
    """
    n = len(series)
    out: List[Dict[str, Any]] = []
    for t, v in enumerate(series):
        row: Dict[str, Any] = {"index": t, "value": v}
        if t >= n - lag_periods:
            row.update(status="incomplete_period", reason="recent periods are still being reported")
        else:
            seasonal = [series[s] for s in range(t - period, -1, -period)]
            earlier = list(series[:t])
            if len(seasonal) >= min_seasonal:
                hist, basis = seasonal, "same_season"
            elif len(earlier) >= min_seasonal:
                hist, basis = earlier, "all_earlier"
            else:
                row.update(status="not_assessable", reason="not enough history")
                out.append(row)
                continue
            z = robust_z(v, hist, floor_fraction)
            row.update(z=z, basis=basis, history_n=len(hist),
                       status="anomalous" if abs(z) >= z_threshold else "normal",
                       direction=("high" if z > 0 else "low") if abs(z) >= z_threshold else None)
        out.append(row)
    return out
