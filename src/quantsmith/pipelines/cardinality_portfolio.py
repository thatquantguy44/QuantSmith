"""Reference pipeline for spec 0034 — cardinality-constrained portfolio construction.

Composes two already-shipped, dependency-free solvers instead of inventing a third:

* ``solve_milp`` (``optimization_solvers.py``, spec 0013) selects *which* names to
  hold — at most ``max_names``, maximizing linear expected return.
* ``solve_portfolio`` (``portfolio_construction.py``, spec 0007) sizes *how much* to
  hold in each selected name, by mean-variance QP on the reduced dimension.

This is a **documented two-stage heuristic**, not a joint mixed-integer *quadratic*
program (MIQP) solve — true cardinality-constrained mean-variance optimization is
NP-hard and out of scope for a dependency-free reference solver (see spec 0034's
Non-Goals and RISK-001). Neither ``optimization_solvers.py`` nor
``portfolio_construction.py`` is modified; this module only calls both.

Long-only only: both underlying solvers assume ``x >= 0``, so a negative ``lower``
bound raises rather than being silently ignored.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from .optimization_solvers import solve_milp
from .portfolio_construction import ConstraintSet, solve_portfolio

Vector = Sequence[float]
Matrix = Sequence[Sequence[float]]


def _validate_long_only(lower: float) -> None:
    if lower < 0:
        raise ValueError(
            "cardinality_portfolio is long-only; lower must be >= 0 "
            "(short positions are not supported -- see spec 0034 Non-Goals)"
        )


# ---------------------------------------------------------------------------
# Stage 1 — selection (MILP, linear objective) — REQ-001, REQ-003, REQ-004, REQ-005
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CardinalitySelection:
    status: str  # "optimal" | "infeasible" | "unbounded"
    selected: Optional[Tuple[int, ...]]
    objective: Optional[float]


def select_cardinality_support(
    alpha: Vector,
    max_names: int,
    budget: float = 1.0,
    lower: float = 0.0,
    upper: float = 1.0,
    min_weight_selected: float = 0.0,
) -> CardinalitySelection:
    """Select at most ``max_names`` names by maximizing linear expected return.

    Solves a MILP over variables ``[w_0..w_{n-1}, z_0..z_{n-1}]``: maximize
    ``alpha . w`` subject to ``sum(w) = budget``, ``0 <= w_i <= upper * z_i``,
    ``min_weight_selected * z_i <= w_i`` (when ``min_weight_selected > 0``),
    ``z_i in {0, 1}``, and ``sum(z) <= max_names``. Deterministic; returns
    ``status="infeasible"`` (never a wrong number) when no feasible selection
    exists — e.g. ``max_names`` too small to reach ``budget`` given ``upper``.
    """
    _validate_long_only(lower)
    n = len(alpha)
    if n == 0:
        raise ValueError("alpha must be non-empty")
    if max_names <= 0:
        raise ValueError("max_names must be positive")
    if min_weight_selected < 0:
        raise ValueError("min_weight_selected must be >= 0")

    nv = 2 * n
    # Minimize -alpha.w (== maximize alpha.w); z has no objective cost.
    c = [-a for a in alpha] + [0.0] * n

    A_ub: List[List[float]] = []
    b_ub: List[float] = []

    for i in range(n):
        row = [0.0] * nv
        row[i] = 1.0
        row[n + i] = -upper
        A_ub.append(row)
        b_ub.append(0.0)

    if min_weight_selected > 0:
        for i in range(n):
            row = [0.0] * nv
            row[i] = -1.0
            row[n + i] = min_weight_selected
            A_ub.append(row)
            b_ub.append(0.0)

    for i in range(n):
        row = [0.0] * nv
        row[n + i] = 1.0
        A_ub.append(row)
        b_ub.append(1.0)

    cardinality_row = [0.0] * n + [1.0] * n
    A_ub.append(cardinality_row)
    b_ub.append(float(max_names))

    A_eq = [[1.0] * n + [0.0] * n]
    b_eq = [budget]

    integer_vars = list(range(n, nv))
    result = solve_milp(c, A_ub, b_ub, A_eq, b_eq, integer_vars=integer_vars, sense="min")

    if result.status != "optimal":
        return CardinalitySelection(status=result.status, selected=None, objective=None)

    w = result.x[:n]
    z = result.x[n:]
    selected = tuple(sorted(i for i in range(n) if z[i] > 0.5))
    objective = sum(alpha[i] * w[i] for i in range(n))
    return CardinalitySelection(status="optimal", selected=selected, objective=objective)


# ---------------------------------------------------------------------------
# Stage 2 — sizing (QP on the reduced support) — REQ-002, REQ-003, REQ-004, REQ-005
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CardinalityPortfolioResult:
    status: str  # "optimal" | "infeasible" | "unbounded"
    weights: Optional[List[float]]
    selected: Optional[Tuple[int, ...]]
    selection_objective: Optional[float]


def cardinality_constrained_portfolio(
    alpha: Vector,
    cov: Matrix,
    max_names: int,
    budget: float = 1.0,
    lower: float = 0.0,
    upper: float = 1.0,
    min_weight_selected: float = 0.0,
    gross_cap: Optional[float] = None,
    gamma: float = 5.0,
    w_prev: Optional[Vector] = None,
    lambda_to: float = 0.0,
) -> CardinalityPortfolioResult:
    """Select at most ``max_names`` names, then size them by mean-variance QP.

    Stage 1 (``select_cardinality_support``) picks the support. Stage 2 calls
    ``solve_portfolio`` (spec 0007, unmodified) on the reduced-dimension support,
    with ``ConstraintSet.lower`` set to ``min_weight_selected`` so the floor holds
    end to end, not just in the selection stage (RISK-003). Unselected names get
    an exact ``0.0`` in the reconstructed full-length weight vector. Propagates
    ``"infeasible"`` from either stage rather than raising or returning a wrong
    result.
    """
    _validate_long_only(lower)
    n = len(alpha)
    if len(cov) != n or any(len(row) != n for row in cov):
        raise ValueError("cov must be an n x n matrix matching alpha's length")
    if w_prev is not None and len(w_prev) != n:
        raise ValueError("w_prev length must match alpha's length")

    selection = select_cardinality_support(
        alpha, max_names, budget=budget, lower=lower, upper=upper,
        min_weight_selected=min_weight_selected,
    )
    if selection.status != "optimal":
        return CardinalityPortfolioResult(
            status=selection.status, weights=None, selected=None, selection_objective=None,
        )

    selected = selection.selected
    alpha_s = [alpha[i] for i in selected]
    cov_s = [[cov[i][j] for j in selected] for i in selected]
    w_prev_s = [w_prev[i] for i in selected] if w_prev is not None else None
    reduced_lower = min_weight_selected if min_weight_selected > 0 else lower
    constraints_s = ConstraintSet(
        n=len(selected), budget=budget, lower=reduced_lower, upper=upper,
        gross_cap=gross_cap if gross_cap is not None else budget,
    )
    w_s = solve_portfolio(alpha_s, cov_s, constraints_s, gamma=gamma, w_prev=w_prev_s, lambda_to=lambda_to)

    full = [0.0] * n
    for idx, val in zip(selected, w_s):
        full[idx] = val

    return CardinalityPortfolioResult(
        status="optimal", weights=full, selected=selected,
        selection_objective=selection.objective,
    )
