"""Shared helpers: JSON-safe conversion, canonical hashing, column predicates.

This module, like every module in ``analysis/``, imports only the standard
library, the ``investigator`` extra's libraries, and its sibling modules, so the
directory can be copied verbatim into an exported analysis package.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
from typing import Any, Iterable

import numpy as np
import pandas as pd

NUMERIC_ROLES = frozenset({"continuous_numeric", "discrete_numeric"})
CATEGORICAL_ROLES = frozenset({"categorical", "boolean"})
TARGET_ROLES = frozenset({"binary_target", "multiclass_target"})
GROUPABLE_ROLES = CATEGORICAL_ROLES | NUMERIC_ROLES | frozenset({"binary_target"})
ENTITY_ROLES = frozenset({"entity_identifier"})
ID_ROLES = frozenset({"identifier", "entity_identifier"})
TIME_ROLES = frozenset({"timestamp"})


def jsonable(value: Any) -> Any:
    """Convert numpy/pandas scalars and containers to plain JSON-safe values.

    NaN and infinities become ``None``; timestamps become ISO strings; dict
    keys become strings. Lists keep their order; dicts keep insertion order
    (callers sort where order must be stable).
    """
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        f = float(value)
        return f if math.isfinite(f) else None
    if isinstance(value, (pd.Timestamp, _dt.datetime, _dt.date)):
        return value.isoformat()
    if isinstance(value, (np.datetime64,)):
        return pd.Timestamp(value).isoformat()
    if value is pd.NaT:
        return None
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return [jsonable(v) for v in value.tolist()]
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def canonical_json(value: Any) -> str:
    return json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_text(canonical_json(value))


def pretty_json(value: Any) -> str:
    """Stable, human-readable JSON (sorted keys, two-space indent, trailing newline)."""
    return json.dumps(jsonable(value), sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator is None or numerator is None:
        return None
    if denominator == 0:
        return None
    return float(numerator) / float(denominator)


def label(value: Any) -> str:
    """A group label as a string: stable across CSV/Parquet loads."""
    if value is None:
        return "(missing)"
    try:
        if pd.isna(value):
            return "(missing)"
    except (TypeError, ValueError):
        pass
    if isinstance(value, (bool, np.bool_)):
        return "True" if bool(value) else "False"
    if isinstance(value, (float, np.floating)) and float(value).is_integer():
        return str(int(value))
    return str(value)


def labels(s: pd.Series) -> pd.Series:
    """Vectorized :func:`label` for a whole column (missing → ``(missing)``)."""
    missing = s.isna()
    if pd.api.types.is_bool_dtype(s):
        out = s.map({True: "True", False: "False"})
    elif pd.api.types.is_integer_dtype(s):
        out = s.astype("int64").astype(str) if not missing.any() else s.astype("Int64").astype(str)
    elif pd.api.types.is_float_dtype(s):
        x = s.astype("float64")
        integral = x.notna() & np.isfinite(x) & (x % 1 == 0)
        out = x.astype(str)
        if integral.any():
            out = out.where(~integral, x.where(integral).astype("Int64").astype(str))
    else:
        out = s.astype(object)
        present = out[~missing]
        if len(present) and not present.map(type).eq(str).all():
            out = out.astype(str)
    return out.where(~missing, "(missing)").astype(object)


def numeric_series(s: pd.Series) -> pd.Series:
    """The non-missing values of ``s`` as float64."""
    return pd.to_numeric(s, errors="coerce").dropna().astype("float64")


def as_bool_target(s: pd.Series, positive: Any = None) -> tuple[pd.Series, str]:
    """Map a binary column to 1.0/0.0 (missing stays NaN) and name the positive class.

    The positive class is ``positive`` if given; otherwise ``True`` for booleans,
    ``1`` for 0/1 columns, and the less frequent value for anything else (ties:
    the label that sorts last).
    """
    present = s.notna()
    if positive is None and (pd.api.types.is_bool_dtype(s) or pd.api.types.is_numeric_dtype(s)):
        values = set(pd.unique(s[present]).tolist())
        if values and values <= {0, 1}:
            pos = "True" if pd.api.types.is_bool_dtype(s) else "1"
            return s.astype("float64"), pos
    labs = labels(s)
    counts = labs[present].value_counts()
    uniques = sorted(counts.index)
    if positive is not None:
        pos = label(positive)
    elif set(uniques) <= {"0", "1"} or set(uniques) <= {"True", "False"}:
        pos = "1" if "1" in uniques else "True"
    else:
        ranked = sorted(counts.items(), key=lambda kv: (kv[1], -uniques.index(kv[0])))
        pos = ranked[0][0]
    mapped = pd.Series(np.where(present, (labs == pos).astype("float64"), np.nan), index=s.index)
    return mapped.astype("float64"), pos


def _is_missing(v: Any) -> bool:
    try:
        return bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def to_datetime(s: pd.Series) -> pd.Series:
    """Parse a column as timezone-naive ``datetime64[ns]`` (unparseable → NaT)."""
    if pd.api.types.is_datetime64_any_dtype(s):
        out = s
    else:
        out = pd.to_datetime(s, errors="coerce", format="mixed")
    if getattr(out.dt, "tz", None) is not None:
        out = out.dt.tz_convert("UTC").dt.tz_localize(None)
    return out.astype("datetime64[ns]")


def band(s: pd.Series, bins: int) -> pd.Series:
    """Quantile bands of a numeric column, labelled ``[lo, hi]`` with 4 significant digits."""
    x = pd.to_numeric(s, errors="coerce")
    try:
        cats = pd.qcut(x, q=bins, duplicates="drop")
    except ValueError:
        return labels(x)
    edges = [(iv.left, iv.right) for iv in cats.cat.categories]
    if edges:
        edges[0] = (float(x.min()), edges[0][1])  # qcut widens the first edge by 0.1%; show the real minimum
    names = np.array([f"[{lo:.4g}, {hi:.4g}]" for lo, hi in edges] + ["(missing)"], dtype=object)
    codes = cats.cat.codes.to_numpy()
    return pd.Series(names[np.where(codes < 0, len(names) - 1, codes)], index=s.index, dtype=object)


def stable_unique(items: Iterable[Any]) -> list[Any]:
    seen: set = set()
    out = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out
