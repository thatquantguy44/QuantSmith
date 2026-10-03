"""Reference pipeline for spec 0006 — cross-sectional return forecasting.

This module makes the ``0006-ml-return-forecasting`` spec *executable*. It is a
deterministic, dependency-free (standard-library-only) reference that demonstrates
the leakage-safe contracts the spec requires, so the acceptance criteria can be
tested anywhere without numpy, pandas, or a deep-learning runtime.

The models here are intentionally simple stand-ins:

* ``train_baseline`` is a closed-form ridge linear model — the reference stand-in
  for the spec's gradient-boosted-tree baseline (``supervised_learning``).
* ``train_challenger`` is a seeded gradient-descent linear model — the reference
  stand-in for the spec's deep temporal challenger (``deep_time_series`` /
  ``training_systems``).

Production implementations swap those two functions for real models; everything
around them (labels, the point-in-time feature store, purged/embargoed folds,
net-of-cost evaluation, and monitoring) is the contract that keeps a real model
honest and is exercised by the tests in ``tests/test_return_forecasting.py``.

Correctness properties held *by construction* (not by after-the-fact checks):

* REQ-001 / AC-001 — labels use only returns realized strictly after the decision
  day; no feature observed after the decision day enters a label.
* REQ-002 / AC-002 — features are served as-of the decision day from one code path,
  so offline (training) and online (serving) values are identical.
* REQ-003 / AC-003 — folds are purged and embargoed so no train label window
  reaches the test decision days.
* NFR-001 / AC-006 — training is reproducible given a pinned panel and seed.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PriceBar:
    """One adjusted-close observation for a name on a trading-day index."""

    t: int  # trading-day index (0-based, monotonic)
    name: str
    close: float


Panel = Sequence[PriceBar]
Sample = Tuple[int, str]  # (decision_day, name)


@dataclass(frozen=True)
class FeatureConfig:
    """Windows for point-in-time feature construction (all in trading days)."""

    momentum_lookback: int = 20
    momentum_skip: int = 1
    reversal_lookback: int = 3
    vol_window: int = 10

    @property
    def min_history(self) -> int:
        """Earliest decision day index that has enough trailing history."""
        return max(
            self.momentum_lookback,
            self.reversal_lookback,
            self.vol_window + 1,
        )


# ---------------------------------------------------------------------------
# Labels — REQ-001 / AC-001
# ---------------------------------------------------------------------------


def build_labels(panel: Panel, horizon: int = 5) -> Dict[Sample, float]:
    """Cross-sectional forward *excess* return labels.

    The label for decision day ``t`` and name is the ``horizon``-day forward
    return ``close[t + horizon] / close[t] - 1`` (realized strictly after ``t``),
    de-meaned across the names that have a forward return on that day. Only prices
    at ``t`` and ``t + horizon`` enter the label — never a feature observed after
    ``t`` (AC-001).
    """
    if horizon <= 0:
        raise ValueError("horizon must be positive")

    by_name = _closes_by_name(panel)
    raw: Dict[Sample, float] = {}
    for name, closes in by_name.items():
        for t in sorted(closes):
            t_fwd = t + horizon
            if t_fwd in closes and closes[t] > 0:
                raw[(t, name)] = closes[t_fwd] / closes[t] - 1.0

    # Cross-sectional de-mean per decision day.
    days: Dict[int, List[Sample]] = {}
    for key in raw:
        days.setdefault(key[0], []).append(key)

    labels: Dict[Sample, float] = {}
    for day, keys in days.items():
        mean = sum(raw[k] for k in keys) / len(keys)
        for k in keys:
            labels[k] = raw[k] - mean
    return labels


# ---------------------------------------------------------------------------
# Point-in-time feature store — REQ-002 / AC-002
# ---------------------------------------------------------------------------


class FeatureStore:
    """As-of feature store with a single code path for offline and online reads.

    ``offline`` (training) and ``online`` (serving) both filter the panel to
    observations on or before the decision day and call the same private
    ``_compute``. Offline/online parity therefore holds by construction (AC-002),
    and no future observation can leak into a feature (NFR-002).
    """

    def __init__(self, panel: Panel, config: Optional[FeatureConfig] = None):
        self.config = config or FeatureConfig()
        self._by_name = _closes_by_name(panel)

    def offline(self, t: int, name: str) -> Optional[List[float]]:
        return self._as_of(t, name)

    def online(self, t: int, name: str) -> Optional[List[float]]:
        return self._as_of(t, name)

    # -- internals ----------------------------------------------------------

    def _as_of(self, t: int, name: str) -> Optional[List[float]]:
        closes = self._by_name.get(name)
        if closes is None:
            return None
        # As-of: only observations with index <= t are visible.
        visible = {i: c for i, c in closes.items() if i <= t}
        return self._compute(visible, t)

    def _compute(self, closes: Dict[int, float], t: int) -> Optional[List[float]]:
        cfg = self.config
        need = [t]
        need.append(t - cfg.momentum_lookback)
        need.append(t - cfg.momentum_skip)
        need.append(t - cfg.reversal_lookback)
        if any(i not in closes for i in need):
            return None

        momentum = closes[t - cfg.momentum_skip] / closes[t - cfg.momentum_lookback] - 1.0
        reversal = -(closes[t] / closes[t - cfg.reversal_lookback] - 1.0)
        vol = self._realized_vol(closes, t, cfg.vol_window)
        if vol is None:
            return None
        return [momentum, reversal, vol]

    @staticmethod
    def _realized_vol(closes: Dict[int, float], t: int, window: int) -> Optional[float]:
        rets: List[float] = []
        for i in range(t - window + 1, t + 1):
            if i in closes and (i - 1) in closes and closes[i - 1] > 0:
                rets.append(closes[i] / closes[i - 1] - 1.0)
        if len(rets) < 2:
            return None
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        return math.sqrt(var)


# ---------------------------------------------------------------------------
# Purged, embargoed walk-forward folds — REQ-003 / AC-003
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Fold:
    train_days: Tuple[int, ...]
    test_days: Tuple[int, ...]


def make_folds(
    decision_days: Sequence[int],
    n_folds: int = 3,
    horizon: int = 5,
    embargo: int = 1,
) -> List[Fold]:
    """Walk-forward splits with a purge + embargo gap between train and test.

    Test blocks are contiguous and later in time than their training set. Any
    training day is kept only if its label window ends before the test block
    starts, minus the embargo: ``t_train + horizon < test_start - embargo``. This
    guarantees no train label reaches a test decision day (AC-003).
    """
    days = sorted(set(int(d) for d in decision_days))
    if n_folds < 1 or len(days) < n_folds + 1:
        return []

    block = len(days) // (n_folds + 1)
    if block == 0:
        return []

    folds: List[Fold] = []
    for k in range(1, n_folds + 1):
        test_start_idx = k * block
        test_end_idx = (k + 1) * block if k < n_folds else len(days)
        test_days = days[test_start_idx:test_end_idx]
        if not test_days:
            continue
        test_start = test_days[0]
        train_days = [d for d in days[:test_start_idx] if d + horizon < test_start - embargo]
        if not train_days:
            continue
        folds.append(Fold(tuple(train_days), tuple(test_days)))
    return folds


# ---------------------------------------------------------------------------
# Models — REQ-004 (baseline) and REQ-005 (challenger)
# ---------------------------------------------------------------------------


@dataclass
class LinearModel:
    """Linear model ``pred = w . [features, 1]``; the bias is the last weight."""

    weights: List[float]

    def predict(self, x: Sequence[float]) -> float:
        row = list(x) + [1.0]
        return sum(w * v for w, v in zip(self.weights, row))


def train_baseline(
    features: Sequence[Sequence[float]],
    targets: Sequence[float],
    ridge: float = 1e-6,
) -> LinearModel:
    """Closed-form ridge linear regression (deterministic).

    Reference stand-in for the spec's gradient-boosted-tree baseline; it is
    parameter-free beyond the ridge term, so it is reproducible without a seed.
    """
    if not features:
        raise ValueError("no training rows")
    rows = [list(x) + [1.0] for x in features]
    dim = len(rows[0])

    # Normal equations: (X^T X + ridge I) w = X^T y, solved by Gaussian elimination.
    xtx = [[0.0] * dim for _ in range(dim)]
    xty = [0.0] * dim
    for row, y in zip(rows, targets):
        for i in range(dim):
            xty[i] += row[i] * y
            for j in range(dim):
                xtx[i][j] += row[i] * row[j]
    for i in range(dim):
        xtx[i][i] += ridge
    return LinearModel(_solve(xtx, xty))


def train_challenger(
    features: Sequence[Sequence[float]],
    targets: Sequence[float],
    seed: int = 0,
    epochs: int = 400,
    lr: float = 0.05,
) -> LinearModel:
    """Seeded gradient-descent linear model (reproducible given the seed).

    Reference stand-in for the spec's deep temporal challenger. It carries a seed
    precisely so the reproducibility contract (AC-006) has something to assert:
    same panel + same seed => identical weights.
    """
    if not features:
        raise ValueError("no training rows")
    rows = [list(x) + [1.0] for x in features]
    dim = len(rows[0])
    rng = random.Random(seed)
    w = [rng.uniform(-0.01, 0.01) for _ in range(dim)]
    n = len(rows)

    for _ in range(epochs):
        grad = [0.0] * dim
        for row, y in zip(rows, targets):
            err = sum(wi * xi for wi, xi in zip(w, row)) - y
            for i in range(dim):
                grad[i] += err * row[i]
        w = [wi - lr * g / n for wi, g in zip(w, grad)]
    return LinearModel(w)


# ---------------------------------------------------------------------------
# Evaluation — NFR-003 (net of cost) / AC-004 (comparability)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvalResult:
    rank_ic: float
    net_of_cost: float
    turnover: float
    n: int


def evaluate(
    model: LinearModel,
    features: Sequence[Sequence[float]],
    targets: Sequence[float],
    cost_per_turnover: float = 0.0005,
) -> EvalResult:
    """Rank IC plus a toy net-of-cost score with turnover.

    Metrics are computed only on the rows passed in, so evaluating the baseline
    and challenger on the *same* fold's test rows makes them comparable by
    construction (AC-004). Reporting is net of cost, never gross IC alone
    (NFR-003).
    """
    preds = [model.predict(x) for x in features]
    ic = _spearman(preds, list(targets))
    # Position = sign of prediction; turnover = fraction that flip vs. the prior.
    positions = [1.0 if p >= 0 else -1.0 for p in preds]
    flips = sum(1 for a, b in zip(positions, positions[1:]) if a != b)
    turnover = flips / max(len(positions) - 1, 1)
    gross = sum(pos * y for pos, y in zip(positions, targets)) / len(positions)
    net = gross - cost_per_turnover * turnover
    return EvalResult(rank_ic=ic, net_of_cost=net, turnover=turnover, n=len(preds))


# ---------------------------------------------------------------------------
# Monitoring — REQ-006 / AC-005
# ---------------------------------------------------------------------------


def monitor(
    reference: Sequence[float],
    live: Sequence[float],
    baseline_ic: float,
    live_ic: float,
) -> Dict[str, object]:
    """Emit drift, calibration, and decay metrics with a retraining trigger.

    Deterministic and dependency-free. Thresholds are explicit and the retraining
    trigger fires when any metric breaches its threshold (AC-005).
    """
    drift = _population_shift(reference, live)
    calibration = abs(_mean(live) - _mean(reference))
    decay = baseline_ic - live_ic
    thresholds = {"drift": 0.20, "calibration": 0.05, "decay": 0.02}
    triggered = (
        drift > thresholds["drift"]
        or calibration > thresholds["calibration"]
        or decay > thresholds["decay"]
    )
    return {
        "drift": drift,
        "calibration": calibration,
        "decay": decay,
        "thresholds": thresholds,
        "retraining_triggered": bool(triggered),
    }


# ---------------------------------------------------------------------------
# End-to-end orchestration
# ---------------------------------------------------------------------------


@dataclass
class ForecastRun:
    """Result of a full walk-forward run over the panel."""

    folds: List[Fold]
    baseline: List[EvalResult] = field(default_factory=list)
    challenger: List[EvalResult] = field(default_factory=list)

    def mean_baseline_ic(self) -> float:
        return _mean([r.rank_ic for r in self.baseline]) if self.baseline else 0.0

    def mean_challenger_ic(self) -> float:
        return _mean([r.rank_ic for r in self.challenger]) if self.challenger else 0.0


def run_forecast(
    panel: Panel,
    horizon: int = 5,
    n_folds: int = 3,
    embargo: int = 1,
    seed: int = 0,
    config: Optional[FeatureConfig] = None,
) -> ForecastRun:
    """Compose the whole 0006 workflow: labels -> features -> folds -> models.

    Trains the baseline and the challenger on identical folds and evaluates both
    on each fold's held-out test rows, so the comparison is apples-to-apples.
    """
    cfg = config or FeatureConfig()
    labels = build_labels(panel, horizon=horizon)
    store = FeatureStore(panel, cfg)

    # Build the sample table (only decision days with both features and a label).
    samples: Dict[Sample, Tuple[List[float], float]] = {}
    for (t, name), y in labels.items():
        feats = store.offline(t, name)
        if feats is not None:
            samples[(t, name)] = (feats, y)

    decision_days = sorted({t for (t, _n) in samples})
    folds = make_folds(decision_days, n_folds=n_folds, horizon=horizon, embargo=embargo)

    run = ForecastRun(folds=folds)
    for fold in folds:
        train = [(f, y) for (t, _n), (f, y) in samples.items() if t in fold.train_days]
        test = [(f, y) for (t, _n), (f, y) in samples.items() if t in fold.test_days]
        if not train or not test:
            continue
        xtr, ytr = [f for f, _ in train], [y for _, y in train]
        xte, yte = [f for f, _ in test], [y for _, y in test]

        base = train_baseline(xtr, ytr)
        chal = train_challenger(xtr, ytr, seed=seed)
        run.baseline.append(evaluate(base, xte, yte))
        run.challenger.append(evaluate(chal, xte, yte))
    return run


# ---------------------------------------------------------------------------
# Small numeric helpers (stdlib-only)
# ---------------------------------------------------------------------------


def _closes_by_name(panel: Panel) -> Dict[str, Dict[int, float]]:
    out: Dict[str, Dict[int, float]] = {}
    for bar in panel:
        out.setdefault(bar.name, {})[bar.t] = bar.close
    return out


def _solve(a: List[List[float]], b: List[float]) -> List[float]:
    """Solve ``a x = b`` by Gaussian elimination with partial pivoting."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-15:
            continue
        m[col], m[pivot] = m[pivot], m[col]
        pv = m[col][col]
        m[col] = [x / pv for x in m[col]]
        for r in range(n):
            if r != col and m[r][col] != 0.0:
                factor = m[r][col]
                m[r] = [x - factor * y for x, y in zip(m[r], m[col])]
    return [m[i][n] for i in range(n)]


def _rank(values: Sequence[float]) -> List[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _spearman(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) < 2:
        return 0.0
    return _pearson(_rank(a), _rank(b))


def _pearson(a: Sequence[float], b: Sequence[float]) -> float:
    ma, mb = _mean(a), _mean(b)
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = math.sqrt(sum((x - ma) ** 2 for x in a))
    vb = math.sqrt(sum((y - mb) ** 2 for y in b))
    if va == 0 or vb == 0:
        return 0.0
    return cov / (va * vb)


def _mean(values: Sequence[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def _population_shift(reference: Sequence[float], live: Sequence[float]) -> float:
    """A light population-stability proxy: absolute mean+spread shift."""
    if not reference or not live:
        return 0.0
    mean_shift = abs(_mean(live) - _mean(reference))
    spread_ref = _stdev(reference)
    spread_live = _stdev(live)
    spread_shift = abs(spread_live - spread_ref)
    return mean_shift + spread_shift


def _stdev(values: Sequence[float]) -> float:
    values = list(values)
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))
