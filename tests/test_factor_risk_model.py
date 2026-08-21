"""Acceptance tests for spec 0038 -- factor risk model.

Each test is named for the acceptance criterion it covers (see
``specs/0038-factor-risk-model/tasks.md``).
"""

from __future__ import annotations

import math

import pytest

from quantsmith.pipelines.factor_risk_model import (
    decompose_variance,
    marginal_contribution_to_risk,
    risk_concentration,
    stress_loss,
)

TOL = 1e-9

WEIGHTS = [0.4, 0.3, 0.3]
EXPOSURES = [
    [1.0, 0.2],
    [0.8, -0.1],
    [0.5, 0.5],
]
FACTOR_COV = [
    [0.04, 0.005],
    [0.005, 0.02],
]
SPECIFIC_VAR = [0.01, 0.015, 0.02]


# --- AC-001: variance decomposition sums exactly ---


def test_variance_decomposition_sums_exactly_AC_001():
    decomp = decompose_variance(WEIGHTS, EXPOSURES, FACTOR_COV, SPECIFIC_VAR)
    assert math.isclose(
        decomp.factor_variance + decomp.specific_variance, decomp.total_variance, abs_tol=TOL,
    )
    assert decomp.total_variance > 0


# --- AC-002: risk contributions sum exactly ---


def test_risk_contributions_sum_exactly_AC_002():
    decomp = decompose_variance(WEIGHTS, EXPOSURES, FACTOR_COV, SPECIFIC_VAR)
    mctr = marginal_contribution_to_risk(WEIGHTS, EXPOSURES, FACTOR_COV, SPECIFIC_VAR)
    assert math.isclose(sum(mctr.asset_contributions), mctr.total_volatility, abs_tol=TOL)
    assert math.isclose(sum(mctr.factor_contributions), decomp.factor_variance, abs_tol=TOL)


# --- AC-003: concentration reflects dispersion ---


def test_concentration_reflects_dispersion_AC_003():
    concentrated = risk_concentration([0.9, 0.05, 0.05])
    diversified = risk_concentration([0.34, 0.33, 0.33])
    assert concentrated < diversified
    # Equal contributions -> effective number of bets equals the count.
    equal = risk_concentration([0.25, 0.25, 0.25, 0.25])
    assert math.isclose(equal, 4.0, abs_tol=TOL)


# --- AC-004: stress loss is linear in the shock ---


def test_stress_loss_linear_AC_004():
    shock = [0.02, -0.01]
    loss = stress_loss(WEIGHTS, EXPOSURES, shock)
    scaled_loss = stress_loss(WEIGHTS, EXPOSURES, [3 * s for s in shock])
    assert math.isclose(scaled_loss, 3 * loss, abs_tol=TOL)


# --- AC-005: dimension mismatch raises ---


def test_dimension_mismatch_raises_AC_005():
    with pytest.raises(ValueError, match="specific_var"):
        decompose_variance([0.5, 0.5], EXPOSURES, FACTOR_COV, SPECIFIC_VAR)
    with pytest.raises(ValueError, match="exposures"):
        marginal_contribution_to_risk(WEIGHTS, EXPOSURES[:2], FACTOR_COV, SPECIFIC_VAR)
    with pytest.raises(ValueError, match="factor_cov"):
        decompose_variance(WEIGHTS, EXPOSURES, [[0.04]], SPECIFIC_VAR)
    with pytest.raises(ValueError, match="factor_shock"):
        stress_loss(WEIGHTS, EXPOSURES, [0.02])


# --- AC-006: deterministic ---


def test_deterministic_AC_006():
    d1 = decompose_variance(WEIGHTS, EXPOSURES, FACTOR_COV, SPECIFIC_VAR)
    d2 = decompose_variance(WEIGHTS, EXPOSURES, FACTOR_COV, SPECIFIC_VAR)
    assert d1 == d2

    m1 = marginal_contribution_to_risk(WEIGHTS, EXPOSURES, FACTOR_COV, SPECIFIC_VAR)
    m2 = marginal_contribution_to_risk(WEIGHTS, EXPOSURES, FACTOR_COV, SPECIFIC_VAR)
    assert m1 == m2

    assert stress_loss(WEIGHTS, EXPOSURES, [0.02, -0.01]) == stress_loss(WEIGHTS, EXPOSURES, [0.02, -0.01])
