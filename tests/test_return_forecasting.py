"""Acceptance tests for spec 0006 — cross-sectional return forecasting.

Each test is named for the acceptance criterion it covers (see
``specs/0006-ml-return-forecasting/tasks.md``). The pipeline is standard-library
only, so these run without numpy, pandas, or a deep-learning runtime.
"""

from __future__ import annotations

import random

from quantsmith.pipelines.return_forecasting import (
    FeatureStore,
    PriceBar,
    build_labels,
    make_folds,
    monitor,
    run_forecast,
    train_baseline,
    train_challenger,
)

HORIZON = 5
EMBARGO = 1
NAMES = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]


def make_panel(n_days: int = 140, seed: int = 7):
    """Deterministic synthetic price panel (seeded random walk per name)."""
    rng = random.Random(seed)
    bars = []
    for name in NAMES:
        price = 100.0
        for t in range(n_days):
            price *= 1.0 + rng.uniform(-0.02, 0.02)
            bars.append(PriceBar(t=t, name=name, close=round(price, 6)))
    return bars


# --- AC-001: labels use only returns realized strictly after the decision day ---


def test_label_forward_only_AC_001():
    panel = make_panel()
    labels = build_labels(panel, horizon=HORIZON)
    t, name = 40, "AAA"
    assert (t, name) in labels
    baseline = labels[(t, name)]

    # Perturb a price strictly AFTER the label window (index > t + horizon).
    future_idx = t + HORIZON + 10
    perturbed = [
        PriceBar(b.t, b.name, b.close * (5.0 if (b.name == name and b.t == future_idx) else 1.0))
        for b in panel
    ]
    labels_perturbed = build_labels(perturbed, horizon=HORIZON)
    assert labels_perturbed[(t, name)] == baseline  # no dependence on post-window data

    # Perturbing the price AT t + horizon MUST change the label (forward dependency).
    at_window = [
        PriceBar(b.t, b.name, b.close * (1.5 if (b.name == name and b.t == t + HORIZON) else 1.0))
        for b in panel
    ]
    labels_at_window = build_labels(at_window, horizon=HORIZON)
    assert labels_at_window[(t, name)] != baseline


# --- AC-002: offline/online feature parity, as-of the decision day ---


def test_feature_offline_online_parity_AC_002():
    panel = make_panel()
    store = FeatureStore(panel)
    t, name = 50, "BBB"

    offline = store.offline(t, name)
    online = store.online(t, name)
    assert offline is not None
    assert offline == online

    # As-of correctness: dropping all bars after t leaves the features unchanged.
    truncated = [b for b in panel if b.t <= t]
    store_truncated = FeatureStore(truncated)
    assert store_truncated.offline(t, name) == offline


# --- AC-003: purged + embargoed folds never leak train labels into test days ---


def test_folds_purged_embargoed_AC_003():
    days = list(range(0, 130))
    folds = make_folds(days, n_folds=3, horizon=HORIZON, embargo=EMBARGO)
    assert folds, "expected non-empty folds"
    for fold in folds:
        test_start = min(fold.test_days)
        for t_tr in fold.train_days:
            # Train label window ends before the test block, minus the embargo.
            assert t_tr + HORIZON < test_start - EMBARGO


# --- AC-004: baseline and challenger compared on identical test rows ---


def test_baseline_challenger_comparable_AC_004():
    panel = make_panel()
    run = run_forecast(panel, horizon=HORIZON, n_folds=3, embargo=EMBARGO, seed=0)
    assert run.folds
    assert len(run.baseline) == len(run.challenger) == len(run.folds)

    # Same fold -> same number of test rows for both models.
    for base, chal in zip(run.baseline, run.challenger):
        assert base.n == chal.n
        assert base.n > 0

    # Test blocks are non-overlapping in time.
    seen = set()
    for fold in run.folds:
        assert seen.isdisjoint(fold.test_days)
        seen.update(fold.test_days)


# --- AC-005: monitoring emits drift/calibration/decay with a retraining trigger ---


def test_monitoring_emitted_AC_005():
    reference = [0.01, -0.02, 0.03, 0.00, -0.01, 0.02]
    stable = [0.011, -0.019, 0.031, 0.001, -0.009, 0.021]
    report = monitor(reference, stable, baseline_ic=0.05, live_ic=0.049)
    for key in ("drift", "calibration", "decay", "thresholds", "retraining_triggered"):
        assert key in report
    assert isinstance(report["retraining_triggered"], bool)
    assert set(report["thresholds"]) == {"drift", "calibration", "decay"}
    assert report["retraining_triggered"] is False

    # A large IC decay must trip the trigger.
    decayed = monitor(reference, stable, baseline_ic=0.05, live_ic=-0.02)
    assert decayed["retraining_triggered"] is True


# --- AC-006: training is reproducible given the pinned panel and seed ---


def test_training_reproducible_AC_006():
    panel = make_panel()
    labels = build_labels(panel, horizon=HORIZON)
    store = FeatureStore(panel)
    rows = []
    for (t, name), y in sorted(labels.items()):
        feats = store.offline(t, name)
        if feats is not None:
            rows.append((feats, y))
    x = [f for f, _ in rows]
    y = [v for _, v in rows]

    m1 = train_challenger(x, y, seed=42)
    m2 = train_challenger(x, y, seed=42)
    assert m1.weights == m2.weights  # same seed -> identical weights

    m3 = train_challenger(x, y, seed=99)
    assert m3.weights != m1.weights  # different seed -> different weights

    # Whole-run reproducibility on the pinned panel.
    run_a = run_forecast(panel, horizon=HORIZON, seed=1)
    run_b = run_forecast(panel, horizon=HORIZON, seed=1)
    assert [r.rank_ic for r in run_a.challenger] == [r.rank_ic for r in run_b.challenger]


def test_baseline_is_deterministic():
    panel = make_panel()
    labels = build_labels(panel, horizon=HORIZON)
    store = FeatureStore(panel)
    rows = [
        (store.offline(t, name), y)
        for (t, name), y in sorted(labels.items())
        if store.offline(t, name) is not None
    ]
    x = [f for f, _ in rows]
    y = [v for _, v in rows]
    assert train_baseline(x, y).weights == train_baseline(x, y).weights
