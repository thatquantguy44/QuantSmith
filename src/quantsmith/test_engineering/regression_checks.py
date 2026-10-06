"""Checks for regression fits (spec 0098).

The contract is ``fit(X, y) -> coef``: a 1-D array of coefficients with the intercept first when
``intercept=True``. Wrap library estimators, for example
``lambda X, y: np.r_[m.intercept_, m.coef_]`` after ``m.fit(X, y)``.

Four checks, each on seeded synthetic data whose true coefficients are known:

* ``check_coefficient_recovery``: exact on noiseless data; within ``se_multiple`` standard errors on noisy data.
* ``check_feature_scaling_equivariance``: scaling column *j* by *c* divides its coefficient by *c* and changes nothing else.
* ``check_row_permutation_invariance``: shuffling the rows changes nothing.
* ``check_residual_orthogonality``: the normal equations hold, ``X'(y - Xb) = 0``.

Recovery, scaling equivariance and orthogonality are properties of *least squares*. A penalised fit (ridge,
lasso, elastic net) correctly lacks them, so ``check_regression(penalized=True)`` runs only the permutation
check and says which checks it skipped and why. Passing is evidence, not a proof of a correct model.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from ._compare import compare_values, to_jsonable
from ._guard import RETURNED, call_guarded, describe_error
from .generators import RegressionData, regression_dataset, rng_for

Fit = Callable[[np.ndarray, np.ndarray], Sequence[float]]
LIMITS = ("Synthetic linear data with known coefficients: this shows the fit is right when the model is right, not that it is right on your data. "
          "Only least-squares fits are expected to pass recovery, scaling equivariance and orthogonality.")


def _fit(fit: Fit, X: np.ndarray, y: np.ndarray, width: int, timeout_s: float):
    kind, value = call_guarded(fit, (X, y), timeout_s)
    if kind != RETURNED:
        return None, describe_error(kind, value)
    try:
        coef = np.asarray(value, dtype=float).reshape(-1)
    except (TypeError, ValueError) as exc:
        return None, f"fit must return a numeric coefficient vector: {exc}"
    if coef.size != width:
        return None, f"fit returned {coef.size} coefficients, expected {width} (the intercept first when intercept=True, then one per feature)"
    return coef, ""


def _design(X: np.ndarray, intercept: bool) -> np.ndarray:
    return np.hstack([np.ones((X.shape[0], 1)), X]) if intercept else X


def _data(seed: int, i: int, n_obs: int, n_features: int, noise: float, intercept: bool) -> RegressionData:
    return regression_dataset(int(rng_for(seed, i).integers(0, 2 ** 31 - 1)), n_obs, n_features, noise, intercept)


def _summarise(name: str, seed: int, cases: int, evaluated: int, failures: list[dict[str, Any]], errors: list[dict[str, Any]],
               tolerance: dict[str, Any], **extra: Any) -> dict[str, Any]:
    status = "nothing_checked" if cases <= 0 else "violated" if failures else "inconclusive" if errors else "holds"
    return {"check": name, "status": status, "seed": seed, "cases": cases, "evaluated": evaluated, "failures": failures[:3],
            "failure_count": len(failures), "errors": errors[:3], "error_count": len(errors), "tolerance": tolerance, "limits": LIMITS, **extra}


def _loop(name: str, fit: Fit, cases: int, seed: int, n_obs: int, n_features: int, noise: float, intercept: bool, timeout_s: float,
          tolerance: dict[str, Any], body: Callable[[int, RegressionData, np.ndarray, int], Any], needs_base_fit: bool = True) -> dict[str, Any]:
    width = n_features + (1 if intercept else 0)
    failures: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    evaluated = 0
    worst = 0.0
    for i in range(max(0, int(cases))):
        data = _data(seed, i, n_obs, n_features, noise, intercept)
        base, err = _fit(fit, data.X, data.y, width, timeout_s)
        if base is None:
            errors.append({"case": i, "data_seed": data.seed, "error": err})
            continue
        result = body(i, data, base, width)
        if isinstance(result, str):                                     # the body hit an error of its own
            errors.append({"case": i, "data_seed": data.seed, "error": result})
            continue
        evaluated += 1
        ok, measure, detail = result
        worst = max(worst, measure)
        if not ok:
            failures.append({"case": i, "data_seed": data.seed, "measure": measure, **detail})
    return _summarise(name, seed, int(cases), evaluated, failures, errors, tolerance, worst_measure=worst)


def check_coefficient_recovery(fit: Fit, *, intercept: bool = True, n_obs: int = 200, n_features: int = 4, noise: float = 0.0,
                               cases: int = 10, seed: int = 0, tol: float = 1e-6, se_multiple: float = 5.0, timeout_s: float = 10.0) -> dict[str, Any]:
    """Noiseless: every coefficient within ``tol`` of the truth. Noisy: within ``se_multiple`` standard errors."""
    def body(i, data, est, width):
        true = data.coef
        err = np.abs(est - true)
        if noise == 0.0:
            return bool(err.max() <= tol), float(err.max()), {"estimated": to_jsonable(est), "true": to_jsonable(true)}
        Xa = _design(data.X, intercept)
        se = noise * np.sqrt(np.diag(np.linalg.inv(Xa.T @ Xa)))
        z = err / se
        return bool(z.max() <= se_multiple), float(z.max()), {"max_standard_errors": float(z.max()), "estimated": to_jsonable(est), "true": to_jsonable(true)}

    res = _loop("regression_recovery", fit, cases, seed, n_obs, n_features, noise, intercept, timeout_s,
                {"noise": noise, "tol": tol if noise == 0.0 else None, "se_multiple": se_multiple if noise else None}, body)
    res["measure"] = "max absolute coefficient error" if noise == 0.0 else "max error in standard errors"
    return res


def check_feature_scaling_equivariance(fit: Fit, *, intercept: bool = True, n_obs: int = 200, n_features: int = 4, noise: float = 0.5,
                                       cases: int = 10, seed: int = 0, rtol: float = 1e-6, atol: float = 1e-8, timeout_s: float = 10.0) -> dict[str, Any]:
    """Scale one feature column by ``c`` (drawn from [0.5, 4]): its coefficient becomes ``coef/c``; the rest are unchanged. Least squares only."""
    off = 1 if intercept else 0

    def body(i, data, base, width):
        rng = rng_for(seed, i, 1)
        j, c = int(rng.integers(0, n_features)), float(rng.uniform(0.5, 4.0))
        X2 = data.X.copy()
        X2[:, j] *= c
        est, err = _fit(fit, X2, data.y, width, timeout_s)
        if est is None:
            return err
        expected = base.copy()
        expected[off + j] /= c
        ok, dev, _ = compare_values(est, expected, rtol, atol)
        return ok, dev, {"column": j, "factor": c, "estimated": to_jsonable(est), "expected": to_jsonable(expected)}

    return _loop("regression_feature_scaling", fit, cases, seed, n_obs, n_features, noise, intercept, timeout_s, {"rtol": rtol, "atol": atol}, body)


def check_row_permutation_invariance(fit: Fit, *, intercept: bool = True, n_obs: int = 200, n_features: int = 4, noise: float = 0.5,
                                     cases: int = 10, seed: int = 0, rtol: float = 1e-6, atol: float = 1e-8, timeout_s: float = 10.0) -> dict[str, Any]:
    """Shuffle the rows (observations): the coefficients must not change. Holds for penalised fits too; not for order-dependent fits (online SGD)."""
    def body(i, data, base, width):
        perm = rng_for(seed, i, 1).permutation(n_obs)
        est, err = _fit(fit, data.X[perm], data.y[perm], width, timeout_s)
        if est is None:
            return err
        ok, dev, _ = compare_values(est, base, rtol, atol)
        return ok, dev, {"estimated": to_jsonable(est), "expected": to_jsonable(base)}

    return _loop("regression_row_permutation", fit, cases, seed, n_obs, n_features, noise, intercept, timeout_s, {"rtol": rtol, "atol": atol}, body)


def check_residual_orthogonality(fit: Fit, *, intercept: bool = True, n_obs: int = 200, n_features: int = 4, noise: float = 0.5,
                                 cases: int = 10, seed: int = 0, tol: float = 1e-7, timeout_s: float = 10.0) -> dict[str, Any]:
    """Least-squares residuals are orthogonal to every regressor (and sum to zero with an intercept): ``X'(y - Xb) = 0``.
    The measure is ``max |X'r|`` divided by ``max|X| * ||y||``. Least squares only."""
    def body(i, data, est, width):
        Xa = _design(data.X, intercept)
        r = data.y - Xa @ est
        measure = float(np.abs(Xa.T @ r).max() / max(1e-300, np.abs(Xa).max() * np.linalg.norm(data.y)))
        return measure <= tol, measure, {"estimated": to_jsonable(est)}

    return _loop("regression_residual_orthogonality", fit, cases, seed, n_obs, n_features, noise, intercept, timeout_s, {"tol": tol}, body)


def check_regression(fit: Fit, *, penalized: bool = False, cases: int = 10, seed: int = 0, **options: Any) -> dict[str, Any]:
    """All applicable checks. ``penalized=True`` (ridge, lasso, ...) runs only the permutation check and lists what was skipped."""
    runs = {"row_permutation": check_row_permutation_invariance(fit, cases=cases, seed=seed, **options)}
    skipped: dict[str, str] = {}
    if penalized:
        for name in ("coefficient_recovery", "feature_scaling", "residual_orthogonality"):
            skipped[name] = "penalised estimators shrink coefficients, so this least-squares property does not apply"
    else:
        runs["coefficient_recovery"] = check_coefficient_recovery(fit, cases=cases, seed=seed, **options)
        runs["feature_scaling"] = check_feature_scaling_equivariance(fit, cases=cases, seed=seed, **options)
        runs["residual_orthogonality"] = check_residual_orthogonality(fit, cases=cases, seed=seed, **options)
    statuses = [r["status"] for r in runs.values()]
    status = ("nothing_checked" if all(s == "nothing_checked" for s in statuses) else "violated" if "violated" in statuses
              else "inconclusive" if "inconclusive" in statuses or "nothing_checked" in statuses else "holds")
    return {"check": "regression", "status": status, "seed": seed, "cases": cases, "penalized": penalized,
            "checks": {k: {kk: v[kk] for kk in ("status", "failure_count", "error_count", "worst_measure")} for k, v in runs.items()},
            "details": runs, "not_applicable": skipped, "limits": LIMITS}
