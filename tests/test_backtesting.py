"""Acceptance tests for spec 0044 -- backtest engine.

Each test is named for the acceptance criterion it covers (see
``specs/0044-backtesting/tasks.md``).
"""

from __future__ import annotations

import math
import random
import re

import pytest

from quantsmith.pipelines.backtesting import (
    BacktestConfig,
    probabilistic_sharpe_ratio,
    render_backtest_report,
    run_backtest,
)

TOL = 1e-12
FREE = BacktestConfig(transaction_cost_bps=0.0, periods_per_year=252)


# --- AC-001: weights never meet a return at or before their decision index ---


def test_no_lookahead_offset_AC_001():
    # returns[0] is a spike that only a look-ahead bug could capture.
    weights = [[1.0], [1.0], [1.0]]
    returns = [[9.99], [0.01], [0.02], [0.03]]
    result = run_backtest(weights, returns, FREE)

    gross = [p.gross_return for p in result.periods]
    assert gross == [0.01, 0.02, 0.03]
    assert 9.99 not in gross


# --- AC-002: a zero lag is rejected ---


def test_zero_lag_rejected_AC_002():
    with pytest.raises(ValueError, match="look-ahead"):
        run_backtest([[1.0]], [[0.01], [0.02]], BacktestConfig(rebalance_lag=0))


# --- AC-003: net == gross - transaction - financing, exactly ---


def test_net_equals_gross_minus_costs_AC_003():
    weights = [[0.5, -0.5], [0.7, -0.3], [0.2, -0.8]]
    returns = [[0.01, 0.02], [-0.01, 0.03], [0.02, -0.01], [0.00, 0.01]]
    result = run_backtest(
        weights, returns, BacktestConfig(transaction_cost_bps=8.0, borrow_cost_bps_annual=150.0)
    )
    assert result.periods
    for p in result.periods:
        assert math.isclose(
            p.net_return, p.gross_return - p.transaction_cost - p.financing_cost, abs_tol=TOL
        )


# --- AC-004: an unchanged weight vector costs nothing to hold ---


def test_unchanged_weights_cost_nothing_AC_004():
    weights = [[0.6, 0.4], [0.6, 0.4], [0.6, 0.4]]
    returns = [[0.01, 0.01]] * 5
    result = run_backtest(weights, returns, BacktestConfig(transaction_cost_bps=25.0))

    # First period trades in from flat; the rest hold.
    assert result.periods[0].turnover > 0
    assert result.periods[0].transaction_cost > 0
    for p in result.periods[1:]:
        assert p.turnover == 0.0
        assert p.transaction_cost == 0.0


# --- AC-005: financing is charged on short exposure only ---


def test_financing_charged_on_shorts_only_AC_005():
    cfg = BacktestConfig(transaction_cost_bps=0.0, borrow_cost_bps_annual=200.0)
    flat_returns = [[0.0], [0.0], [0.0]]

    shorted = run_backtest([[-1.0], [-1.0]], flat_returns, cfg)
    long_only = run_backtest([[1.0], [1.0]], flat_returns, cfg)

    assert shorted.periods[0].financing_cost > 0
    assert all(p.financing_cost == 0.0 for p in long_only.periods)
    assert shorted.has_shorts is True
    assert long_only.has_shorts is False

    # Twice the short exposure costs twice as much to finance.
    bigger = run_backtest([[-2.0], [-2.0]], flat_returns, cfg)
    assert math.isclose(
        bigger.periods[0].financing_cost, 2 * shorted.periods[0].financing_cost, abs_tol=TOL
    )


# --- AC-006: equity curve and drawdown match a hand computation ---


def test_drawdown_and_equity_curve_AC_006():
    # Net path: +10%, -20%, +5%  (no costs, single asset held at weight 1)
    weights = [[1.0], [1.0], [1.0]]
    returns = [[0.0], [0.10], [-0.20], [0.05]]
    result = run_backtest(weights, returns, FREE)

    assert [round(r, 10) for r in result.net_returns] == [0.10, -0.20, 0.05]

    curve = result.equity_curve
    assert math.isclose(curve[0], 1.10, abs_tol=1e-12)
    assert math.isclose(curve[1], 0.88, abs_tol=1e-12)
    assert math.isclose(curve[2], 0.924, abs_tol=1e-12)

    # Peak 1.10 -> trough 0.88 is a 20% drawdown.
    assert math.isclose(result.max_drawdown, 0.20, abs_tol=1e-12)
    assert math.isclose(result.total_return, 0.924 - 1.0, abs_tol=1e-12)


# --- AC-007: PSR is a probability and rises with sample length ---


def test_probabilistic_sharpe_AC_007():
    rng = random.Random(7)
    sample = [0.001 + rng.gauss(0, 0.005) for _ in range(40)]

    short_psr = probabilistic_sharpe_ratio(sample)
    long_psr = probabilistic_sharpe_ratio(sample * 20)  # same Sharpe, longer sample

    assert 0.0 <= short_psr <= 1.0
    assert 0.0 <= long_psr <= 1.0
    assert long_psr > short_psr

    # Degenerate samples say nothing rather than something false.
    assert probabilistic_sharpe_ratio([0.01, 0.01, 0.01, 0.01]) == 0.0
    assert probabilistic_sharpe_ratio([0.01]) == 0.0


# --- AC-008: active return is net less benchmark, per period ---


def test_active_return_vs_benchmark_AC_008():
    weights = [[1.0], [1.0]]
    returns = [[0.0], [0.03], [0.01]]
    benchmark = [0.0, 0.01, 0.004]

    result = run_backtest(weights, returns, FREE, benchmark=benchmark)
    for p in result.periods:
        assert p.benchmark_return is not None
        assert math.isclose(p.active_return, p.net_return - p.benchmark_return, abs_tol=TOL)
    assert result.active_return is not None

    # With no benchmark supplied, nothing is claimed.
    assert run_backtest(weights, returns, FREE).active_return is None


# --- AC-009: the rendered report satisfies the gate's own themes ---

_GATE_THEMES = [
    r"transaction cost|slippage|commission|borrow",
    r"out.of.sample|oos|walk.forward|holdout",
    r"benchmark|baseline",
    r"turnover|capacity",
    r"multiple.testing|deflated|probabilistic sharpe|psr|p.hack",
]

_SHORT_TRIGGER = r"short.sell|short.selling|shorts?[^a-z]|long.short"
_FINANCING_THEME = r"borrow|short rebate|rebate|stock loan|financing cost|hard.to.borrow"


def test_report_satisfies_gate_themes_AC_009():
    weights = [[0.6, -0.4], [0.5, -0.5], [0.7, -0.3]]
    returns = [[0.01, 0.00], [0.02, -0.01], [-0.01, 0.02], [0.01, 0.01]]
    result = run_backtest(
        weights, returns, BacktestConfig(transaction_cost_bps=5.0, borrow_cost_bps_annual=100.0)
    )
    doc = render_backtest_report(
        result,
        strategy="Test long/short",
        owner="Quant Research",
        universe="2 test assets",
        period="test sample",
        benchmark_name="equal weight",
    )

    for pattern in _GATE_THEMES:
        assert re.search(pattern, doc, re.IGNORECASE), f"gate theme missing: {pattern}"

    # This book holds shorts, so the gate's conditional financing theme applies.
    assert re.search(_SHORT_TRIGGER, doc, re.IGNORECASE)
    assert re.search(_FINANCING_THEME, doc, re.IGNORECASE)

    for section in ("## Summary", "## Results", "## Costs And Execution", "## Reproducibility"):
        assert section in doc

    # The guarantee's limit is stated, not just the guarantee.
    assert "does not establish" in doc


# --- AC-010: deterministic ---


def test_deterministic_AC_010():
    weights = [[0.5, 0.5], [0.4, 0.6]]
    returns = [[0.01, 0.02], [0.00, 0.01], [0.02, -0.01]]
    cfg = BacktestConfig(transaction_cost_bps=7.0, borrow_cost_bps_annual=50.0)

    a = run_backtest(weights, returns, cfg)
    b = run_backtest(weights, returns, cfg)
    assert a.periods == b.periods
    assert a.sharpe == b.sharpe
    assert a.probabilistic_sharpe == b.probabilistic_sharpe

    args = dict(strategy="S", owner="O", universe="U", period="P")
    assert render_backtest_report(a, **args) == render_backtest_report(b, **args)
