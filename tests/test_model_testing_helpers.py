"""Tests for the model-testing helpers (spec 0098).

Each check is proven able to fail: a case where it must pass and a case where it must not. SciPy is used
only as an independent oracle and the tests that need it skip without it.
"""

import math
import time

import numpy as np
import pytest

from quantsmith.test_engineering.differential import compare_implementations
from quantsmith.test_engineering.generators import (
    convex_instance,
    generate_inputs,
    parse_input_spec,
    regression_dataset,
    return_panel,
    rng_for,
    spd_matrix,
)
from quantsmith.test_engineering.metamorphic import (
    check_relation,
    idempotence,
    monotone,
    permutation,
    scaling,
    symmetry,
    translation,
)

# ---- AC-001: seeded generators, constructed optima ----------------------------------------------

def test_generators_are_deterministic_and_leave_global_state_alone_AC_001():
    before = np.random.get_state()[1].copy()
    a1, a2 = generate_inputs("vector:5", 4, seed=7), generate_inputs("vector:5", 4, seed=7)
    assert all(np.array_equal(x, y) for x, y in zip(a1, a2))
    assert not np.array_equal(a1[0], generate_inputs("vector:5", 4, seed=8)[0])
    assert not np.array_equal(a1[0], a1[1])                                   # cases use independent streams
    assert np.array_equal(return_panel(3, 20, 4), return_panel(3, 20, 4))
    d1, d2 = regression_dataset(5), regression_dataset(5)
    assert np.array_equal(d1.y, d2.y) and np.array_equal(d1.coef, d2.coef)
    i1, i2 = convex_instance(9, "qp", nonneg=True), convex_instance(9, "qp", nonneg=True)
    assert np.array_equal(i1.q, i2.q) and i1.objective_star == i2.objective_star
    assert (np.random.get_state()[1] == before).all()


def test_spd_matrix_is_symmetric_positive_definite_AC_001():
    m = spd_matrix(rng_for(1), 6)
    assert np.allclose(m, m.T) and np.linalg.eigvalsh(m).min() > 0


def test_input_spec_parsing_and_bad_specs_AC_001():
    assert parse_input_spec("matrix:3x4").shape() == (3, 4)
    assert parse_input_spec("spd:3").shape() == (3, 3) and parse_input_spec("scalar").shape() == ()
    for bad in ("vector", "vector:0", "matrix:3", "cube:3", "scalar:2"):
        with pytest.raises(ValueError):
            parse_input_spec(bad)
    with pytest.raises(ValueError):
        rng_for(-1)


@pytest.mark.parametrize("kind", ["lp", "qp"])
@pytest.mark.parametrize("nonneg", [False, True])
def test_constructed_instance_satisfies_its_own_kkt_conditions_AC_001(kind, nonneg):
    for seed in range(40):
        inst = convex_instance(seed, kind, n_vars=4, nonneg=nonneg)
        x, y, z = inst.x_star, inst.y_star, inst.z_star
        assert np.abs(inst.gradient(x) + inst.A.T @ y - z).max() < 1e-10          # stationarity
        assert (inst.A @ x - inst.b).max() <= 1e-10 and (y >= 0).all() and (z >= 0).all()
        assert np.abs(y * (inst.A @ x - inst.b)).max() < 1e-10                    # complementary slackness
        if nonneg:
            assert (x >= 0).all() and np.abs(z * x).max() < 1e-10
        assert inst.objective(x) == pytest.approx(inst.objective_star)


def test_instance_scaling_and_relaxation_helpers_AC_001():
    inst = convex_instance(3, "lp", nonneg=True)
    s = inst.scaled(4.0)
    assert s.objective_star == pytest.approx(4.0 * inst.objective_star) and np.array_equal(s.x_star, inst.x_star)
    r = inst.relaxed(0.5)
    assert np.allclose(r.b, inst.b + 0.5) and r.objective_star is None and r.x_star is None
    with pytest.raises(ValueError):
        inst.scaled(-1.0)
    with pytest.raises(ValueError):
        inst.relaxed(-0.1)
    with pytest.raises(ValueError):
        convex_instance(0, "milp")


def test_constructed_lp_optimum_matches_scipy_oracle_AC_001():
    linprog = pytest.importorskip("scipy.optimize").linprog
    for seed in range(25):
        for nonneg in (False, True):
            inst = convex_instance(seed, "lp", n_vars=4, nonneg=nonneg)
            res = linprog(inst.q, A_ub=inst.A, b_ub=inst.b, bounds=[(0, None) if nonneg else (None, None)] * 4, method="highs")
            assert res.status == 0
            assert res.fun == pytest.approx(inst.objective_star, rel=1e-7, abs=1e-7)
            if inst.unique_x:
                assert np.allclose(res.x, inst.x_star, atol=1e-6)


def test_constructed_qp_optimum_matches_scipy_oracle_AC_001():
    opt = pytest.importorskip("scipy.optimize")
    for seed in range(15):
        for nonneg in (False, True):
            inst = convex_instance(seed, "qp", n_vars=4, nonneg=nonneg)
            res = opt.minimize(inst.objective, np.zeros(4), jac=inst.gradient, method="SLSQP",
                               bounds=[(0, None)] * 4 if nonneg else None,
                               constraints=[{"type": "ineq", "fun": lambda x, i=inst: i.b - i.A @ x, "jac": lambda x, i=inst: -i.A}],
                               options={"ftol": 1e-12, "maxiter": 500})
            assert res.success
            assert res.fun == pytest.approx(inst.objective_star, rel=1e-6, abs=1e-6)
            assert np.allclose(res.x, inst.x_star, atol=1e-4)


# ---- AC-002: metamorphic relations --------------------------------------------------------------

def total(x):
    return float(np.sum(x))


def sum_of_squares(x):
    return float(np.sum(np.asarray(x) ** 2))


def test_scaling_holds_for_homogeneous_and_fails_for_the_rest_AC_002():
    assert check_relation(total, scaling(1), spec="vector:5", cases=20)["status"] == "holds"
    res = check_relation(sum_of_squares, scaling(1), spec="vector:5", cases=20)
    assert res["status"] == "violated" and res["violations"] == 20 and res["counterexamples"][0]["factor"] > 0
    assert check_relation(sum_of_squares, scaling(2), spec="vector:5", cases=20)["status"] == "holds"


def test_permutation_invariant_and_equivariant_AC_002():
    assert check_relation(total, permutation("invariant"), spec="vector:6")["status"] == "holds"
    assert check_relation(lambda x: float(x[0]), permutation("invariant"), spec="vector:6")["status"] == "violated"
    assert check_relation(lambda x: np.asarray(x) * 2.0, permutation("equivariant"), spec="vector:6")["status"] == "holds"
    assert check_relation(np.sort, permutation("equivariant"), spec="vector:6")["status"] == "violated"
    # permuting the columns of a data matrix permutes both axes of its covariance
    cov = lambda data: np.cov(np.asarray(data), rowvar=False)
    rel = permutation("equivariant", axis=1, symmetric_output=True)
    assert check_relation(cov, rel, spec="matrix:30x4", cases=10)["status"] == "holds"
    assert check_relation(lambda data: cov(data)[:, ::-1], rel, spec="matrix:30x4", cases=10)["status"] == "violated"


def test_translation_idempotence_symmetry_AC_002():
    assert check_relation(np.mean, translation("equivariant"), spec="vector:6")["status"] == "holds"
    assert check_relation(np.std, translation("invariant"), spec="vector:6")["status"] == "holds"
    assert check_relation(np.mean, translation("invariant"), spec="vector:6")["status"] == "violated"
    assert check_relation(np.sort, idempotence(), spec="vector:6")["status"] == "holds"
    assert check_relation(lambda x: np.asarray(x) * 2.0, idempotence(), spec="vector:6")["status"] == "violated"
    assert check_relation(lambda x: np.asarray(x) ** 3, symmetry("odd"), spec="vector:3")["status"] == "holds"
    assert check_relation(lambda x: np.asarray(x) ** 3, symmetry("even"), spec="vector:3")["status"] == "violated"
    assert check_relation(lambda x: np.asarray(x) ** 2, symmetry("even"), spec="vector:3")["status"] == "holds"


def test_monotone_detects_the_wrong_direction_AC_002():
    assert check_relation(total, monotone(True), spec="vector:4")["status"] == "holds"
    assert check_relation(lambda x: -total(x), monotone(True), spec="vector:4")["status"] == "violated"
    assert check_relation(lambda x: -total(x), monotone(False), spec="vector:4")["status"] == "holds"
    assert check_relation(lambda x: float(np.asarray(x)[0]), monotone(True, index=1), spec="vector:4")["status"] == "holds"
    assert check_relation(lambda x: np.asarray(x), monotone(True), spec="vector:4")["status"] == "inconclusive"   # non-scalar output


def test_relations_report_zero_cases_exceptions_and_hangs_honestly_AC_002():
    assert check_relation(total, scaling(), spec="vector:3", cases=0)["status"] == "nothing_checked"
    res = check_relation(lambda x: 1 / 0, scaling(), spec="vector:3", cases=3)
    assert res["status"] == "inconclusive" and res["error_count"] == 3 and "ZeroDivisionError" in res["errors"][0]["error"]
    start = time.monotonic()
    res = check_relation(lambda x: time.sleep(5), scaling(), spec="vector:3", cases=2, timeout_s=0.2)
    assert res["status"] == "inconclusive" and res["errors"][0]["error"] == "timeout" and time.monotonic() - start < 3
    # a violation outranks errors elsewhere; NaN outputs are a violation unless equal_nan is set
    assert check_relation(lambda x: float("nan"), scaling(), spec="vector:3", cases=3)["status"] == "violated"
    assert check_relation(lambda x: float("nan"), scaling(), spec="vector:3", cases=3, equal_nan=True)["status"] == "holds"
    with pytest.raises(ValueError):
        check_relation(total, scaling())


def test_relation_check_is_reproducible_from_its_seed_AC_002():
    a = check_relation(sum_of_squares, scaling(1), spec="vector:5", cases=10, seed=4)
    b = check_relation(sum_of_squares, scaling(1), spec="vector:5", cases=10, seed=4)
    assert a == b and "limits" in a and a["assumption"]
    assert a["counterexamples"][0]["case"] == 0 and a["seed"] == 4


# ---- AC-003: differential runner ----------------------------------------------------------------

def test_differential_agree_and_disagree_AC_003():
    same = compare_implementations({"np": total, "py": lambda x: float(sum(x))}, spec="vector:8")
    assert same["status"] == "agree" and same["disagreements"] == 0 and "both wrong" in same["limits"]
    off = compare_implementations({"np": total, "off": lambda x: total(x) + 1e-3 * x[0]}, spec="vector:8")
    assert off["status"] == "disagree" and off["worst_case"]["implementation"] == "off" and off["per_implementation"]["off"]["max_deviation"] > 0
    assert len(off["mismatches"]) <= 3 and off["worst_case"]["input"]


def test_differential_exception_handling_AC_003():
    def boom(x):
        raise ValueError("bad")

    assert compare_implementations({"a": total, "b": boom}, spec="vector:3", cases=3)["status"] == "disagree"
    assert compare_implementations({"a": boom, "b": boom}, spec="vector:3", cases=3)["status"] == "agree"
    assert compare_implementations({"a": boom, "b": lambda x: 1 / 0}, spec="vector:3", cases=3)["status"] == "disagree"


def test_differential_zero_cases_timeouts_and_bad_arguments_AC_003():
    assert compare_implementations({"a": total, "b": total}, spec="vector:3", cases=0)["status"] == "nothing_compared"
    res = compare_implementations({"a": total, "slow": lambda x: time.sleep(3)}, spec="vector:3", cases=1, timeout_s=0.1)
    assert res["status"] == "inconclusive" and res["inconclusive"] == 1
    with pytest.raises(ValueError):
        compare_implementations({"only": total}, spec="vector:3")
    with pytest.raises(ValueError):
        compare_implementations({"a": total, "b": total}, spec="vector:3", reference="c")
    with pytest.raises(ValueError):
        compare_implementations({"a": total, "b": total})


def test_differential_accepts_explicit_inputs_and_a_named_reference_AC_003():
    objs = [{"v": 1.0}, {"v": 2.0}]
    res = compare_implementations({"a": lambda o: o["v"] * 2, "b": lambda o: o["v"] + o["v"]}, inputs=objs, reference="b")
    assert res["status"] == "agree" and res["reference"] == "b" and res["cases"] == 2
    assert compare_implementations({"a": lambda o: np.array([1.0, 2.0]), "b": lambda o: np.array([1.0, 2.0, 3.0])}, inputs=objs)["status"] == "disagree"
    assert math.isinf(compare_implementations({"a": lambda o: 1.0, "b": lambda o: float("nan")}, inputs=objs)["worst_case"]["deviation"])


# ---- AC-005: KKT certificate and the solver runner ----------------------------------------------

from quantsmith.test_engineering.optimization_checks import (
    check_solver_on_instances,
    kkt_check,
    kkt_check_quadratic,
    nonneg_least_squares,
)


def test_nonneg_least_squares_matches_scipy_AC_005():
    scipy_nnls = pytest.importorskip("scipy.optimize").nnls
    rng = np.random.default_rng(0)
    for _ in range(100):
        m, n = int(rng.integers(2, 9)), int(rng.integers(1, 7))
        A, b = rng.standard_normal((m, n)), rng.standard_normal(m)
        x, resid, converged = nonneg_least_squares(A, b)
        _, resid_scipy = scipy_nnls(A, b)
        assert converged and (x >= 0).all() and resid == pytest.approx(resid_scipy, abs=1e-9)


@pytest.mark.parametrize("kind", ["lp", "qp"])
@pytest.mark.parametrize("nonneg", [False, True])
def test_kkt_holds_at_the_constructed_optimum_with_recovered_multipliers_AC_005(kind, nonneg):
    for seed in range(30):
        inst = convex_instance(seed, kind, nonneg=nonneg)
        rep = kkt_check_quadratic(inst.Q, inst.q, inst.x_star, A_ub=inst.A, b_ub=inst.b, lower=0.0 if nonneg else None)
        assert rep["satisfied"] and rep["multipliers_source"] == "recovered" and rep["certifies_optimality"] is True


def test_kkt_names_the_failed_condition_AC_005():
    inst = convex_instance(1, "qp")
    moved = inst.x_star + 0.05
    rep = kkt_check_quadratic(inst.Q, inst.q, moved, A_ub=inst.A, b_ub=inst.b)
    assert not rep["satisfied"] and rep["status"] == "violated" and "stationarity" in rep["failed"]
    far = inst.x_star + 100.0                                               # certainly outside the feasible set
    assert "primal_feasibility" in kkt_check_quadratic(inst.Q, inst.q, far, A_ub=inst.A, b_ub=inst.b)["failed"]
    assert rep.get("limits")


def test_kkt_with_supplied_multipliers_checks_signs_and_stationarity_AC_005():
    inst = convex_instance(2, "lp", nonneg=True)
    g, G = inst.A @ inst.x_star - inst.b, inst.A
    bounds_g, bounds_G = -inst.x_star, -np.eye(4)
    values, jac = np.r_[g, bounds_g], np.vstack([G, bounds_G])
    good = kkt_check(inst.gradient(inst.x_star), ineq_values=values, ineq_jac=jac, ineq_multipliers=np.r_[inst.y_star, inst.z_star])
    assert good["satisfied"] and good["multipliers_source"] == "supplied"
    flipped = np.r_[-inst.y_star, inst.z_star]
    assert "multiplier_sign" in kkt_check(inst.gradient(inst.x_star), ineq_values=values, ineq_jac=jac, ineq_multipliers=flipped)["failed"]
    wrong = np.r_[inst.y_star * 2, inst.z_star]
    assert "stationarity" in kkt_check(inst.gradient(inst.x_star), ineq_values=values, ineq_jac=jac, ineq_multipliers=wrong)["failed"]


def test_kkt_equality_constraints_and_unconstrained_AC_005():
    # min x^2 + y^2 s.t. x + y = 1: optimum (0.5, 0.5) with nu = -1
    ok = kkt_check_quadratic(2 * np.eye(2), [0.0, 0.0], [0.5, 0.5], A_eq=[[1, 1]], b_eq=[1.0])
    assert ok["satisfied"] and ok["multipliers"]["equality"][0] == pytest.approx(-1.0)
    bad = kkt_check_quadratic(2 * np.eye(2), [0.0, 0.0], [0.7, 0.3], A_eq=[[1, 1]], b_eq=[1.0])
    assert "stationarity" in bad["failed"]
    assert "primal_feasibility" in kkt_check_quadratic(2 * np.eye(2), [0.0, 0.0], [0.5, 0.4], A_eq=[[1, 1]], b_eq=[1.0])["failed"]
    assert kkt_check([0.0, 0.0])["satisfied"] and not kkt_check([1.0, 0.0])["satisfied"]


def test_kkt_certifies_optimality_only_for_convex_problems_AC_005():
    indefinite = kkt_check_quadratic(np.diag([1.0, -1.0]), [0.0, 0.0], [0.0, 0.0])
    assert indefinite["satisfied"] and indefinite["certifies_optimality"] is False        # a saddle point, not an optimum
    assert kkt_check([0.0])["certifies_optimality"] is None
    with pytest.raises(ValueError):
        kkt_check([1.0, 2.0], ineq_values=[0.0], ineq_jac=[[1.0, 2.0, 3.0]])
    with pytest.raises(ValueError):
        kkt_check([1.0], ineq_values=[0.0], ineq_jac=[[1.0]], ineq_multipliers=[1.0, 2.0])


def _scipy_lp(inst):
    linprog = pytest.importorskip("scipy.optimize").linprog
    n = inst.q.size
    res = linprog(inst.q, A_ub=inst.A, b_ub=inst.b, bounds=[(0, None) if inst.nonneg else (None, None)] * n, method="highs")
    return (res.x, float(res.fun)) if res.status == 0 else None


def _scipy_qp(inst):
    opt = pytest.importorskip("scipy.optimize")
    n = inst.q.size
    res = opt.minimize(inst.objective, np.zeros(n), jac=inst.gradient, method="SLSQP", bounds=[(0, None)] * n if inst.nonneg else None,
                       constraints=[{"type": "ineq", "fun": lambda x: inst.b - inst.A @ x, "jac": lambda x: -inst.A}],
                       options={"ftol": 1e-12, "maxiter": 1000})        # 1e-14 is below SLSQP's noise floor on scaled problems
    return (res.x, float(res.fun)) if res.success else None


@pytest.mark.parametrize("nonneg", [False, True])
def test_runner_passes_a_correct_lp_solver_AC_005(nonneg):
    rep = check_solver_on_instances(_scipy_lp, kind="lp", cases=25, seed=1, nonneg=nonneg)
    assert rep["status"] == "holds", rep["failures"]
    assert all(t["failed"] == 0 and t["passed"] == 25 for t in rep["per_check"].values())


@pytest.mark.parametrize("nonneg", [False, True])
def test_runner_passes_a_correct_qp_solver_AC_005(nonneg):
    rep = check_solver_on_instances(_scipy_qp, kind="qp", cases=15, seed=2, nonneg=nonneg, tol_kkt=1e-4, rtol=1e-5, atol=1e-5)
    assert rep["status"] == "holds", rep["failures"]


def test_runner_fails_broken_solvers_on_the_check_each_one_breaks_AC_005():
    def drops_last_constraint(inst):
        linprog = pytest.importorskip("scipy.optimize").linprog
        res = linprog(inst.q, A_ub=inst.A[:-1], b_ub=inst.b[:-1], bounds=[(0, None) if inst.nonneg else (None, None)] * inst.q.size, method="highs")
        return (res.x, float(res.fun)) if res.status == 0 else None

    rep = check_solver_on_instances(drops_last_constraint, kind="lp", cases=20, seed=3, nonneg=True, checks=("known_optimum", "kkt"))
    assert rep["status"] == "violated" and rep["per_check"]["known_optimum"]["failed"] > 0 and rep["per_check"]["kkt"]["failed"] > 0
    assert any(f["check"] == "kkt" and "primal_feasibility" in f["reason"] for f in rep["failures"])

    def lies_about_objective(inst):
        x, obj = _scipy_lp(inst)
        return x, obj + 0.5

    rep = check_solver_on_instances(lies_about_objective, kind="lp", cases=10, seed=3, checks=("known_optimum", "kkt"))
    assert rep["per_check"]["known_optimum"]["failed"] == 10 and rep["failures"][0]["reason"] in ("objective_mismatch", "reported_objective_differs_from_objective_at_x")

    def worse_when_relaxed(inst):                                           # a test double: misbehaves only on relaxed problems
        x, obj = _scipy_lp(inst)
        return (x, obj + 5.0) if inst.objective_star is None else (x, obj)

    rep = check_solver_on_instances(worse_when_relaxed, kind="lp", cases=10, seed=3)
    assert rep["per_check"]["relaxation"]["failed"] == 10 and rep["per_check"]["known_optimum"]["failed"] == 0 and rep["per_check"]["kkt"]["failed"] == 0

    def ignores_scale(inst):                                                # normalises the objective, a classic scaling bug
        s = float(np.abs(inst.q).max()) or 1.0
        x, obj = _scipy_lp(inst.scaled(1.0 / s))
        return x, obj

    rep = check_solver_on_instances(ignores_scale, kind="lp", cases=10, seed=3, checks=("scaling", "relaxation"))
    assert rep["per_check"]["scaling"]["failed"] > 0


def test_runner_reports_crashes_hangs_and_zero_cases_AC_005():
    def crashes(inst):
        raise RuntimeError("solver blew up")

    rep = check_solver_on_instances(crashes, cases=3, checks=("known_optimum",))
    assert rep["status"] == "violated" and "RuntimeError" in rep["failures"][0]["reason"]
    rep = check_solver_on_instances(lambda inst: None, cases=3, checks=("kkt",))
    assert rep["failures"][0]["reason"] == "solver_returned_no_optimum"
    rep = check_solver_on_instances(lambda inst: time.sleep(5), cases=1, checks=("known_optimum",), timeout_s=0.2)
    assert rep["failures"][0]["reason"] == "timeout"
    assert check_solver_on_instances(crashes, cases=0)["status"] == "nothing_checked"
    with pytest.raises(ValueError):
        check_solver_on_instances(crashes, checks=("nope",))


def test_runner_failures_reproduce_from_the_instance_seed_AC_005():
    def lies(inst):
        x, obj = _scipy_lp(inst)
        return x, obj + 1.0

    rep = check_solver_on_instances(lies, cases=3, seed=11, checks=("known_optimum",))
    f = rep["failures"][0]
    inst = convex_instance(f["instance_seed"], "lp", n_vars=4)
    assert inst.objective_star == pytest.approx(f["expected"]) and rep == check_solver_on_instances(lies, cases=3, seed=11, checks=("known_optimum",))


# ---- AC-004: regression checks ------------------------------------------------------------------

from quantsmith.test_engineering.regression_checks import (
    check_coefficient_recovery,
    check_feature_scaling_equivariance,
    check_regression,
    check_residual_orthogonality,
    check_row_permutation_invariance,
)


def ols_fit(X, y):
    Xa = np.hstack([np.ones((len(X), 1)), X])
    return np.linalg.lstsq(Xa, y, rcond=None)[0]


def ridge_fit(lam):
    def fit(X, y):
        Xa = np.hstack([np.ones((len(X), 1)), X])
        penalty = lam * np.eye(Xa.shape[1])
        penalty[0, 0] = 0.0                                                   # the intercept is not shrunk
        return np.linalg.solve(Xa.T @ Xa + penalty, Xa.T @ y)
    return fit


def statuses(report):
    return {k: v["status"] for k, v in report["checks"].items()}


def test_least_squares_passes_every_regression_check_AC_004():
    rep = check_regression(ols_fit)
    assert rep["status"] == "holds" and not rep["not_applicable"]
    assert set(statuses(rep)) == {"row_permutation", "coefficient_recovery", "feature_scaling", "residual_orthogonality"}
    assert all(s == "holds" for s in statuses(rep).values()) and rep["limits"]


def test_a_biased_fit_fails_recovery_and_orthogonality_but_not_scaling_AC_004():
    rep = check_regression(lambda X, y: 0.9 * ols_fit(X, y))
    s = statuses(rep)
    assert rep["status"] == "violated"
    assert s["coefficient_recovery"] == "violated" and s["residual_orthogonality"] == "violated"
    assert s["feature_scaling"] == "holds" and s["row_permutation"] == "holds"        # uniform shrinkage preserves both
    failure = check_coefficient_recovery(lambda X, y: 0.9 * ols_fit(X, y), cases=2)["failures"][0]
    assert failure["measure"] > 1e-3 and failure["data_seed"] >= 0 and failure["true"] and failure["estimated"]


def test_a_fit_that_drops_the_intercept_is_caught_AC_004():
    def no_intercept(X, y):
        return np.r_[0.0, np.linalg.lstsq(X, y, rcond=None)[0]]

    assert check_coefficient_recovery(no_intercept)["status"] == "violated"
    assert check_residual_orthogonality(no_intercept)["status"] == "violated"


def test_a_fit_that_depends_on_row_order_is_caught_AC_004():
    assert check_row_permutation_invariance(lambda X, y: ols_fit(X[:150], y[:150]))["status"] == "violated"


def test_penalised_fits_are_not_failed_for_properties_they_lack_AC_004():
    rep = check_regression(ridge_fit(5.0), penalized=True)
    assert rep["status"] == "holds" and set(rep["not_applicable"]) == {"coefficient_recovery", "feature_scaling", "residual_orthogonality"}
    assert set(rep["checks"]) == {"row_permutation"}
    misuse = check_regression(ridge_fit(5.0), penalized=False)                  # ridge judged as least squares: expected to fail
    assert misuse["status"] == "violated" and statuses(misuse)["coefficient_recovery"] == "violated"


def test_noisy_recovery_uses_standard_errors_AC_004():
    ok = check_coefficient_recovery(ols_fit, noise=1.0, cases=10)
    assert ok["status"] == "holds" and ok["worst_measure"] < 5.0 and "standard errors" in ok["measure"]
    bad = check_coefficient_recovery(lambda X, y: 0.9 * ols_fit(X, y), noise=0.1, cases=5)
    assert bad["status"] == "violated" and bad["worst_measure"] > 5.0


def test_no_intercept_models_and_option_passthrough_AC_004():
    def ols_no_intercept(X, y):
        return np.linalg.lstsq(X, y, rcond=None)[0]

    rep = check_regression(ols_no_intercept, intercept=False, n_features=3, n_obs=80, cases=5)
    assert rep["status"] == "holds"


def test_regression_checks_report_crashes_wrong_shapes_and_zero_cases_AC_004():
    crash = check_coefficient_recovery(lambda X, y: 1 / 0, cases=3)
    assert crash["status"] == "inconclusive" and crash["error_count"] == 3
    wrong = check_coefficient_recovery(lambda X, y: [1.0], cases=2)
    assert wrong["status"] == "inconclusive" and "expected 5" in wrong["errors"][0]["error"]
    assert check_coefficient_recovery(ols_fit, cases=0)["status"] == "nothing_checked"
    assert check_regression(ols_fit, cases=0)["status"] == "nothing_checked"
    assert check_feature_scaling_equivariance(lambda X, y: "not numbers", cases=1)["status"] == "inconclusive"


def test_regression_checks_are_reproducible_AC_004():
    a = check_regression(lambda X, y: 0.9 * ols_fit(X, y), seed=5, cases=4)
    assert a == check_regression(lambda X, y: 0.9 * ols_fit(X, y), seed=5, cases=4)


# ---- AC-006: ML checks --------------------------------------------------------------------------

from quantsmith.test_engineering.ml_checks import (
    accuracy,
    check_beats_baseline,
    check_determinism,
    check_noise_features,
    check_shuffled_label_placebo,
    holdout_split,
    r2_score,
)

N_ROWS, TEST_FRACTION = 400, 0.3
_rng = np.random.default_rng(0)
ML_X = _rng.standard_normal((N_ROWS, 3))
ML_Y_SIGNAL = 2 * ML_X[:, 0] - ML_X[:, 1] + 0.5 * _rng.standard_normal(N_ROWS)
ML_Y_NOISE = _rng.standard_normal(N_ROWS)
TRAIN_ROWS = N_ROWS - round(N_ROWS * TEST_FRACTION)


def ols_predict(Xa, ya, Xb):
    coef = np.linalg.lstsq(np.c_[np.ones(len(Xa)), Xa], ya, rcond=None)[0]
    return np.c_[np.ones(len(Xb)), Xb] @ coef


def test_signal_beats_its_placebo_and_noise_does_not_AC_006():
    good = check_shuffled_label_placebo(ols_predict, ML_X, ML_Y_SIGNAL)
    assert good["status"] == "holds" and good["p_value"] <= 0.05 and good["real_score"] > 0.8 and not good["placebo_scores_high"]
    assert good["placebo"]["max"] < good["real_score"] and good["n_placebo"] == 30
    none = check_shuffled_label_placebo(ols_predict, ML_X, ML_Y_NOISE)
    assert none["status"] == "violated" and none["p_value"] > 0.05 and none["notes"]


def test_a_model_that_reads_the_held_out_labels_is_flagged_AC_006():
    def reads_test_labels(Xa, ya, Xb):                                       # cheats: ignores training data, returns the held-out truth
        return ML_Y_SIGNAL[TRAIN_ROWS:TRAIN_ROWS + len(Xb)]

    rep = check_shuffled_label_placebo(reads_test_labels, ML_X, ML_Y_SIGNAL)
    assert rep["status"] == "violated" and rep["placebo_scores_high"] and rep["real_score"] == pytest.approx(1.0)
    assert any("reading held-out labels" in n for n in rep["notes"])


def test_determinism_passes_seeded_and_fails_unseeded_models_AC_006():
    assert check_determinism(ols_predict, ML_X, ML_Y_SIGNAL)["status"] == "holds"

    def unseeded(Xa, ya, Xb):
        return ols_predict(Xa, ya, Xb) + np.random.random(len(Xb))              # draws from global state each call

    bad = check_determinism(unseeded, ML_X, ML_Y_SIGNAL)
    assert bad["status"] == "violated" and bad["max_deviation"] > 0 and "seed" in bad["note"]
    assert check_determinism(ols_predict, ML_X, ML_Y_SIGNAL, repeats=1)["status"] == "nothing_checked"
    labels = (ML_Y_SIGNAL > 0).astype(int)
    assert check_determinism(lambda a, b, c: np.array(["up"] * len(c)), ML_X, labels)["status"] == "holds"


def test_beats_baseline_regression_and_classification_AC_006():
    assert check_beats_baseline(ols_predict, ML_X, ML_Y_SIGNAL)["status"] == "holds"
    worse = check_beats_baseline(ols_predict, ML_X, ML_Y_NOISE)
    assert worse["status"] == "violated" and worse["model_score"] <= worse["baseline_score"]
    labels = (ML_Y_SIGNAL > 0).astype(int)
    knows = lambda Xa, ya, Xb: (Xb[:, 0] * 2 - Xb[:, 1] > 0).astype(int)
    assert check_beats_baseline(knows, ML_X, labels, score=accuracy, baseline="majority")["status"] == "holds"
    assert check_beats_baseline(lambda a, b, c: np.zeros(len(c), dtype=int), ML_X, labels, score=accuracy, baseline="majority")["status"] == "violated"
    custom = check_beats_baseline(ols_predict, ML_X, ML_Y_SIGNAL, baseline=lambda ytr, Xte: np.zeros(len(Xte)), margin=0.1)
    assert custom["status"] == "holds" and custom["baseline"] == "callable"


def test_noise_features_catch_a_model_that_finds_skill_without_features_AC_006():
    assert check_noise_features(ols_predict, ML_X, ML_Y_SIGNAL)["status"] == "holds"

    def reads_test_labels(Xa, ya, Xb):
        return ML_Y_SIGNAL[TRAIN_ROWS:TRAIN_ROWS + len(Xb)]

    rep = check_noise_features(reads_test_labels, ML_X, ML_Y_SIGNAL)
    assert rep["status"] == "violated" and rep["excess_over_baseline"] > 0.5


def test_ml_split_defaults_to_chronological_and_never_overlaps_AC_006():
    tr, te = holdout_split(100, 0.3)
    assert list(tr) == list(range(70)) and list(te) == list(range(70, 100))            # the future is the test set
    tr, te = holdout_split(100, 0.3, "random", seed=1)
    assert set(tr).isdisjoint(te) and len(tr) + len(te) == 100 and not np.array_equal(te, np.arange(70, 100))
    assert np.array_equal(holdout_split(100, 0.3, "random", seed=1)[1], te)
    for bad in ({"test_fraction": 0.0}, {"test_fraction": 1.0}, {"split": "stratified"}):
        with pytest.raises(ValueError):
            holdout_split(100, **{"test_fraction": 0.3, **bad})
    with pytest.raises(ValueError):
        holdout_split(1, 0.5)
    seen = {}

    def spy(Xa, ya, Xb):
        seen["train_max"], seen["test_min"] = Xa[:, 0].max(), Xb[:, 0].min()
        return np.zeros(len(Xb))

    index_feature = np.arange(50, dtype=float).reshape(-1, 1)
    check_beats_baseline(spy, index_feature, np.arange(50.0))
    assert seen["train_max"] < seen["test_min"]                                         # no future rows in training


def test_ml_checks_report_crashes_bad_outputs_and_unreachable_alpha_AC_006():
    assert check_shuffled_label_placebo(lambda a, b, c: 1 / 0, ML_X, ML_Y_SIGNAL)["status"] == "inconclusive"
    short = check_beats_baseline(lambda a, b, c: [1.0], ML_X, ML_Y_SIGNAL)
    assert short["status"] == "inconclusive" and "predictions for" in short["error"]
    few = check_shuffled_label_placebo(ols_predict, ML_X, ML_Y_SIGNAL, n_placebo=10)
    assert few["status"] == "inconclusive" and "cannot reach" in few["notes"][0]
    assert check_shuffled_label_placebo(ols_predict, ML_X, ML_Y_SIGNAL, n_placebo=0)["status"] == "nothing_checked"
    with pytest.raises(ValueError):
        check_beats_baseline(ols_predict, ML_X, ML_Y_SIGNAL, baseline="median")
    with pytest.raises(ValueError):
        check_beats_baseline(ols_predict, ML_X[:10], ML_Y_SIGNAL)
    assert r2_score([1, 2, 3], [1, 2, 3]) == 1.0 and r2_score([1, 1, 1], [1, 1, 1]) == 0.0 and accuracy([1, 0], [1, 1]) == 0.5


def test_ml_checks_are_reproducible_from_the_seed_AC_006():
    a = check_shuffled_label_placebo(ols_predict, ML_X, ML_Y_SIGNAL, seed=3)
    assert a == check_shuffled_label_placebo(ols_predict, ML_X, ML_Y_SIGNAL, seed=3) and a["limits"]
    assert a["placebo"] != check_shuffled_label_placebo(ols_predict, ML_X, ML_Y_SIGNAL, seed=4)["placebo"]


# ---- AC-007: command line -----------------------------------------------------------------------

import json
import sys
import textwrap

from quantsmith.test_engineering import cli

DEMO_MODULE = """\
import numpy as np
def total(x): return float(np.sum(x))
def sumsq(x): return float(np.sum(np.asarray(x) ** 2))
def total_loop(x): return float(sum(x))
def total_off(x): return float(np.sum(x)) + 1e-3
def to_nan(x): return float("nan")
def boom(x): raise ValueError("no")
NOT_CALLABLE = 3
"""


@pytest.fixture
def demo(tmp_path):
    name = f"mm_demo_{abs(hash(str(tmp_path)))}"
    (tmp_path / f"{name}.py").write_text(textwrap.dedent(DEMO_MODULE), encoding="utf-8")
    yield name, str(tmp_path)
    sys.modules.pop(name, None)
    if str(tmp_path) in sys.path:
        sys.path.remove(str(tmp_path))


def run_cli(capsys, *argv):
    code = cli.main(list(argv))
    return code, json.loads(capsys.readouterr().out)


def test_cli_metamorphic_exit_codes_AC_007(demo, capsys):
    name, root = demo
    code, out = run_cli(capsys, "metamorphic", "--target", f"{name}:total", "--relation", "scaling", "--input", "vector:5", "--root", root)
    assert code == 0 and out["status"] == "holds" and out["target"] == f"{name}:total" and out["relation"] == "scaling"
    code, out = run_cli(capsys, "metamorphic", "--target", f"{name}:sumsq", "--relation", "scaling", "--param", "degree=1", "--input", "vector:5",
                        "--cases", "3", "--root", root)
    assert code == 1 and out["status"] == "violated" and out["counterexamples"]
    code, out = run_cli(capsys, "metamorphic", "--target", f"{name}:sumsq", "--relation", "scaling", "--param", "degree=2", "--input", "vector:5", "--root", root)
    assert code == 0 and out["params"]["degree"] == 2
    code, out = run_cli(capsys, "metamorphic", "--target", f"{name}:boom", "--relation", "scaling", "--input", "vector:5", "--cases", "2", "--root", root)
    assert code == 2 and out["status"] == "inconclusive"
    code, out = run_cli(capsys, "metamorphic", "--target", f"{name}:total", "--relation", "scaling", "--input", "vector:5", "--cases", "0", "--root", root)
    assert code == 2 and out["status"] == "nothing_checked"


def test_cli_metamorphic_params_and_string_relations_AC_007(demo, capsys):
    name, root = demo
    code, out = run_cli(capsys, "metamorphic", "--target", f"{name}:total", "--relation", "permutation", "--param", "kind=invariant",
                        "--input", "vector:6", "--root", root)
    assert code == 0 and out["params"]["kind"] == "invariant"
    code, out = run_cli(capsys, "metamorphic", "--target", f"{name}:total", "--relation", "monotone", "--param", "increasing=True", "--input", "vector:4", "--root", root)
    assert code == 0 and out["params"]["increasing"] is True


def test_cli_output_is_standard_json_even_with_non_finite_values_AC_007(demo, capsys):
    name, root = demo
    code = cli.main(["metamorphic", "--target", f"{name}:to_nan", "--relation", "scaling", "--input", "vector:3", "--cases", "2", "--root", root])
    text = capsys.readouterr().out
    assert code == 1
    out = json.loads(text, parse_constant=lambda c: pytest.fail(f"non-standard JSON constant {c}"))   # bare Infinity/NaN would fail here
    assert out["max_deviation"] == "inf"


def test_cli_differential_exit_codes_AC_007(demo, capsys):
    name, root = demo
    code, out = run_cli(capsys, "differential", "--target", f"{name}:total_loop", "--reference", f"{name}:total", "--input", "vector:6", "--root", root)
    assert code == 0 and out["status"] == "agree" and out["reference"] == f"{name}:total"
    code, out = run_cli(capsys, "differential", "--target", f"{name}:total_off", "--reference", f"{name}:total", "--input", "vector:6", "--cases", "3", "--root", root)
    assert code == 1 and out["status"] == "disagree" and out["worst_case"]["implementation"] == f"{name}:total_off"
    code, out = run_cli(capsys, "differential", "--target", f"{name}:total_off", "--reference", f"{name}:total", "--input", "vector:6",
                        "--cases", "3", "--atol", "0.01", "--root", root)
    assert code == 0 and out["status"] == "agree"
    code, out = run_cli(capsys, "differential", "--target", f"{name}:total_loop", "--reference", f"{name}:total", "--input", "vector:6", "--cases", "0", "--root", root)
    assert code == 2 and out["status"] == "nothing_compared"
    code, out = run_cli(capsys, "differential", "--target", f"{name}:total", "--reference", f"{name}:total", "--input", "vector:6", "--root", root)
    assert code == 2 and out["error"] == "bad_input" and "different" in out["message"]


def test_cli_bad_input_exits_two_with_bad_input_AC_007(demo, capsys):
    name, root = demo
    for argv in (
        ["metamorphic", "--target", f"{name}:total", "--relation", "nope", "--input", "vector:5"],
        ["metamorphic", "--target", f"{name}:total", "--relation", "scaling", "--param", "bogus=1", "--input", "vector:5"],
        ["metamorphic", "--target", f"{name}:total", "--relation", "scaling", "--param", "noequals", "--input", "vector:5"],
        ["metamorphic", "--target", f"{name}:total", "--relation", "scaling", "--input", "cube:5"],
        ["metamorphic", "--target", f"{name}:NOT_CALLABLE", "--relation", "scaling", "--input", "vector:5"],
        ["metamorphic", "--target", "nodots", "--relation", "scaling", "--input", "vector:5"],
        ["metamorphic", "--target", "no_such_module_xyz:f", "--relation", "scaling", "--input", "vector:5"],
        ["differential", "--target", f"{name}:total", "--reference", "nodots", "--input", "vector:5"],
    ):
        code, out = run_cli(capsys, *argv, "--root", root)
        assert code == 2 and out["error"] == "bad_input", argv
