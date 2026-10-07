"""Segmentation tools. Spec ``0099`` (REQ-004, REQ-006).

Groups come from a categorical column or from quantile bands of a numeric one.
A group smaller than the minimum cell size is never reported on its own; it is
pooled into ``(small groups)`` and left out of comparisons.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats

from .registry import Params, ToolContext, analysis_tool
from .relationships import two_group_rates
from .utils import (
    CATEGORICAL_ROLES,
    ENTITY_ROLES,
    GROUPABLE_ROLES,
    NUMERIC_ROLES,
    as_bool_target,
    band,
    labels,
)

ALL_ROLES = frozenset({
    "identifier", "entity_identifier", "timestamp", "continuous_numeric", "discrete_numeric",
    "categorical", "boolean", "binary_target", "multiclass_target", "free_text", "constant",
})
SMALL = "(small groups)"


def groups_for(df: pd.DataFrame, col: str, ctx: ToolContext, bins: int) -> pd.Series:
    """Group labels for ``col``: quantile bands for numeric roles, labels otherwise."""
    if ctx.roles.get(col) in NUMERIC_ROLES and df[col].nunique(dropna=True) > bins:
        return band(df[col], bins)
    return labels(df[col])


def _group_order(labels: List[str]) -> List[str]:
    def key(lab: str):
        if lab.startswith("[") and "," in lab:
            try:
                return (0, float(lab[1:].split(",")[0]), lab)
            except ValueError:
                pass
        return (1, 0.0, lab)
    return sorted(labels, key=key)


class TargetRatesParams(Params):
    target: str
    by: str
    bins: int = 5
    reference: Optional[str] = None
    positive: Optional[str] = None


@analysis_tool(name="compare_target_rates", category="segmentation", version="1.0.0",
               params=TargetRatesParams,
               columns={"target": frozenset({"binary_target"}), "by": GROUPABLE_ROLES - {"binary_target"}},
               reveals_values=True)
def compare_target_rates(df: pd.DataFrame, p: TargetRatesParams, ctx: ToolContext) -> dict:
    """Target rate per group of one column, the most extreme group against the largest (reference) group."""
    y, positive = as_bool_target(df[p.target], p.positive or ctx.positive)
    g = groups_for(df, p.by, ctx, p.bins)
    valid = y.notna()
    frame = pd.DataFrame({"g": g[valid], "y": y[valid]})
    agg = frame.groupby("g", sort=False)["y"].agg(["count", "sum"])
    n_total = int(valid.sum())
    groups, small_n, small_pos = [], 0, 0
    for lab in _group_order([str(i) for i in agg.index]):
        n, pos = int(agg.loc[lab, "count"]), int(agg.loc[lab, "sum"])
        if n < ctx.min_cell:
            small_n, small_pos = small_n + n, small_pos + pos
            continue
        groups.append({"group": lab, "n": n, "positives": pos, "rate": pos / n, "share": n / n_total})
    overall = float(frame["y"].mean()) if n_total else None
    out: Dict[str, Any] = {"target": p.target, "by": p.by, "positive": positive, "n": n_total,
                           "overall_rate": overall, "groups": groups,
                           "small_groups": {"n": small_n, "positives": small_pos} if small_n else None,
                           "tests": []}
    if len(groups) < 2:
        return out
    table = np.array([[gr["positives"], gr["n"] - gr["positives"]] for gr in groups], dtype=float)
    if table.sum(axis=0).min() > 0:
        chi2, pval, dof, _ = stats.chi2_contingency(table, correction=False)
        out.update({"chi2": float(chi2), "chi2_dof": int(dof), "chi2_p": float(pval)})
        out["tests"].append({"name": "chi2_groups", "p_value": float(pval)})
    ref_label = p.reference if p.reference in {gr["group"] for gr in groups} else \
        min(groups, key=lambda gr: (-gr["n"], gr["group"]))["group"]
    ref = next(gr for gr in groups if gr["group"] == ref_label)
    others = [gr for gr in groups if gr["group"] != ref_label]

    def distance(gr: dict) -> float:
        if gr["rate"] == 0 or ref["rate"] == 0:
            return abs(gr["rate"] - ref["rate"]) * 1e6
        return abs(math.log(gr["rate"] / ref["rate"]))
    extreme = min(others, key=lambda gr: (-distance(gr), gr["group"]))
    t = two_group_rates(extreme["positives"], extreme["n"], ref["positives"], ref["n"])
    out.update({"reference": ref, "extreme": extreme, "extreme_ratio": t["ratio"],
                "extreme_p": t["p_value"], "extreme_test": t["test"]})
    if t["p_value"] is not None:
        out["tests"].append({"name": "extreme_vs_reference", "p_value": t["p_value"]})
    return out


class SegmentsParams(Params):
    metric: str
    by: str
    bins: int = 5


@analysis_tool(name="compare_segments", category="segmentation", version="1.0.0",
               params=SegmentsParams,
               columns={"metric": NUMERIC_ROLES, "by": GROUPABLE_ROLES}, reveals_values=True)
def compare_segments(df: pd.DataFrame, p: SegmentsParams, ctx: ToolContext) -> dict:
    """Mean and median of a numeric metric per group, with a Kruskal–Wallis test across groups."""
    x = pd.to_numeric(df[p.metric], errors="coerce")
    g = groups_for(df, p.by, ctx, p.bins)
    frame = pd.DataFrame({"g": g, "x": x}).dropna(subset=["x"])
    groups, samples, small = [], [], 0
    parts = {str(k): v for k, v in frame.groupby("g", sort=False)}
    for lab in _group_order(list(parts)):
        part = parts[lab]
        n = int(len(part))
        if n < ctx.min_cell:
            small += n
            continue
        groups.append({"group": str(lab), "n": n, "mean": float(part["x"].mean()), "median": float(part["x"].median())})
        samples.append(part["x"].to_numpy())
    out: Dict[str, Any] = {"metric": p.metric, "by": p.by, "groups": groups, "small_groups_n": small, "tests": []}
    if len(samples) >= 2 and all(s.size >= 2 for s in samples) and np.ptp(np.concatenate(samples)) > 0:
        h, pval = stats.kruskal(*samples)
        out.update({"kruskal_h": float(h), "kruskal_p": float(pval)})
        out["tests"].append({"name": "kruskal", "p_value": float(pval)})
    means = [gr["mean"] for gr in groups]
    if len(means) >= 2 and min(means) > 0:
        hi = max(groups, key=lambda gr: (gr["mean"], gr["group"]))
        lo = min(groups, key=lambda gr: (gr["mean"], gr["group"]))
        out.update({"high_group": hi, "low_group": lo, "mean_ratio": hi["mean"] / lo["mean"]})
    return out


def _gini(counts: np.ndarray) -> float:
    if counts.size == 0 or counts.sum() == 0:
        return 0.0
    x = np.sort(counts.astype("float64"))
    n = x.size
    return float((2 * np.arange(1, n + 1) - n - 1).dot(x) / (n * x.sum()))


class EntityConcentrationParams(Params):
    entity: str
    target: Optional[str] = None
    value: Optional[str] = None
    subset_column: Optional[str] = None
    subset_value: Optional[str] = None
    positive: Optional[str] = None


@analysis_tool(name="analyze_entity_concentration", category="segmentation", version="1.0.0",
               params=EntityConcentrationParams,
               columns={"entity": ENTITY_ROLES, "target": frozenset({"binary_target"}),
                        "value": NUMERIC_ROLES, "subset_column": CATEGORICAL_ROLES | NUMERIC_ROLES})
def analyze_entity_concentration(df: pd.DataFrame, p: EntityConcentrationParams, ctx: ToolContext) -> dict:
    """How concentrated rows, target positives, and value are among the entities (top 1% and 10% shares, Gini)."""
    data = df
    if p.subset_column is not None:
        data = df[labels(df[p.subset_column]) == str(p.subset_value)]
    data = data[data[p.entity].notna()]
    counts = data.groupby(p.entity, sort=True).size().to_numpy()
    n_ent = int(counts.size)
    out: Dict[str, Any] = {"entity": p.entity, "rows": int(len(data)), "n_entities": n_ent,
                           "subset": {"column": p.subset_column, "value": p.subset_value} if p.subset_column else None}
    if n_ent == 0:
        return out
    k1, k10 = max(1, math.ceil(0.01 * n_ent)), max(1, math.ceil(0.10 * n_ent))
    srt = np.sort(counts)[::-1]
    out.update({"rows_per_entity_mean": float(counts.mean()), "rows_per_entity_median": float(np.median(counts)),
                "rows_per_entity_max": int(counts.max()),
                "top1pct_entities": k1, "top1pct_row_share": float(srt[:k1].sum() / srt.sum()),
                "top10pct_row_share": float(srt[:k10].sum() / srt.sum()), "row_gini": _gini(counts)})
    if p.target is not None:
        y, positive = as_bool_target(data[p.target], p.positive or ctx.positive)
        pos = pd.DataFrame({"e": data[p.entity], "y": y}).dropna().groupby("e", sort=True)["y"].sum().to_numpy()
        total = float(pos.sum())
        ps = np.sort(pos)[::-1]
        out.update({"positive": positive, "positives": int(total),
                    "entities_with_positive": int((pos > 0).sum()),
                    "top1pct_positive_share": float(ps[:k1].sum() / total) if total else None,
                    "top10pct_positive_share": float(ps[:k10].sum() / total) if total else None})
    if p.value is not None:
        v = pd.DataFrame({"e": data[p.entity], "v": pd.to_numeric(data[p.value], errors="coerce")}).dropna()
        sums = np.sort(v.groupby("e", sort=True)["v"].sum().to_numpy())[::-1]
        total_v = float(sums.sum())
        out.update({"value": p.value, "top1pct_value_share": float(sums[:k1].sum() / total_v) if total_v > 0 else None})
    return out


class StratifiedParams(Params):
    target: str
    by: str
    strata: str
    exposed: Optional[str] = None
    reference: Optional[str] = None
    missing_indicator: bool = False
    bins: int = 4
    positive: Optional[str] = None


@analysis_tool(name="stratified_target_rates", category="segmentation", version="1.0.0",
               params=StratifiedParams,
               columns={"target": frozenset({"binary_target"}), "by": ALL_ROLES - {"binary_target"},
                        "strata": GROUPABLE_ROLES - {"binary_target"}},
               reveals_values=True)
def stratified_target_rates(df: pd.DataFrame, p: StratifiedParams, ctx: ToolContext) -> dict:
    """Target rate of an exposed group against a reference group within strata of another column (Mantel–Haenszel)."""
    y, positive = as_bool_target(df[p.target], p.positive or ctx.positive)
    if p.missing_indicator:
        exposed = df[p.by].isna()
        reference = df[p.by].notna()
        exp_label, ref_label = f"{p.by} missing", f"{p.by} present"
    else:
        lab = labels(df[p.by])
        exposed, reference = lab == str(p.exposed), lab == str(p.reference)
        exp_label, ref_label = str(p.exposed), str(p.reference)
    strata = groups_for(df, p.strata, ctx, p.bins)
    valid = y.notna() & (exposed | reference)
    frame = pd.DataFrame({"s": strata[valid], "e": exposed[valid].astype(int), "y": y[valid]})
    num = den = 0.0
    cmh_num = cmh_var = 0.0
    shown, ratios = [], []
    for s_lab in _group_order([str(v) for v in frame["s"].unique()]):
        part = frame[frame["s"] == s_lab]
        e, r = part[part["e"] == 1], part[part["e"] == 0]
        n1, n0 = len(e), len(r)
        a, c = float(e["y"].sum()), float(r["y"].sum())
        N = n1 + n0
        if n1 == 0 or n0 == 0:
            continue
        num += a * n0 / N
        den += c * n1 / N
        m1, m0 = a + c, N - (a + c)
        if N > 1:
            cmh_num += a - n1 * m1 / N
            cmh_var += n1 * n0 * m1 * m0 / (N * N * (N - 1))
        if n1 >= ctx.min_cell and n0 >= ctx.min_cell:
            rr = (a / n1) / (c / n0) if c > 0 else None
            shown.append({"stratum": s_lab, "n_exposed": n1, "n_reference": n0,
                          "rate_exposed": a / n1, "rate_reference": c / n0, "ratio": rr})
            if rr is not None:
                ratios.append(rr)
    e_all, r_all = frame[frame["e"] == 1], frame[frame["e"] == 0]
    crude = None
    if len(e_all) and len(r_all) and r_all["y"].mean() > 0:
        crude = float(e_all["y"].mean() / r_all["y"].mean())
    mh = (num / den) if den > 0 else None
    pval = None
    if cmh_var > 0:
        stat = (abs(cmh_num) - 0.5) ** 2 / cmh_var
        pval = float(stats.chi2.sf(stat, 1))
    return {"target": p.target, "by": p.by, "strata_column": p.strata, "positive": positive,
            "exposed": exp_label, "reference": ref_label, "n_exposed": int(len(e_all)), "n_reference": int(len(r_all)),
            "crude_ratio": crude, "mh_rate_ratio": mh, "cmh_p_value": pval, "strata": shown,
            "share_strata_ratio_above_1": (sum(r > 1 for r in ratios) / len(ratios)) if ratios else None,
            "tests": ([{"name": "cmh", "p_value": pval}] if pval is not None else [])}
