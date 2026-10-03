"""Reference pipeline for spec 0021 — model/signal monitoring.

Computes the health of a live model or signal against a reference: distribution drift,
calibration error, alpha decay (information-coefficient drop), and a volatility-regime
shift. It emits both a health verdict and a list of ``Observation``s that the alerting
engine (`0020`) evaluates — so monitoring detects and alerting notifies, without either
owning the other. Standard-library only and deterministic. Generalizes the ad-hoc
``monitor`` in ``return_forecasting`` (`0006`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from .alerting import Observation


@dataclass(frozen=True)
class MonitorThresholds:
    drift: float = 0.20
    calibration: float = 0.05
    decay: float = 0.02
    regime: float = 0.50            # |vol ratio - 1| that flags a regime shift


@dataclass(frozen=True)
class SignalHealth:
    drift: float
    calibration: float
    decay: float
    regime_shift: float
    breaches: List[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return not self.breaches

    def observations(self) -> List[Observation]:
        """The measured values, as observations the alerting engine can evaluate."""
        return [
            Observation("drift", self.drift),
            Observation("calibration", self.calibration),
            Observation("decay", self.decay),
            Observation("regime_shift", self.regime_shift),
        ]


def monitor_signal(
    reference: Sequence[float],
    live: Sequence[float],
    baseline_ic: float,
    live_ic: float,
    thresholds: Optional[MonitorThresholds] = None,
) -> SignalHealth:
    """Compute signal health from a reference vs a live sample.

    * drift — a population-stability proxy (mean + spread shift).
    * calibration — absolute mean shift.
    * decay — ``baseline_ic - live_ic`` (a drop is positive decay).
    * regime_shift — ``|stdev(live) / stdev(reference) - 1|``.

    Honest by construction: any check over its threshold appears in ``breaches`` and
    makes the signal unhealthy.
    """
    th = thresholds or MonitorThresholds()
    drift = _population_shift(reference, live)
    calibration = abs(_mean(live) - _mean(reference))
    decay = baseline_ic - live_ic
    regime_shift = _regime_shift(reference, live)

    breaches: List[str] = []
    if drift > th.drift:
        breaches.append(f"drift {drift:.3f} > {th.drift}")
    if calibration > th.calibration:
        breaches.append(f"calibration {calibration:.3f} > {th.calibration}")
    if decay > th.decay:
        breaches.append(f"decay {decay:.3f} > {th.decay}")
    if regime_shift > th.regime:
        breaches.append(f"regime_shift {regime_shift:.3f} > {th.regime}")

    return SignalHealth(
        drift=drift, calibration=calibration, decay=decay,
        regime_shift=regime_shift, breaches=breaches,
    )


# --- helpers ---------------------------------------------------------------


def _mean(values: Sequence[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def _stdev(values: Sequence[float]) -> float:
    values = list(values)
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / (len(values) - 1))


def _population_shift(reference: Sequence[float], live: Sequence[float]) -> float:
    if not reference or not live:
        return 0.0
    return abs(_mean(live) - _mean(reference)) + abs(_stdev(live) - _stdev(reference))


def _regime_shift(reference: Sequence[float], live: Sequence[float]) -> float:
    sref = _stdev(reference)
    slive = _stdev(live)
    if sref == 0:
        return 0.0 if slive == 0 else 1.0
    return abs(slive / sref - 1.0)
