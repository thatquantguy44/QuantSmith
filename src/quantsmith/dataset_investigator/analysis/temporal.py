"""Temporal tools. Spec ``0099`` (REQ-004, REQ-006).

Per-period volume, metric and target-rate series with trend tests;
distribution shift (KS and PSI) with a scanned breakpoint; target drift; rates
and counts by hour, weekday, or month; and how a category mix differs between
a time window and the rest. A scanned breakpoint's p-value is
Bonferroni-corrected for the number of candidate splits scanned, because the
largest of several KS statistics is not an ordinary KS statistic. Above
``SCAN_ROWS`` rows the breakpoint is chosen on a seeded sample and every
reported statistic is then computed on all rows at that breakpoint.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Literal, Optional

import numpy as np
import pandas as pd
from scipy import stats

from .registry import Params, ToolContext, analysis_tool
from .relationships import two_group_rates
from .utils import (
    CATEGORICAL_ROLES,
    NUMERIC_ROLES,
    TIME_ROLES,
    as_bool_target,
    labels,
    to_datetime,
)

PSI_EPS = 1e-6
SCAN_ROWS = 100_000
PARTS = {"hour": 24, "weekday": 7, "month": 12}


def psi(expected: np.ndarray, actual: np.ndarray) -> float:
    """Population stability index between two count vectors over the same bins."""
    e = expected / expected.sum() if expected.sum() else expected
    a = actual / actual.sum() if actual.sum() else actual
    e = np.clip(e, PSI_EPS, None)
    a = np.clip(a, PSI_EPS, None)
    return float(((a - e) * np.log(a / e)).sum())


def _bucket(t: pd.Series, part: str) -> pd.Series:
    if part == "hour":
        return t.dt.hour
    if part == "weekday":
        return t.dt.dayofweek
    return t.dt.month - 1


def _trend(values: List[float]) -> Optional[Dict[str, float]]:
    if len(values) < 3 or np.ptp(values) == 0:
        return None
    x = np.arange(len(values), dtype="float64")
    fit = stats.linregress(x, np.asarray(values, dtype="float64"))
    first, last = fit.intercept, fit.intercept + fit.slope * (len(values) - 1)
    return {"slope": float(fit.slope), "p_value": float(fit.pvalue), "r": float(fit.rvalue),
            "fitted_first": float(first), "fitted_last": float(last),
            "relative_change": float(last / first - 1) if first > 0 else None}


class TimeSeriesParams(Params):
    timestamp: str
    metric: Optional[str] = None
    target: Optional[str] = None
    freq: Optional[Literal["D", "W", "M"]] = None
    positive: Optional[str] = None


@analysis_tool(name="analyze_time_series", category="temporal", version="1.0.0", params=TimeSeriesParams,
               columns={"timestamp": TIME_ROLES, "metric": NUMERIC_ROLES, "target": frozenset({"binary_target"})})
def analyze_time_series(df: pd.DataFrame, p: TimeSeriesParams, ctx: ToolContext) -> dict:
    """Rows, metric mean and target rate per period, with a linear trend test on each series."""
    t = to_datetime(df[p.timestamp])
    valid = t.notna()
    span = (t[valid].max() - t[valid].min()).days if valid.any() else 0
    freq = p.freq or ("M" if span > 365 else "W" if span > 60 else "D")
    period = t[valid].dt.to_period(freq)
    frame = pd.DataFrame({"period": period})
    if p.metric:
        frame["metric"] = pd.to_numeric(df.loc[valid, p.metric], errors="coerce")
    if p.target:
        frame["y"], _ = as_bool_target(df.loc[valid, p.target], p.positive or ctx.positive)
    rows = []
    for per, part in frame.groupby("period", sort=True):
        n = int(len(part))
        row: Dict[str, Any] = {"period": str(per), "start": per.start_time.isoformat(), "n": n}
        if p.metric:
            row["metric_mean"] = float(part["metric"].mean()) if n >= ctx.min_cell else None
        if p.target:
            row["rate"] = float(part["y"].mean()) if n >= ctx.min_cell else None
        rows.append(row)
    out: Dict[str, Any] = {"timestamp": p.timestamp, "freq": freq, "periods": rows, "n_periods": len(rows),
                           "first": rows[0]["start"] if rows else None, "last": rows[-1]["start"] if rows else None,
                           "tests": []}
    for key, field in (("volume", "n"), ("metric", "metric_mean"), ("rate", "rate")):
        series = [r[field] for r in rows if r.get(field) is not None]
        tr = _trend(series) if rows and field in rows[0] else None
        out[f"trend_{key}"] = tr
        if tr:
            out["tests"].append({"name": f"trend_{key}", "p_value": tr["p_value"]})
    return out


class ShiftParams(Params):
    column: str
    timestamp: str
    split: Optional[str] = None
    bins: int = 10


@analysis_tool(name="detect_distribution_shift", category="temporal", version="1.0.0", params=ShiftParams,
               columns={"column": NUMERIC_ROLES | CATEGORICAL_ROLES, "timestamp": TIME_ROLES}, reveals_values=True)
def detect_distribution_shift(df: pd.DataFrame, p: ShiftParams, ctx: ToolContext) -> dict:
    """Whether a column's distribution changed over time: KS and PSI before/after a given or scanned breakpoint."""
    t = to_datetime(df[p.timestamp])
    numeric = ctx.roles.get(p.column) in NUMERIC_ROLES
    x = pd.to_numeric(df[p.column], errors="coerce") if numeric else labels(df[p.column])
    ok = t.notna() & (x.notna() if numeric else df[p.column].notna())
    t, x = t[ok], x[ok]
    if p.split:
        candidates = [pd.Timestamp(p.split)]
    else:
        candidates = sorted({t.quantile(q) for q in np.round(np.arange(0.2, 0.801, 0.05), 2)})
    ts, xs = t, x
    if len(t) > SCAN_ROWS and len(candidates) > 1:
        pick = np.sort(np.random.default_rng(ctx.seed).choice(len(t), size=SCAN_ROWS, replace=False))
        ts, xs = t.iloc[pick], x.iloc[pick]
    best = None
    for split in candidates:
        before, after = xs[ts < split], xs[ts >= split]
        if len(before) < ctx.min_n or len(after) < ctx.min_n:
            continue
        if numeric:
            res = stats.ks_2samp(before.to_numpy(), after.to_numpy())
            stat, pval = float(res.statistic), float(res.pvalue)
        else:
            cats = sorted(set(before) | set(after))
            tab = np.array([[int((before == c).sum()) for c in cats], [int((after == c).sum()) for c in cats]])
            tab = tab[:, tab.sum(axis=0) > 0]
            _, pval, _, _ = stats.chi2_contingency(tab, correction=False)
            stat = float(psi(tab[0].astype(float), tab[1].astype(float)))
        if best is None or stat > best[0] + 1e-15:
            best = (stat, pval, split)
    out: Dict[str, Any] = {"column": p.column, "timestamp": p.timestamp, "numeric": numeric,
                           "candidates_scanned": len(candidates), "scan_rows": int(len(ts)), "tests": []}
    if best is None:
        return {**out, "skipped": "too few rows on one side of every candidate split"}
    split = best[2]
    before, after = x[t < split], x[t >= split]
    if numeric:
        res = stats.ks_2samp(before.to_numpy(), after.to_numpy())
        stat, pval = float(res.statistic), float(res.pvalue)
    else:
        cats = sorted(set(before) | set(after))
        tab = np.array([[int((before == c).sum()) for c in cats], [int((after == c).sum()) for c in cats]])
        tab = tab[:, tab.sum(axis=0) > 0]
        _, pval, _, _ = stats.chi2_contingency(tab, correction=False)
        stat = float(psi(tab[0].astype(float), tab[1].astype(float)))
    p_adj_split = min(1.0, pval * len(candidates))
    out.update({"breakpoint": pd.Timestamp(split).isoformat(), "n_before": int(len(before)), "n_after": int(len(after)),
                "p_value": p_adj_split, "p_value_unscanned": pval})
    if numeric:
        b, a = before.to_numpy(dtype="float64"), after.to_numpy(dtype="float64")
        edges = np.unique(np.quantile(b, np.linspace(0, 1, p.bins + 1)))
        edges[0], edges[-1] = -np.inf, np.inf
        hb, ha = np.histogram(b, edges)[0], np.histogram(a, edges)[0]
        pooled = math.sqrt(((b.size - 1) * b.var(ddof=1) + (a.size - 1) * a.var(ddof=1)) / (b.size + a.size - 2))
        lo, hi = np.quantile(np.concatenate([b, a]), [0.01, 0.99])
        fig_edges = np.linspace(lo, hi, 21) if hi > lo else np.array([lo, lo + 1])
        out.update({"ks": stat, "psi": psi(hb.astype(float), ha.astype(float)),
                    "mean_before": float(b.mean()), "mean_after": float(a.mean()), "pooled_std": pooled,
                    "shift_sd": (float(a.mean() - b.mean()) / pooled) if pooled > 0 else None,
                    "abs_shift_sd": abs(float(a.mean() - b.mean()) / pooled) if pooled > 0 else None,
                    "histogram": {"edges": fig_edges.tolist(),
                                  "before": np.histogram(b, fig_edges)[0].tolist(),
                                  "after": np.histogram(a, fig_edges)[0].tolist()}})
    else:
        out.update({"psi": stat})
    out["tests"].append({"name": "shift", "p_value": p_adj_split})
    return out


class TargetShiftParams(Params):
    target: str
    timestamp: str
    split: str
    positive: Optional[str] = None


@analysis_tool(name="detect_target_shift", category="temporal", version="1.0.0", params=TargetShiftParams,
               columns={"target": frozenset({"binary_target"}), "timestamp": TIME_ROLES})
def detect_target_shift(df: pd.DataFrame, p: TargetShiftParams, ctx: ToolContext) -> dict:
    """Target rate before and after a date, with a 2×2 test."""
    t = to_datetime(df[p.timestamp])
    y, positive = as_bool_target(df[p.target], p.positive or ctx.positive)
    ok = t.notna() & y.notna()
    split = pd.Timestamp(p.split)
    before, after = y[ok & (t < split)], y[ok & (t >= split)]
    r = two_group_rates(int(after.sum()), int(len(after)), int(before.sum()), int(len(before)))
    ratio = r["ratio"]
    return {"target": p.target, "split": split.isoformat(), "positive": positive,
            "n_before": int(len(before)), "n_after": int(len(after)),
            "rate_before": r["rate_b"], "rate_after": r["rate_a"], "rate_ratio": ratio,
            "rate_change_abs": abs(ratio - 1) if ratio is not None else None, "p_value": r["p_value"],
            "tests": ([{"name": "target_shift", "p_value": r["p_value"]}] if r["p_value"] is not None else [])}


class PeriodRatesParams(Params):
    timestamp: str
    target: str
    part: Literal["hour", "weekday", "month"] = "hour"
    positive: Optional[str] = None


@analysis_tool(name="compare_period_rates", category="temporal", version="1.0.0", params=PeriodRatesParams,
               columns={"timestamp": TIME_ROLES, "target": frozenset({"binary_target"})})
def compare_period_rates(df: pd.DataFrame, p: PeriodRatesParams, ctx: ToolContext) -> dict:
    """Rows, positives and target rate by hour of day, weekday, or month, with a chi-square test."""
    t = to_datetime(df[p.timestamp])
    y, positive = as_bool_target(df[p.target], p.positive or ctx.positive)
    ok = t.notna() & y.notna()
    frame = pd.DataFrame({"b": _bucket(t[ok], p.part), "y": y[ok]})
    agg = frame.groupby("b", sort=True)["y"].agg(["count", "sum"])
    buckets = []
    for b in range(PARTS[p.part]):
        n = int(agg.loc[b, "count"]) if b in agg.index else 0
        pos = int(agg.loc[b, "sum"]) if b in agg.index else 0
        buckets.append({"bucket": b, "n": n, "positives": pos, "rate": (pos / n) if n >= ctx.min_cell else None})
    usable = [b for b in buckets if b["rate"] is not None]
    out: Dict[str, Any] = {"timestamp": p.timestamp, "target": p.target, "part": p.part, "positive": positive,
                           "n": int(ok.sum()), "overall_rate": float(frame["y"].mean()) if len(frame) else None,
                           "buckets": buckets, "tests": []}
    tab = np.array([[b["positives"], b["n"] - b["positives"]] for b in usable], dtype=float)
    if len(usable) >= 2 and tab.sum(axis=0).min() > 0:
        chi2, pval, _, _ = stats.chi2_contingency(tab, correction=False)
        out.update({"chi2": float(chi2), "chi2_p": float(pval)})
        out["tests"].append({"name": "chi2_buckets", "p_value": float(pval)})
    return out


class WindowCountsParams(Params):
    timestamp: str
    target: str
    part: Literal["hour", "weekday", "month"] = "hour"
    window: List[int]
    positive: Optional[str] = None


@analysis_tool(name="compare_window_counts", category="temporal", version="1.0.0", params=WindowCountsParams,
               columns={"timestamp": TIME_ROLES, "target": frozenset({"binary_target"})})
def compare_window_counts(df: pd.DataFrame, p: WindowCountsParams, ctx: ToolContext) -> dict:
    """Volume and positives per bucket inside a window (e.g. hours 1–4) against the rest, with binomial tests."""
    B = PARTS[p.part]
    window = sorted({int(w) for w in p.window if 0 <= int(w) < B})
    w = len(window)
    t = to_datetime(df[p.timestamp])
    y, positive = as_bool_target(df[p.target], p.positive or ctx.positive)
    ok = t.notna() & y.notna()
    inside = _bucket(t[ok], p.part).isin(window)
    yy = y[ok]
    rows_in, rows_out = int(inside.sum()), int((~inside).sum())
    pos_in, pos_out = int(yy[inside].sum()), int(yy[~inside].sum())
    out: Dict[str, Any] = {"timestamp": p.timestamp, "target": p.target, "part": p.part, "window": window,
                           "buckets_in_window": w, "buckets_total": B, "rows_window": rows_in, "rows_rest": rows_out,
                           "positives_window": pos_in, "positives_rest": pos_out, "positive": positive, "tests": []}
    if w == 0 or w == B:
        return {**out, "skipped": "window must contain some but not all buckets"}
    vol_in, vol_out = rows_in / w, rows_out / (B - w)
    pin, pout = pos_in / w, pos_out / (B - w)
    out.update({
        "volume_per_bucket_window": vol_in, "volume_per_bucket_rest": vol_out,
        "volume_ratio": vol_in / vol_out if vol_out else None,
        "positives_per_bucket_window": pin, "positives_per_bucket_rest": pout,
        "positives_ratio": pin / pout if pout else None,
        "rate_window": pos_in / rows_in if rows_in else None, "rate_rest": pos_out / rows_out if rows_out else None,
    })
    out["rate_ratio"] = (out["rate_window"] / out["rate_rest"]) if out["rate_window"] is not None and out["rate_rest"] else None
    share = w / B
    if pos_in + pos_out:
        out["p_positives"] = float(stats.binomtest(pos_in, pos_in + pos_out, share).pvalue)
        out["tests"].append({"name": "positives_share", "p_value": out["p_positives"]})
    if rows_in + rows_out:
        out["p_volume"] = float(stats.binomtest(rows_in, rows_in + rows_out, share).pvalue)
        out["tests"].append({"name": "volume_share", "p_value": out["p_volume"]})
    return out


def _composition(a: pd.Series, b: pd.Series, ctx: ToolContext) -> Dict[str, Any]:
    cats = sorted(set(a) | set(b))
    ca = np.array([int((a == c).sum()) for c in cats], dtype=float)
    cb = np.array([int((b == c).sum()) for c in cats], dtype=float)
    keep = (ca + cb) >= ctx.min_cell
    shares = [{"value": c, "share_a": ca[i] / ca.sum() if ca.sum() else None,
               "share_b": cb[i] / cb.sum() if cb.sum() else None}
              for i, c in enumerate(cats) if keep[i]]
    out: Dict[str, Any] = {"psi": psi(ca[keep], cb[keep]) if keep.sum() >= 2 else None, "shares": shares, "tests": []}
    tab = np.vstack([ca[keep], cb[keep]])
    if keep.sum() >= 2 and tab.sum(axis=1).min() > 0:
        _, pval, _, _ = stats.chi2_contingency(tab, correction=False)
        out["p_value"] = float(pval)
        out["tests"].append({"name": "composition", "p_value": float(pval)})
    return out


class WindowCompositionParams(Params):
    timestamp: str
    by: str
    part: Literal["hour", "weekday", "month"] = "hour"
    window: List[int]


@analysis_tool(name="compare_window_composition", category="temporal", version="1.0.0",
               params=WindowCompositionParams,
               columns={"timestamp": TIME_ROLES, "by": CATEGORICAL_ROLES}, reveals_values=True)
def compare_window_composition(df: pd.DataFrame, p: WindowCompositionParams, ctx: ToolContext) -> dict:
    """How the mix of a categorical column inside a time window differs from the rest (PSI, chi-square)."""
    t = to_datetime(df[p.timestamp])
    ok = t.notna() & df[p.by].notna()
    inside = _bucket(t[ok], p.part).isin(p.window)
    lab = labels(df.loc[ok, p.by])
    out = _composition(lab[~inside], lab[inside], ctx)
    return {"timestamp": p.timestamp, "by": p.by, "part": p.part, "window": sorted(p.window),
            "a": "rest", "b": "window", **out}


class PeriodCompositionParams(Params):
    timestamp: str
    by: str
    split: str


@analysis_tool(name="compare_period_composition", category="temporal", version="1.0.0",
               params=PeriodCompositionParams,
               columns={"timestamp": TIME_ROLES, "by": CATEGORICAL_ROLES}, reveals_values=True)
def compare_period_composition(df: pd.DataFrame, p: PeriodCompositionParams, ctx: ToolContext) -> dict:
    """How the mix of a categorical column after a date differs from before it (PSI, chi-square)."""
    t = to_datetime(df[p.timestamp])
    ok = t.notna() & df[p.by].notna()
    split = pd.Timestamp(p.split)
    lab = labels(df.loc[ok, p.by])
    after = t[ok] >= split
    out = _composition(lab[~after], lab[after], ctx)
    return {"timestamp": p.timestamp, "by": p.by, "split": split.isoformat(), "a": "before", "b": "after", **out}
