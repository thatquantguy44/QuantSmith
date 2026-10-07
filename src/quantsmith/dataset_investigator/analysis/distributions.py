"""Distribution tools. Spec ``0099`` (REQ-004, REQ-006).

Numeric summaries use the definitions the tests check against: sample
standard deviation and variance (ddof=1), linear-interpolated quantiles,
bias-corrected skew and excess kurtosis (``scipy.stats`` with ``bias=False``).
"""

from __future__ import annotations

import math
from typing import List, Optional

import numpy as np
import pandas as pd
from scipy import stats

from .registry import Params, ToolContext, analysis_tool
from .utils import CATEGORICAL_ROLES, NUMERIC_ROLES, labels, numeric_series

QUANTILES = {"p01": 0.01, "p05": 0.05, "p25": 0.25, "p75": 0.75, "p95": 0.95, "p99": 0.99}


def numeric_summary(x: np.ndarray) -> dict:
    """The summary statistics of a 1-D float array (no missing values)."""
    n = int(x.size)
    out: dict = {"count": n}
    if n == 0:
        return out
    q = np.quantile(x, list(QUANTILES.values()))
    out.update({
        "mean": float(np.mean(x)), "median": float(np.median(x)),
        "std": float(np.std(x, ddof=1)) if n > 1 else None,
        "var": float(np.var(x, ddof=1)) if n > 1 else None,
        "min": float(np.min(x)), "max": float(np.max(x)),
        **{k: float(v) for k, v in zip(QUANTILES, q)},
        "skew": float(stats.skew(x, bias=False)) if n > 2 and np.ptp(x) > 0 else None,
        "kurtosis": float(stats.kurtosis(x, fisher=True, bias=False)) if n > 3 and np.ptp(x) > 0 else None,
    })
    iqr = out["p75"] - out["p25"]
    lo, hi = out["p25"] - 1.5 * iqr, out["p75"] + 1.5 * iqr
    out["outlier_pct"] = float(np.mean((x < lo) | (x > hi)))
    if out["min"] >= 0 and x.sum() > 0:
        k = max(1, int(math.ceil(0.01 * n)))
        top = np.sort(x)[-k:]
        out["top1pct_share_of_total"] = float(top.sum() / x.sum())
    else:
        out["top1pct_share_of_total"] = None
    return out


class DistributionsParams(Params):
    columns: Optional[List[str]] = None


@analysis_tool(name="analyze_distributions", category="distributions", version="1.0.0",
               params=DistributionsParams, columns={"columns": NUMERIC_ROLES})
def analyze_distributions(df: pd.DataFrame, p: DistributionsParams, ctx: ToolContext) -> dict:
    """Mean, median, quantiles, variance, skew, kurtosis, tail concentration, outlier share per numeric column."""
    cols = p.columns or ctx.columns(NUMERIC_ROLES, allow_pii=False)
    rows = int(len(df))
    out = []
    for col in cols:
        x = numeric_series(df[col]).to_numpy()
        summary = numeric_summary(x)
        summary.update({"column": col, "missing_pct": 1 - (x.size / rows) if rows else 0.0})
        out.append(summary)
    return {"rows": rows, "columns": out}


class CategoriesParams(Params):
    columns: Optional[List[str]] = None
    top_k: int = 10


@analysis_tool(name="analyze_categories", category="distributions", version="1.0.0",
               params=CategoriesParams, columns={"columns": CATEGORICAL_ROLES}, reveals_values=True)
def analyze_categories(df: pd.DataFrame, p: CategoriesParams, ctx: ToolContext) -> dict:
    """Category frequencies and concentration; categories below the minimum cell size are pooled."""
    cols = p.columns or ctx.columns(CATEGORICAL_ROLES, allow_pii=False)
    out = []
    for col in cols:
        values = labels(df[col].dropna())
        n = int(len(values))
        counts = values.value_counts()
        ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        shown = [{"value": v, "count": int(c), "share": c / n} for v, c in ordered if c >= ctx.min_cell][: p.top_k]
        shown_values = {s["value"] for s in shown}
        rest = int(sum(c for v, c in ordered if v not in shown_values))
        probs = counts.to_numpy() / n if n else np.array([])
        entropy = float(-(probs * np.log(probs)).sum()) if n else 0.0
        out.append({
            "column": col, "n": n, "n_categories": int(len(counts)), "top": shown,
            "other_count": rest, "top_share": shown[0]["share"] if shown else None,
            "entropy": entropy,
            "normalized_entropy": entropy / math.log(len(counts)) if len(counts) > 1 else 0.0,
        })
    return {"columns": out}
