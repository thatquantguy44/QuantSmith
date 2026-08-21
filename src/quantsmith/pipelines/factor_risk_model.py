"""Reference pipeline for spec 0038 — factor risk model.

A standard Barra-style factor risk decomposition, dependency-free (plain
``Sequence[Sequence[float]]`` matrices, the same vocabulary
``portfolio_construction.py`` already uses). Given an already-estimated factor
exposure matrix and factor covariance (this module does not estimate a factor
model, it consumes one — the same scope boundary ``portfolio_construction.py``
draws around its own covariance matrix input), it decomposes portfolio variance
into factor and specific risk, attributes that risk back to assets and factors
via an Euler decomposition (the parts always sum exactly to the total, by
construction), measures risk concentration, and estimates a linear, first-order
stress loss under a supplied factor shock.

``stress_loss`` is a **linear approximation**, not a full repricing — stated
here and in every place this module is documented, never implied otherwise.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence, Tuple

Vector = Sequence[float]
Matrix = Sequence[Sequence[float]]


def _validate_dims(weights: Vector, exposures: Matrix, factor_cov: Matrix, specific_var: Vector) -> Tuple[int, int]:
    n = len(weights)
    if len(specific_var) != n:
        raise ValueError(f"specific_var length ({len(specific_var)}) must match weights length ({n})")
    if len(exposures) != n:
        raise ValueError(f"exposures must have {n} rows (one per asset), got {len(exposures)}")
    k = len(exposures[0]) if n else 0
    if any(len(row) != k for row in exposures):
        raise ValueError("exposures rows must all have the same number of factor columns")
    if len(factor_cov) != k or any(len(row) != k for row in factor_cov):
        raise ValueError(f"factor_cov must be {k} x {k} to match exposures' factor columns")
    return n, k


def _matT_vec(matrix: Matrix, vector: Vector, n: int, k: int) -> List[float]:
    """``matrix^T . vector`` -- matrix is n x k, vector is length n, result is length k."""
    return [sum(matrix[i][j] * vector[i] for i in range(n)) for j in range(k)]


def _mat_vec(matrix: Matrix, vector: Vector) -> List[float]:
    return [sum(row[j] * vector[j] for j in range(len(vector))) for row in matrix]


def _dot(a: Vector, b: Vector) -> float:
    return sum(ai * bi for ai, bi in zip(a, b))


def _portfolio_factor_exposure(weights: Vector, exposures: Matrix, n: int, k: int) -> List[float]:
    return _matT_vec(exposures, weights, n, k)


@dataclass(frozen=True)
class VarianceDecomposition:
    total_variance: float
    factor_variance: float
    specific_variance: float


def decompose_variance(
    weights: Vector,
    exposures: Matrix,
    factor_cov: Matrix,
    specific_var: Vector,
) -> VarianceDecomposition:
    """Decompose total portfolio variance into factor and specific risk.

    ``factor_variance + specific_variance == total_variance`` exactly (within
    floating-point tolerance), by construction. Deterministic.
    """
    n, k = _validate_dims(weights, exposures, factor_cov, specific_var)
    f = _portfolio_factor_exposure(weights, exposures, n, k)
    factor_variance = _dot(f, _mat_vec(factor_cov, f)) if k else 0.0
    specific_variance = sum(w * w * sv for w, sv in zip(weights, specific_var))
    return VarianceDecomposition(
        total_variance=factor_variance + specific_variance,
        factor_variance=factor_variance,
        specific_variance=specific_variance,
    )


@dataclass(frozen=True)
class RiskContributions:
    asset_contributions: List[float]     # sums to sqrt(total_variance)
    factor_contributions: List[float]    # sums to factor_variance
    total_volatility: float


def marginal_contribution_to_risk(
    weights: Vector,
    exposures: Matrix,
    factor_cov: Matrix,
    specific_var: Vector,
) -> RiskContributions:
    """Attribute portfolio risk to assets and factors via Euler decomposition.

    ``sum(asset_contributions) == sqrt(total_variance)`` and
    ``sum(factor_contributions) == factor_variance``, both exactly (within
    tolerance) -- the Euler identity for a quadratic form guarantees this, it
    is not a separate check bolted on afterward. Deterministic.
    """
    n, k = _validate_dims(weights, exposures, factor_cov, specific_var)
    f = _portfolio_factor_exposure(weights, exposures, n, k)
    f_cov_f = _mat_vec(factor_cov, f) if k else [0.0] * k
    factor_variance = _dot(f, f_cov_f) if k else 0.0
    specific_variance = sum(w * w * sv for w, sv in zip(weights, specific_var))
    total_variance = factor_variance + specific_variance
    total_volatility = math.sqrt(total_variance) if total_variance > 0 else 0.0

    # Sigma . w = exposures . (factor_cov . f) + specific_var (elementwise) * weights
    exposures_f_cov_f = _mat_vec(exposures, f_cov_f) if k else [0.0] * n
    sigma_w = [exposures_f_cov_f[i] + specific_var[i] * weights[i] for i in range(n)]

    if total_volatility > 0:
        asset_contributions = [weights[i] * sigma_w[i] / total_volatility for i in range(n)]
    else:
        asset_contributions = [0.0] * n

    factor_contributions = [f[j] * f_cov_f[j] for j in range(k)]

    return RiskContributions(
        asset_contributions=asset_contributions,
        factor_contributions=factor_contributions,
        total_volatility=total_volatility,
    )


def risk_concentration(contributions: Sequence[float]) -> float:
    """Effective number of bets: ``1 / sum(share_i^2)`` where shares sum to 1.

    Higher is more diversified; lower is more concentrated. Returns ``0.0``
    for an empty or all-zero contribution set (nothing to concentrate).
    """
    total = sum(contributions)
    if not contributions or total == 0:
        return 0.0
    shares = [c / total for c in contributions]
    herfindahl = sum(s * s for s in shares)
    return 1.0 / herfindahl if herfindahl > 0 else 0.0


def stress_loss(weights: Vector, exposures: Matrix, factor_shock: Vector) -> float:
    """Estimate portfolio P&L under a factor shock via the linear factor model.

    ``loss = (exposures^T . weights) . factor_shock`` -- a **linear, first-order
    approximation**, not a full repricing under the shock. Deterministic and
    linear in ``factor_shock`` (scaling the shock scales the estimate by the
    same factor).
    """
    n = len(weights)
    if len(exposures) != n:
        raise ValueError(f"exposures must have {n} rows (one per asset), got {len(exposures)}")
    k = len(exposures[0]) if n else 0
    if any(len(row) != k for row in exposures):
        raise ValueError("exposures rows must all have the same number of factor columns")
    if len(factor_shock) != k:
        raise ValueError(f"factor_shock length ({len(factor_shock)}) must match exposures' factor columns ({k})")

    f = _portfolio_factor_exposure(weights, exposures, n, k)
    return _dot(f, factor_shock)
