"""Evidence-linked recommendations (POC spec §9 contract).

Spec ``0121`` REQ-011 (POC AC-05, AC-18). Every recommendation is built from
findings and their evidence; it carries a runnable next diagnostic (a
rendered, read-only template — rendered, never executed here) or a precise
question for the data owner, and a verification criterion. Priority follows
an explicit rubric: blockers and rule or contract violations first, then
material concentrated issues, then exploratory items. Business consequence
is ``unknown`` unless the context supplies a materiality threshold; no
monetary impact is ever invented. Nothing here repairs, deletes, or writes.
"""

from __future__ import annotations

from typing import Any

from .evidence import Finding, ResearchSession
from .templates import TemplateError

__all__ = ["PRIORITY", "build_recommendations"]

PRIORITY = {"blocker": "high", "material": "medium", "limitation": "medium", "exploratory": "low"}
_ORDER = {"high": 0, "medium": 1, "low": 2}
MAX_EXPLORATORY = 5


def _diagnostic(s: ResearchSession, template: str, **args: Any) -> dict[str, Any] | None:
    try:
        r = s.executor.render(template, **args)
    except TemplateError:
        return None
    return {"type": "query", "template": r.template, "template_version": r.version, "sql": r.sql,
            "parameters": r.redacted_params(), "executes": False,
            "note": "rendered read-only template; run it through the research tools, never by hand-editing"}


def _question(text: str) -> dict[str, Any]:
    return {"type": "question", "for": "data owner", "text": text}


def _plan(s: ResearchSession, f: Finding) -> dict[str, Any]:
    ctx = s.context
    seg = ctx.segments[0] if ctx.segments else None
    kind = f.kind
    if kind == "grain_repeats":
        probe = list(ctx.grain_probe_columns)
        keys = list(ctx.business_grain)
        diag = _diagnostic(s, "key_repeats", keys=keys + probe) if probe else None
        return {"category": "grain", "action": f"Verify the {'×'.join(keys)} grain before any deduplication: "
                f"{f.counts.get('repeated_keys')} keys repeat.",
                "next": diag or _question(f"Which columns complete the business key beyond {'×'.join(keys)}?"),
                "verification": "repeated_keys = 0 at the confirmed grain, or the grain is redefined in the contract",
                "effort": "small"}
    if kind == "grain_unconfigured":
        return {"category": "context", "action": "Declare the business grain so uniqueness can be checked.",
                "next": _question("Which columns uniquely identify a row (for example security × counterparty × "
                                  "business date)?"),
                "verification": "a rerun with business_grain reports the grain family completed", "effort": "small"}
    if kind == "duplicate_rows":
        return {"category": "grain", "action": "Confirm whether identical rows are legitimate repeated positions or "
                "load duplicates; do not deduplicate until confirmed.",
                "next": _question("Can two identical rows be legitimate in this feed (for example split lots)?"),
                "verification": "owner answer recorded; contract updated", "effort": "small"}
    if kind == "missing_concentration":
        col = f.columns[0]
        by_seg, by_date = f.counts.get("by_segment"), f.counts.get("by_date")
        target = (by_date or by_seg or {}).get("group")
        diag = _diagnostic(s, "nulls_by_group", column=col, group=seg or ctx.time_column,
                           limit=int(ctx.budgets["max_groups"])) if (seg or ctx.time_column) else None
        return {"category": "data_quality", "action": f"Check the source feed for {col} where missing values "
                f"concentrate ({target if not isinstance(target, dict) else target.get('untrusted_text')}); "
                "do not impute.", "next": diag or _question(f"Was the {col} load complete for that group?"),
                "verification": f"{col} missing rate in that group returns to the overall rate", "effort": "small"}
    if kind in ("missing_values", "empty_column", "target_missing"):
        return {"category": "data_quality", "action": f"Confirm whether missing {', '.join(f.columns)} is expected.",
                "next": _question(f"Is {', '.join(f.columns)} optional, or should every row carry it?"),
                "verification": "expected-missing rule added to the contract proposal, or the gap fixed at source",
                "effort": "small"}
    if kind.startswith("rule:"):
        rule_id = kind.split(":", 1)[1]
        diag = None
        rule = next((r for r in s.facts.get("rules", []) if r.get("rule_id") == rule_id), None)
        from .rules import RULES, plan_rule
        spec = next((r for r in RULES if r.rule_id == rule_id), None)
        if spec is not None and (seg or ctx.time_column):
            built, _ = plan_rule(spec, ctx, s.dataset.columns)
            if built:
                diag = _diagnostic(s, "rule_counts_by_group", group=seg or ctx.time_column, violation=built[0],
                                   applicable=built[1], limit=int(ctx.budgets["max_groups"]))
        return {"category": "domain_rule", "action": f"Investigate {f.counts.get('violations')} rows violating "
                f"{rule_id} at the source; this is an observation, not a correction.",
                "next": diag or _question(f"Are rows violating {rule_id} expected (for example corrections in flight)?"),
                "verification": f"{rule_id} violations = 0 on rerun, or an approved exception recorded",
                "effort": "medium" if rule and rule.get("violations", 0) > 10 else "small"}
    if kind.startswith("pit_"):
        return {"category": "point_in_time", "action": "Use as-of-correct values: lag or exclude records published "
                "after their business date in any signal or backtest.",
                "next": _question("Which timestamp marks when each value became available to the desk, and in which "
                                  "timezone?"),
                "verification": "availability family completed with zero inverted or late-published rows in use",
                "effort": "medium"}
    if kind == "time_gaps":
        return {"category": "coverage", "action": "Confirm the missing business dates with the feed owner.",
                "next": _question(f"Were there no records on {', '.join(f.counts.get('missing_dates', [])[:5])}, "
                                  "or did the load fail?"),
                "verification": "missing dates explained or backfilled", "effort": "small"}
    if kind in ("schema_change", "distribution_shift"):
        return {"category": "reference", "action": "Confirm the change against the reference with the feed owner "
                "before downstream use.", "next": _question("Was this change announced?"),
                "verification": "reference profile updated after review", "effort": "small"}
    return {"category": "exploratory", "action": f"Review: {f.observation}",
            "next": _question("Is this pattern expected?"),
            "verification": "reviewed and recorded", "effort": "small"}


def build_recommendations(s: ResearchSession) -> list[dict[str, Any]]:
    charts_by_evidence: dict[str, list[str]] = {}
    for c in s.charts:
        for eid in c["usermeta"]["sfmeridian"]["evidence_ids"]:
            charts_by_evidence.setdefault(eid, []).append(c["usermeta"]["sfmeridian"]["chart_id"])
    materiality = s.context.thresholds.get("materiality_missing_rate")
    recs: list[dict[str, Any]] = []
    exploratory = 0
    ordered = sorted(s.findings, key=lambda f: (_ORDER[PRIORITY[f.severity]], f.finding_id))
    for f in ordered:
        if f.severity == "exploratory":
            exploratory += 1
            if exploratory > MAX_EXPLORATORY:
                continue
        plan = _plan(s, f)
        confidence = ("high: exact pushed-down aggregate over the declared filtered population"
                      if f.scope == "full_filtered_population" else
                      "medium: computed on an ordered extract, not the population")
        limitations = [] if f.scope == "full_filtered_population" else [
            "applies to the returned extract only; not a random sample"]
        recs.append({
            "recommendation_id": f"R-{len(recs) + 1:03d}", "priority": PRIORITY[f.severity],
            "category": plan["category"], "action": plan["action"], "finding_id": f.finding_id,
            "evidence_ids": list(f.evidence_ids), "scope": f.scope, "counts": f.counts,
            "chart_ids": sorted({c for e in f.evidence_ids for c in charts_by_evidence.get(e, [])}),
            "observation": f.observation, "hypothesis": f.hypothesis, "confidence": confidence,
            "limitations": limitations,
            "business_consequence": "unknown — no materiality threshold supplied" if materiality is None
            else f"compare with the supplied materiality threshold ({materiality})",
            "next_diagnostic": plan["next"], "dependencies": [], "effort": plan["effort"],
            "verification": plan["verification"], "executes": False,
        })
    return recs
