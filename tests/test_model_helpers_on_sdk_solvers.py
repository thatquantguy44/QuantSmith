"""The model-testing helpers (spec 0098) applied to the SDK's own solvers: worked examples and evidence for REQ-008.

``solve_lp`` (spec 0013) and ``solve_portfolio`` (spec 0007) are the first real targets. SciPy is the independent oracle and the
tests that need it skip without it. Findings are recorded in ``specs/0098-model-testing-helpers/validation.md``.
"""

import numpy as np
import pytest

from quantsmith.pipelines.optimization_solvers import solve_lp
from quantsmith.pipelines.portfolio_construction import (
    ConstraintSet,
    portfolio_variance,
    solve_portfolio,
)
from quantsmith.test_engineering.differential import compare_implementations
from quantsmith.test_engineering.generators import rng_for, spd_matrix
from quantsmith.test_engineering.metamorphic import check_relation, monotone
from quantsmith.test_engineering.optimization_checks import (
    check_solver_on_instances,
    kkt_check_quadratic,
)


def sdk_lp(inst):
    """Adapter: a constructed LP (``x >= 0``) through ``solve_lp``."""
    res = solve_lp(inst.q.tolist(), inst.A.tolist(), inst.b.tolist())
    return (res.x, res.objective) if res.status == "optimal" else None


# ---- solve_lp ------------------------------------------------------------------------------------

@pytest.mark.parametrize("n_vars", [3, 4, 6])
def test_solve_lp_passes_known_optimum_kkt_scaling_and_relaxation_AC_008(n_vars):
    rep = check_solver_on_instances(sdk_lp, kind="lp", cases=60, seed=0, n_vars=n_vars, nonneg=True)
    assert rep["status"] == "holds", rep["failures"]
    assert all(t["passed"] == 60 for t in rep["per_check"].values())


def random_degenerate_lp(rng):
    """Small integer data (degenerate vertices are likely), equality rows, either sense, sometimes bounded by an extra row."""
    n, m, me = int(rng.integers(2, 6)), int(rng.integers(1, 5)), int(rng.integers(0, 3))
    x0 = rng.integers(0, 4, size=n).astype(float)
    A = rng.integers(-3, 4, size=(m, n)).astype(float)
    b = A @ x0 + rng.integers(0, 2, size=m)
    Ae = rng.integers(-2, 3, size=(me, n)).astype(float)
    c = rng.integers(-3, 4, size=n).astype(float)
    if rng.random() < 0.67:
        A, b = np.vstack([A, np.ones(n)]), np.r_[b, x0.sum() + 5]
    return {"c": c, "A": A, "b": b, "Ae": Ae, "be": Ae @ x0, "sense": "max" if rng.random() < 0.5 else "min"}


STATUS_CODE = {"optimal": 0.0, "infeasible": 2.0, "unbounded": 3.0}


def test_solve_lp_agrees_with_scipy_on_degenerate_equality_and_max_problems_AC_008():
    linprog = pytest.importorskip("scipy.optimize").linprog

    def sdk(p):
        r = solve_lp(p["c"].tolist(), p["A"].tolist(), p["b"].tolist(), p["Ae"].tolist() or None, p["be"].tolist() or None, sense=p["sense"])
        return np.array([STATUS_CODE[r.status], r.objective if r.status == "optimal" else 0.0])

    def oracle(p):
        sign = 1.0 if p["sense"] == "min" else -1.0
        r = linprog(sign * p["c"], A_ub=p["A"], b_ub=p["b"], A_eq=p["Ae"] if len(p["Ae"]) else None, b_eq=p["be"] if len(p["Ae"]) else None,
                    bounds=(0, None), method="highs")
        code = {0: 0.0, 2: 2.0, 3: 3.0}[r.status]
        return np.array([code, sign * r.fun if r.status == 0 else 0.0])

    problems = [random_degenerate_lp(rng_for(0, i)) for i in range(300)]
    rep = compare_implementations({"sdk": sdk, "scipy": oracle}, inputs=problems, reference="scipy", rtol=1e-6, atol=1e-6)
    assert rep["status"] == "agree", rep["mismatches"]
    statuses = {s for s in (oracle(p)[0] for p in problems)}
    assert statuses >= {0.0, 3.0}                                             # the sample exercises optimal and unbounded outcomes


# ---- solve_portfolio -----------------------------------------------------------------------------

def portfolio_problem(seed, upper=0.6):
    rng = rng_for(seed)
    n = int(rng.integers(3, 9))
    return {"n": n, "cov": 0.1 * spd_matrix(rng, n), "alpha": rng.normal(0.0, 0.03, n), "upper": upper, "gamma": 5.0}


def sdk_portfolio(p, **kw):
    c = ConstraintSet(n=p["n"], budget=1.0, lower=0.0, upper=p["upper"], gross_cap=1.0)
    return np.array(solve_portfolio(p["alpha"].tolist(), p["cov"].tolist(), c, gamma=p["gamma"], **kw))


def portfolio_kkt(p, w, **tol):
    return kkt_check_quadratic(p["gamma"] * p["cov"], -p["alpha"], w, A_eq=np.ones((1, p["n"])), b_eq=[1.0], lower=0.0, upper=p["upper"], **tol)


def test_solve_portfolio_satisfies_kkt_so_its_answer_is_optimal_AC_008():
    for seed in range(10):                                                   # each solve is 4000 pure-Python iterations (~0.35 s)
        p = portfolio_problem(seed)
        rep = portfolio_kkt(p, sdk_portfolio(p))
        assert rep["satisfied"] and rep["certifies_optimality"] is True, (seed, rep["failed"], rep["stationarity_residual"])


def test_solve_portfolio_with_a_turnover_penalty_satisfies_kkt_AC_008():
    """The penalty is ``lambda_to/2 * ||w - w_prev||^2``, so the QP becomes ``Q = gamma*cov + lambda*I``, ``q = -alpha - lambda*w_prev``."""
    for seed in range(3):
        p = portfolio_problem(seed)
        w_prev = rng_for(seed, 9).dirichlet(np.ones(p["n"]))
        lam = 2.0
        w = sdk_portfolio(p, w_prev=w_prev.tolist(), lambda_to=lam)
        rep = kkt_check_quadratic(p["gamma"] * p["cov"] + lam * np.eye(p["n"]), -p["alpha"] - lam * w_prev, w, A_eq=np.ones((1, p["n"])),
                                  b_eq=[1.0], lower=0.0, upper=p["upper"])
        assert rep["satisfied"] and rep["certifies_optimality"] is True, (seed, rep["failed"], rep["stationarity_residual"])
        no_penalty = kkt_check_quadratic(p["gamma"] * p["cov"], -p["alpha"], w, A_eq=np.ones((1, p["n"])), b_eq=[1.0], lower=0.0, upper=p["upper"])
        assert not no_penalty["satisfied"]                                    # the penalty really changes the answer: w is not optimal without it


def test_the_kkt_check_can_tell_when_portfolio_solver_stops_early_AC_008():
    p = portfolio_problem(5)
    early = portfolio_kkt(p, sdk_portfolio(p, iterations=3))
    assert not early["satisfied"] and "stationarity" in early["failed"]
    residuals = [portfolio_kkt(p, sdk_portfolio(p, iterations=k))["stationarity_residual"] for k in (3, 20, 4000)]
    assert residuals[0] > residuals[1] > residuals[2]                         # the residual falls as the solver converges
    assert portfolio_kkt(p, sdk_portfolio(p))["satisfied"]


def test_solve_portfolio_is_equivariant_to_relabelling_assets_AC_008():
    """Permuting the assets must permute the weights: a metamorphic relation run as a differential check on one input."""
    problems = []
    for seed in range(8):
        p = portfolio_problem(seed)
        p["perm"] = rng_for(seed, 1).permutation(p["n"])
        problems.append(p)

    def permute_after(p):
        return sdk_portfolio(p)[p["perm"]]

    def permute_before(p):
        q = dict(p, alpha=p["alpha"][p["perm"]], cov=p["cov"][np.ix_(p["perm"], p["perm"])])
        return sdk_portfolio(q)

    rep = compare_implementations({"solve_then_permute": permute_after, "permute_then_solve": permute_before}, inputs=problems, rtol=1e-7, atol=1e-9)
    assert rep["status"] == "agree", rep["mismatches"]


def test_portfolio_variance_is_non_increasing_in_risk_aversion_AC_008():
    p = portfolio_problem(3)
    cache = {}

    def variance_at(g):
        key = round(float(g[0]), 12)
        if key not in cache:                                                  # the second check below reuses every solve
            cache[key] = portfolio_variance(sdk_portfolio(dict(p, gamma=key)).tolist(), p["cov"].tolist())
        return cache[key]

    gammas = [np.array([g]) for g in np.linspace(0.5, 20.0, 8)]
    rep = check_relation(variance_at, monotone(increasing=False, index=0, step=0.5), inputs=gammas, atol=1e-9)
    assert rep["status"] == "holds", rep["counterexamples"]
    assert check_relation(variance_at, monotone(increasing=True, index=0, step=0.5), inputs=gammas, atol=1e-9)["status"] == "violated"
