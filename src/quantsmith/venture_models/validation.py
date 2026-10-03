"""Shared point-in-time, sample-size, interval, and governance tools for spec 0095.

Everything here exists to stop a model from looking better than it is:

* ``as_of_view`` rebuilds a cohort *as it was known on a date* (an outcome after the date becomes
  censored), which is the venture-specific form of "no look-ahead";
* ``out_of_time_split`` trains only on that view and tests on cohorts formed later;
* ``assert_features_known`` rejects any feature learned after the cohort's formation date;
* ``require_min_n`` and ``bootstrap_ci`` refuse thin samples and put intervals on point estimates;
* ``deployability`` computes, never labels, whether a model may inform a decision (it may not, until
  real-data evidence and a named reviewer exist).

Standard library only.
"""

from __future__ import annotations

import random
from datetime import date
from typing import Any, Callable, Dict, List, Mapping, Sequence, Tuple

CENSORED = "censored"


class LeakageError(ValueError):
    """A feature, edge, or value was learned after the date a model is allowed to know."""


class SmallSampleError(ValueError):
    """A sample is too small to support the requested estimate."""


def day(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def require_min_n(n: int, minimum: int, what: str) -> None:
    if n < minimum:
        raise SmallSampleError(f"{what}: n={n} is below the minimum {minimum}")


# ------------------------------------------------------------- point in time
def as_of_view(subjects: Sequence[Mapping[str, Any]], as_of: str) -> List[Dict[str, Any]]:
    """Subjects as known on ``as_of``.

    Each subject needs ``id``, ``formation_date``, ``end_date`` and ``event`` (``"censored"`` or a
    cause). Subjects formed after ``as_of`` are absent. An event or censoring after ``as_of`` becomes
    censoring at ``as_of``: the world had not shown the outcome yet. Inputs are not modified.
    """
    cutoff = day(as_of)
    out: List[Dict[str, Any]] = []
    for s in subjects:
        formed, ended = day(s["formation_date"]), day(s["end_date"])
        if ended < formed:
            raise ValueError(f"subject {s.get('id')}: end_date precedes formation_date")
        if formed > cutoff:
            continue
        d = dict(s)
        if ended > cutoff:
            d["end_date"] = cutoff.isoformat()
            d["event"] = CENSORED
        out.append(d)
    return out


def out_of_time_split(subjects: Sequence[Mapping[str, Any]], split_date: str,
                      observation_end: str) -> Dict[str, Any]:
    """Train on what was known at ``split_date``; test on cohorts formed after it, followed to ``observation_end``."""
    if day(split_date) >= day(observation_end):
        raise ValueError("split_date must precede observation_end")
    train = as_of_view(subjects, split_date)
    later = [s for s in subjects if day(s["formation_date"]) > day(split_date)]
    test = as_of_view(later, observation_end)
    if not train or not test:
        raise SmallSampleError("the split leaves an empty training or test set")
    return {"train": train, "test": test, "split_date": day(split_date).isoformat(),
            "observation_end": day(observation_end).isoformat()}


def assert_features_known(rows: Sequence[Mapping[str, Any]], formation_key: str = "formation_date",
                          known_key: str = "feature_known_at") -> None:
    """Raise ``LeakageError`` listing every feature known after its row's formation date.

    Each row carries ``feature_known_at``: ``{feature_name: date}``. A feature with no recorded
    date is also rejected: an unknown date cannot be shown to be safe.
    """
    problems: List[str] = []
    for r in rows:
        formed = day(r[formation_key])
        features = r.get("features", {})
        known = r.get(known_key, {})
        for name in features:
            if name not in known:
                problems.append(f"{r.get('id')}: feature {name} has no known_at date")
            elif day(known[name]) > formed:
                problems.append(f"{r.get('id')}: feature {name} known {known[name]} after formation {formed.isoformat()}")
    if problems:
        raise LeakageError("; ".join(problems))


# ------------------------------------------------------------------ intervals
def bootstrap_ci(data: Sequence[Any], stat: Callable[[Sequence[Any]], float], n_boot: int = 500,
                 seed: int = 0, alpha: float = 0.05, min_n: int = 20) -> Dict[str, float]:
    """Percentile bootstrap interval for ``stat(data)``. Deterministic; refuses fewer than ``min_n`` items."""
    require_min_n(len(data), min_n, "bootstrap")
    point = stat(data)
    vals: List[float] = []
    for b in range(n_boot):
        rng = random.Random(f"{seed}-{b}")
        sample = [data[rng.randrange(len(data))] for _ in range(len(data))]
        vals.append(stat(sample))
    vals.sort()
    lo = vals[int((alpha / 2) * (n_boot - 1))]
    hi = vals[int((1 - alpha / 2) * (n_boot - 1))]
    return {"estimate": point, "low": lo, "high": hi, "n": len(data), "n_boot": n_boot}


# ---------------------------------------------------------------- governance
def _named(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def deployability(model: Mapping[str, Any]) -> Tuple[bool, List[str]]:
    """Whether a model record may inform a decision. Computed from evidence, never from a label.

    Requires: status ``validated``; ``usable_for_decisions`` true; a reviewed catalog record; and at
    least one real-data validation evidence entry with a dataset snapshot hash, an out-of-time
    period, metrics, and a named reviewer. Synthetic-only validation never qualifies.
    """
    reasons: List[str] = []
    if model.get("status") != "validated":
        reasons.append(f"status is {model.get('status')!r}, not 'validated'")
    if model.get("validation_status") == "synthetic_only":
        reasons.append("validation is synthetic only")
    if model.get("usable_for_decisions") is not True:
        reasons.append("usable_for_decisions is not true")
    if model.get("review_status") != "reviewed":
        reasons.append("the catalog record is not reviewed by a named person")
    evidence = [e for e in model.get("validation_evidence", []) or []
                if _named(e.get("dataset_snapshot_hash")) and _named(e.get("out_of_time_period"))
                and isinstance(e.get("metrics"), Mapping) and e["metrics"] and _named(e.get("reviewer"))]
    if not evidence:
        reasons.append("no complete real-data validation evidence (snapshot hash, out-of-time period, metrics, reviewer)")
    return (not reasons, reasons)
