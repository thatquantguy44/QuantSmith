"""Reference pipeline for spec 0041 -- cross-sectional ranking forecast.

``0006`` (``return_forecasting.py``) trains its baseline and challenger with
point-wise regression loss, then scores them with cross-sectional rank IC.
That is a mismatch: a model trained to minimize point-wise error is not
directly trained to get the cross-sectional *order* right, which is what a
long/short selection process actually consumes.

This module changes only the training objective. ``train_ranker`` optimizes
a pairwise (RankNet-style) logistic ranking loss over same-day pairs only,
producing a ``return_forecasting.LinearModel`` -- the same scorer type
``0006``'s own baseline produces. Every other piece of ``0006``'s
already-shipped, leakage-safe machinery (``build_labels``, ``FeatureStore``,
``make_folds``, ``evaluate``, ``LinearModel``) is imported and reused
unmodified, never reimplemented.

``run_ranking_forecast``'s AC-006 comparison (ranker vs. point-wise baseline
on a synthetic, rank-only-signal panel) demonstrates a *mechanism* -- a
ranking objective is favored when only rank, not magnitude, carries signal
-- on a constructed fixture. It is not a backtested market claim.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .return_forecasting import (
    EvalResult,
    FeatureConfig,
    FeatureStore,
    Fold,
    LinearModel,
    Panel,
    Sample,
    build_labels,
    evaluate,
    make_folds,
    train_baseline,
)

DayGroup = Sequence[Tuple[Sequence[float], float]]


# ---------------------------------------------------------------------------
# Pairwise ranking loss -- REQ-001 / REQ-002
# ---------------------------------------------------------------------------


def train_ranker(
    day_groups: Sequence[DayGroup],
    seed: int = 0,
    epochs: int = 300,
    lr: float = 0.05,
) -> LinearModel:
    """Pairwise (RankNet-style) linear ranking scorer.

    Trains ``s = w . [x, 1]`` so that, within each ``day_group``, a
    higher-labeled sample scores above a lower-labeled one. Preference pairs
    are formed *only* within a single ``day_group`` -- never across two
    groups -- so cross-day comparison is structurally impossible, not merely
    filtered out after the fact (NFR-003).

    Deterministic given ``seed``: the only randomness is the initial weight
    vector (AC-005).
    """
    groups = [list(g) for g in day_groups if len(g) >= 2]
    if not groups:
        raise ValueError("no day group has at least two samples to rank")

    dim = len(groups[0][0][0]) + 1
    rng = random.Random(seed)
    w = [rng.uniform(-0.01, 0.01) for _ in range(dim)]

    pairs_per_group: List[List[Tuple[List[float], List[float]]]] = []
    for group in groups:
        rows = [(list(x) + [1.0], y) for x, y in group]
        pairs = [(xi, xj) for xi, yi in rows for xj, yj in rows if yi > yj]
        if pairs:
            pairs_per_group.append(pairs)

    total_pairs = sum(len(p) for p in pairs_per_group)
    if total_pairs == 0:
        raise ValueError("no ranking pairs: every day group has tied or single-valued targets")

    for _ in range(epochs):
        grad = [0.0] * dim
        for pairs in pairs_per_group:
            for xi, xj in pairs:
                si = sum(wk * xk for wk, xk in zip(w, xi))
                sj = sum(wk * xk for wk, xk in zip(w, xj))
                p = _sigmoid(sj - si)  # > 0.5 while i is mis-ranked below j
                for k in range(dim):
                    grad[k] += p * (xj[k] - xi[k])
        w = [wk - lr * gk / total_pairs for wk, gk in zip(w, grad)]

    return LinearModel(w)


def _sigmoid(z: float) -> float:
    if z >= 0:
        e = math.exp(-z)
        return 1.0 / (1.0 + e)
    e = math.exp(z)
    return e / (1.0 + e)


# ---------------------------------------------------------------------------
# Orchestration -- REQ-003 / REQ-004
# ---------------------------------------------------------------------------


@dataclass
class RankingForecastRun:
    """Result of running both the ranker and 0006's point-wise baseline."""

    folds: List[Fold]
    ranker: List[EvalResult] = field(default_factory=list)
    pointwise: List[EvalResult] = field(default_factory=list)

    def mean_ranker_ic(self) -> float:
        return _mean([r.rank_ic for r in self.ranker]) if self.ranker else 0.0

    def mean_pointwise_ic(self) -> float:
        return _mean([r.rank_ic for r in self.pointwise]) if self.pointwise else 0.0


def run_ranking_forecast(
    panel: Panel,
    horizon: int = 5,
    n_folds: int = 3,
    embargo: int = 1,
    seed: int = 0,
    config: Optional[FeatureConfig] = None,
) -> RankingForecastRun:
    """Train the ranker and 0006's point-wise baseline on identical folds.

    Reuses ``build_labels``, ``FeatureStore``, and ``make_folds`` from
    ``return_forecasting.py`` unmodified, and evaluates both models with
    ``return_forecasting.evaluate`` -- no new evaluation code -- so the
    comparison is apples-to-apples on the metric a ranking loss is meant to
    improve.
    """
    cfg = config or FeatureConfig()
    labels = build_labels(panel, horizon=horizon)
    store = FeatureStore(panel, cfg)

    samples: Dict[Sample, Tuple[List[float], float]] = {}
    for (t, name), y in labels.items():
        feats = store.offline(t, name)
        if feats is not None:
            samples[(t, name)] = (feats, y)

    decision_days = sorted({t for (t, _n) in samples})
    folds = make_folds(decision_days, n_folds=n_folds, horizon=horizon, embargo=embargo)

    run = RankingForecastRun(folds=folds)
    for fold in folds:
        train = [(t, f, y) for (t, _n), (f, y) in samples.items() if t in fold.train_days]
        test = [(f, y) for (t, _n), (f, y) in samples.items() if t in fold.test_days]
        if not train or not test:
            continue

        by_day: Dict[int, List[Tuple[List[float], float]]] = {}
        for t, f, y in train:
            by_day.setdefault(t, []).append((f, y))
        day_groups = list(by_day.values())

        xtr, ytr = [f for _, f, _ in train], [y for _, _, y in train]
        xte, yte = [f for f, _ in test], [y for _, y in test]

        ranker = train_ranker(day_groups, seed=seed)
        pointwise = train_baseline(xtr, ytr)

        run.ranker.append(evaluate(ranker, xte, yte))
        run.pointwise.append(evaluate(pointwise, xte, yte))
    return run


def _mean(values: Sequence[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0
