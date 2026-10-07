"""Semantic column roles. Spec ``0099`` (REQ-002).

Each column gets one role, the rule that assigned it, and the evidence behind
it. Roles decide which tools may touch a column (the registry checks them), so
an identifier is never averaged and a free-text field is never grouped on.
Caller-supplied roles, target, and timestamp always win.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

import pandas as pd

from .models import ColumnProfile, Config

_ID_NAME = re.compile(r"(^|_)(id|uuid|guid|key)$|^id_", re.IGNORECASE)
_TARGET_NAME = re.compile(r"^(is|has)_|(^|_)(target|label|outcome|fraud|default|churn|churned|y)$", re.IGNORECASE)
TEXT_SAMPLE = 20_000  # text heuristics (length, words, spaces) read a seeded sample
_YES_NO = {"yes", "no", "y", "n", "true", "false", "t", "f"}


def _evidence(rule: str, s: pd.Series, n_unique: int, unique_ratio: float, missing_pct: float, **extra) -> Dict:
    return {"rule": rule, "dtype": str(s.dtype), "n_unique": n_unique,
            "unique_ratio": round(unique_ratio, 6), "missing_pct": round(missing_pct, 6), **extra}


def _infer(name: str, s: pd.Series, rows: int, config: Config, target_taken: bool) -> tuple:
    non_null = s.dropna()
    n = int(len(non_null))
    n_unique = int(non_null.nunique())
    unique_ratio = (n_unique / n) if n else 0.0
    missing_pct = (1 - n / rows) if rows else 0.0
    ev = lambda rule, **kw: _evidence(rule, s, n_unique, unique_ratio, missing_pct, **kw)

    if config.target == name:
        return ("binary_target" if n_unique == 2 else "multiclass_target"), ev("caller target"), True
    if config.timestamp == name:
        return "timestamp", ev("caller timestamp"), True
    if n_unique <= 1:
        return "constant", ev("at most one distinct non-missing value"), False
    if pd.api.types.is_datetime64_any_dtype(s):
        return "timestamp", ev("datetime dtype"), False

    looks_target = (config.target is None and not target_taken and n_unique == 2
                    and bool(_TARGET_NAME.search(name)))
    if looks_target:
        return "binary_target", ev("two values and a target-like name"), False
    if pd.api.types.is_bool_dtype(s):
        return "boolean", ev("boolean dtype"), False

    if _ID_NAME.search(name):
        if unique_ratio >= 0.95:
            return "identifier", ev("identifier-like name and at least 95% unique"), False
        if n_unique > max(20, int(0.001 * rows)):
            return "entity_identifier", ev("identifier-like name, repeated values, high cardinality"), False

    if pd.api.types.is_numeric_dtype(s):
        integer = pd.api.types.is_integer_dtype(s) or bool((non_null % 1 == 0).all())
        if integer and unique_ratio == 1.0 and non_null.is_monotonic_increasing and n > 20:
            return "identifier", ev("unique, increasing integers (a row number)"), False
        if n_unique == 2:
            return "boolean", ev("numeric with two values"), False
        if integer and n_unique <= 20:
            return "discrete_numeric", ev("integer with at most 20 distinct values"), False
        return "continuous_numeric", ev("numeric"), False

    probe = non_null if n <= TEXT_SAMPLE else non_null.sample(n=TEXT_SAMPLE, random_state=0)
    looks_numeric = n and pd.to_numeric(probe.astype(str).str.strip(), errors="coerce").notna().mean() >= 0.9
    numeric_text = pd.to_numeric(non_null.astype(str).str.strip(), errors="coerce") if looks_numeric else None
    parsed = int(numeric_text.notna().sum()) if numeric_text is not None else 0
    if numeric_text is not None and parsed / n >= 0.95:
        values = numeric_text.dropna()
        integer = bool((values % 1 == 0).all())
        role = "discrete_numeric" if integer and values.nunique() <= 20 else "continuous_numeric"
        return role, ev("numbers stored as text", non_numeric_entries=n - parsed), False
    sample = non_null if n <= TEXT_SAMPLE else non_null.sample(n=TEXT_SAMPLE, random_state=0)
    text = sample.astype(str)
    lengths = text.str.len()
    words = text.str.split().str.len()
    has_space = float((text.str.contains(" ")).mean()) if n else 0.0
    if n_unique == 2 and set(non_null.astype(str).str.lower().unique()) <= _YES_NO:
        return "boolean", ev("two yes/no-like values"), False
    if unique_ratio >= 0.95 and float(lengths.mean()) <= 40 and has_space < 0.05 and n > 20:
        return "identifier", ev("unique short tokens without spaces"), False
    if float(words.mean()) >= 3 or (float(lengths.mean()) >= 30 and unique_ratio >= 0.5):
        return "free_text", ev("multi-word values", mean_words=round(float(words.mean()), 3)), False
    return "categorical", ev("text with repeated values"), False


def infer_columns(df: pd.DataFrame, config: Optional[Config] = None) -> List[ColumnProfile]:
    """Assign a role to every column (REQ-002). Overrides in ``config.roles`` win."""
    config = config or Config()
    rows = int(len(df))
    out: List[ColumnProfile] = []
    target_taken = config.target is not None
    for name in df.columns:
        s = df[name]
        role, ev, _ = _infer(name, s, rows, config, target_taken)
        if role == "binary_target":
            target_taken = True
        overridden = name in config.roles
        if overridden:
            ev = {**ev, "rule": f"caller override (inferred {role})"}
            role = config.roles[name]
        out.append(ColumnProfile(
            name=name, dtype=str(s.dtype), role=role, pii=name in set(config.pii), overridden=overridden,
            n_unique=int(ev["n_unique"]), unique_ratio=float(ev["unique_ratio"]),
            missing_pct=float(ev["missing_pct"]), evidence=ev,
        ))
    return out


def target_column(columns: List[ColumnProfile], config: Config) -> Optional[str]:
    if config.target:
        return config.target
    for c in columns:
        if c.role in ("binary_target", "multiclass_target"):
            return c.name
    return None


def timestamp_column(columns: List[ColumnProfile], config: Config) -> Optional[str]:
    if config.timestamp:
        return config.timestamp
    for c in columns:
        if c.role == "timestamp":
            return c.name
    return None
