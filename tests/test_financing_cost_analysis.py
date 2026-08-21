"""Acceptance tests for spec 0028 — financing cost analysis.

Each test is named for the acceptance criterion it covers (see
``specs/0028-financing-cost-analysis/tasks.md``). Standard-library only.
"""

from __future__ import annotations

import pytest

from quantsmith.pipelines.financing_cost_analysis import (
    CapacityFinding,
    FinancedPosition,
    FinancingLeg,
    capacity_limit,
    check_point_in_time,
    decompose,
    financing_aware_returns,
    flag_understated_backtest,
    position_from_borrow_rate,
    spread_sensitivity,
)


def _position(**overrides):
    defaults = dict(
        position_id="p1",
        side="short",
        notional=1_000_000.0,
        period_start="2026-07-01",
        period_end="2026-07-31",  # 30 days
        legs=(
            FinancingLeg(kind="borrow_fee", rate_bps=250.0, rate_asof="2026-06-30"),
            FinancingLeg(kind="rebate", rate_bps=50.0, rate_asof="2026-06-30"),
        ),
        classification="HTB",
    )
    defaults.update(overrides)
    return FinancedPosition(**defaults)


# --- AC-001: per-leg cost-of-carry decomposition, explicit ACT/360 day-count ---


def test_decompose_all_legs_AC_001():
    pos = _position(
        legs=(
            FinancingLeg(kind="borrow_fee", rate_bps=250.0, rate_asof="2026-06-30"),
            FinancingLeg(kind="rebate", rate_bps=50.0, rate_asof="2026-06-30"),
            FinancingLeg(kind="funding", rate_bps=40.0, rate_asof="2026-06-30"),
            FinancingLeg(kind="margin", rate_bps=10.0, rate_asof="2026-06-30"),
        )
    )
    [d] = decompose([pos])

    assert d.days == 30
    # notional * rate/10000 * days/360, hand-computed
    assert d.borrow_fee_cost == pytest.approx(1_000_000.0 * 0.025 * 30 / 360)
    assert d.rebate_income == pytest.approx(1_000_000.0 * 0.005 * 30 / 360)
    assert d.funding_cost == pytest.approx(1_000_000.0 * 0.0040 * 30 / 360)
    assert d.margin_cost == pytest.approx(1_000_000.0 * 0.0010 * 30 / 360)
    assert d.net_financing_cost == pytest.approx(
        d.borrow_fee_cost - d.rebate_income + d.funding_cost + d.margin_cost
    )
    assert d.net_financing_cost > 0  # borrow fee dominates the small rebate/funding/margin


def test_position_validation_rejects_bad_side_and_notional_AC_001():
    with pytest.raises(ValueError):
        _position(side="sideways")
    with pytest.raises(ValueError):
        _position(notional=0.0)
    with pytest.raises(ValueError):
        FinancingLeg(kind="not-a-leg", rate_bps=10.0, rate_asof="2026-06-30")


# --- AC-002: financing-aware returns, gross vs net, drag reported ---


def test_financing_aware_returns_reports_drag_AC_002():
    pos = _position()
    [d] = decompose([pos])
    result = financing_aware_returns(gross_return=50_000.0, decompositions=[d])

    assert result.gross_return == 50_000.0
    assert result.financing_cost == pytest.approx(d.net_financing_cost)
    assert result.net_return == pytest.approx(50_000.0 - d.net_financing_cost)
    assert result.drag == pytest.approx(d.net_financing_cost)


# --- AC-003: flag a backtest that understates the computed financing cost ---


def test_flag_understated_backtest_AC_003():
    pos = _position()
    [d] = decompose([pos])

    understated = flag_understated_backtest(reported_cost=0.0, computed_cost=d.net_financing_cost)
    assert len(understated) == 1
    assert "understated" in understated[0]

    # A backtest that already reports at or above the computed cost is not flagged.
    honest = flag_understated_backtest(
        reported_cost=d.net_financing_cost, computed_cost=d.net_financing_cost
    )
    assert honest == []
    generous = flag_understated_backtest(
        reported_cost=d.net_financing_cost * 2, computed_cost=d.net_financing_cost
    )
    assert generous == []


# --- AC-004: financing-spread sensitivity to a uniform rate shock ---


def test_spread_sensitivity_is_monotonic_in_shock_AC_004():
    pos = _position()  # borrow_fee + rebate legs only; shock moves borrow_fee, not rebate
    result = spread_sensitivity([pos], shocks_bps=(-100.0, -50.0, 0.0, 50.0, 100.0))

    shocks = sorted(result)
    costs = [result[s] for s in shocks]
    assert costs == sorted(costs)  # monotonically increasing as the shock rises
    assert result[0.0] == pytest.approx(decompose([pos])[0].net_financing_cost)

    # A large negative shock cannot push the borrow leg below zero (clamped).
    extreme = spread_sensitivity([pos], shocks_bps=(-10_000.0,))
    assert extreme[-10_000.0] >= -decompose([pos])[0].rebate_income - 1e-9


# --- AC-005: capacity findings keyed by borrow classification ---


def test_capacity_limit_flags_constrained_classification_AC_005():
    htb = _position(position_id="p-htb", classification="HTB", notional=1_000_000.0)
    gc = _position(position_id="p-gc", classification="GC", notional=200_000.0)

    findings = capacity_limit([htb, gc], available_notional_by_classification={"HTB": 500_000.0})
    by_class = {f.classification: f for f in findings}

    assert by_class["HTB"].constrained is True
    assert by_class["HTB"].requested_notional == 1_000_000.0
    assert by_class["HTB"].available_notional == 500_000.0
    # GC has no configured cap -> unlimited -> not constrained.
    assert by_class["GC"].constrained is False

    # A long position never contributes to short-borrow capacity.
    long_pos = _position(position_id="p-long", side="long", classification=None, legs=(
        FinancingLeg(kind="funding", rate_bps=40.0, rate_asof="2026-06-30"),
    ))
    findings_with_long = capacity_limit([htb, long_pos], available_notional_by_classification={})
    assert len(findings_with_long) == 1  # only the short HTB position is keyed


# --- AC-006: point-in-time check flags a look-ahead financing rate ---


def test_check_point_in_time_flags_lookahead_AC_006():
    clean = _position()
    assert check_point_in_time([clean]) == []

    lookahead = _position(
        legs=(FinancingLeg(kind="borrow_fee", rate_bps=250.0, rate_asof="2026-08-15"),)
    )
    findings = check_point_in_time([lookahead])
    assert len(findings) == 1
    assert "look-ahead" in findings[0]


# --- Reconciliation with the securities-lending runtime's vocabulary (0023) ---


def test_position_from_borrow_rate_reconciles_with_sec_lending_AC_001():
    pos = position_from_borrow_rate(
        position_id="sec-lend-1",
        rate_bps=250.0,
        classification="HTB",
        notional=1_000_000.0,
        period_start="2026-07-01",
        period_end="2026-07-31",
        rate_asof="2026-06-30",
        rebate_rate_bps=50.0,
    )
    assert pos.side == "short"
    assert pos.classification == "HTB"
    [d] = decompose([pos])
    assert d.net_financing_cost > 0
