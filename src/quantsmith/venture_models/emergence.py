"""Technology-emergence detection baseline for spec 0095.

Flags a technology domain whose recent count growth is unusually fast compared with its own history,
using robust statistics (Theil-Sen slope, median absolute deviation) on log counts. Two venture-specific
traps are handled on purpose: the trailing periods are dropped because channels report late
(a partial last quarter is not a decline, and not a surge), and a domain is not assessed without enough
history or enough volume. The result is an indicator with its evidence, never a finding that a
technology "has emerged".
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

from .validation import require_min_n

MAD_SCALE = 1.4826


def median(xs: Sequence[float]) -> float:
    s = sorted(xs)
    n = len(s)
    if n == 0:
        raise ValueError("median of an empty sequence")
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def mad(xs: Sequence[float]) -> float:
    m = median(xs)
    return median([abs(x - m) for x in xs])


def theil_sen(xs: Sequence[float], ys: Sequence[float]) -> Dict[str, float]:
    """Median of pairwise slopes and the median intercept. Robust to outliers."""
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError("need at least two paired points")
    slopes = [(ys[j] - ys[i]) / (xs[j] - xs[i]) for i in range(len(xs)) for j in range(i + 1, len(xs)) if xs[j] != xs[i]]
    if not slopes:
        raise ValueError("all x values are equal")
    slope = median(slopes)
    return {"slope": slope, "intercept": median([y - slope * x for x, y in zip(xs, ys)])}


def growth_signal(counts: Sequence[float], lag_periods: int = 2, recent: int = 6, baseline: int = 12,
                  min_count: float = 10.0, z_threshold: float = 3.0, sigma_floor: float = 0.05) -> Dict[str, Any]:
    """Emergence indicator for one domain's count series (oldest first).

    The last ``lag_periods`` are dropped as incomplete. The recent log-count slope is compared with the
    baseline slope in units of the baseline's robust noise. This is an *onset* detector: an emergence that
    has been under way longer than the recent window starts to fill the baseline and stops being flagged,
    so a ``not_emerging`` result does not mean a technology is not growing. Returns ``status`` ``emerging``,
    ``not_emerging``, or ``not_assessable`` with the numbers behind it.
    """
    series = list(counts[:-lag_periods]) if lag_periods else list(counts)
    base = {"dropped_incomplete_periods": lag_periods, "assessed_periods": len(series), "z_threshold": z_threshold}
    if len(series) < recent + baseline:
        return {**base, "status": "not_assessable", "reasons": [f"needs {recent + baseline} complete periods, has {len(series)}"]}
    rec_w = series[-recent:]
    if sum(rec_w) / recent < min_count:
        return {**base, "status": "not_assessable", "reasons": [f"recent mean count below {min_count}"]}
    lg = [math.log1p(v) for v in series]
    xb = list(range(baseline))
    ts_b = theil_sen(xb, lg[-(recent + baseline):-recent])
    resid = [y - (ts_b["intercept"] + ts_b["slope"] * x) for x, y in zip(xb, lg[-(recent + baseline):-recent])]
    # Counts carry sampling noise of about 1/sqrt(mean) on the log scale however calm the series looks;
    # a short baseline can underestimate it, so the scale never falls below that floor.
    poisson_floor = 1.0 / math.sqrt(max(sum(series[-(recent + baseline):-recent]) / baseline, 1.0))
    sigma = max(MAD_SCALE * mad(resid), sigma_floor, poisson_floor)
    xr = list(range(recent))
    ts_r = theil_sen(xr, lg[-recent:])
    sxx = sum((x - (recent - 1) / 2.0) ** 2 for x in xr)
    z = (ts_r["slope"] - ts_b["slope"]) / (sigma / math.sqrt(sxx))
    status = "emerging" if z >= z_threshold and ts_r["slope"] > 0 else "not_emerging"
    return {**base, "status": status, "z": z, "slope_recent": ts_r["slope"], "slope_baseline": ts_b["slope"],
            "growth_per_period": math.expm1(ts_r["slope"]), "baseline_sigma": sigma, "poisson_floor": poisson_floor,
            "reasons": []}


def retrospective_detection(series_list: Sequence[Sequence[float]], onsets: Sequence[Optional[int]],
                            min_series: int = 20, **params: Any) -> Dict[str, Any]:
    """Replay each series period by period using only data known at that point.

    ``onsets[i]`` is the true emergence period of series ``i`` or ``None`` for a non-emergent series.
    Reports detection rate and delay (periods from onset to first flag) for the emergent series and
    the share of non-emergent series ever flagged (false-alarm rate).
    """
    require_min_n(len(series_list), min_series, "retrospective detection")
    delays: List[int] = []
    detected = emergent = flat = false_alarms = 0
    for s, onset in zip(series_list, onsets):
        first: Optional[int] = None
        for t in range(1, len(s) + 1):
            if growth_signal(s[:t], **params)["status"] == "emerging":
                first = t - 1
                break
        if onset is None:
            flat += 1
            false_alarms += 1 if first is not None else 0
        else:
            emergent += 1
            if first is not None and first >= onset:
                detected += 1
                delays.append(first - onset)
            elif first is not None:
                false_alarms += 0          # flagged before onset: counted below as an early flag
    early = sum(1 for s, o in zip(series_list, onsets) if o is not None and any(
        growth_signal(s[:t], **params)["status"] == "emerging" for t in range(1, o + 1)))
    return {"n_emergent": emergent, "n_flat": flat, "detection_rate": detected / emergent if emergent else None,
            "median_delay_periods": median(delays) if delays else None, "false_alarm_rate": false_alarms / flat if flat else None,
            "flagged_before_onset": early, "note": "synthetic series only; says nothing about real technologies"}
