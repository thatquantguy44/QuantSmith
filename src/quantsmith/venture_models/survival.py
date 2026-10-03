"""Round-progression survival baselines for spec 0095.

Time from a stage milestone to the next qualifying round, with exit and failure as competing events.
Estimators here are the standard, checkable ones:

* ``kaplan_meier`` (single event, Greenwood variance, log-log interval);
* ``cumulative_incidence`` (Aalen-Johansen, competing risks) — the correct way to report "probability
  of the next round by month 18" when exits and failures also remove companies from the risk set;
* a discrete-time cause-specific hazard model (``fit_hazard_model``) with ridge-regularized logistic
  regression, combined into cumulative incidence by ``predict_cif``;
* ``calibration_by_group`` and ``harrell_c`` for out-of-time evaluation.

Censoring is information: a company with no news is censored, **not** a failure. Validation on
anything but real, point-in-time cohorts is only a check that the arithmetic is right.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from .validation import CENSORED, SmallSampleError, day, require_min_n

Z95 = 1.959963984540054


# ---------------------------------------------------------------- durations
def durations_from_subjects(subjects: Sequence[Mapping[str, Any]]) -> List[Tuple[int, str]]:
    """``(days_from_formation_to_end, event_or_censored)`` per subject."""
    out = []
    for s in subjects:
        d = (day(s["end_date"]) - day(s["formation_date"])).days
        if d < 0:
            raise ValueError(f"subject {s.get('id')}: negative duration")
        out.append((d, s["event"]))
    return out


# -------------------------------------------------------------- Kaplan-Meier
def kaplan_meier(durations: Sequence[float], observed: Sequence[bool], z: float = Z95) -> List[Dict[str, float]]:
    """Kaplan-Meier survival steps with Greenwood variance and a log-log interval.

    Subjects censored at an event time are still at risk at that time. Returns one row per distinct
    event time.
    """
    if len(durations) != len(observed) or not durations:
        raise ValueError("durations and observed must be the same non-zero length")
    order = sorted(range(len(durations)), key=lambda i: durations[i])
    n_risk = len(durations)
    surv, gsum = 1.0, 0.0
    steps: List[Dict[str, float]] = []
    i = 0
    while i < len(order):
        t = durations[order[i]]
        d = c = 0
        j = i
        while j < len(order) and durations[order[j]] == t:
            if observed[order[j]]:
                d += 1
            else:
                c += 1
            j += 1
        if d:
            surv *= 1.0 - d / n_risk
            gsum += d / (n_risk * (n_risk - d)) if n_risk > d else 0.0
            if surv > 0.0 and gsum > 0.0:
                se_ll = math.sqrt(gsum) / abs(math.log(surv))
                lo, hi = surv ** math.exp(z * se_ll), surv ** math.exp(-z * se_ll)
            else:
                lo = hi = surv
            steps.append({"time": t, "n_risk": n_risk, "n_events": d, "survival": surv,
                          "greenwood_var": surv * surv * gsum, "ci_low": lo, "ci_high": hi})
        n_risk -= d + c
        i = j
    return steps


def step_value(steps: Sequence[Mapping[str, float]], t: float, key: str, default: float) -> float:
    """Value of a right-continuous step function at ``t``."""
    value = default
    for s in steps:
        if s["time"] <= t:
            value = s[key]
        else:
            break
    return value


# ----------------------------------------------------- Aalen-Johansen (CIF)
def cumulative_incidence(durations: Sequence[float], events: Sequence[str], cause: str) -> List[Dict[str, float]]:
    """Aalen-Johansen cumulative incidence of ``cause`` with other causes competing.

    ``events[i]`` is the cause or ``"censored"``. CIF increments by S(t-) * d_cause / n_risk, where
    S is the all-cause Kaplan-Meier survival. Unlike ``1 - KM`` with other causes treated as
    censored, this never overstates the probability of ``cause``.
    """
    if len(durations) != len(events) or not durations:
        raise ValueError("durations and events must be the same non-zero length")
    order = sorted(range(len(durations)), key=lambda i: durations[i])
    n_risk = len(durations)
    surv, cif = 1.0, 0.0
    steps: List[Dict[str, float]] = []
    i = 0
    while i < len(order):
        t = durations[order[i]]
        d_all = d_cause = c = 0
        j = i
        while j < len(order) and durations[order[j]] == t:
            e = events[order[j]]
            if e == CENSORED:
                c += 1
            else:
                d_all += 1
                if e == cause:
                    d_cause += 1
            j += 1
        if d_all:
            cif += surv * d_cause / n_risk
            surv *= 1.0 - d_all / n_risk
            steps.append({"time": t, "cif": cif, "n_risk": n_risk, "all_cause_survival": surv})
        n_risk -= d_all + c
        i = j
    return steps


def cif_at(steps: Sequence[Mapping[str, float]], t: float) -> float:
    return step_value(steps, t, "cif", 0.0)


# ------------------------------------------------ discrete-time hazard model
def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def _solve(a: List[List[float]], b: List[float]) -> List[float]:
    """Gaussian elimination with partial pivoting."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            raise ValueError("singular system in the hazard fit; increase the ridge")
        m[col], m[piv] = m[piv], m[col]
        for r in range(col + 1, n):
            f = m[r][col] / m[col][col]
            for c in range(col, n + 1):
                m[r][c] -= f * m[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (m[r][n] - sum(m[r][c] * x[c] for c in range(r + 1, n))) / m[r][r]
    return x


@dataclass(frozen=True)
class HazardModel:
    causes: Tuple[str, ...]
    n_features: int
    interval_days: int
    n_intervals: int
    weights: Mapping[str, Tuple[float, ...]]       # per cause: n_intervals dummies then feature coefficients
    n_subjects: int
    converged: Mapping[str, bool]


def person_periods(subjects: Sequence[Mapping[str, Any]], interval_days: int, n_intervals: int,
                   cause: str) -> List[Tuple[int, Tuple[float, ...], int]]:
    """Expand subjects into ``(interval_index, features, y)`` rows for one cause.

    A subject contributes every *fully observed* interval. If the cause occurs in an interval, that
    interval has y=1 and the subject leaves; another cause removes the subject at that interval
    (cause-specific hazard); a subject censored mid-interval contributes only completed intervals.
    """
    rows: List[Tuple[int, Tuple[float, ...], int]] = []
    for s in subjects:
        d = (day(s["end_date"]) - day(s["formation_date"])).days
        x = tuple(float(v) for v in s.get("features_vector", ()))
        full = d // interval_days
        event = s["event"]
        if event != CENSORED:
            k_event = min(max(math.ceil(d / interval_days) if d > 0 else 1, 1), n_intervals + 1)
            for k in range(1, min(k_event - 1, n_intervals) + 1):
                rows.append((k - 1, x, 0))
            if k_event <= n_intervals:
                rows.append((k_event - 1, x, 1 if event == cause else 0))
        else:
            for k in range(1, min(full, n_intervals) + 1):
                rows.append((k - 1, x, 0))
    return rows


def _fit_logistic(rows: Sequence[Tuple[int, Tuple[float, ...], int]], n_intervals: int, n_features: int,
                  ridge: float, interval_ridge: float, max_iter: int = 60, tol: float = 1e-9) -> Tuple[List[float], bool]:
    p = n_intervals + n_features
    beta = [0.0] * p
    pen = [interval_ridge] * n_intervals + [ridge] * n_features
    converged = False
    for _ in range(max_iter):
        grad = [-pen[j] * beta[j] for j in range(p)]
        hess = [[0.0] * p for _ in range(p)]
        for k, x, y in rows:
            idx = [k] + [n_intervals + f for f in range(n_features)]
            vals = [1.0] + list(x)
            eta = sum(beta[i] * v for i, v in zip(idx, vals))
            mu = _sigmoid(eta)
            w = mu * (1.0 - mu)
            for a, va in zip(idx, vals):
                grad[a] += (y - mu) * va
                for b, vb in zip(idx, vals):
                    hess[a][b] += w * va * vb
        for j in range(p):
            hess[j][j] += pen[j]
        step = _solve(hess, grad)
        beta = [b + s for b, s in zip(beta, step)]
        if max(abs(s) for s in step) < tol:
            converged = True
            break
    return beta, converged


def fit_hazard_model(subjects: Sequence[Mapping[str, Any]], causes: Sequence[str], interval_days: int = 180,
                     n_intervals: int = 8, ridge: float = 1.0, interval_ridge: float = 0.01,
                     min_subjects: int = 50) -> HazardModel:
    """Fit one discrete-time logistic hazard per cause (cause-specific hazards).

    ``subjects`` carry ``features_vector`` (numbers known at formation; check with
    ``assert_features_known`` first). Refuses fewer than ``min_subjects`` subjects.
    """
    require_min_n(len(subjects), min_subjects, "hazard model")
    n_features = len(subjects[0].get("features_vector", ()))
    weights, converged = {}, {}
    for cause in causes:
        rows = person_periods(subjects, interval_days, n_intervals, cause)
        if not any(y for _, _, y in rows):
            raise SmallSampleError(f"no {cause!r} events to fit")
        beta, ok = _fit_logistic(rows, n_intervals, n_features, ridge, interval_ridge)
        weights[cause], converged[cause] = tuple(beta), ok
    return HazardModel(tuple(causes), n_features, interval_days, n_intervals, weights, len(subjects), converged)


def _interval_hazards(model: HazardModel, features: Sequence[float], k: int) -> Dict[str, float]:
    h = {}
    for c in model.causes:
        w = model.weights[c]
        eta = w[k] + sum(w[model.n_intervals + f] * float(v) for f, v in enumerate(features))
        h[c] = _sigmoid(eta)
    total = sum(h.values())
    if total >= 1.0:                                  # keep the hazards a valid sub-distribution
        h = {c: v / (total + 1e-12) for c, v in h.items()}
    return h


def predict_cif(model: HazardModel, features: Sequence[float], cause: str, horizon_days: int) -> float:
    """Cumulative incidence of ``cause`` by ``horizon_days`` from cause-specific discrete hazards.

    A horizon that falls inside an interval takes the completed intervals in full and a proportional
    share of the next interval's incidence (it is never rounded up to the interval boundary, which would
    count days the horizon does not cover). Horizons past the last fitted interval are capped there.
    """
    if horizon_days <= 0:
        return 0.0
    full, rem = divmod(horizon_days, model.interval_days)
    surv, cif = 1.0, 0.0
    for k in range(min(full, model.n_intervals)):
        h = _interval_hazards(model, features, k)
        cif += surv * h[cause]
        surv *= 1.0 - sum(h.values())
    if rem and full < model.n_intervals:
        h = _interval_hazards(model, features, full)
        cif += (rem / model.interval_days) * surv * h[cause]
    return cif


# --------------------------------------------------------------- evaluation
def calibration_by_group(predictions: Sequence[float], durations: Sequence[float], events: Sequence[str],
                         cause: str, horizon: float, n_groups: int = 5, min_group: int = 20) -> List[Dict[str, Any]]:
    """Mean predicted vs Aalen-Johansen observed incidence by prediction group at ``horizon``.

    A group whose follow-up never reaches ``horizon`` (no one observed that long) is marked not
    assessable: calling an unobserved tail "zero events" is the survivorship trap in a new form.
    """
    n = len(predictions)
    require_min_n(n, n_groups * min_group, "calibration")
    order = sorted(range(n), key=lambda i: predictions[i])
    size = n // n_groups
    out = []
    for g in range(n_groups):
        idx = order[g * size:(g + 1) * size if g < n_groups - 1 else n]
        d = [durations[i] for i in idx]
        e = [events[i] for i in idx]
        mean_pred = sum(predictions[i] for i in idx) / len(idx)
        if max(d) < horizon:
            out.append({"group": g + 1, "n": len(idx), "mean_predicted": mean_pred, "observed": None,
                        "assessable": False, "reason": "follow-up does not reach the horizon"})
            continue
        observed = cif_at(cumulative_incidence(d, e, cause), horizon)
        out.append({"group": g + 1, "n": len(idx), "mean_predicted": mean_pred, "observed": observed,
                    "assessable": True, "difference": mean_pred - observed})
    return out


def harrell_c(risk: Sequence[float], durations: Sequence[float], events: Sequence[str], cause: str,
              min_pairs: int = 100) -> Dict[str, Any]:
    """Cause-specific concordance. A pair is comparable when i had ``cause`` at T_i and T_j > T_i
    (other causes and censoring count as 'later or censored'); concordant if risk_i > risk_j."""
    conc = tied = comp = 0
    n = len(risk)
    for i in range(n):
        if events[i] != cause:
            continue
        for j in range(n):
            if durations[j] > durations[i]:
                comp += 1
                if risk[i] > risk[j]:
                    conc += 1
                elif risk[i] == risk[j]:
                    tied += 1
    if comp < min_pairs:
        raise SmallSampleError(f"concordance: {comp} comparable pairs is below the minimum {min_pairs}")
    return {"c_index": (conc + 0.5 * tied) / comp, "comparable_pairs": comp,
            "note": "cause-specific; competing events treated as later-or-censored"}
