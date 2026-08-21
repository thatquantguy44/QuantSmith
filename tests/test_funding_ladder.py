"""Acceptance tests for spec 0035 -- funding ladder min-cost flow.

Each test is named for the acceptance criterion it covers (see
``specs/0035-funding-ladder/tasks.md``).
"""

from __future__ import annotations

import math

from quantsmith.pipelines.funding_ladder import (
    FundingObligation,
    FundingTenor,
    solve_funding_ladder,
)

TOL = 1e-6

TENORS = [
    FundingTenor("overnight", tenor_days=1, capacity=50, rate=0.02),
    FundingTenor("1mo", tenor_days=30, capacity=100, rate=0.03),
    FundingTenor("3mo", tenor_days=90, capacity=200, rate=0.04),
]
OBLIGATIONS = [
    FundingObligation("payroll", horizon_days=1, notional=40),
    FundingObligation("vendor", horizon_days=20, notional=60),
    FundingObligation("quarterly", horizon_days=80, notional=100),
]


def allocated_to(result, obligation_name: str) -> float:
    return sum(v for (_, o), v in result.allocations.items() if o == obligation_name)


# --- AC-001: every obligation is fully funded ---


def test_every_obligation_fully_funded_AC_001():
    result = solve_funding_ladder(TENORS, OBLIGATIONS)
    assert result.status == "optimal"
    for obligation in OBLIGATIONS:
        assert math.isclose(allocated_to(result, obligation.name), obligation.notional, abs_tol=TOL)


# --- AC-002: an ineligible tenor (too short) is never used ---


def test_ineligible_tenor_never_used_AC_002():
    short_only = [FundingTenor("overnight", tenor_days=1, capacity=1000, rate=0.01)]
    far_obligation = [FundingObligation("far", horizon_days=30, notional=10)]
    result = solve_funding_ladder(short_only, far_obligation)
    assert result.status == "infeasible"

    # Mixed case: overnight is ineligible for the 20-day obligation, must not appear.
    mixed = [
        FundingTenor("overnight", tenor_days=1, capacity=1000, rate=0.001),
        FundingTenor("1mo", tenor_days=30, capacity=1000, rate=0.05),
    ]
    obligation = [FundingObligation("vendor", horizon_days=20, notional=10)]
    result2 = solve_funding_ladder(mixed, obligation)
    assert result2.status == "optimal"
    assert ("overnight", "vendor") not in result2.allocations
    assert result2.allocations[("1mo", "vendor")] == 10


# --- AC-003: a tenor's utilization never exceeds its capacity ---


def test_tenor_capacity_respected_AC_003():
    result = solve_funding_ladder(TENORS, OBLIGATIONS)
    assert result.status == "optimal"
    for tenor in TENORS:
        assert result.tenor_utilization[tenor.name] <= tenor.capacity + TOL


# --- AC-004: the cheaper eligible tenor is preferred ---


def test_cheaper_tenor_preferred_AC_004():
    tenors = [
        FundingTenor("1mo", tenor_days=30, capacity=100, rate=0.01),
        FundingTenor("3mo", tenor_days=90, capacity=100, rate=0.05),
    ]
    obligations = [FundingObligation("x", horizon_days=20, notional=50)]
    result = solve_funding_ladder(tenors, obligations)
    assert result.status == "optimal"
    assert result.allocations.get(("1mo", "x")) == 50
    assert ("3mo", "x") not in result.allocations


# --- AC-005: allocation breakdown and tenor utilization are both reported ---


def test_allocation_and_utilization_reported_AC_005():
    result = solve_funding_ladder(TENORS, OBLIGATIONS)
    assert result.status == "optimal"
    assert len(result.allocations) > 0
    assert set(result.tenor_utilization) == {t.name for t in TENORS}
    assert sum(result.allocations.values()) == sum(result.tenor_utilization.values())


# --- AC-006: infeasibility is reported explicitly, never a partial result ---


def test_infeasible_reported_explicitly_AC_006():
    tight_tenors = [FundingTenor("overnight", tenor_days=1, capacity=10, rate=0.02)]
    big_obligation = [FundingObligation("big", horizon_days=1, notional=100)]
    result = solve_funding_ladder(tight_tenors, big_obligation)
    assert result.status == "infeasible"
    assert result.allocations == {}
    assert result.tenor_utilization == {}


# --- AC-007: deterministic ---


def test_deterministic_AC_007():
    r1 = solve_funding_ladder(TENORS, OBLIGATIONS)
    r2 = solve_funding_ladder(TENORS, OBLIGATIONS)
    assert r1.allocations == r2.allocations
    assert r1.tenor_utilization == r2.tenor_utilization
    assert r1.total_cost == r2.total_cost
