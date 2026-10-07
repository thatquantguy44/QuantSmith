"""Relationship tools. Spec ``0099`` (REQ-004, REQ-006).

Pearson and Spearman correlations with p-values, mutual information with a
target, target rates by whether a value is missing, and partial correlation.
Every test reports its p-value under ``tests`` so the run can adjust them all
together (Benjamini–Hochberg).
"""

from __future__ import annotations

import math
from typing import List, Optional

import numpy as np
import pandas as pd
from scipy import stats

from .registry import Params, ToolContext, analysis_tool
from .utils import (
    CATEGORICAL_ROLES,
    NUMERIC_ROLES,
    TARGET_ROLES,
    as_bool_target,
    labels,
)

ALL_ROLES = frozenset({
    "identifier", "entity_identifier", "timestamp", "continuous_numeric", "discrete_numeric",
    "categorical", "boolean", "binary_target", "multiclass_target", "free_text", "constant",
})
FEATURE_ROLES = NUMERIC_ROLES | CATEGORICAL_ROLES


class CorrelationsParams(Params):
    columns: Optional[List[str]] = None
    min_n: int = 10


@analysis_tool(name="calculate_correlations", category="relationships", version="1.0.0",
               params=CorrelationsParams, columns={"columns": NUMERIC_ROLES})
def calculate_correlations(df: pd.DataFrame, p: CorrelationsParams, ctx: ToolContext) -> dict:
    """Pearson and Spearman correlation, with p-values, for every pair of numeric columns."""
    cols = sorted(p.columns or ctx.columns(NUMERIC_ROLES))[: ctx.max_numeric_columns]
    data = df[cols].apply(pd.to_numeric, errors="coerce")
    complete = {c: bool(data[c].notna().all()) for c in cols}
    ranks = {c: stats.rankdata(data[c].to_numpy()) for c in cols if complete[c]}
    pairs, tests = [], []
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            sub = data[[a, b]].dropna()
            n = int(len(sub))
            if n < p.min_n or sub[a].nunique() < 2 or sub[b].nunique() < 2:
                continue
            r, rp = stats.pearsonr(sub[a], sub[b])
            if complete[a] and complete[b]:
                rho, sp = stats.pearsonr(ranks[a], ranks[b])  # Spearman = Pearson on ranks
            else:
                rho, sp = stats.spearmanr(sub[a], sub[b])
            pairs.append({"a": a, "b": b, "n": n, "pearson": float(r), "pearson_p": float(rp),
                          "spearman": float(rho), "spearman_p": float(sp)})
            tests.append({"name": f"pearson:{a}|{b}", "p_value": float(rp)})
    pairs.sort(key=lambda d: (-abs(d["pearson"]), d["a"], d["b"]))
    return {"columns": cols, "pairs": pairs, "tests": tests}


def _discretize(s: pd.Series, bins: int, numeric: bool) -> pd.Series:
    if numeric:
        x = pd.to_numeric(s, errors="coerce")
        try:
            return pd.qcut(x, q=bins, labels=False, duplicates="drop").astype("float64")
        except ValueError:
            return x
    lab = labels(s).where(s.notna(), None)
    top = lab.value_counts().index[:20]
    return lab.where(lab.isin(top) | lab.isna(), "(other)")


def mutual_info(x: pd.Series, y: pd.Series) -> float:
    """Mutual information (nats) between two discrete series, over rows where both are present."""
    ok = x.notna().to_numpy() & y.notna().to_numpy()
    xc, _ = pd.factorize(x[ok], sort=True)
    yc, ny = pd.factorize(y[ok], sort=True)
    if not len(xc):
        return 0.0
    k = int(xc.max()) + 1
    joint = np.bincount(xc * len(ny) + yc, minlength=k * len(ny)).reshape(k, len(ny)).astype("float64")
    total = joint.sum()
    if total == 0:
        return 0.0
    pxy = joint / total
    px = pxy.sum(axis=1, keepdims=True)
    py = pxy.sum(axis=0, keepdims=True)
    nz = pxy > 0
    return float((pxy[nz] * np.log(pxy[nz] / (px @ py)[nz])).sum())


class MutualInformationParams(Params):
    target: str
    features: Optional[List[str]] = None
    bins: int = 10


@analysis_tool(name="mutual_information", category="relationships", version="1.0.0",
               params=MutualInformationParams,
               columns={"target": TARGET_ROLES, "features": FEATURE_ROLES})
def mutual_information(df: pd.DataFrame, p: MutualInformationParams, ctx: ToolContext) -> dict:
    """Mutual information between each feature (numeric binned into quantiles) and the target."""
    feats = p.features or [c for c in ctx.columns(FEATURE_ROLES) if c != p.target]
    y = labels(df[p.target]).where(df[p.target].notna(), None)
    hy = mutual_info(y, y)
    out = []
    for col in feats:
        x = _discretize(df[col], p.bins, ctx.roles.get(col) in NUMERIC_ROLES)
        mi = mutual_info(x, y)
        out.append({"feature": col, "mi": mi, "normalized_mi": mi / hy if hy > 0 else 0.0})
    out.sort(key=lambda d: (-d["mi"], d["feature"]))
    return {"target": p.target, "target_entropy": hy, "features": out}


def two_group_rates(pos_a: int, n_a: int, pos_b: int, n_b: int) -> dict:
    """Rates, ratio and a 2×2 test (Fisher below 5 expected per cell, else chi-square)."""
    table = np.array([[pos_a, n_a - pos_a], [pos_b, n_b - pos_b]], dtype=float)
    rate_a = pos_a / n_a if n_a else None
    rate_b = pos_b / n_b if n_b else None
    ratio = (rate_a / rate_b) if rate_a is not None and rate_b else None
    if n_a == 0 or n_b == 0 or table.sum(axis=0).min() == 0:
        p, test = None, "none"
    else:
        expected = stats.contingency.expected_freq(table)
        if expected.min() < 5:
            _, p = stats.fisher_exact(table)
            test = "fisher"
        else:
            _, p, _, _ = stats.chi2_contingency(table, correction=False)
            test = "chi2"
    return {"rate_a": rate_a, "rate_b": rate_b, "ratio": ratio, "p_value": None if p is None else float(p), "test": test}


class MissingnessTargetParams(Params):
    target: str
    columns: Optional[List[str]] = None
    positive: Optional[str] = None


@analysis_tool(name="compare_target_rates_by_missingness", category="relationships", version="1.0.0",
               params=MissingnessTargetParams, columns={"target": frozenset({"binary_target"}), "columns": ALL_ROLES})
def compare_target_rates_by_missingness(df: pd.DataFrame, p: MissingnessTargetParams, ctx: ToolContext) -> dict:
    """Target rate where each column is missing versus present, for columns 1–99% missing."""
    y, positive = as_bool_target(df[p.target], p.positive or ctx.positive)
    rows = len(df)
    cols = p.columns or [c for c in df.columns if c != p.target]
    out, tests = [], []
    for col in cols:
        miss = df[col].isna() & y.notna()
        pres = df[col].notna() & y.notna()
        n_m, n_p = int(miss.sum()), int(pres.sum())
        if not rows or not (0.01 <= df[col].isna().mean() <= 0.99) or n_m < ctx.min_cell or n_p < ctx.min_cell:
            continue
        pos_m, pos_p = int(y[miss].sum()), int(y[pres].sum())
        t = two_group_rates(pos_m, n_m, pos_p, n_p)
        out.append({"column": col, "n_missing": n_m, "n_present": n_p, "positives_missing": pos_m,
                    "positives_present": pos_p, "rate_missing": t["rate_a"], "rate_present": t["rate_b"],
                    "ratio": t["ratio"], "p_value": t["p_value"], "test": t["test"]})
        if t["p_value"] is not None:
            tests.append({"name": f"missing:{col}", "p_value": t["p_value"]})
    out.sort(key=lambda d: (-(d["ratio"] or 0), d["column"]))
    return {"target": p.target, "positive": positive, "columns": out, "tests": tests}


class PartialCorrelationParams(Params):
    x: str
    y: str
    control: str


@analysis_tool(name="partial_correlation", category="relationships", version="1.0.0",
               params=PartialCorrelationParams,
               columns={"x": NUMERIC_ROLES, "y": NUMERIC_ROLES, "control": NUMERIC_ROLES})
def partial_correlation(df: pd.DataFrame, p: PartialCorrelationParams, ctx: ToolContext) -> dict:
    """Pearson correlation of x and y after removing the linear effect of a control column."""
    sub = df[[p.x, p.y, p.control]].apply(pd.to_numeric, errors="coerce").dropna()
    n = int(len(sub))
    r_xy = float(sub[p.x].corr(sub[p.y]))
    r_xz = float(sub[p.x].corr(sub[p.control]))
    r_yz = float(sub[p.y].corr(sub[p.control]))
    denom = math.sqrt(max(0.0, (1 - r_xz ** 2) * (1 - r_yz ** 2)))
    partial = (r_xy - r_xz * r_yz) / denom if denom > 0 else None
    pval = None
    if partial is not None and n > 3 and abs(partial) < 1:
        t = partial * math.sqrt((n - 3) / (1 - partial ** 2))
        pval = float(2 * stats.t.sf(abs(t), df=n - 3))
    return {"x": p.x, "y": p.y, "control": p.control, "n": n, "correlation": r_xy,
            "partial_correlation": partial, "abs_partial": abs(partial) if partial is not None else None,
            "p_value": pval, "tests": ([{"name": "partial", "p_value": pval}] if pval is not None else [])}
