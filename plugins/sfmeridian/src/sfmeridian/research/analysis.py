"""Deterministic research tools (the POC spec's §6 catalog) for securities finance.

Spec ``0121`` REQ-006, REQ-007, REQ-008, REQ-014, REQ-015. Each function
takes the run's :class:`ResearchSession` and arguments, runs only rendered
templates through the session's executor, registers evidence, updates the
coverage ledger and findings, and returns a structured result with scope,
method, warnings, and evidence IDs.

Exact pushed-down aggregates over the declared filtered population back
summaries, grain, missingness, time coverage, segments, and rule counts.
A bounded ordered extract backs distributions, relationships, availability,
and type inference, and everything derived from it says so.
"""

from __future__ import annotations

import json
import math
import statistics
from datetime import date, datetime
from datetime import time as dtime
from pathlib import Path
from typing import Any

from . import intake
from .evidence import ResearchSession
from .rules import plan_rule, rules_for
from .sources import SourceError

__all__ = ["TOOLS"]

FULL = "full_filtered_population"
EXTRACT = "ordered_extract"
_TEXT_LIMIT = 64


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def query_columns(s: ResearchSession) -> list[str]:
    """Columns templates may name: declared columns minus excluded ones."""
    return [c for c in s.dataset.columns if c not in s.context.exclude_columns]


def analysis_columns(s: ResearchSession) -> list[str]:
    """Columns analysed for distributions: allowed list, else non-sensitive query columns."""
    base = list(s.context.allowed_analysis_columns) or [c for c in query_columns(s)
                                                       if c not in s.context.sensitive_columns]
    return base[: int(s.context.budgets["max_columns"])]


def _num(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _rate(part: float, whole: float) -> float | None:
    return round(part / whole, 6) if whole else None


def _text(v: Any) -> Any:
    """Source text is untrusted data: shortened and marked, never interpreted."""
    if isinstance(v, str):
        return {"untrusted_text": v[:_TEXT_LIMIT] + ("…" if len(v) > _TEXT_LIMIT else "")}
    return v


def _finding_for(s: ResearchSession, kind: str, column: str | None) -> Any | None:
    return next((f for f in s.findings if f.kind == kind and (column is None or column in f.columns)), None)


def _extract(s: ResearchSession) -> dict[str, Any]:
    """One cached ordered extract of the analysis columns (plus availability/target columns)."""
    if "extract" in s.facts:
        return s.facts["extract"]
    ctx = s.context
    cols = list(dict.fromkeys(analysis_columns(s) + [c for c in (
        ctx.feature_availability.get("event_time_column"), ctx.feature_availability.get("available_at_column"),
        ctx.target.get("column"), ctx.target.get("available_at_column"), ctx.time_column)
        if c and c not in ctx.sensitive_columns and c not in ctx.exclude_columns]))
    remaining = int(ctx.budgets["max_rows_local"]) - s.budget.rows_local
    limit = max(1, min(s.dataset.max_rows, remaining))
    result = s.executor.run("extract", columns=cols, order_by=list(s.dataset.order_by), limit=limit)
    s.facts["extract"] = {"rows": result["rows"], "provenance": result["provenance"], "columns": cols,
                          "truncated": result["provenance"]["truncated"]}
    if result["provenance"]["truncated"]:
        s.limitation(f"Distributions, relationships, and availability checks use an ordered extract of "
                     f"{len(result['rows'])} rows (truncated): results describe the returned extract only, "
                     "not the population, and the extract is not a random sample.")
    return s.facts["extract"]


def _scope_words(scope: str) -> str:
    return "in the filtered population" if scope == FULL else "in the returned extract"


# --------------------------------------------------------------------------
# families
# --------------------------------------------------------------------------

def intake_family(s: ResearchSession, args: dict[str, Any]) -> dict[str, Any]:
    ds = s.dataset
    if ds.source != "file":
        s.ledger.set("intake", "skipped", "database source: the POC file-intake checks are covered by the schema, "
                     "grain, and domain-rule families")
        return {"status": "skipped"}
    raw = ds.path.read_bytes()
    report = intake.investigate(ds.path.name, raw, s.facts.get("contract") or {}, s.context.as_of)
    eid = s.evidence.add("research.intake", summary=f"POC intake status {report['status']}",
                         value={k: report.get(k) for k in ("status", "sha256", "rows", "duplicate_rows", "grain",
                                                           "dates", "malformed_row_numbers", "findings")},
                         scope=FULL, method="POC deterministic-v1 intake checks", denominator=report.get("rows"))
    severity = {"blocker": "blocker", "warning": "material"}
    for f in report["findings"]:
        sev = severity.get(f["severity"], "material")
        if f["check"] in ("numeric_outliers", "future_dates"):
            sev = "exploratory"
        if f["check"] == "grain_unconfirmed":
            sev = "limitation"
        s.add_finding(family="intake", kind=f"intake_{f['check']}", severity=sev, observation=f["detail"],
                      evidence_ids=[eid], scope=FULL)
    s.facts["intake"] = report
    s.ledger.set("intake", "completed", f"POC intake status: {report['status']}", [eid])
    return {"status": report["status"], "evidence_ids": [eid], "findings": len(report["findings"])}


def inspect_schema(s: ResearchSession, args: dict[str, Any]) -> dict[str, Any]:
    cols = query_columns(s)
    remaining = int(s.context.budgets["max_rows_local"]) - s.budget.rows_local
    sample = s.executor.run("extract", columns=[c for c in cols if c not in s.context.sensitive_columns],
                            order_by=list(s.dataset.order_by), limit=max(1, min(200, remaining)))
    rows = sample["rows"]
    profiles = intake.profile([c for c in cols if c not in s.context.sensitive_columns], rows)
    types = {c: p["type"] for c, p in profiles.items()}
    for c in s.context.sensitive_columns:
        if c in cols:
            types[c] = "sensitive_not_profiled"
    s.facts["types"] = types
    eid = s.evidence.add("research.inspect_schema", summary=f"{len(cols)} queryable columns; types inferred",
                         value={"declared_columns": list(s.dataset.columns), "excluded": list(s.context.exclude_columns),
                                "inferred_types": types},
                         scope=EXTRACT, method="type inference (POC rules) over an ordered sample of up to 200 rows",
                         provenance=[sample["provenance"]], denominator=len(rows),
                         warnings=["types are inferred from a sample, not read from the catalog"])
    s.ledger.set("schema", "completed", "declared columns checked; types inferred from an ordered sample", [eid])
    return {"evidence_ids": [eid], "types": types, "scope": EXTRACT}


def summarize_columns(s: ResearchSession, args: dict[str, Any]) -> dict[str, Any]:
    types = s.facts.get("types", {})
    summaries: dict[str, Any] = {}
    provenance = []
    for c in analysis_columns(s):
        r = s.executor.run("column_summary", column=c, numeric=types.get(c) == "numeric")
        row = r["rows"][0]
        n, non_null = row["n"], row["non_null"]
        item = {"n": n, "non_null": non_null, "nulls": n - non_null, "null_rate": _rate(n - non_null, n),
                "distinct": row["distinct_n"], "min": _text(row["min_v"]), "max": _text(row["max_v"])}
        if "sum_v" in row and row["sum_v"] is not None and non_null:
            item["mean"] = round(_num(row["sum_v"]) / non_null, 9)
        summaries[c] = item
        provenance.append(r["provenance"])
    total = next(iter(summaries.values()))["n"] if summaries else 0
    s.facts["rows"] = total
    s.facts["summaries"] = summaries
    candidates = [c for c, v in summaries.items() if total and v["non_null"] == total and v["distinct"] == total]
    s.facts["candidate_keys"] = candidates
    eid = s.evidence.add("research.summarize_columns", summary=f"{len(summaries)} columns over {total} rows",
                         value={"rows": total, "columns": summaries, "candidate_single_column_keys": candidates},
                         scope=FULL, method="pushed-down COUNT, COUNT(column), COUNT(DISTINCT), MIN, MAX, SUM",
                         provenance=provenance, denominator=total,
                         exclusions="SQL NULL counted as missing; mean over non-null values; SUM converted to float "
                                    "for the mean only")
    materiality = s.context.thresholds.get("materiality_missing_rate")
    for c, v in summaries.items():
        if v["nulls"]:
            sev = "material" if materiality is not None and v["null_rate"] >= materiality else "exploratory"
            s.add_finding(family="univariate", kind="missing_values", severity=sev, columns=[c], scope=FULL,
                          observation=f"{c}: {v['nulls']} of {total} rows missing ({v['null_rate']:.2%}) "
                                      f"{_scope_words(FULL)}", evidence_ids=[eid],
                          counts={"nulls": v["nulls"], "rows": total, "null_rate": v["null_rate"],
                                  "materiality_threshold": materiality})
        if total and v["non_null"] == 0:
            s.add_finding(family="univariate", kind="empty_column", severity="material", columns=[c], scope=FULL,
                          observation=f"{c} is entirely missing {_scope_words(FULL)}", evidence_ids=[eid],
                          counts={"rows": total})
    s.ledger.set("univariate", "completed", f"{len(summaries)} analysis columns summarised", [eid])
    return {"evidence_ids": [eid], "rows": total, "columns_with_missing":
            sorted(c for c, v in summaries.items() if v["nulls"]), "scope": FULL}


def check_grain(s: ResearchSession, args: dict[str, Any]) -> dict[str, Any]:
    ctx = s.context
    extra = list(args.get("extra_columns") or [])
    keys = list(ctx.business_grain) + [c for c in extra if c not in ctx.business_grain]
    provenance = []
    # Exact duplicate rows across every queryable column (POC duplicate check, pushed down).
    if "duplicate_rows" not in s.facts and not extra:
        r = s.executor.run("key_repeats", keys=query_columns(s))
        dup = r["rows"][0]
        s.facts["duplicate_rows"] = dup
        provenance.append(r["provenance"])
        if dup["repeated_keys"]:
            eid = s.evidence.add("research.check_grain", summary="exact duplicate rows",
                                 value=dup, scope=FULL, method="GROUP BY every queryable column HAVING COUNT(*) > 1",
                                 provenance=[r["provenance"]], denominator=s.facts.get("rows"))
            s.add_finding(family="duplicates_grain", kind="duplicate_rows", severity="material", scope=FULL,
                          observation=f"{dup['rows_in_repeats']} rows form {dup['repeated_keys']} groups of identical "
                                      f"rows {_scope_words(FULL)}; business significance unknown",
                          evidence_ids=[eid], counts=dict(dup))
    if not ctx.business_grain:
        cands = s.facts.get("candidate_keys", [])
        eid = s.evidence.add("research.check_grain", summary="no business grain configured",
                             value={"candidate_single_column_keys": cands}, scope=FULL,
                             method="unique and complete columns from the pushed-down summaries",
                             denominator=s.facts.get("rows"))
        s.add_finding(family="duplicates_grain", kind="grain_unconfigured", severity="limitation", scope=FULL,
                      observation="No business grain configured: grain cannot be checked. Unique, complete columns "
                                  f"({', '.join(cands) or 'none'}) are candidates only, not confirmed keys.",
                      evidence_ids=[eid], counts={"candidates": cands})
        s.ledger.set("duplicates_grain", "blocked", "no business_grain in the research context", [eid])
        return {"status": "blocked", "evidence_ids": [eid]}
    r_missing = s.executor.run("key_missing", keys=keys)
    r_repeat = s.executor.run("key_repeats", keys=keys)
    provenance += [r_missing["provenance"], r_repeat["provenance"]]
    value = {"keys": keys, "missing_key_rows": r_missing["rows"][0]["missing_key_rows"], **r_repeat["rows"][0]}
    eid = s.evidence.add("research.check_grain", summary=f"grain {'×'.join(keys)}", value=value, scope=FULL,
                         method="pushed-down key-null count and GROUP BY keys HAVING COUNT(*) > 1",
                         provenance=provenance, denominator=s.facts.get("rows"))
    if extra:
        base = _finding_for(s, "grain_repeats", None)
        resolved = value["repeated_keys"] == 0
        s.facts["grain_probe"] = value
        if base:
            base.evidence_ids.append(eid)
            base.hypothesis = (f"Repeats disappear at {'×'.join(keys)}: the business grain may include "
                               f"{', '.join(extra)}." if resolved else
                               f"Repeats persist at {'×'.join(keys)} ({value['repeated_keys']} keys): true duplicates "
                               "or a further grain column.")
            base.counts["probe"] = value
        return {"evidence_ids": [eid], "resolved_by_probe": resolved, "scope": FULL}
    s.facts["grain"] = value
    if value["repeated_keys"] or value["missing_key_rows"]:
        s.add_finding(family="duplicates_grain", kind="grain_repeats", severity="blocker", columns=keys, scope=FULL,
                      observation=f"Grain {'×'.join(keys)}: {value['repeated_keys']} keys repeat across "
                                  f"{value['rows_in_repeats']} rows and {value['missing_key_rows']} rows miss a key "
                                  f"component, {_scope_words(FULL)}", evidence_ids=[eid], counts=dict(value),
                      follow_up={"tool": "research.check_grain", "args": {"extra_columns": list(ctx.grain_probe_columns)}}
                      if ctx.grain_probe_columns else None)
    s.ledger.set("duplicates_grain", "completed", f"grain {'×'.join(keys)} checked", [eid])
    return {"evidence_ids": [eid], "repeated_keys": value["repeated_keys"],
            "missing_key_rows": value["missing_key_rows"], "scope": FULL}


def inspect_missingness(s: ResearchSession, args: dict[str, Any]) -> dict[str, Any]:
    ctx = s.context
    column = args["column"]
    by = args["by"]
    group = ctx.time_column if by == "date" else args.get("segment") or (ctx.segments[0] if ctx.segments else None)
    if not group:
        return {"status": "skipped", "reason": f"no {'time column' if by == 'date' else 'segment'} configured"}
    limit = int(ctx.budgets["max_groups"])
    r = s.executor.run("nulls_by_group", column=column, group=group, limit=limit)
    rows = r["rows"]
    total_nulls = sum(x["nulls"] or 0 for x in rows)
    total = sum(x["n"] for x in rows)
    overall = _rate(total_nulls, total) or 0.0
    groups = [{"group": _text(x["grp"]), "n": x["n"], "nulls": x["nulls"] or 0, "rate": _rate(x["nulls"] or 0, x["n"])}
              for x in rows]
    top = max(groups, key=lambda g: (g["nulls"], str(g["group"])), default=None)
    share = _rate(top["nulls"], total_nulls) if top and total_nulls else 0.0
    concentrated = bool(top and total_nulls and share >= 0.5 and (top["rate"] or 0) >= 2 * overall)
    eid = s.evidence.add("research.inspect_missingness", summary=f"{column} missing by {group}",
                         value={"column": column, "group_by": group, "groups": groups, "total_nulls": total_nulls,
                                "rows": total, "overall_rate": overall, "top_group": top, "top_share_of_nulls": share,
                                "concentrated": concentrated, "groups_truncated": r["provenance"]["truncated"]},
                         scope=FULL, method="pushed-down COUNT and SUM(CASE WHEN column IS NULL) GROUP BY group",
                         provenance=[r["provenance"]], denominator=total,
                         warnings=["only the first groups by key order are returned"] if r["provenance"]["truncated"] else [])
    s.facts.setdefault("missing_by", {})[(column, by)] = {"group": group, "top": top, "concentrated": concentrated}
    if concentrated:
        existing = _finding_for(s, "missing_concentration", column)
        piece = f"{group}={top['group'] if not isinstance(top['group'], dict) else top['group']['untrusted_text']}"
        if existing:
            existing.evidence_ids.append(eid)
            existing.observation += f"; by {group}: {top['nulls']} of {total_nulls} missing values ({share:.0%}) at {piece}"
            existing.counts[f"by_{by}"] = {"group": top["group"], "nulls": top["nulls"], "rate": top["rate"]}
        else:
            s.add_finding(family="missingness", kind="missing_concentration", severity="material", columns=[column],
                          scope=FULL, evidence_ids=[eid],
                          observation=f"{column}: missing values concentrate by {group}: {top['nulls']} of "
                                      f"{total_nulls} ({share:.0%}) at {piece}, rate {top['rate']:.0%} vs "
                                      f"{overall:.1%} overall",
                          counts={f"by_{by}": {"group": top["group"], "nulls": top["nulls"], "rate": top["rate"]},
                                  "total_nulls": total_nulls, "rows": total, "overall_rate": overall},
                          hypothesis="A feed or load gap for that group, not random missingness.")
    s.ledger.set("missingness", "completed", "missingness diagnosed by date and segment", [eid])
    return {"evidence_ids": [eid], "concentrated": concentrated, "group_by": group, "scope": FULL}


def inspect_time(s: ResearchSession, args: dict[str, Any]) -> dict[str, Any]:
    ctx = s.context
    t = ctx.time_column
    if not t:
        s.ledger.set("temporal", "blocked", "no time_column in the research context")
        return {"status": "blocked"}
    r = s.executor.run("nulls_by_group", column=t, group=t, limit=int(ctx.budgets["max_groups"]))
    counts = {str(x["grp"]): x["n"] for x in r["rows"] if x["grp"] is not None}
    observed = sorted(counts)
    value: dict[str, Any] = {"dates": len(observed), "first": observed[0] if observed else None,
                             "last": observed[-1] if observed else None, "rows_by_date": counts,
                             "null_dates": next((x["n"] for x in r["rows"] if x["grp"] is None), 0),
                             "truncated": r["provenance"]["truncated"]}
    reason = "coverage by date computed"
    future = [d for d in observed if d > ctx.as_of]
    value["future_dates"] = future
    if ctx.calendar_dates and observed:
        expected = [d for d in ctx.calendar_dates if observed[0] <= d <= observed[-1]]
        value["missing_dates"] = [d for d in expected if d not in counts]
        value["unexpected_dates"] = [d for d in observed if d not in set(ctx.calendar_dates)]
        reason += "; gaps checked against the supplied calendar"
    else:
        value["missing_dates"] = None
        reason += "; gap analysis skipped: no calendar supplied (no weekday or holiday assumption is made)"
        s.limitation("Calendar gap analysis skipped: no calendar_dates supplied.")
    eid = s.evidence.add("research.inspect_time", summary=f"{len(observed)} distinct {t} values", value=value,
                         scope=FULL, method="pushed-down COUNT GROUP BY time column", provenance=[r["provenance"]],
                         denominator=s.facts.get("rows"))
    s.facts["time"] = value
    if value.get("missing_dates"):
        s.add_finding(family="temporal", kind="time_gaps", severity="material", columns=[t], scope=FULL,
                      evidence_ids=[eid], counts={"missing_dates": value["missing_dates"]},
                      observation=f"{len(value['missing_dates'])} expected business date(s) have no rows: "
                                  f"{', '.join(value['missing_dates'][:10])}")
    if value.get("unexpected_dates"):
        s.add_finding(family="temporal", kind="unexpected_dates", severity="exploratory", columns=[t], scope=FULL,
                      evidence_ids=[eid], counts={"unexpected_dates": value["unexpected_dates"]},
                      observation=f"{len(value['unexpected_dates'])} date(s) are not in the supplied calendar")
    if future:
        s.add_finding(family="temporal", kind="future_dates", severity="exploratory", columns=[t], scope=FULL,
                      evidence_ids=[eid], counts={"future_dates": future},
                      observation=f"{len(future)} date(s) after the as-of {ctx.as_of}; may be scheduled events")
    s.ledger.set("temporal", "completed", reason, [eid])
    return {"evidence_ids": [eid], "dates": len(observed), "scope": FULL}


def check_domain_rules(s: ResearchSession, args: dict[str, Any]) -> dict[str, Any]:
    ctx = s.context
    rules = rules_for(ctx.dataset_kind)
    if not rules:
        s.ledger.set("domain_rules", "skipped", f"no securities-finance rule pack for dataset_kind {ctx.dataset_kind!r}")
        return {"status": "skipped"}
    wanted = args.get("rule_id")
    group = args.get("by")
    cols = query_columns(s)
    out = []
    eids = []
    for rule in rules:
        if wanted and rule.rule_id != wanted:
            continue
        built, reason = plan_rule(rule, ctx, cols)
        if built is None:
            out.append({"rule_id": rule.rule_id, "status": "skipped", "reason": reason})
            continue
        violation, applicable = built
        if group:
            r = s.executor.run("rule_counts_by_group", group=group, violation=violation, applicable=applicable,
                               limit=int(ctx.budgets["max_groups"]))
            groups = [{"group": _text(x["grp"]), "n": x["n"], "applicable": x["applicable"] or 0,
                       "violations": x["violations"] or 0} for x in r["rows"]]
            eid = s.evidence.add("research.check_domain_rules", summary=f"{rule.rule_id} by {group}",
                                 value={"rule_id": rule.rule_id, "group_by": group, "groups": groups},
                                 scope=FULL, method="pushed-down SUM(CASE WHEN applicable AND violated) GROUP BY group",
                                 provenance=[r["provenance"]], denominator=sum(g["applicable"] for g in groups),
                                 exclusions="rows with a missing rule input are not applicable")
            finding = _finding_for(s, f"rule:{rule.rule_id}", None)
            if finding:
                finding.evidence_ids.append(eid)
                worst = max(groups, key=lambda g: (g["violations"], str(g["group"])))
                finding.counts[f"by_{group}"] = worst
            out.append({"rule_id": rule.rule_id, "by": group, "groups": groups, "evidence_id": eid})
            eids.append(eid)
            continue
        r = s.executor.run("rule_counts", violation=violation, applicable=applicable)
        row = r["rows"][0]
        value = {"rule_id": rule.rule_id, "title": rule.title, "convention": rule.convention, "n": row["n"],
                 "applicable": row["applicable"] or 0, "violations": row["violations"] or 0,
                 "excluded_missing_inputs": row["n"] - (row["applicable"] or 0)}
        eid = s.evidence.add("research.check_domain_rules", summary=rule.title, value=value, scope=FULL,
                             method="pushed-down SUM(CASE WHEN applicable AND violated)", provenance=[r["provenance"]],
                             denominator=value["applicable"],
                             exclusions=f"{value['excluded_missing_inputs']} rows with a missing input not applicable")
        eids.append(eid)
        out.append({"rule_id": rule.rule_id, "status": "checked", **{k: value[k] for k in ("applicable", "violations")},
                    "evidence_id": eid})
        if value["violations"]:
            s.add_finding(family="domain_rules", kind=f"rule:{rule.rule_id}", severity=rule.severity, scope=FULL,
                          columns=[ctx.column(c) for c in rule.columns], evidence_ids=[eid], counts=value,
                          observation=f"{rule.title}: {value['violations']} of {value['applicable']} applicable rows "
                                      f"violate it {_scope_words(FULL)} ({rule.convention})",
                          follow_up={"tool": "research.check_domain_rules",
                                     "args": {"rule_id": rule.rule_id, "by": ctx.segments[0]}} if ctx.segments else None)
    if not group:
        s.facts["rules"] = out
        skipped = [o for o in out if o.get("status") == "skipped"]
        reason = f"{len(out) - len(skipped)} rule(s) checked, {len(skipped)} skipped" + (
            ": " + "; ".join(f"{o['rule_id']} ({o['reason']})" for o in skipped) if skipped else "")
        s.ledger.set("domain_rules", "completed" if len(skipped) < len(out) else "skipped", reason, eids)
    return {"rules": out, "evidence_ids": eids, "scope": FULL}


def inspect_numeric(s: ResearchSession, args: dict[str, Any]) -> dict[str, Any]:
    ex = _extract(s)
    column = args["column"]
    raw = [r.get(column) for r in ex["rows"]]
    values = [v for v in (_num(x) for x in raw) if v is not None]
    scope = EXTRACT
    value: dict[str, Any] = {"column": column, "n_extract": len(raw), "n_numeric": len(values),
                             "truncated": ex["truncated"]}
    if len(values) >= 4:
        q = statistics.quantiles(values, n=4, method="inclusive")
        iqr = q[2] - q[0]
        lo, hi = q[0] - 1.5 * iqr, q[2] + 1.5 * iqr
        flags = [v for v in values if v < lo or v > hi]
        width = (max(values) - min(values)) / 10 or 1.0
        bins = [0] * 10
        for v in values:
            bins[min(9, int((v - min(values)) / width))] += 1
        value.update(q1=q[0], median=q[1], q3=q[2], iqr_low=lo, iqr_high=hi, iqr_flags=len(flags),
                     min=min(values), max=max(values), mean=statistics.fmean(values),
                     stdev=statistics.pstdev(values),
                     histogram={"bin_start": min(values), "bin_width": width, "counts": bins})
    eid = s.evidence.add("research.inspect_numeric", summary=f"{column} distribution", value=value, scope=scope,
                         method="inclusive quartiles, 1.5×IQR flags, 10-bin histogram on the ordered extract",
                         provenance=[ex["provenance"]], denominator=len(values),
                         exclusions="non-numeric and missing values excluded; decimals converted to float for statistics",
                         warnings=["ordered extract, not a random sample"])
    s.facts.setdefault("numeric", {})[column] = {"evidence_id": eid, **value}
    if value.get("iqr_flags"):
        s.add_finding(family="numeric", kind="iqr_flags", severity="exploratory", columns=[column], scope=scope,
                      evidence_ids=[eid], counts={"flags": value["iqr_flags"], "n": len(values)},
                      observation=f"{column}: {value['iqr_flags']} of {len(values)} values outside 1.5×IQR "
                                  f"{_scope_words(scope)} — flags, not errors (specials can legitimately be extreme)")
    s.ledger.set("numeric", "completed", "numeric distributions on the ordered extract", [eid])
    return {"evidence_ids": [eid], "scope": scope}


def inspect_categories(s: ResearchSession, args: dict[str, Any]) -> dict[str, Any]:
    column = args["column"]
    if column in s.context.sensitive_columns:
        raise SourceError("E_RESEARCH_SENSITIVE", f"{column} is sensitive: category values are not returned")
    r = s.executor.run("group_counts", column=column, limit=20)
    rows = r["rows"]
    total = s.facts.get("rows") or sum(x["n"] for x in rows)
    levels = [{"value": _text(x["grp"]), "n": x["n"], "share": _rate(x["n"], total)} for x in rows]
    distinct = s.facts.get("summaries", {}).get(column, {}).get("distinct")
    rare = [lv for lv in levels if (lv["share"] or 0) < 0.01]
    value = {"column": column, "top_levels": levels, "distinct": distinct, "more_levels": r["provenance"]["truncated"],
             "rare_levels_in_top": len(rare)}
    eid = s.evidence.add("research.inspect_categories", summary=f"{column} levels", value=value, scope=FULL,
                         method="pushed-down COUNT GROUP BY column, top 20 by frequency", provenance=[r["provenance"]],
                         denominator=total, warnings=["level text is untrusted source data"])
    if levels and (levels[0]["share"] or 0) > 0.9:
        s.add_finding(family="categorical", kind="dominant_category", severity="exploratory", columns=[column],
                      scope=FULL, evidence_ids=[eid], counts={"share": levels[0]["share"], "rows": total},
                      observation=f"{column}: one level holds {levels[0]['share']:.0%} of rows")
    s.ledger.set("categorical", "completed", "category frequencies pushed down", [eid])
    return {"evidence_ids": [eid], "levels": len(levels), "scope": FULL}


def inspect_relationships(s: ResearchSession, args: dict[str, Any]) -> dict[str, Any]:
    types = s.facts.get("types", {})
    numeric_cols = [c for c in analysis_columns(s) if types.get(c) == "numeric"]
    if len(numeric_cols) < 2:
        s.ledger.set("relationships", "skipped", "fewer than two numeric analysis columns")
        return {"status": "skipped"}
    ex = _extract(s)
    max_pairs = int(s.context.budgets["max_pairs"])
    pairs = [(a, b) for i, a in enumerate(numeric_cols) for b in numeric_cols[i + 1:]]
    screened = pairs[:max_pairs]
    results = []
    for a, b in screened:
        xs, ys = [], []
        for r in ex["rows"]:
            x, y = _num(r.get(a)), _num(r.get(b))
            if x is not None and y is not None:
                xs.append(x)
                ys.append(y)
        corr = None
        if len(xs) >= 3 and statistics.pstdev(xs) and statistics.pstdev(ys):
            corr = round(statistics.correlation(xs, ys), 6)
        results.append({"a": a, "b": b, "n": len(xs), "pearson": corr})
    strong = s.context.thresholds.get("strong_correlation")
    value = {"pairs_available": len(pairs), "pairs_screened": len(screened), "results": results,
             "strong_threshold": strong}
    eid = s.evidence.add("research.inspect_relationships", summary=f"{len(screened)} numeric pairs screened",
                         value=value, scope=EXTRACT, method="Pearson correlation on pairwise-complete extract rows",
                         provenance=[ex["provenance"]], denominator=len(ex["rows"]),
                         warnings=["descriptive, not causal; no significance test", "ordered extract"])
    if strong is not None:
        for res in results:
            if res["pearson"] is not None and abs(res["pearson"]) >= strong:
                s.add_finding(family="relationships", kind="strong_association", severity="exploratory",
                              columns=[res["a"], res["b"]], scope=EXTRACT, evidence_ids=[eid], counts=res,
                              observation=f"{res['a']} and {res['b']}: Pearson {res['pearson']} over {res['n']} rows "
                                          f"{_scope_words(EXTRACT)} (descriptive, not causal; {len(screened)} pairs screened)")
    s.ledger.set("relationships", "completed",
                 f"{len(screened)} of {len(pairs)} pairs screened" + ("" if strong is not None else
                                                                      "; no strong_correlation threshold, so none flagged"),
                 [eid])
    return {"evidence_ids": [eid], "pairs_screened": len(screened), "scope": EXTRACT}


def compare_segments(s: ResearchSession, args: dict[str, Any]) -> dict[str, Any]:
    ctx = s.context
    if not ctx.segments:
        s.ledger.set("segments", "skipped", "no segments in the research context")
        return {"status": "skipped"}
    column, segment = args["column"], args.get("segment") or ctx.segments[0]
    r = s.executor.run("segment_numeric", column=column, group=segment, limit=int(ctx.budgets["max_groups"]))
    groups = []
    for x in r["rows"]:
        mean = round(_num(x["sum_v"]) / x["non_null"], 9) if x["non_null"] and _num(x["sum_v"]) is not None else None
        groups.append({"segment": _text(x["grp"]), "n": x["n"], "non_null": x["non_null"], "mean": mean,
                       "min": x["min_v"], "max": x["max_v"]})
    eid = s.evidence.add("research.compare_segments", summary=f"{column} by {segment}",
                         value={"column": column, "segment": segment, "groups": groups}, scope=FULL,
                         method="pushed-down COUNT, MIN, MAX, SUM GROUP BY segment", provenance=[r["provenance"]],
                         denominator=sum(g["n"] for g in groups), exclusions="mean over non-null values")
    means = [g["mean"] for g in groups if g["mean"] not in (None, 0)]
    if len(means) >= 2 and max(means) / min(means) >= 2 and min(means) > 0:
        s.add_finding(family="segments", kind="segment_difference", severity="exploratory", columns=[column, segment],
                      scope=FULL, evidence_ids=[eid], counts={"max_mean": max(means), "min_mean": min(means)},
                      observation=f"{column}: segment means differ by {max(means) / min(means):.1f}× across {segment} "
                                  "(descriptive)")
    s.ledger.set("segments", "completed", f"{column} compared across {segment}", [eid])
    return {"evidence_ids": [eid], "scope": FULL}


def _parse_ts(value: Any, naive_tz: str | None, end_of_day: bool, default_tz: str | None) -> tuple[datetime | None, str]:
    """Parse ISO date/datetime; return (aware datetime or None, status)."""
    from zoneinfo import ZoneInfo
    if value is None:
        return None, "missing"
    text = str(value).strip()
    try:
        if len(text) == 10:
            d = date.fromisoformat(text)
            tz = naive_tz or default_tz
            if not tz:
                return None, "naive"
            return datetime.combine(d, dtime.max if end_of_day else dtime.min, tzinfo=ZoneInfo(tz)), "date"
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None, "invalid"
    if dt.tzinfo is None:
        if not naive_tz:
            return None, "naive"
        dt = dt.replace(tzinfo=ZoneInfo(naive_tz))
    return dt, "aware"


def inspect_availability(s: ResearchSession, args: dict[str, Any]) -> dict[str, Any]:
    ctx = s.context
    fa = ctx.feature_availability
    event_col, avail_col = fa.get("event_time_column"), fa.get("available_at_column")
    if not avail_col:
        s.ledger.set("availability", "skipped", "no feature_availability.available_at_column configured")
        return {"status": "skipped"}
    if not ctx.timezone:
        s.add_finding(family="availability", kind="pit_timezone_missing", severity="limitation", scope=FULL,
                      evidence_ids=[s.evidence.add("research.inspect_availability", summary="timezone missing",
                                                   value={"reason": "no context timezone"}, scope=FULL,
                                                   method="context validation")],
                      observation="Point-in-time checks need a context timezone to place the as-of decision time.")
        s.ledger.set("availability", "blocked", "no timezone in the research context")
        return {"status": "blocked"}
    from zoneinfo import ZoneInfo
    cutoff = datetime.combine(date.fromisoformat(ctx.as_of), dtime.max, tzinfo=ZoneInfo(ctx.timezone))
    ex = _extract(s)
    naive_tz = fa.get("naive_timezone")
    stats = {"rows": len(ex["rows"]), "missing_available": 0, "naive_available": 0, "invalid": 0,
             "inverted": 0, "published_after_event_day": 0, "after_decision_cutoff": 0}
    lags: list[float] = []
    for r in ex["rows"]:
        avail, status = _parse_ts(r.get(avail_col), naive_tz, False, None)
        if status == "missing":
            stats["missing_available"] += 1
            continue
        if status == "naive":
            stats["naive_available"] += 1
            continue
        if status == "invalid":
            stats["invalid"] += 1
            continue
        if avail > cutoff:
            stats["after_decision_cutoff"] += 1
        if event_col:
            start, _ = _parse_ts(r.get(event_col), naive_tz, False, ctx.timezone)
            end, _ = _parse_ts(r.get(event_col), naive_tz, True, ctx.timezone)
            if start is None:
                continue
            if avail < start:
                stats["inverted"] += 1
            if end is not None and avail > end:
                stats["published_after_event_day"] += 1
            lags.append((avail - start).total_seconds() / 3600)
    if lags:
        stats["lag_hours_median"] = round(statistics.median(lags), 4)
        stats["lag_hours_max"] = round(max(lags), 4)
    stats["decision_cutoff"] = cutoff.isoformat()
    eid = s.evidence.add("research.inspect_availability", summary=f"{avail_col} vs as-of {ctx.as_of} ({ctx.timezone})",
                         value=stats, scope=EXTRACT,
                         method="ISO timestamps with offsets compared in UTC; dates placed in the context timezone; "
                                "decision cutoff = as-of end of day in the context timezone",
                         provenance=[ex["provenance"]], denominator=stats["rows"],
                         warnings=["an extraction timestamp is not an availability guarantee",
                                   "absence of flags does not prove the data free of look-ahead"])
    if stats["naive_available"]:
        s.add_finding(family="availability", kind="pit_naive_timestamps", severity="limitation", scope=EXTRACT,
                      columns=[avail_col], evidence_ids=[eid], counts={"naive": stats["naive_available"]},
                      observation=f"{avail_col}: {stats['naive_available']} timestamps have no timezone and none is "
                                  "declared; those rows cannot be placed in time")
        s.ledger.set("availability", "blocked", f"{avail_col} has naive timestamps and no naive_timezone", [eid])
        return {"status": "blocked", "evidence_ids": [eid]}
    for key, sev, text in (("inverted", "blocker", "available before the event it describes"),
                           ("published_after_event_day", "material",
                            "published after the end of its business date: using it for that date is look-ahead"),
                           ("after_decision_cutoff", "material", f"not yet available at the as-of {ctx.as_of}")):
        if stats[key]:
            s.add_finding(family="availability", kind=f"pit_{key}", severity=sev, scope=EXTRACT,
                          columns=[c for c in (event_col, avail_col) if c], evidence_ids=[eid],
                          counts={key: stats[key], "rows": stats["rows"]},
                          observation=f"{stats[key]} of {stats['rows']} rows {_scope_words(EXTRACT)} were {text}")
    s.ledger.set("availability", "completed", "availability timing checked on the ordered extract", [eid])
    return {"evidence_ids": [eid], "scope": EXTRACT}


def inspect_target(s: ResearchSession, args: dict[str, Any]) -> dict[str, Any]:
    target = s.context.target.get("column")
    if not target:
        s.ledger.set("target", "skipped", "no target configured")
        return {"status": "skipped"}
    r = s.executor.run("column_summary", column=target, numeric=True)
    row = r["rows"][0]
    value = {"column": target, "n": row["n"], "missing": row["n"] - row["non_null"],
             "distinct": row["distinct_n"], "min": row["min_v"], "max": row["max_v"]}
    eid = s.evidence.add("research.inspect_target", summary=f"target {target}", value=value, scope=FULL,
                         method="pushed-down target summary", provenance=[r["provenance"]], denominator=row["n"])
    if value["missing"]:
        s.add_finding(family="target", kind="target_missing", severity="material", columns=[target], scope=FULL,
                      evidence_ids=[eid], counts=value,
                      observation=f"target {target}: {value['missing']} of {row['n']} rows missing")
    s.ledger.set("target", "completed", "target summarised (descriptive only)", [eid])
    return {"evidence_ids": [eid], "scope": FULL}


def compare_reference(s: ResearchSession, args: dict[str, Any], base_dir: Path | None = None) -> dict[str, Any]:
    ref_path = s.context.reference_profile
    if not ref_path:
        s.ledger.set("reference", "skipped", "no versioned reference profile supplied: no drift claim is made")
        return {"status": "skipped"}
    path = Path(ref_path) if Path(ref_path).is_absolute() else (base_dir or Path(".")) / ref_path
    try:
        ref = json.loads(path.read_text(encoding="utf-8"))
        ref_cols = ref["columns"]
        version = ref["version"]
    except (OSError, ValueError, KeyError):
        s.ledger.set("reference", "blocked", "reference profile unreadable or missing version/columns")
        return {"status": "blocked"}
    current = s.facts.get("summaries", {})
    shift = s.context.thresholds.get("reference_shift")
    changes = {"added": sorted(set(current) - set(ref_cols)), "removed": sorted(set(ref_cols) - set(current)),
               "columns": {}}
    for c in sorted(set(current) & set(ref_cols)):
        cur, old = current[c], ref_cols[c]
        delta: dict[str, Any] = {}
        if old.get("null_rate") is not None and cur.get("null_rate") is not None:
            delta["null_rate"] = [old["null_rate"], cur["null_rate"]]
        if old.get("mean") not in (None, 0) and cur.get("mean") is not None:
            delta["mean_rel_change"] = round((cur["mean"] - old["mean"]) / abs(old["mean"]), 6)
        changes["columns"][c] = delta
    eid = s.evidence.add("research.compare_reference", summary=f"against reference {version}",
                         value={"reference_version": version, **changes}, scope=FULL,
                         method="column set, null rate, and mean compared with the versioned reference profile",
                         denominator=s.facts.get("rows"))
    if changes["added"] or changes["removed"]:
        s.add_finding(family="reference", kind="schema_change", severity="material", scope=FULL, evidence_ids=[eid],
                      counts={"added": changes["added"], "removed": changes["removed"]},
                      observation=f"columns changed against reference {version}: +{changes['added']} -{changes['removed']}")
    if shift is not None:
        for c, d in changes["columns"].items():
            if abs(d.get("mean_rel_change", 0)) >= shift:
                s.add_finding(family="reference", kind="distribution_shift", severity="material", columns=[c],
                              scope=FULL, evidence_ids=[eid], counts=d,
                              observation=f"{c}: mean moved {d['mean_rel_change']:+.0%} against reference {version}")
    s.ledger.set("reference", "completed", f"compared with reference {version}", [eid])
    return {"evidence_ids": [eid], "scope": FULL}


TOOLS = {
    "intake": intake_family, "inspect_schema": inspect_schema, "summarize_columns": summarize_columns,
    "check_grain": check_grain, "inspect_missingness": inspect_missingness, "inspect_time": inspect_time,
    "check_domain_rules": check_domain_rules, "inspect_numeric": inspect_numeric,
    "inspect_categories": inspect_categories, "inspect_relationships": inspect_relationships,
    "compare_segments": compare_segments, "inspect_availability": inspect_availability,
    "inspect_target": inspect_target, "compare_reference": compare_reference,
}
