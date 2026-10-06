"""Checks for optimisation solvers (spec 0098).

``kkt_check`` certifies a candidate solution: it measures primal feasibility, recovers (or accepts) the
Lagrange multipliers, and measures stationarity, multiplier signs and complementary slackness. For a
convex problem, satisfying KKT means the point is globally optimal; for a non-convex one it only means a
stationary point. ``check_solver_on_instances`` runs a solver on seeded convex LPs/QPs whose optimum is
known by construction (``generators.convex_instance``) and applies four checks: known optimum, KKT of the
returned point, objective scaling, and constraint relaxation.

Only ``numpy`` is used. Multipliers come from an own non-negative least squares (Lawson-Hanson).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from ._compare import to_jsonable
from ._guard import RETURNED, call_guarded, describe_error
from .generators import ConvexInstance, convex_instance, rng_for

KKT_LIMITS = ("KKT certifies a global optimum only for convex problems (affine constraints and a convex objective); otherwise it shows a stationary point. "
              "Recovered multipliers assume the active set is {g >= -tol_active}; a degenerate point can fail with an unlucky tolerance.")
RUNNER_LIMITS = ("Constructed instances are convex, bounded, feasible and non-degenerate with a known optimum; a solver that passes may still fail "
                 "infeasible, unbounded, degenerate or badly scaled problems. Failures reproduce from instance_seed.")


def nonneg_least_squares(A: np.ndarray, b: np.ndarray, max_iter: int | None = None) -> tuple[np.ndarray, float, bool]:
    """Minimise ``||A x - b||`` subject to ``x >= 0`` (Lawson-Hanson). Returns ``(x, residual_norm, converged)``."""
    A, b = np.asarray(A, dtype=float), np.asarray(b, dtype=float)
    m, n = A.shape
    x = np.zeros(n)
    if n == 0:
        return x, float(np.linalg.norm(b)), True
    passive = np.zeros(n, dtype=bool)
    tol = 10 * np.finfo(float).eps * max(m, n) * max(np.abs(A).sum(axis=0).max(), 1.0)
    max_iter = max_iter or 30 * n
    w = A.T @ (b - A @ x)
    it = 0
    while (~passive).any() and w[~passive].max() > tol:
        it += 1
        if it > max_iter:
            return x, float(np.linalg.norm(A @ x - b)), False
        j = int(np.argmax(np.where(passive, -np.inf, w)))
        passive[j] = True
        s = np.zeros(n)
        s[passive] = np.linalg.lstsq(A[:, passive], b, rcond=None)[0]
        while passive.any() and s[passive].min() <= tol:
            neg = passive & (s <= tol)
            alpha = np.min(x[neg] / (x[neg] - s[neg]))
            x = x + alpha * (s - x)
            passive &= x > tol
            s = np.zeros(n)
            if passive.any():
                s[passive] = np.linalg.lstsq(A[:, passive], b, rcond=None)[0]
        x = s
        w = A.T @ (b - A @ x)
    return x, float(np.linalg.norm(A @ x - b)), True


def _rows(jac: Sequence[Sequence[float]] | None, n: int) -> np.ndarray:
    return np.zeros((0, n)) if jac is None else np.atleast_2d(np.asarray(jac, dtype=float))


def kkt_check(grad: Sequence[float], *, ineq_values: Sequence[float] | None = None, ineq_jac: Sequence[Sequence[float]] | None = None,
              eq_values: Sequence[float] | None = None, eq_jac: Sequence[Sequence[float]] | None = None,
              ineq_multipliers: Sequence[float] | None = None, eq_multipliers: Sequence[float] | None = None,
              tol_primal: float = 1e-6, tol_stationarity: float = 1e-6, tol_complementarity: float = 1e-6, tol_active: float = 1e-6,
              tol_dual: float = 1e-9, convex: bool | None = None) -> dict[str, Any]:
    """KKT report for minimising ``f`` subject to ``g(x) <= 0`` and ``h(x) = 0`` at a point with gradient ``grad``.

    Conditions: ``grad + G'lam + H'nu = 0``, ``lam >= 0``, ``lam_i g_i = 0``. Pass the multipliers a solver
    returned, or leave them out to recover the best ones on the active set. ``satisfied`` needs every
    condition within tolerance; stationarity is relative to ``1 + max|grad|``.
    """
    grad = np.asarray(grad, dtype=float).reshape(-1)
    n = grad.size
    g = np.zeros(0) if ineq_values is None else np.asarray(ineq_values, dtype=float).reshape(-1)
    G = _rows(ineq_jac, n)
    h = np.zeros(0) if eq_values is None else np.asarray(eq_values, dtype=float).reshape(-1)
    H = _rows(eq_jac, n)
    if G.shape[0] != g.size or H.shape[0] != h.size or (G.size and G.shape[1] != n) or (H.size and H.shape[1] != n):
        raise ValueError("constraint values and Jacobians must have matching row counts and n columns")

    primal = float(max(np.max(np.maximum(g, 0.0), initial=0.0), np.max(np.abs(h), initial=0.0)))
    active = np.flatnonzero(g >= -tol_active)
    supplied = ineq_multipliers is not None or eq_multipliers is not None
    if supplied:
        lam = np.zeros(g.size) if ineq_multipliers is None else np.asarray(ineq_multipliers, dtype=float).reshape(-1)
        nu = np.zeros(h.size) if eq_multipliers is None else np.asarray(eq_multipliers, dtype=float).reshape(-1)
        if lam.size != g.size or nu.size != h.size:
            raise ValueError("multiplier lengths must match the constraint counts")
        converged = True
    else:
        cols = [G[active].T, H.T, -H.T]
        M = np.hstack(cols) if any(c.size for c in cols) else np.zeros((n, 0))
        theta, _, converged = nonneg_least_squares(M, -grad)
        lam = np.zeros(g.size)
        lam[active] = theta[:active.size]
        nu = theta[active.size:active.size + h.size] - theta[active.size + h.size:]
    stationarity = float(np.max(np.abs(grad + G.T @ lam + H.T @ nu), initial=0.0))
    sign = float(max(0.0, -lam.min())) if lam.size else 0.0
    comp = float(np.max(np.abs(lam * g), initial=0.0))
    scale = 1.0 + float(np.max(np.abs(grad), initial=0.0))

    failed = []
    if primal > tol_primal:
        failed.append("primal_feasibility")
    if stationarity > tol_stationarity * scale:
        failed.append("stationarity")
    if sign > tol_dual:
        failed.append("multiplier_sign")
    if comp > tol_complementarity:
        failed.append("complementary_slackness")
    satisfied = not failed and converged
    if not converged:
        failed.append("multiplier_recovery_did_not_converge")
    return {"check": "kkt", "status": "holds" if satisfied else "violated", "satisfied": satisfied, "failed": failed,
            "primal_violation": primal, "stationarity_residual": stationarity, "multiplier_sign_violation": sign,
            "complementarity_violation": comp, "active_constraints": int(active.size), "multipliers_source": "supplied" if supplied else "recovered",
            "multipliers": {"inequality": lam.tolist(), "equality": nu.tolist()},
            "tolerance": {"primal": tol_primal, "stationarity": tol_stationarity, "complementarity": tol_complementarity, "active": tol_active, "dual": tol_dual},
            "certifies_optimality": (bool(satisfied and convex) if convex is not None else None), "convex": convex, "limits": KKT_LIMITS}


def kkt_check_quadratic(Q: Sequence[Sequence[float]] | None, q: Sequence[float], x: Sequence[float], *,
                        A_ub: Sequence[Sequence[float]] | None = None, b_ub: Sequence[float] | None = None,
                        A_eq: Sequence[Sequence[float]] | None = None, b_eq: Sequence[float] | None = None,
                        lower: Sequence[float] | None = None, upper: Sequence[float] | None = None, **tolerances: Any) -> dict[str, Any]:
    """KKT for ``min ½x'Qx + q'x`` s.t. ``A_ub x <= b_ub``, ``A_eq x = b_eq``, ``lower <= x <= upper`` (``Q=None`` is an LP).
    ``lower``/``upper`` may be scalars, arrays, or ``None``; infinite entries are ignored."""
    x = np.asarray(x, dtype=float).reshape(-1)
    n = x.size
    Qm = np.zeros((n, n)) if Q is None else np.asarray(Q, dtype=float)
    grad = Qm @ x + np.asarray(q, dtype=float).reshape(-1)
    g_rows: list[np.ndarray] = []
    g_vals: list[float] = []
    if A_ub is not None:
        A = _rows(A_ub, n)
        g_rows += list(A)
        g_vals += list(A @ x - np.asarray(b_ub, dtype=float).reshape(-1))
    for bound, sign in ((lower, -1.0), (upper, 1.0)):
        if bound is None:
            continue
        vec = np.broadcast_to(np.asarray(bound, dtype=float), (n,))
        for j in np.flatnonzero(np.isfinite(vec)):
            row = np.zeros(n)
            row[j] = sign
            g_rows.append(row)
            g_vals.append(sign * (x[j] - vec[j]))
    eq_vals = None if A_eq is None else _rows(A_eq, n) @ x - np.asarray(b_eq, dtype=float).reshape(-1)
    sym = (Qm + Qm.T) / 2
    convex = bool(np.linalg.eigvalsh(sym).min() >= -1e-9 * max(1.0, np.abs(sym).max())) if n else True
    res = kkt_check(grad, ineq_values=g_vals or None, ineq_jac=np.array(g_rows) if g_rows else None,
                    eq_values=eq_vals, eq_jac=A_eq, convex=convex, **tolerances)
    return res


# ---- solver runner on constructed instances ---------------------------------------------------

Solve = Callable[[ConvexInstance], tuple[Sequence[float], float] | None]
ALL_CHECKS = ("known_optimum", "kkt", "scaling", "relaxation")


def _solve(solve: Solve, inst: ConvexInstance, timeout_s: float):
    kind, value = call_guarded(solve, (inst,), timeout_s)
    if kind != RETURNED:
        return None, describe_error(kind, value)
    if value is None:
        return None, "solver_returned_no_optimum"
    try:
        x, obj = value
        return (np.asarray(x, dtype=float).reshape(-1), float(obj)), ""
    except (TypeError, ValueError) as exc:
        return None, f"solver result must be (x, objective): {exc}"


def _kkt(inst: ConvexInstance, x: np.ndarray, tol: float) -> dict[str, Any]:
    return kkt_check_quadratic(inst.Q, inst.q, x, A_ub=inst.A, b_ub=inst.b, lower=0.0 if inst.nonneg else None,
                               tol_primal=tol, tol_stationarity=tol, tol_complementarity=tol, tol_active=tol)


def check_solver_on_instances(solve: Solve, *, kind: str = "lp", cases: int = 20, seed: int = 0, n_vars: int = 4,
                              n_ineq: int | None = None, nonneg: bool = False, checks: Sequence[str] = ALL_CHECKS,
                              rtol: float = 1e-6, atol: float = 1e-6, tol_kkt: float = 1e-5, scale_factor: float = 3.0,
                              relax_delta: float = 0.5, timeout_s: float = 10.0, max_failures: int = 5) -> dict[str, Any]:
    """Run ``solve(instance) -> (x, objective) | None`` on ``cases`` seeded convex instances.

    A solver that raises, hangs, or finds no optimum on a valid instance fails the check (the instance is
    feasible and bounded by construction). ``instance_seed`` in each failure regenerates the instance with
    ``convex_instance(instance_seed, kind, n_vars=..., n_ineq=..., nonneg=...)``.
    """
    unknown = sorted(set(checks) - set(ALL_CHECKS))
    if unknown:
        raise ValueError(f"unknown checks {unknown}; choose from {list(ALL_CHECKS)}")
    tally = {c: {"passed": 0, "failed": 0} for c in checks}
    failures: list[dict[str, Any]] = []

    def record(check: str, case: int, inst_seed: int, ok: bool, reason: str = "", **detail: Any) -> None:
        tally[check]["passed" if ok else "failed"] += 1
        if not ok and len(failures) < max_failures:
            failures.append({"check": check, "case": case, "instance_seed": inst_seed, "reason": reason, **{k: to_jsonable(v) for k, v in detail.items()}})

    close = lambda a, b: abs(a - b) <= atol + rtol * abs(b)
    for i in range(int(cases)):
        iseed = int(rng_for(seed, i).integers(0, 2 ** 31 - 1))
        inst = convex_instance(iseed, kind, n_vars=n_vars, n_ineq=n_ineq, nonneg=nonneg)
        base, err = _solve(solve, inst, timeout_s)
        for c in ("known_optimum", "kkt"):
            if c in checks and base is None:
                record(c, i, iseed, False, err)
        if base is not None:
            x, obj = base
            if "known_optimum" in checks:
                if not close(obj, inst.objective_star):
                    record("known_optimum", i, iseed, False, "objective_mismatch", got=obj, expected=inst.objective_star)
                elif inst.unique_x and not np.allclose(x, inst.x_star, atol=max(atol, 1e-6) * 10, rtol=rtol):
                    record("known_optimum", i, iseed, False, "point_mismatch", got=x, expected=inst.x_star)
                else:
                    record("known_optimum", i, iseed, True)
            if "kkt" in checks:
                rep = _kkt(inst, x, tol_kkt)
                if not close(inst.objective(x), obj):
                    record("kkt", i, iseed, False, "reported_objective_differs_from_objective_at_x", reported=obj, at_x=inst.objective(x))
                elif not rep["satisfied"]:
                    record("kkt", i, iseed, False, "kkt_failed:" + ",".join(rep["failed"]), residuals={k: rep[k] for k in ("primal_violation", "stationarity_residual", "multiplier_sign_violation", "complementarity_violation")})
                else:
                    record("kkt", i, iseed, True)
        if "scaling" in checks:
            s, err = _solve(solve, inst.scaled(scale_factor), timeout_s)
            if s is None:
                record("scaling", i, iseed, False, err)
            elif not close(s[1], scale_factor * inst.objective_star):
                record("scaling", i, iseed, False, "objective_did_not_scale", got=s[1], expected=scale_factor * inst.objective_star)
            elif inst.unique_x and not np.allclose(s[0], inst.x_star, atol=max(atol, 1e-6) * 10, rtol=rtol):
                record("scaling", i, iseed, False, "optimal_point_moved_when_objective_scaled", got=s[0], expected=inst.x_star)
            else:
                record("scaling", i, iseed, True)
        if "relaxation" in checks:
            r, err = _solve(solve, inst.relaxed(relax_delta), timeout_s)
            if r is None:
                record("relaxation", i, iseed, False, err)
            elif r[1] > inst.objective_star + atol + rtol * abs(inst.objective_star):
                record("relaxation", i, iseed, False, "relaxing_constraints_worsened_the_optimum", relaxed=r[1], original=inst.objective_star)
            else:
                record("relaxation", i, iseed, True)

    total_failed = sum(t["failed"] for t in tally.values())
    status = "nothing_checked" if cases <= 0 or not checks else ("violated" if total_failed else "holds")
    return {"check": "solver_instances", "status": status, "kind": kind, "seed": seed, "cases": int(cases), "n_vars": n_vars, "n_ineq": n_ineq,
            "nonneg": nonneg, "per_check": tally, "failures": failures, "tolerance": {"rtol": rtol, "atol": atol, "kkt": tol_kkt}, "limits": RUNNER_LIMITS}
