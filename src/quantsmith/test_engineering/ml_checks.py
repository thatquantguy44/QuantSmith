"""Checks for ML models (spec 0098).

The contract is ``fit_predict(X_train, y_train, X_test) -> predictions`` (one prediction per test row). Wrap an
estimator with ``lambda Xa, ya, Xb: est.fit(Xa, ya).predict(Xb)``.

* ``check_determinism``: the same inputs give the same predictions (a model that draws unseeded randomness fails).
* ``check_shuffled_label_placebo``: train on permuted *training* labels, score against the true held-out labels. Real
  skill must beat that placebo (permutation p-value), and placebo scores must not sit above the baseline.
* ``check_noise_features``: replace the features with noise; a model must show no skill over the baseline.
* ``check_beats_baseline``: the model's held-out score must exceed a stated baseline (train mean, majority class, or your own).

Default evaluation is a chronological holdout (the last ``test_fraction`` of rows), so time-ordered data is never shuffled
into the training set. Use ``split="random"`` only for exchangeable rows. Higher ``score`` is better.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from ._guard import RETURNED, call_guarded, describe_error
from .generators import rng_for

FitPredict = Callable[[np.ndarray, np.ndarray, np.ndarray], Sequence[float]]
Score = Callable[[np.ndarray, np.ndarray], float]
Baseline = str | Callable[[np.ndarray, np.ndarray], np.ndarray]
LIMITS = ("A permutation p-value from n placebo fits has resolution 1/(n+1). Skill over a placebo is not skill that will persist out of sample, "
          "and a model can pass these checks and still be wrong; they catch evaluation mistakes, not every model flaw.")


def r2_score(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    yt, yp = np.asarray(y_true, dtype=float), np.asarray(y_pred, dtype=float)
    ss_tot = float(((yt - yt.mean()) ** 2).sum())
    return 1.0 - float(((yt - yp) ** 2).sum()) / ss_tot if ss_tot > 0 else 0.0


def accuracy(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    return float(np.mean(np.asarray(y_true) == np.asarray(y_pred)))


def holdout_split(n: int, test_fraction: float = 0.3, split: str = "chronological", seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Train and test row indices. ``chronological``: the last rows are the test set. ``random``: a seeded shuffle."""
    if not 0.0 < test_fraction < 1.0:
        raise ValueError("test_fraction must be strictly between 0 and 1")
    n_test = max(1, round(n * test_fraction))
    if n - n_test < 1:
        raise ValueError("not enough rows for a train/test split")
    if split == "chronological":
        idx = np.arange(n)
    elif split == "random":
        idx = rng_for(seed, 99).permutation(n)
    else:
        raise ValueError("split must be 'chronological' or 'random'")
    return idx[:n - n_test], idx[n - n_test:]


def _predict(fp: FitPredict, Xa, ya, Xb, timeout_s: float) -> tuple[np.ndarray | None, str]:
    kind, value = call_guarded(fp, (Xa, ya, Xb), timeout_s)
    if kind != RETURNED:
        return None, describe_error(kind, value)
    try:
        pred = np.asarray(value).reshape(-1)
    except (TypeError, ValueError) as exc:
        return None, f"fit_predict must return one prediction per test row: {exc}"
    if pred.size != len(Xb):
        return None, f"fit_predict returned {pred.size} predictions for {len(Xb)} test rows"
    return pred, ""


def _baseline_prediction(baseline: Baseline, ytr: np.ndarray, Xte: np.ndarray) -> np.ndarray:
    if callable(baseline):
        return np.asarray(baseline(ytr, Xte)).reshape(-1)
    if baseline == "mean":
        return np.full(len(Xte), float(np.mean(ytr)))
    if baseline == "majority":
        values, counts = np.unique(ytr, return_counts=True)
        return np.full(len(Xte), values[int(np.argmax(counts))])
    raise ValueError("baseline must be 'mean', 'majority' or a callable (y_train, X_test) -> predictions")


def _prepare(X, y, test_fraction, split, seed):
    X, y = np.asarray(X), np.asarray(y)
    if len(X) != len(y):
        raise ValueError("X and y must have the same number of rows")
    tr, te = holdout_split(len(X), test_fraction, split, seed)
    return X[tr], y[tr], X[te], y[te]


def _result(name: str, status: str, **fields: Any) -> dict[str, Any]:
    return {"check": name, "status": status, **fields, "limits": LIMITS}


def check_determinism(fit_predict: FitPredict, X, y, *, repeats: int = 3, test_fraction: float = 0.3, split: str = "chronological",
                      seed: int = 0, rtol: float = 0.0, atol: float = 0.0, timeout_s: float = 30.0) -> dict[str, Any]:
    """Call ``fit_predict`` ``repeats`` times on identical inputs; predictions must agree within ``rtol``/``atol`` (exact by default)."""
    Xtr, ytr, Xte, _ = _prepare(X, y, test_fraction, split, seed)
    runs: list[np.ndarray] = []
    for _ in range(max(0, int(repeats))):
        pred, err = _predict(fit_predict, Xtr.copy(), ytr.copy(), Xte.copy(), timeout_s)
        if pred is None:
            return _result("ml_determinism", "inconclusive", error=err, runs=len(runs), seed=seed)
        runs.append(pred)
    if len(runs) < 2:
        return _result("ml_determinism", "nothing_checked", runs=len(runs), seed=seed)
    try:
        dev = max(float(np.max(np.abs(r.astype(float) - runs[0].astype(float)))) for r in runs[1:])
        ok = all(np.allclose(r.astype(float), runs[0].astype(float), rtol=rtol, atol=atol) for r in runs[1:])
    except (TypeError, ValueError):                                              # non-numeric labels
        ok = all(np.array_equal(r, runs[0]) for r in runs[1:])
        dev = 0.0 if ok else float("inf")
    return _result("ml_determinism", "holds" if ok else "violated", runs=len(runs), max_deviation=dev, seed=seed,
                   tolerance={"rtol": rtol, "atol": atol},
                   note=None if ok else "identical inputs gave different predictions: seed the model's randomness or remove hidden state")


def check_beats_baseline(fit_predict: FitPredict, X, y, *, score: Score = r2_score, baseline: Baseline = "mean", margin: float = 0.0,
                         test_fraction: float = 0.3, split: str = "chronological", seed: int = 0, timeout_s: float = 30.0) -> dict[str, Any]:
    """The model's held-out score must exceed the baseline's by more than ``margin``."""
    Xtr, ytr, Xte, yte = _prepare(X, y, test_fraction, split, seed)
    pred, err = _predict(fit_predict, Xtr, ytr, Xte, timeout_s)
    if pred is None:
        return _result("ml_beats_baseline", "inconclusive", error=err, seed=seed)
    model, base = float(score(yte, pred)), float(score(yte, _baseline_prediction(baseline, ytr, Xte)))
    return _result("ml_beats_baseline", "holds" if model > base + margin else "violated", model_score=model, baseline_score=base, margin=margin,
                   baseline=baseline if isinstance(baseline, str) else "callable", split=split, test_rows=len(yte), seed=seed)


def check_shuffled_label_placebo(fit_predict: FitPredict, X, y, *, score: Score = r2_score, baseline: Baseline = "mean", n_placebo: int = 30,
                                 alpha: float = 0.05, test_fraction: float = 0.3, split: str = "chronological", seed: int = 0,
                                 timeout_s: float = 30.0) -> dict[str, Any]:
    """Skill must beat a placebo trained on permuted training labels (``p = (1 + #placebo >= real) / (1 + n)``, needs ``p <= alpha``).

    Also flagged: ``placebo_scores_high`` when the placebo mean sits more than three placebo standard deviations above the
    baseline score. A model cannot learn from shuffled labels, so high placebo scores point to an evaluation that reads the
    held-out labels (leakage) or to a wrong baseline.
    """
    Xtr, ytr, Xte, yte = _prepare(X, y, test_fraction, split, seed)
    real_pred, err = _predict(fit_predict, Xtr, ytr, Xte, timeout_s)
    if real_pred is None:
        return _result("ml_shuffled_label_placebo", "inconclusive", error=err, seed=seed)
    real = float(score(yte, real_pred))
    base = float(score(yte, _baseline_prediction(baseline, ytr, Xte)))
    placebo: list[float] = []
    for k in range(max(0, int(n_placebo))):
        perm = rng_for(seed, k, 2).permutation(len(ytr))
        pred, err = _predict(fit_predict, Xtr, ytr[perm], Xte, timeout_s)
        if pred is None:
            return _result("ml_shuffled_label_placebo", "inconclusive", error=f"placebo fit {k}: {err}", seed=seed)
        placebo.append(float(score(yte, pred)))
    if not placebo:
        return _result("ml_shuffled_label_placebo", "nothing_checked", real_score=real, seed=seed)
    arr = np.asarray(placebo)
    p = float((1 + np.sum(arr >= real)) / (1 + arr.size))
    sd = float(arr.std())
    high = bool(arr.mean() - base > 3.0 * sd)
    if 1.0 / (1 + arr.size) > alpha and not high:                      # even a perfect model could not reach alpha
        return _result("ml_shuffled_label_placebo", "inconclusive", real_score=real, baseline_score=base, p_value=p, alpha=alpha, n_placebo=int(arr.size),
                       seed=seed, notes=[f"{arr.size} placebo fits cannot reach p <= {alpha} (smallest possible p is {1.0 / (1 + arr.size):.3f}); use n_placebo >= {int(np.ceil(1 / alpha)) - 1}"])
    skill = p <= alpha and not high
    notes = []
    if p > alpha:
        notes.append("model score is not distinguishable from models trained on shuffled labels")
    if high:
        notes.append("placebo models score well above the baseline: the evaluation may be reading held-out labels, or the baseline is wrong")
    return _result("ml_shuffled_label_placebo", "holds" if skill else "violated", real_score=real, baseline_score=base, p_value=p, alpha=alpha,
                   n_placebo=int(arr.size), placebo={"mean": float(arr.mean()), "sd": sd, "min": float(arr.min()), "max": float(arr.max())},
                   placebo_scores_high=high, split=split, test_rows=len(yte), seed=seed, notes=notes)


def check_noise_features(fit_predict: FitPredict, X, y, *, score: Score = r2_score, baseline: Baseline = "mean", repeats: int = 10,
                         k: float = 3.0, test_fraction: float = 0.3, split: str = "chronological", seed: int = 0, timeout_s: float = 30.0) -> dict[str, Any]:
    """Replace the features with standard-normal noise (true labels kept). A model must not beat the baseline: the mean noise score
    must stay within ``k`` standard errors of it. Failure suggests the model or the evaluation finds skill that no feature can carry."""
    Xtr, ytr, Xte, yte = _prepare(X, y, test_fraction, split, seed)
    scores: list[float] = []
    for r in range(max(0, int(repeats))):
        rng = rng_for(seed, r, 3)
        pred, err = _predict(fit_predict, rng.standard_normal(Xtr.shape), ytr, rng.standard_normal(Xte.shape), timeout_s)
        if pred is None:
            return _result("ml_noise_features", "inconclusive", error=f"noise run {r}: {err}", seed=seed)
        scores.append(float(score(yte, pred)))
    if len(scores) < 2:
        return _result("ml_noise_features", "nothing_checked", runs=len(scores), seed=seed)
    base = float(score(yte, _baseline_prediction(baseline, ytr, Xte)))
    arr = np.asarray(scores)
    se = float(arr.std(ddof=1) / np.sqrt(arr.size))
    excess = float(arr.mean() - base)
    ok = excess <= k * se if se > 0 else excess <= 1e-12
    return _result("ml_noise_features", "holds" if ok else "violated", noise_score_mean=float(arr.mean()), scores=[float(v) for v in arr], baseline_score=base,
                   excess_over_baseline=excess, standard_error=se, k=k, runs=int(arr.size), split=split, seed=seed,
                   note=None if ok else "the model scores above the baseline on pure noise features")
