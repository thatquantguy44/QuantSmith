"""Acceptance tests for spec 0046 -- walk-forward backtest harness.

Each test is named for the acceptance criterion it covers (see
``specs/0046-walk-forward/tasks.md``).
"""

from __future__ import annotations

import random
import re

import pytest

from quantsmith.pipelines.backtesting import BacktestConfig
from quantsmith.pipelines.return_forecasting import make_folds
from quantsmith.pipelines.walk_forward import (
    render_walk_forward_report,
    walk_forward_backtest,
)

FREE = BacktestConfig(transaction_cost_bps=0.0, periods_per_year=252, rebalance_lag=1)


def synthetic_returns(n=120, assets=2, seed=11):
    rng = random.Random(seed)
    return [[rng.gauss(0.0004, 0.010) for _ in range(assets)] for _ in range(n)]


def equal_weight(train, test):
    return [[0.5, 0.5] for _ in test]


# --- AC-001: folds are make_folds', not a second implementation ---


def test_folds_delegate_to_make_folds_AC_001():
    returns = synthetic_returns()
    result = walk_forward_backtest(
        returns, equal_weight, n_folds=3, horizon=2, embargo=1, config=FREE
    )
    expected = make_folds(list(range(len(returns))), n_folds=3, horizon=2, embargo=1)

    assert len(result.folds) == len(expected)
    for got, want in zip(result.folds, expected):
        assert got.train_periods == want.train_days
        assert got.test_periods == want.test_days


# --- AC-002: fit_predict called once per fold, train disjoint from test ---


def test_fit_predict_called_once_per_fold_disjoint_AC_002():
    returns = synthetic_returns()
    calls = []

    def recording(train, test):
        calls.append((tuple(train), tuple(test)))
        return [[0.5, 0.5] for _ in test]

    result = walk_forward_backtest(returns, recording, n_folds=3, horizon=2, config=FREE)

    assert len(calls) == len(result.folds)
    for train, test in calls:
        assert set(train).isdisjoint(set(test)), "a training period leaked into the test block"
        assert max(train) < min(test), "training must precede the held-out block"


# --- AC-003: fold slicing preserves the engine's rebalance lag ---


def test_fold_alignment_preserves_lag_AC_003():
    # Single asset; return at period p is p/1000 so its origin is identifiable.
    n = 60
    returns = [[p / 1000.0] for p in range(n)]

    def unit(train, test):
        return [[1.0] for _ in test]

    result = walk_forward_backtest(returns, unit, n_folds=2, horizon=1, embargo=1, config=FREE)

    fold = result.folds[0]
    t0 = fold.test_periods[0]
    first_gross = fold.result.periods[0].gross_return

    # With lag 1 the first weight meets the return of the NEXT global period.
    assert first_gross == pytest.approx((t0 + 1) / 1000.0)
    assert first_gross != pytest.approx(t0 / 1000.0)


# --- AC-004: the fold distribution is reported ---


def test_fold_distribution_reported_AC_004():
    result = walk_forward_backtest(
        synthetic_returns(), equal_weight, n_folds=3, horizon=2, config=FREE
    )

    assert len(result.fold_sharpes) == len(result.folds)
    assert len(result.fold_net_returns) == len(result.folds)
    assert result.sharpe_dispersion >= 0.0
    assert 0.0 <= result.positive_fold_fraction <= 1.0
    assert result.best_fold is not None and result.worst_fold is not None
    assert result.best_fold.result.sharpe >= result.worst_fold.result.sharpe
    assert result.mean_fold_sharpe == pytest.approx(
        sum(result.fold_sharpes) / len(result.fold_sharpes)
    )


# --- AC-005: pooled series is held-out periods only ---


def test_pooled_out_of_sample_series_AC_005():
    result = walk_forward_backtest(
        synthetic_returns(), equal_weight, n_folds=3, horizon=2, config=FREE
    )

    expected = sum(len(f.result.periods) for f in result.folds)
    assert result.evaluated_periods == expected
    assert len(result.pooled_net_returns) == expected
    assert 0.0 <= result.pooled_probabilistic_sharpe <= 1.0

    # Nothing from a training block can appear: the pooled length equals the
    # sum of the per-fold evaluated periods, which came from test blocks only.
    total_test = sum(len(f.test_periods) for f in result.folds)
    assert expected <= total_test


# --- AC-006: a wrong weight count is rejected, naming the fold ---


def test_wrong_weight_count_raises_AC_006():
    def too_few(train, test):
        return [[0.5, 0.5] for _ in test][:-1]

    with pytest.raises(ValueError, match="fold 0"):
        walk_forward_backtest(synthetic_returns(), too_few, n_folds=3, horizon=2, config=FREE)


# --- AC-007: the report satisfies the gate's themes ---

_GATE_THEMES = [
    r"transaction cost|slippage|commission|borrow",
    r"out.of.sample|oos|walk.forward|holdout",
    r"benchmark|baseline",
    r"turnover|capacity",
    r"multiple.testing|deflated|probabilistic sharpe|psr|p.hack",
]


def test_report_satisfies_gate_themes_AC_007():
    result = walk_forward_backtest(
        synthetic_returns(), equal_weight, n_folds=3, horizon=2,
        config=BacktestConfig(transaction_cost_bps=5.0, periods_per_year=252),
    )
    doc = render_walk_forward_report(
        result, strategy="Test", owner="Quant Research",
        universe="2 test assets", period="120 periods",
    )

    for pattern in _GATE_THEMES:
        assert re.search(pattern, doc, re.IGNORECASE), f"gate theme missing: {pattern}"

    assert "| Fold |" in doc  # the fold distribution table
    assert "Sharpe dispersion across folds" in doc
    assert "cannot establish" in doc  # the guarantee's stated limit


# --- AC-008: deterministic ---


def test_deterministic_AC_008():
    returns = synthetic_returns()
    a = walk_forward_backtest(returns, equal_weight, n_folds=3, horizon=2, config=FREE)
    b = walk_forward_backtest(returns, equal_weight, n_folds=3, horizon=2, config=FREE)

    assert a.fold_sharpes == b.fold_sharpes
    assert a.pooled_net_returns == b.pooled_net_returns

    args = dict(strategy="S", owner="O", universe="U", period="P")
    assert render_walk_forward_report(a, **args) == render_walk_forward_report(b, **args)


# --- AC-009: too few periods raises rather than returning nothing ---


def test_too_few_periods_raises_AC_009():
    with pytest.raises(ValueError, match="too few periods"):
        walk_forward_backtest([[0.01]] * 3, lambda tr, te: [[1.0] for _ in te],
                              n_folds=5, horizon=2, config=FREE)
