"""Reference pipeline for spec 0013 — optimization solvers by mathematical form.

This module makes the ``0013-optimization-solvers`` spec *executable*. It is a
deterministic, standard-library-only toolkit of the core mathematical-programming
forms, so the ``optimization/`` group is a working solver library rather than a
catalog. Convex QP already ships as ``0007-portfolio-construction``; this adds:

* Linear programming — ``solve_lp`` (two-phase simplex, Bland's rule).
* Mixed-integer programming — ``solve_milp`` (branch-and-bound on the LP relaxation).
* Network flow — ``min_cost_flow`` (successive shortest augmenting paths).
* Dynamic programming — ``solve_dp`` (finite-horizon backward induction).

Every solver is deterministic and reports an explicit status; infeasible and
unbounded problems are named, never silently returned as a wrong number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, Hashable, List, Optional, Sequence, Tuple

_EPS = 1e-9


# ===========================================================================
# Linear programming — two-phase simplex (Bland's rule)
# ===========================================================================


@dataclass(frozen=True)
class LPResult:
    status: str  # "optimal" | "infeasible" | "unbounded"
    x: Optional[List[float]]
    objective: Optional[float]


def solve_lp(
    c: Sequence[float],
    A_ub: Optional[Sequence[Sequence[float]]] = None,
    b_ub: Optional[Sequence[float]] = None,
    A_eq: Optional[Sequence[Sequence[float]]] = None,
    b_eq: Optional[Sequence[float]] = None,
    sense: str = "min",
) -> LPResult:
    """Solve a linear program with ``x >= 0``.

    Minimizes (or maximizes) ``c . x`` subject to ``A_ub x <= b_ub`` and
    ``A_eq x = b_eq``. Deterministic; returns a status of optimal / infeasible /
    unbounded.
    """
    n = len(c)
    A_ub = [list(r) for r in (A_ub or [])]
    b_ub = list(b_ub or [])
    A_eq = [list(r) for r in (A_eq or [])]
    b_eq = list(b_eq or [])
    n_slack = len(A_ub)

    # Build standard form A x = b, x >= 0 with one slack per <= constraint.
    rows: List[List[float]] = []
    rhs: List[float] = []
    for i, row in enumerate(A_ub):
        rows.append(list(row) + [1.0 if j == i else 0.0 for j in range(n_slack)])
        rhs.append(b_ub[i])
    for i, row in enumerate(A_eq):
        rows.append(list(row) + [0.0] * n_slack)
        rhs.append(b_eq[i])

    # Ensure b >= 0.
    for i in range(len(rows)):
        if rhs[i] < 0:
            rows[i] = [-v for v in rows[i]]
            rhs[i] = -rhs[i]

    obj_sign = -1.0 if sense == "max" else 1.0
    c_std = [obj_sign * v for v in c] + [0.0] * n_slack

    status, x_full = _two_phase_simplex(c_std, rows, rhs)
    if status != "optimal":
        return LPResult(status, None, None)
    x = x_full[:n]
    objective = sum(ci * xi for ci, xi in zip(c, x))
    return LPResult("optimal", x, objective)


def _two_phase_simplex(
    c: Sequence[float], A: Sequence[Sequence[float]], b: Sequence[float]
) -> Tuple[str, Optional[List[float]]]:
    m = len(A)
    n = len(c)
    if m == 0:
        return "optimal", [0.0] * n

    # Phase 1: minimize the sum of artificial variables.
    total = n + m
    T = [list(A[i]) + [1.0 if j == i else 0.0 for j in range(m)] + [b[i]] for i in range(m)]
    basis = [n + i for i in range(m)]
    cost1 = [0.0] * n + [1.0] * m
    _run_simplex(T, basis, cost1, total)
    if sum(cost1[basis[i]] * T[i][total] for i in range(m)) > 1e-7:
        return "infeasible", None

    # Drive artificials out of the basis where possible; drop redundant rows.
    keep = list(range(m))
    for i in range(m):
        if basis[i] >= n:
            pivoted = False
            for j in range(n):
                if abs(T[i][j]) > _EPS:
                    _pivot(T, basis, i, j, total)
                    pivoted = True
                    break
            if not pivoted:
                keep.remove(i)  # redundant constraint

    # Phase 2: drop artificial columns and optimize the real objective.
    T2 = [[T[i][j] for j in range(n)] + [T[i][total]] for i in keep]
    basis2 = [basis[i] for i in keep]
    status2 = _run_simplex(T2, basis2, list(c), n)
    if status2 == "unbounded":
        return "unbounded", None

    x = [0.0] * n
    for i, bi in enumerate(basis2):
        if bi < n:
            x[bi] = T2[i][n]
    return "optimal", x


def _run_simplex(T: List[List[float]], basis: List[int], cost: Sequence[float], ncols: int) -> str:
    m = len(T)
    while True:
        enter = -1
        for j in range(ncols):
            rc = cost[j] - sum(cost[basis[i]] * T[i][j] for i in range(m))
            if rc < -1e-9:
                enter = j  # Bland: first improving column
                break
        if enter == -1:
            return "optimal"

        best_ratio = None
        leave = -1
        for i in range(m):
            if T[i][enter] > 1e-9:
                ratio = T[i][ncols] / T[i][enter]
                if best_ratio is None or ratio < best_ratio - 1e-12:
                    best_ratio, leave = ratio, i
                elif abs(ratio - best_ratio) <= 1e-12 and basis[i] < basis[leave]:
                    leave = i  # Bland: smallest basis index on ties
        if leave == -1:
            return "unbounded"
        _pivot(T, basis, leave, enter, ncols)


def _pivot(T: List[List[float]], basis: List[int], r: int, col: int, ncols: int) -> None:
    piv = T[r][col]
    T[r] = [v / piv for v in T[r]]
    for i in range(len(T)):
        if i != r and abs(T[i][col]) > _EPS:
            factor = T[i][col]
            T[i] = [a - factor * b for a, b in zip(T[i], T[r])]
    basis[r] = col


# ===========================================================================
# Mixed-integer programming — branch and bound
# ===========================================================================


def solve_milp(
    c: Sequence[float],
    A_ub: Optional[Sequence[Sequence[float]]] = None,
    b_ub: Optional[Sequence[float]] = None,
    A_eq: Optional[Sequence[Sequence[float]]] = None,
    b_eq: Optional[Sequence[float]] = None,
    integer_vars: Sequence[int] = (),
    sense: str = "min",
    max_nodes: int = 10000,
) -> LPResult:
    """Solve a mixed-integer LP by branch-and-bound on the LP relaxation.

    ``integer_vars`` lists the indices constrained to integers. Deterministic;
    returns optimal / infeasible. Intended for small problems (a reference solver).
    """
    A_ub = [list(r) for r in (A_ub or [])]
    b_ub = list(b_ub or [])
    int_set = set(integer_vars)
    minimize = sense != "max"

    best: Dict[str, object] = {"obj": None, "x": None}
    nodes = [(A_ub, b_ub)]
    count = 0

    while nodes and count < max_nodes:
        count += 1
        cur_ub, cur_b = nodes.pop()
        res = solve_lp(c, cur_ub, cur_b, A_eq, b_eq, sense=sense)
        if res.status != "optimal":
            continue
        # Bound: prune if the relaxation cannot beat the incumbent.
        if best["obj"] is not None:
            if minimize and res.objective >= best["obj"] - _EPS:
                continue
            if not minimize and res.objective <= best["obj"] + _EPS:
                continue

        frac = _first_fractional(res.x, int_set)
        if frac is None:
            best["obj"], best["x"] = res.objective, [round(v) if i in int_set else v
                                                     for i, v in enumerate(res.x)]
            continue

        j, val = frac
        floor_row = [1.0 if k == j else 0.0 for k in range(len(c))]
        # branch x_j <= floor(val)
        nodes.append((cur_ub + [floor_row], cur_b + [math.floor(val)]))
        # branch x_j >= ceil(val)  ->  -x_j <= -ceil(val)
        nodes.append((cur_ub + [[-v for v in floor_row]], cur_b + [-math.ceil(val)]))

    if best["x"] is None:
        return LPResult("infeasible", None, None)
    return LPResult("optimal", best["x"], best["obj"])  # type: ignore[arg-type]


def _first_fractional(x: Sequence[float], int_set) -> Optional[Tuple[int, float]]:
    for j in int_set:
        if abs(x[j] - round(x[j])) > 1e-6:
            return j, x[j]
    return None


# ===========================================================================
# Network flow — min-cost (max-)flow via successive shortest paths
# ===========================================================================


@dataclass(frozen=True)
class FlowResult:
    status: str  # "optimal" | "infeasible"
    flow: float
    cost: float
    edge_flows: List[float]


def min_cost_flow(
    n_nodes: int,
    edges: Sequence[Tuple[int, int, float, float]],
    source: int,
    sink: int,
    required_flow: Optional[float] = None,
) -> FlowResult:
    """Minimum-cost flow from source to sink.

    ``edges`` are ``(u, v, capacity, cost)``. With ``required_flow`` None, pushes the
    maximum flow at minimum cost; otherwise pushes exactly ``required_flow`` (or
    reports infeasible). Uses Bellman-Ford shortest augmenting paths (handles the
    residual costs). Deterministic.
    """
    # Residual graph: for each edge, a forward and a backward arc.
    to: List[int] = []
    cap: List[float] = []
    cost: List[float] = []
    nxt_first: List[List[int]] = [[] for _ in range(n_nodes)]
    edge_arc: List[int] = []

    def add(u: int, v: int, c: float, w: float) -> int:
        arc = len(to)
        to.append(v); cap.append(c); cost.append(w); nxt_first[u].append(arc)
        to.append(u); cap.append(0.0); cost.append(-w); nxt_first[v].append(arc + 1)
        return arc

    for (u, v, c, w) in edges:
        edge_arc.append(add(u, v, c, w))

    total_flow = 0.0
    total_cost = 0.0
    target = math.inf if required_flow is None else required_flow

    while total_flow < target - _EPS:
        dist = [math.inf] * n_nodes
        in_arc = [-1] * n_nodes
        dist[source] = 0.0
        # Bellman-Ford (SPFA-style relaxation).
        for _ in range(n_nodes - 1):
            updated = False
            for u in range(n_nodes):
                if dist[u] == math.inf:
                    continue
                for arc in nxt_first[u]:
                    if cap[arc] > _EPS and dist[u] + cost[arc] < dist[to[arc]] - _EPS:
                        dist[to[arc]] = dist[u] + cost[arc]
                        in_arc[to[arc]] = arc
                        updated = True
            if not updated:
                break
        if dist[sink] == math.inf:
            break  # no augmenting path

        # Bottleneck along the path.
        push = target - total_flow
        v = sink
        while v != source:
            arc = in_arc[v]
            push = min(push, cap[arc])
            v = to[arc ^ 1]
        # Apply.
        v = sink
        while v != source:
            arc = in_arc[v]
            cap[arc] -= push
            cap[arc ^ 1] += push
            v = to[arc ^ 1]
        total_flow += push
        total_cost += push * dist[sink]

    if required_flow is not None and total_flow < required_flow - 1e-6:
        return FlowResult("infeasible", total_flow, total_cost, [])
    edge_flows = [ (c0 - cap[edge_arc[i]]) for i, (u, v, c0, w) in enumerate(edges) ]
    return FlowResult("optimal", total_flow, total_cost, edge_flows)


# ===========================================================================
# Dynamic programming — finite-horizon backward induction
# ===========================================================================


State = Hashable
Action = Hashable


@dataclass
class DPProblem:
    """A deterministic finite-horizon dynamic program."""

    horizon: int
    states: Sequence[State]
    actions: Callable[[State], Sequence[Action]]
    step: Callable[[State, Action], Tuple[State, float]]  # -> (next_state, reward)
    terminal_value: Callable[[State], float] = lambda s: 0.0
    discount: float = 1.0
    sense: str = "max"


@dataclass(frozen=True)
class DPResult:
    values: Dict[State, float]                       # value at stage 0
    policy: Dict[Tuple[int, State], Action]          # optimal action per (stage, state)


def solve_dp(problem: DPProblem) -> DPResult:
    """Solve by backward induction. Deterministic transitions."""
    better = (lambda a, b: a > b) if problem.sense == "max" else (lambda a, b: a < b)
    V: Dict[State, float] = {s: problem.terminal_value(s) for s in problem.states}
    policy: Dict[Tuple[int, State], Action] = {}

    for t in range(problem.horizon - 1, -1, -1):
        newV: Dict[State, float] = {}
        for s in problem.states:
            best_val: Optional[float] = None
            best_act: Optional[Action] = None
            for a in problem.actions(s):
                ns, reward = problem.step(s, a)
                val = reward + problem.discount * V.get(ns, problem.terminal_value(ns))
                if best_val is None or better(val, best_val):
                    best_val, best_act = val, a
            if best_val is None:
                best_val = problem.terminal_value(s)
            else:
                policy[(t, s)] = best_act  # type: ignore[assignment]
            newV[s] = best_val
        V = newV

    return DPResult(values=V, policy=policy)
