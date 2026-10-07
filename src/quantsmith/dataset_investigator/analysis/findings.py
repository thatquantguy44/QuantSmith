"""Candidate findings, interestingness, and multiple-testing adjustment.
Spec ``0099`` (REQ-007).

A *rule* reads one tool result and emits candidate findings. Rules are pure
functions of the result, so the validator can re-run the tool and re-derive
the same finding to prove it reproduces (REQ-010). Claims are written from the
evidence by templates; every number in a claim comes from its evidence, and
names and labels are wrapped in backticks.

Interestingness is ``I = (w_M·M + w_S·S + w_P·P + w_A·A) / Σw``:

* **M** magnitude, kind-specific and in [0, 1] (e.g. ``1 − 1/ratio`` for a rate ratio);
* **S** support, ``min(1, −log10(p_BH)/10)`` from the Benjamini–Hochberg-adjusted
  p-value over every test in the run (0.5 for a descriptive finding with no test);
* **P** prevalence, the share of rows the finding concerns;
* **A** actionability, a prior per kind (:data:`ACTIONABILITY`).
"""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional, Tuple

from .models import Finding, InvestigationState, Score, ToolExecution
from .registry import spec
from .relationships import two_group_rates
from .utils import sha256_json

ACTIONABILITY = {
    "target_rate_gap": 0.9, "missingness_target": 0.8, "period_rate_window": 0.8, "distribution_shift": 0.8,
    "trend": 0.7, "entity_concentration": 0.7, "segment_gap": 0.6, "multivariate_outliers": 0.6,
    "multivariate_regimes": 0.5,
    "correlation": 0.5, "outlier_heavy": 0.4, "skewed_distribution": 0.3,
    "target_imbalance": 0.6, "duplicate_rows": 0.6, "duplicate_ids": 0.7, "missing_values": 0.6,
    "constant_column": 0.4, "near_constant_column": 0.3, "negative_values": 0.7, "mixed_types": 0.5,
    "high_cardinality": 0.3, "timestamp_issue": 0.6,
}
DESCRIPTIVE_SUPPORT = 0.5
RATIO_MIN = 1.5
REGIME_SHARE = 0.05  # above this share, "outliers" are a second population, not anomalies


def pct(x: float, d: int = 2) -> str:
    return f"{x * 100:.{d}f}%"


def num(x: float, d: int = 2) -> str:
    """Fixed decimals with thousands separators; three significant figures when that would print zero."""
    if x != 0 and abs(x) < 0.5 * 10 ** (-d):
        return f"{x:.3g}"
    return f"{x:,.{d}f}"


def _finding(ex: ToolExecution, kind: str, family: str, claim: str, subject: Dict[str, Any],
             evidence: Dict[str, Any], *, n: int, magnitude: float, prevalence: float,
             test: Optional[str] = None, p_value: Optional[float] = None, quality: bool = False,
             method: str = "") -> Finding:
    s = spec(ex.tool)
    key = f"{kind}:{ex.execution_id}:{sha256_json(subject)[:8]}"
    return Finding(
        key=key, kind=kind, family=family, quality=quality, claim=claim, subject=subject, evidence=evidence,
        method=method or s.description, module=f"dataset_analysis.{s.module}", function=s.function,
        tool=ex.tool, version=ex.version, params=ex.params, execution_id=ex.execution_id,
        test=test, p_value=p_value, n=int(n), magnitude=float(max(0.0, min(1.0, magnitude))),
        prevalence=float(max(0.0, min(1.0, prevalence))),
    )


def _ratio_magnitude(r: Optional[float]) -> float:
    if not r or r <= 0:
        return 0.0
    big = max(r, 1 / r)
    return 1 - 1 / big


# --- rules: one per tool -------------------------------------------------------

def _r_duplicates(ex, res, st):
    out = []
    if res["duplicate_rows"]:
        out.append(_finding(ex, "duplicate_rows", "quality",
                            f"{res['duplicate_rows']:,} rows ({pct(res['duplicate_rows_pct'])}) are exact duplicates.",
                            {}, {"duplicate_rows": res["duplicate_rows"], "duplicate_rows_pct": res["duplicate_rows_pct"]},
                            n=res["rows"], magnitude=min(1, res["duplicate_rows_pct"] * 10),
                            prevalence=res["duplicate_rows_pct"], quality=True))
    for d in res["identifiers"]:
        if d["duplicate_rows"]:
            out.append(_finding(ex, "duplicate_ids", "quality",
                                f"`{d['column']}` repeats: {d['duplicate_rows']:,} rows reuse an id already seen "
                                f"({d['ids_repeated']:,} ids appear more than once).",
                                {"column": d["column"]}, {"duplicate_rows": d["duplicate_rows"], "ids_repeated": d["ids_repeated"]},
                                n=res["rows"], magnitude=min(1, d["duplicate_rows"] / max(res["rows"], 1) * 10),
                                prevalence=d["duplicate_rows"] / max(res["rows"], 1), quality=True))
    return out


def _r_missingness(ex, res, st):
    warn = st.config.missing_warn
    return [_finding(ex, "missing_values", "quality", f"`{c['column']}` is missing in {pct(c['missing_pct'])} of rows.",
                     {"column": c["column"]}, {"missing": c["missing"], "missing_pct": c["missing_pct"]},
                     n=res["rows"], magnitude=c["missing_pct"], prevalence=c["missing_pct"], quality=True)
            for c in res["columns"] if c["missing_pct"] >= warn]


def _r_column_quality(ex, res, st):
    rows = max(res["rows"], 1)
    out = []
    for c in res["constant"]:
        out.append(_finding(ex, "constant_column", "quality", f"`{c['column']}` is constant.",
                            {"column": c["column"]}, {"n_unique": c["n_unique"]}, n=rows, magnitude=0.5,
                            prevalence=1.0, quality=True))
    for c in res["near_constant"]:
        out.append(_finding(ex, "near_constant_column", "quality",
                            f"`{c['column']}` is nearly constant: one value covers {pct(c['top_share'])} of rows.",
                            {"column": c["column"]}, {"top_share": c["top_share"]}, n=rows, magnitude=c["top_share"],
                            prevalence=1.0, quality=True))
    for c in res["negative_in_nonnegative"]:
        out.append(_finding(ex, "negative_values", "quality",
                            f"`{c['column']}` has {c['negative']:,} negative values ({pct(c['negative_pct'])}), "
                            f"which its name suggests are impossible.",
                            {"column": c["column"]}, {"negative": c["negative"], "negative_pct": c["negative_pct"]},
                            n=rows, magnitude=min(1, c["negative_pct"] * 10), prevalence=c["negative_pct"], quality=True))
    for c in res["mixed_types"]:
        out.append(_finding(ex, "mixed_types", "quality",
                            f"`{c['column']}` mixes types: {pct(c['numeric_like_share'])} of values are numbers and "
                            f"{c['non_numeric']:,} are not.",
                            {"column": c["column"]}, {"numeric_like_share": c["numeric_like_share"], "non_numeric": c["non_numeric"]},
                            n=rows, magnitude=0.5, prevalence=1.0, quality=True))
    for c in res["high_cardinality_categoricals"]:
        out.append(_finding(ex, "high_cardinality", "quality",
                            f"`{c['column']}` has {c['n_unique']:,} distinct values ({pct(c['unique_ratio'])} unique).",
                            {"column": c["column"]}, {"n_unique": c["n_unique"], "unique_ratio": c["unique_ratio"]},
                            n=rows, magnitude=c["unique_ratio"], prevalence=1.0, quality=True))
    for c in res["timestamp_issues"]:
        parts, ev = [], {}
        if c.get("before_1900"):
            ev["cutoff_year"] = 1900
        for key, text in (("after_as_of", "after the as-of date"), ("before_1900", "before 1900"), ("unparseable", "unparseable")):
            if c.get(key):
                parts.append(f"{c[key]:,} {text}")
                ev[key] = c[key]
        bad = sum(c.get(k) or 0 for k in ("after_as_of", "before_1900", "unparseable"))
        out.append(_finding(ex, "timestamp_issue", "quality", f"`{c['column']}` has impossible timestamps: {', '.join(parts)}.",
                            {"column": c["column"], "as_of": c.get("as_of")}, ev, n=rows,
                            magnitude=min(1, bad / rows * 10), prevalence=bad / rows, quality=True))
    return out


def _r_target_balance(ex, res, st):
    rate = res.get("positive_rate")
    if rate is None or rate >= 0.1:
        return []
    return [_finding(ex, "target_imbalance", "quality",
                     f"`{res['target']}` is imbalanced: {pct(rate)} of rows are `{res['positive']}`.",
                     {"target": res["target"], "positive": res["positive"]},
                     {"positive_rate": rate, "positives": res["positives"], "n": res["n"]},
                     n=res["n"], magnitude=1 - rate * 10, prevalence=1.0, quality=True)]


def _r_distributions(ex, res, st):
    out = []
    for c in res["columns"]:
        skew = c.get("skew")
        if skew is None or abs(skew) < 2 or c["count"] < st.config.min_n:
            continue
        side = "right" if skew > 0 else "left"
        ev = {"skew": skew, "count": c["count"], "median": c["median"], "mean": c["mean"]}
        claim = f"`{c['column']}` is heavily {side}-skewed (skew {num(skew, 1)}; mean {num(c['mean'])} vs median {num(c['median'])})"
        if c.get("top1pct_share_of_total") is not None:
            ev["top1pct_share_of_total"] = c["top1pct_share_of_total"]
            ev["top_fraction"] = 0.01
            claim += f"; the top 1% of values hold {pct(c['top1pct_share_of_total'], 1)} of the total"
        out.append(_finding(ex, "skewed_distribution", "distributions", claim + ".", {"column": c["column"]}, ev,
                            n=c["count"], magnitude=min(1, abs(skew) / 10), prevalence=1.0))
    return out


def _r_outliers(ex, res, st):
    out = []
    for c in res["columns"]:
        if c.get("skipped") or c["outlier_pct"] < 0.01 or (c.get("excess_ratio") or 0) < 10:
            continue
        if c.get("skew") is not None and abs(c["skew"]) >= 2:
            continue  # a heavy tail, already reported as a skewed distribution
        out.append(_finding(ex, "outlier_heavy", "anomalies",
                            f"`{c['column']}` has {c['outliers']:,} values ({pct(c['outlier_pct'])}) beyond a robust "
                            f"z-score of {num(res['threshold'], 1)}, {num(c['excess_ratio'], 0)}× the share a normal distribution gives.",
                            {"column": c["column"]},
                            {"outliers": c["outliers"], "outlier_pct": c["outlier_pct"], "threshold": res["threshold"],
                             "excess_ratio": c["excess_ratio"], "n": c["n"]},
                            n=c["n"], magnitude=min(1, c["outlier_pct"] * 10), prevalence=c["outlier_pct"]))
    return out


def _r_multivariate(ex, res, st):
    if res.get("skipped") or res["method"] != "mahalanobis":
        return []
    expected = res["expected_pct"]
    if res["outliers"] < st.config.min_cell or res["outlier_pct"] < 5 * expected:
        return []
    if res["outlier_pct"] > REGIME_SHARE:
        return [_finding(ex, "multivariate_regimes", "anomalies",
                         f"{res['outliers']:,} rows ({pct(res['outlier_pct'])}) lie outside the robust core of "
                         f"{len(res['columns'])} numeric columns: too many to be isolated outliers, so the rows "
                         f"likely come from more than one regime.",
                         {"columns": res["columns"]},
                         {"outliers": res["outliers"], "outlier_pct": res["outlier_pct"], "n": res["n"],
                          "n_columns": len(res["columns"]), "regime_share_threshold": REGIME_SHARE},
                         n=res["n"], magnitude=min(1, res["outlier_pct"] * 2), prevalence=res["outlier_pct"])]
    return [_finding(ex, "multivariate_outliers", "anomalies",
                     f"{res['outliers']:,} rows ({pct(res['outlier_pct'])}) are multivariate outliers across "
                     f"{len(res['columns'])} numeric columns (robust Mahalanobis distance), "
                     f"{num(res['outlier_pct'] / expected, 0)}× the expected share.",
                     {"columns": res["columns"]},
                     {"outliers": res["outliers"], "outlier_pct": res["outlier_pct"], "expected_pct": expected,
                      "excess_ratio": res["outlier_pct"] / expected, "n": res["n"], "n_columns": len(res["columns"])},
                     n=res["n"], magnitude=min(1, res["outlier_pct"] * 10), prevalence=res["outlier_pct"])]


def _r_correlations(ex, res, st):
    rows = max(st.dataset.rows, 1)
    out = []
    for c in res["pairs"]:
        if abs(c["pearson"]) < 0.5 or c["n"] < st.config.min_n:
            continue
        out.append(_finding(ex, "correlation", "relationships",
                            f"`{c['a']}` and `{c['b']}` are correlated (Pearson {num(c['pearson'])}, Spearman {num(c['spearman'])}).",
                            {"a": c["a"], "b": c["b"]},
                            {"pearson": c["pearson"], "spearman": c["spearman"], "n": c["n"]},
                            n=c["n"], magnitude=abs(c["pearson"]), prevalence=c["n"] / rows,
                            test=f"{ex.execution_id}:pearson:{c['a']}|{c['b']}", p_value=c["pearson_p"]))
    return out


def _r_target_rates(ex, res, st):
    ratio = res.get("extreme_ratio")
    if ratio is None or not (ratio >= RATIO_MIN or ratio <= 1 / RATIO_MIN):
        return []
    e, r = res["extreme"], res["reference"]
    if e["n"] < st.config.min_n or "(missing)" in (e["group"], r["group"]):
        return []  # missing versus present is the missingness rule's finding
    hi, lo = (e, r) if ratio >= 1 else (r, e)
    high_to_low = hi["rate"] / lo["rate"] if lo["rate"] else ratio
    claim = (f"The `{res['target']}` rate for `{res['by']}` = `{hi['group']}` is {num(high_to_low)}× that for "
             f"`{res['by']}` = `{lo['group']}` ({pct(hi['rate'])} vs {pct(lo['rate'])}).")
    # The subject names the higher-rate group "exposed", so every test of this gap expects a ratio above 1.
    return [_finding(ex, "target_rate_gap", "segmentation", claim,
                     {"target": res["target"], "by": res["by"], "exposed": hi["group"], "reference": lo["group"]},
                     {"rate_extreme": e["rate"], "rate_reference": r["rate"], "ratio": ratio,
                      "ratio_high_to_low": high_to_low,
                      "n_extreme": e["n"], "n_reference": r["n"], "positives_extreme": e["positives"],
                      "positives_reference": r["positives"], "overall_rate": res["overall_rate"]},
                     n=e["n"] + r["n"], magnitude=_ratio_magnitude(ratio), prevalence=e["share"],
                     test=f"{ex.execution_id}:extreme_vs_reference", p_value=res.get("extreme_p"),
                     method="Grouped target-rate comparison")]


def _r_missing_target(ex, res, st):
    out = []
    for c in res["columns"]:
        ratio = c["ratio"]
        if ratio is None or not (ratio >= RATIO_MIN or ratio <= 1 / RATIO_MIN):
            continue
        out.append(_finding(ex, "missingness_target", "relationships",
                            f"Rows where `{c['column']}` is missing have a `{res['target']}` rate {num(ratio)}× that of rows "
                            f"where it is present ({pct(c['rate_missing'])} vs {pct(c['rate_present'])}).",
                            {"target": res["target"], "column": c["column"]},
                            {"rate_missing": c["rate_missing"], "rate_present": c["rate_present"], "ratio": ratio,
                             "n_missing": c["n_missing"], "n_present": c["n_present"],
                             "positives_missing": c["positives_missing"], "positives_present": c["positives_present"]},
                            n=c["n_missing"] + c["n_present"], magnitude=_ratio_magnitude(ratio),
                            prevalence=c["n_missing"] / max(c["n_missing"] + c["n_present"], 1),
                            test=f"{ex.execution_id}:missing:{c['column']}", p_value=c["p_value"]))
    return out


def _r_segments(ex, res, st):
    ratio = res.get("mean_ratio")
    if ratio is None or ratio < RATIO_MIN:
        return []
    hi, lo = res["high_group"], res["low_group"]
    rows = max(st.dataset.rows, 1)
    return [_finding(ex, "segment_gap", "segmentation",
                     f"Mean `{res['metric']}` is {num(ratio)}× higher in `{res['by']}` = `{hi['group']}` than in "
                     f"`{res['by']}` = `{lo['group']}` ({num(hi['mean'])} vs {num(lo['mean'])}).",
                     {"metric": res["metric"], "by": res["by"], "high": hi["group"], "low": lo["group"]},
                     {"mean_high": hi["mean"], "mean_low": lo["mean"], "ratio": ratio, "n_high": hi["n"], "n_low": lo["n"]},
                     n=hi["n"] + lo["n"], magnitude=_ratio_magnitude(ratio), prevalence=(hi["n"] + lo["n"]) / rows,
                     test=f"{ex.execution_id}:kruskal", p_value=res.get("kruskal_p"))]


def _r_time_series(ex, res, st):
    out = []
    names = {"volume": "row volume", "metric": f"mean `{ex.params.get('metric')}`", "rate": f"`{ex.params.get('target')}` rate"}
    for key in ("volume", "metric", "rate"):
        tr = res.get(f"trend_{key}")
        if not tr or tr.get("relative_change") is None or abs(tr["relative_change"]) < 0.2:
            continue
        direction = "rises" if tr["relative_change"] > 0 else "falls"
        out.append(_finding(ex, "trend", "temporal",
                            f"{names[key][0].upper() + names[key][1:]} {direction} {pct(abs(tr['relative_change']), 1)} over "
                            f"{res['n_periods']} periods (fitted linear trend).",
                            {"series": key, "timestamp": res["timestamp"], "freq": res["freq"],
                             "column": ex.params.get("metric") if key == "metric" else ex.params.get("target") if key == "rate" else None},
                            {"relative_change": tr["relative_change"], "abs_relative_change": abs(tr["relative_change"]),
                             "slope": tr["slope"], "n_periods": res["n_periods"]},
                            n=sum(p["n"] for p in res["periods"]), magnitude=min(1, abs(tr["relative_change"])), prevalence=1.0,
                            test=f"{ex.execution_id}:trend_{key}", p_value=tr["p_value"]))
    return out


def _r_shift(ex, res, st):
    if res.get("skipped"):
        return []
    n = res["n_before"] + res["n_after"]
    date = res["breakpoint"][:10]
    if res["numeric"]:
        if res["ks"] < 0.1 or res["psi"] < 0.1:
            return []
        claim = (f"`{res['column']}` shifted at `{date}`: KS {num(res['ks'])}, PSI {num(res['psi'])}, mean "
                 f"{num(res['mean_before'])} before vs {num(res['mean_after'])} after "
                 f"({num(res['abs_shift_sd'])} standard deviations).")
        ev = {"ks": res["ks"], "psi": res["psi"], "mean_before": res["mean_before"], "mean_after": res["mean_after"],
              "abs_shift_sd": res["abs_shift_sd"], "n_before": res["n_before"], "n_after": res["n_after"]}
        mag = max(res["ks"], min(1.0, res["psi"] / 0.5))
    else:
        if res["psi"] < 0.1:
            return []
        claim = f"The mix of `{res['column']}` shifted at `{date}` (PSI {num(res['psi'])})."
        ev = {"psi": res["psi"], "n_before": res["n_before"], "n_after": res["n_after"]}
        mag = min(1.0, res["psi"] / 0.5)
    return [_finding(ex, "distribution_shift", "temporal", claim,
                     {"column": res["column"], "timestamp": res["timestamp"], "breakpoint": res["breakpoint"], "date": date},
                     ev, n=n, magnitude=mag, prevalence=res["n_after"] / max(n, 1),
                     test=f"{ex.execution_id}:shift", p_value=res["p_value"])]


def best_window(buckets: List[Dict[str, Any]], overall: float, min_cell: int) -> Optional[Tuple[List[int], Dict[str, Any]]]:
    """The longest run of consecutive buckets whose rate is at least 1.5× the overall rate."""
    hot = [b["bucket"] for b in buckets if b["rate"] is not None and overall and b["rate"] >= RATIO_MIN * overall]
    runs, run = [], []
    for b in hot:
        if run and b == run[-1] + 1:
            run.append(b)
        else:
            if run:
                runs.append(run)
            run = [b]
    if run:
        runs.append(run)
    if not runs:
        return None
    by = {b["bucket"]: b for b in buckets}
    def stats_for(r):
        n_in = sum(by[b]["n"] for b in r)
        pos_in = sum(by[b]["positives"] for b in r)
        n_out = sum(b["n"] for b in buckets) - n_in
        pos_out = sum(b["positives"] for b in buckets) - pos_in
        return n_in, pos_in, n_out, pos_out
    best = min(runs, key=lambda r: (-stats_for(r)[1], r[0]))
    n_in, pos_in, n_out, pos_out = stats_for(best)
    if n_in < min_cell or n_out < min_cell:
        return None
    t = two_group_rates(pos_in, n_in, pos_out, n_out)
    return best, {"n_window": n_in, "positives_window": pos_in, "n_rest": n_out, "positives_rest": pos_out, **t}


def _r_period_rates(ex, res, st):
    found = best_window(res["buckets"], res["overall_rate"], st.config.min_cell)
    if not found:
        return []
    window, w = found
    if w["ratio"] is None or w["ratio"] < RATIO_MIN:
        return []
    start, end = window[0], window[-1]
    unit = res["part"]
    claim = (f"The `{res['target']}` rate for {unit} {start} to {end} is {num(w['ratio'])}× the rest "
             f"({pct(w['rate_a'])} vs {pct(w['rate_b'])}).")
    return [_finding(ex, "period_rate_window", "temporal", claim,
                     {"target": res["target"], "timestamp": res["timestamp"], "part": unit, "window": window},
                     {"window_start": start, "window_end": end, "rate_window": w["rate_a"], "rate_rest": w["rate_b"],
                      "ratio": w["ratio"], "n_window": w["n_window"], "n_rest": w["n_rest"],
                      "positives_window": w["positives_window"], "positives_rest": w["positives_rest"]},
                     n=w["n_window"] + w["n_rest"], magnitude=_ratio_magnitude(w["ratio"]),
                     prevalence=w["n_window"] / max(w["n_window"] + w["n_rest"], 1),
                     test=f"{ex.execution_id}:window:{unit}:{start}-{end}", p_value=w["p_value"])]


def _r_entity(ex, res, st):
    share = res.get("top1pct_positive_share")
    out = []
    if share is not None and share >= 0.2 and res["positives"] >= st.config.min_cell and res.get("subset") is None:
        out.append(_finding(ex, "entity_concentration", "segmentation",
                            f"The top 1% of `{res['entity']}` values ({res['top1pct_entities']:,} of {res['n_entities']:,}) "
                            f"account for {pct(share, 1)} of `{ex.params.get('target')}` positives.",
                            {"entity": res["entity"], "target": ex.params.get("target"), "measure": "positives"},
                            {"top1pct_positive_share": share, "top1pct_entities": res["top1pct_entities"], "top_fraction": 0.01,
                             "n_entities": res["n_entities"], "positives": res["positives"]},
                            n=res["rows"], magnitude=share, prevalence=0.01))
    rshare = res.get("top1pct_row_share")
    if rshare is not None and rshare >= 0.2 and res.get("subset") is None:
        out.append(_finding(ex, "entity_concentration", "segmentation",
                            f"The top 1% of `{res['entity']}` values ({res['top1pct_entities']:,} of {res['n_entities']:,}) "
                            f"account for {pct(rshare, 1)} of rows.",
                            {"entity": res["entity"], "measure": "rows"},
                            {"top1pct_row_share": rshare, "top1pct_entities": res["top1pct_entities"], "top_fraction": 0.01,
                             "n_entities": res["n_entities"], "rows": res["rows"]},
                            n=res["rows"], magnitude=rshare, prevalence=0.01))
    return out


RULES: Dict[str, Callable] = {
    "analyze_duplicates": _r_duplicates, "analyze_missingness": _r_missingness,
    "analyze_column_quality": _r_column_quality, "analyze_target_balance": _r_target_balance,
    "analyze_distributions": _r_distributions, "detect_outliers": _r_outliers,
    "detect_multivariate_outliers": _r_multivariate, "calculate_correlations": _r_correlations,
    "compare_target_rates": _r_target_rates, "compare_target_rates_by_missingness": _r_missing_target,
    "compare_segments": _r_segments, "analyze_time_series": _r_time_series,
    "detect_distribution_shift": _r_shift, "compare_period_rates": _r_period_rates,
    "analyze_entity_concentration": _r_entity,
}


def derive(ex: ToolExecution, result: Dict[str, Any], state: InvestigationState) -> List[Finding]:
    rule = RULES.get(ex.tool)
    return rule(ex, result, state) if rule else []


def derive_all(state: InvestigationState) -> List[Finding]:
    """Candidate findings from every plan execution, deduplicated by key, in a stable order."""
    seen, out = set(), []
    for ex in state.executions:
        if ex.origin != "plan":
            continue
        for f in derive(ex, state.results[ex.execution_id], state):
            if f.key not in seen:
                seen.add(f.key)
                out.append(f)
    return out


def _strings(value: Any) -> List[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, (list, tuple)):
        return [s for v in value for s in _strings(v)]
    return []


def dedupe_keys(f: Finding) -> List[str]:
    """Findings sharing a key say the same thing. A target-rate gap is also keyed by each of its two
    groups' size and positive count: a group identical in both to a group of a higher-ranked gap is the
    same rows seen through another column (every add-on column's "no internet service" group, say), so
    the lower-ranked gap adds nothing and is merged into it."""
    cols = sorted(_strings(f.subject))
    keys = [f"{f.kind}|{'|'.join(cols)}"]
    if f.kind == "target_rate_gap":
        e, target = f.evidence, f.subject.get("target")
        for side in ("extreme", "reference"):
            keys.append(f"gap-group|{target}|{e.get('n_' + side)}|{e.get('positives_' + side)}")
    return keys


# --- multiple testing and scores ----------------------------------------------

def benjamini_hochberg(pvalues: Dict[str, float]) -> Dict[str, float]:
    """BH-adjusted p-values (step-up, monotone), keyed like the input."""
    items = sorted(((k, float(p)) for k, p in pvalues.items() if p is not None), key=lambda kv: (kv[1], kv[0]))
    m = len(items)
    adjusted: Dict[str, float] = {}
    running = 1.0
    for rank in range(m, 0, -1):
        k, p = items[rank - 1]
        running = min(running, p * m / rank)
        adjusted[k] = min(1.0, running)
    return adjusted


def all_tests(state: InvestigationState) -> Dict[str, float]:
    """Every p-value in the run: each tool test, plus tests a finding rule computed itself."""
    tests: Dict[str, float] = {}
    for ex in state.executions:
        if ex.origin == "validation":
            continue
        for t in state.results.get(ex.execution_id, {}).get("tests", []):
            if t.get("p_value") is not None:
                tests[f"{ex.execution_id}:{t['name']}"] = t["p_value"]
    for f in state.findings:
        if f.test and f.p_value is not None and f.test not in tests:
            tests[f.test] = f.p_value
    return tests


def support(p_adjusted: Optional[float]) -> float:
    if p_adjusted is None:
        return DESCRIPTIVE_SUPPORT
    return float(min(1.0, -math.log10(max(p_adjusted, 1e-300)) / 10))


def score(state: InvestigationState) -> None:
    """Set ``p_adjusted`` and the interestingness score on every finding, in place."""
    adjusted = benjamini_hochberg(all_tests(state))
    w = state.config.weights
    total = w.M + w.S + w.P + w.A
    for f in state.findings:
        f.p_adjusted = adjusted.get(f.test) if f.test else None
        S = support(f.p_adjusted)
        A = ACTIONABILITY.get(f.kind, 0.5)
        I = (w.M * f.magnitude + w.S * S + w.P * f.prevalence + w.A * A) / total if total else 0.0
        f.score = Score(I=round(I, 6), M=round(f.magnitude, 6), S=round(S, 6), P=round(f.prevalence, 6), A=A)


def ranked(findings: List[Finding]) -> List[Finding]:
    return sorted(findings, key=lambda f: (-(f.score.I if f.score else 0), f.key))
