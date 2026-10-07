"""Profile tools: dataset shape and roles, target balance. Spec ``0099`` (REQ-004)."""

from __future__ import annotations

from typing import Optional

import pandas as pd

from .registry import Params, ToolContext, analysis_tool
from .utils import TARGET_ROLES, as_bool_target, labels


class ProfileParams(Params):
    pass


@analysis_tool(name="profile_dataset", category="profile", version="1.0.0", params=ProfileParams)
def profile_dataset(df: pd.DataFrame, p: ProfileParams, ctx: ToolContext) -> dict:
    """Row and column counts, roles, missingness and cardinality per column."""
    rows = int(len(df))
    columns = []
    role_counts: dict = {}
    for col in df.columns:
        s = df[col]
        role = ctx.roles.get(col, "unknown")
        role_counts[role] = role_counts.get(role, 0) + 1
        missing = int(s.isna().sum())
        columns.append({
            "column": col, "dtype": str(s.dtype), "role": role, "pii": col in ctx.pii,
            "missing": missing, "missing_pct": (missing / rows) if rows else 0.0,
            "n_unique": int(s.nunique(dropna=True)),
        })
    return {
        "rows": rows, "columns": int(df.shape[1]),
        "role_counts": dict(sorted(role_counts.items())),
        "column_profiles": columns,
        "cells_missing_pct": float(df.isna().to_numpy().mean()) if df.size else 0.0,
    }


class TargetBalanceParams(Params):
    target: str
    positive: Optional[str] = None


@analysis_tool(name="analyze_target_balance", category="profile", version="1.0.0",
               params=TargetBalanceParams, columns={"target": TARGET_ROLES})
def analyze_target_balance(df: pd.DataFrame, p: TargetBalanceParams, ctx: ToolContext) -> dict:
    """Class counts and imbalance of the target; classes below the minimum cell size are pooled."""
    s = df[p.target]
    n = int(s.notna().sum())
    counts = labels(s.dropna()).value_counts()
    classes, small = [], 0
    for value, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if count < ctx.min_cell:
            small += int(count)
        else:
            classes.append({"value": value, "count": int(count), "share": count / n})
    out = {"target": p.target, "n": n, "missing": int(s.isna().sum()), "n_classes": int(len(counts)),
           "classes": classes, "small_classes_count": small}
    if ctx.roles.get(p.target) == "binary_target" or len(counts) == 2:
        y, positive = as_bool_target(s, p.positive or ctx.positive)
        positives = int(y.sum())
        out.update({"positive": positive, "positives": positives,
                    "positive_rate": positives / n if n else None,
                    "imbalance_ratio": ((n - positives) / positives) if positives else None})
    shares = [c["share"] for c in classes]
    out["minority_share"] = min(shares) if shares else None
    return out
