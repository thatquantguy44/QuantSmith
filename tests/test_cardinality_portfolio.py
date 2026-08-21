"""Acceptance tests for spec 0034 -- cardinality-constrained portfolio construction.

Each test is named for the acceptance criterion it covers (see
``specs/0034-cardinality-constrained-portfolio/tasks.md``).
"""

from __future__ import annotations

import math

import pytest

from quantsmith.pipelines.cardinality_portfolio import (
    cardinality_constrained_portfolio,
    select_cardinality_support,
)

ALPHA = [0.10, 0.08, 0.05, 0.03, 0.01]
COV = [
    [0.04, 0.01, 0.01, 0.00, 0.00],
    [0.01, 0.03, 0.01, 0.00, 0.00],
    [0.01, 0.01, 0.03, 0.01, 0.00],
    [0.00, 0.00, 0.01, 0.02, 0.00],
    [0.00, 0.00, 0.00, 0.00, 0.02],
]
TOL = 1e-6


# --- AC-001: at most max_names names are held ---


def test_selection_respects_max_names_AC_001():
    result = cardinality_constrained_portfolio(ALPHA, COV, max_names=2, upper=0.6)
    assert result.status == "optimal"
    nonzero = [w for w in result.weights if w > TOL]
    assert len(nonzero) <= 2
    assert len(result.selected) <= 2


# --- AC-002: unselected names are exactly zero ---


def test_unselected_weights_are_zero_AC_002():
    result = cardinality_constrained_portfolio(ALPHA, COV, max_names=2, upper=0.6)
    for i, w in enumerate(result.weights):
        if i not in result.selected:
            assert w == 0.0


# --- AC-003: min_weight_selected enforced in the final weights ---


def test_min_weight_selected_enforced_AC_003():
    result = cardinality_constrained_portfolio(
        ALPHA, COV, max_names=3, upper=0.6, min_weight_selected=0.15,
    )
    assert result.status == "optimal"
    for w in result.weights:
        assert w == 0.0 or w >= 0.15 - TOL


# --- AC-004: infeasible combinations are reported explicitly ---


def test_infeasible_reported_explicitly_AC_004():
    # max_names=1 with upper=0.6 cannot reach budget=1.0 -- no feasible selection.
    selection = select_cardinality_support(ALPHA, max_names=1, budget=1.0, upper=0.6)
    assert selection.status == "infeasible"
    assert selection.selected is None
    assert selection.objective is None

    result = cardinality_constrained_portfolio(ALPHA, COV, max_names=1, budget=1.0, upper=0.6)
    assert result.status == "infeasible"
    assert result.weights is None
    assert result.selected is None


# --- AC-005: a negative lower bound raises, naming the long-only restriction ---


def test_negative_lower_raises_AC_005():
    with pytest.raises(ValueError, match="long-only"):
        select_cardinality_support(ALPHA, max_names=2, lower=-0.1)
    with pytest.raises(ValueError, match="long-only"):
        cardinality_constrained_portfolio(ALPHA, COV, max_names=2, lower=-0.1)


# --- AC-006: deterministic ---


def test_deterministic_AC_006():
    r1 = cardinality_constrained_portfolio(ALPHA, COV, max_names=3, upper=0.6, min_weight_selected=0.1)
    r2 = cardinality_constrained_portfolio(ALPHA, COV, max_names=3, upper=0.6, min_weight_selected=0.1)
    assert r1.selected == r2.selected
    assert r1.weights == r2.weights


# --- AC-007: turnover penalty composition (0007's behavior is unmodified) ---


def test_turnover_penalty_composition_AC_007():
    prior = [0.5, 0.5, 0.0, 0.0, 0.0]

    def turnover(w):
        return sum(abs(wi - pi) for wi, pi in zip(w, prior))

    free = cardinality_constrained_portfolio(
        ALPHA, COV, max_names=2, upper=0.6, gamma=10.0, w_prev=prior, lambda_to=0.0,
    )
    sticky = cardinality_constrained_portfolio(
        ALPHA, COV, max_names=2, upper=0.6, gamma=10.0, w_prev=prior, lambda_to=50.0,
    )
    assert free.status == "optimal" and sticky.status == "optimal"
    assert turnover(sticky.weights) <= turnover(free.weights) + TOL
