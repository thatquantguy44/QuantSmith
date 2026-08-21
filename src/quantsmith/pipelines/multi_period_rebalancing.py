"""Reference pipeline for spec 0036 — multi-period rebalancing (dynamic programming).

Composes an already-shipped, dependency-free solver instead of inventing a new
one: ``solve_dp`` (``optimization_solvers.py``, spec 0013) solves the sequential
decision of trading a single discretized position toward a target over a finite
horizon, trading off transaction cost (per unit traded) against tracking-error
cost (per unit away from target) each period. ``optimization_solvers.py`` is not
modified.

This is deliberately a **single discretized position dimension**, not a general
multi-asset rebalancing problem -- ``solve_dp`` requires an enumerable, hashable
state space, which a continuous multi-asset weight vector is not. See spec 0036's
Non-Goals. Unlike ``0034``/``0035``, there is no "infeasible" outcome here: "stay
put" (zero trade) is always a valid action, so a well-formed problem always has a
defined optimal policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from .optimization_solvers import DPProblem, solve_dp


@dataclass(frozen=True)
class RebalancingPlan:
    position_path: List[float]   # position after each period, length == horizon
    trades: List[float]           # trade taken each period, length == horizon
    total_cost: float


def solve_multi_period_rebalancing(
    grid: Sequence[float],
    start_position: float,
    target: float,
    horizon: int,
    max_trade: float,
    transaction_cost_per_unit: float,
    tracking_cost_per_unit: float,
    discount: float = 1.0,
) -> RebalancingPlan:
    """Trade a position toward ``target`` over ``horizon`` periods at minimum cost.

    ``grid`` is the set of position levels the state can take; ``start_position``
    and ``target`` must both be in ``grid``. At each period the position may move
    to any grid point within ``max_trade`` of its current value (enforced by
    action-set construction, not a post-hoc check) — "stay put" is always
    available. Per-period cost is ``transaction_cost_per_unit * |trade| +
    tracking_cost_per_unit * |position - target|``; the terminal period adds one
    more tracking-error charge for ending away from target. Deterministic.
    """
    grid = list(grid)
    if start_position not in grid:
        raise ValueError("start_position must be a value in grid")
    if target not in grid:
        raise ValueError("target must be a value in grid")
    if horizon <= 0:
        raise ValueError("horizon must be positive")
    if max_trade < 0:
        raise ValueError("max_trade must be >= 0")

    def actions(state: float) -> List[float]:
        return [g for g in grid if abs(g - state) <= max_trade]

    def step(state: float, next_position: float):
        cost = (
            transaction_cost_per_unit * abs(next_position - state)
            + tracking_cost_per_unit * abs(next_position - target)
        )
        return next_position, cost

    def terminal_value(state: float) -> float:
        return tracking_cost_per_unit * abs(state - target)

    problem = DPProblem(
        horizon=horizon,
        states=grid,
        actions=actions,
        step=step,
        terminal_value=terminal_value,
        discount=discount,
        sense="min",
    )
    result = solve_dp(problem)

    position_path: List[float] = []
    trades: List[float] = []
    state = start_position
    for t in range(horizon):
        next_position = result.policy.get((t, state), state)
        trades.append(next_position - state)
        state = next_position
        position_path.append(state)

    return RebalancingPlan(
        position_path=position_path,
        trades=trades,
        total_cost=result.values[start_position],
    )
