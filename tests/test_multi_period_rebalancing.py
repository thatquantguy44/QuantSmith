"""Acceptance tests for spec 0036 -- multi-period rebalancing (dynamic programming).

Each test is named for the acceptance criterion it covers (see
``specs/0036-multi-period-rebalancing/tasks.md``).
"""

from __future__ import annotations

import math

from quantsmith.pipelines.multi_period_rebalancing import solve_multi_period_rebalancing

TOL = 1e-6
GRID = [0.0, 0.25, 0.5, 0.75, 1.0]


def realized_cost(plan, start, target, transaction_cost_per_unit, tracking_cost_per_unit):
    total = 0.0
    state = start
    for trade, pos in zip(plan.trades, plan.position_path):
        total += transaction_cost_per_unit * abs(trade) + tracking_cost_per_unit * abs(pos - target)
        state = pos
    total += tracking_cost_per_unit * abs(state - target)
    return total


# --- AC-001: costless trading moves immediately to target and stays ---


def test_immediate_move_to_target_when_free_AC_001():
    plan = solve_multi_period_rebalancing(
        GRID, start_position=0.0, target=1.0, horizon=3, max_trade=1.0,
        transaction_cost_per_unit=0.0, tracking_cost_per_unit=1.0,
    )
    assert plan.position_path[0] == 1.0
    assert all(p == 1.0 for p in plan.position_path)


# --- AC-002: prohibitively expensive trading never trades ---


def test_no_trade_when_prohibitively_expensive_AC_002():
    plan = solve_multi_period_rebalancing(
        GRID, start_position=0.0, target=1.0, horizon=3, max_trade=1.0,
        transaction_cost_per_unit=1000.0, tracking_cost_per_unit=1.0,
    )
    assert all(t == 0.0 for t in plan.trades)
    assert all(p == 0.0 for p in plan.position_path)


# --- AC-003 / AC-004: capped trade size reaches target over multiple periods ---


def test_multi_period_path_to_target_AC_003():
    plan = solve_multi_period_rebalancing(
        GRID, start_position=0.0, target=1.0, horizon=4, max_trade=0.25,
        transaction_cost_per_unit=0.01, tracking_cost_per_unit=1.0,
    )
    assert plan.position_path[-1] == 1.0
    assert plan.position_path != [1.0] * 4  # took more than one period


def test_max_trade_never_exceeded_AC_004():
    plan = solve_multi_period_rebalancing(
        GRID, start_position=0.0, target=1.0, horizon=4, max_trade=0.25,
        transaction_cost_per_unit=0.01, tracking_cost_per_unit=1.0,
    )
    for trade in plan.trades:
        assert abs(trade) <= 0.25 + TOL


# --- AC-005: reported total cost matches the realized path cost ---


def test_total_cost_matches_realized_path_cost_AC_005():
    plan = solve_multi_period_rebalancing(
        GRID, start_position=0.0, target=0.75, horizon=3, max_trade=0.5,
        transaction_cost_per_unit=0.05, tracking_cost_per_unit=0.2,
    )
    expected = realized_cost(plan, 0.0, 0.75, 0.05, 0.2)
    assert math.isclose(plan.total_cost, expected, abs_tol=TOL)


# --- AC-006: deterministic ---


def test_deterministic_AC_006():
    kwargs = dict(
        grid=GRID, start_position=0.0, target=0.75, horizon=3, max_trade=0.5,
        transaction_cost_per_unit=0.05, tracking_cost_per_unit=0.2,
    )
    p1 = solve_multi_period_rebalancing(**kwargs)
    p2 = solve_multi_period_rebalancing(**kwargs)
    assert p1.position_path == p2.position_path
    assert p1.trades == p2.trades
    assert p1.total_cost == p2.total_cost
