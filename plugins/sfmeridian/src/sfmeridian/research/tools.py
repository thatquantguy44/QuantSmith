"""``research.*`` tools in the shared registry (spec ``0121`` REQ-006, REQ-015).

A research run is a session held in ``ctx.session["research"]``:
``research.start`` validates the dataset declaration and research context,
opens a budgeted, read-only executor, and probes the source; the family tools
add evidence, coverage, and findings; ``research.render_charts`` and
``research.recommend_actions`` build outputs from evidence only;
``research.finish`` re-probes the source (mutable-view check), closes the
coverage ledger with the stop reason, and writes the bundle.

Effects: database work is ``execute_read`` (rendered read-only templates
only); ``research.finish`` is ``report`` (writes the local bundle only).
"""

from __future__ import annotations

import time
from dataclasses import replace
from typing import Any

from ..access import caller, withheld_columns
from ..tools import ToolContext, ToolError, ToolRegistry, ToolSpec, _obj
from . import analysis
from .bundle import write_bundle
from .charts import build_charts, validate_chart
from .context import ContextError, parse_context
from .evidence import ResearchSession
from .recommend import build_recommendations
from .sources import Budget, BudgetExhausted, Executor, SourceError, load_dataset

__all__ = ["FAMILY_OF", "register"]

FAMILY_OF = {
    "intake": "intake", "inspect_schema": "schema", "summarize_columns": "univariate", "check_grain": "duplicates_grain",
    "inspect_missingness": "missingness", "inspect_time": "temporal", "check_domain_rules": "domain_rules",
    "inspect_numeric": "numeric", "inspect_categories": "categorical", "inspect_relationships": "relationships",
    "compare_segments": "segments", "inspect_target": "target", "inspect_availability": "availability",
    "compare_reference": "reference",
}


def session(ctx: ToolContext) -> ResearchSession:
    s = ctx.session.get("research")
    if s is None:
        raise ToolError("E_RESEARCH_NO_SESSION", "call research.start first")
    return s


def _probe(s: ResearchSession) -> dict[str, Any]:
    r = s.executor.run("consistency", change_column=s.context.change_column)
    return r["rows"][0]


def _start(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    try:
        dataset = load_dataset(ctx.config, args["dataset"])
    except SourceError as exc:
        raise ToolError(exc.code, exc.message) from None
    try:
        context = parse_context(args["context"], dataset.columns)
    except ContextError as exc:
        raise ToolError("E_RESEARCH_CONTEXT", str(exc)) from None
    withheld = withheld_columns(ctx.config, caller(ctx.config, ctx.actor), dataset.obj or dataset.id, dataset.columns)
    if withheld:
        clash = sorted(set(withheld) & (set(context.segments) | set(context.allowed_analysis_columns)))
        if clash:
            raise ToolError("E_ACCESS_CLEARANCE", f"the caller's clearance withholds {', '.join(clash)}; it cannot be "
                                                  "a segment or an analysis column")
        context = replace(context, sensitive_columns=tuple(sorted(set(context.sensitive_columns) | set(withheld))))
    decl = next(d for d in ctx.config.data.get("datasets", []) if d["id"] == dataset.id)
    dataset.is_view = decl.get("object_type") == "view"
    budget = Budget(dict(context.budgets), clock=ctx.clients.get("clock", time.monotonic))
    budget.start()
    allowed = [c for c in dataset.columns if c not in context.exclude_columns]
    executor = Executor(dataset, budget, connections=ctx.clients.get("connections"), config=ctx.config,
                        allowed=allowed, sensitive=context.sensitive_columns)
    s = ResearchSession(dataset=dataset, context=context, executor=executor, budget=budget,
                        config_hash=ctx.config.hash)
    s.facts["contract"] = decl.get("contract")
    if withheld:
        s.limitation(f"Values of {', '.join(sorted(withheld))} are withheld at the caller's clearance (0115 access controls).")
    ctx.session["research"] = s
    try:
        s.facts["probe_start"] = _probe(s)
    except BudgetExhausted as exc:
        raise ToolError("E_BUDGET_EXHAUSTED", exc.message) from None
    except SourceError as exc:
        raise ToolError(exc.code, exc.message) from None
    return {"dataset": dataset.describe(), "dataset_kind": context.dataset_kind,
            "rows_at_start": s.facts["probe_start"]["n"], "budgets": context.budgets,
            "connector_capabilities": executor.capabilities}


def _family(name: str):
    def handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        s = session(ctx)
        fn = analysis.TOOLS[name]
        try:
            if name == "compare_reference":
                return fn(s, args, base_dir=ctx.config.resolve_path("."))
            return fn(s, args)
        except BudgetExhausted as exc:
            raise ToolError("E_BUDGET_EXHAUSTED", exc.message) from None
        except SourceError as exc:
            if exc.code != "E_SOURCE_TRANSIENT":
                s.ledger.set(FAMILY_OF[name], "blocked", f"{exc.code}: {exc.message}")
            raise ToolError(exc.code, exc.message) from None
        finally:
            s.tool_calls.append({"tool": f"research.{name}", "args": args})
    return handler


def _charts(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    s = session(ctx)
    s.charts = build_charts(s)
    problems = {c["usermeta"]["sfmeridian"]["chart_id"]: validate_chart(c) for c in s.charts}
    bad = {k: v for k, v in problems.items() if v}
    if bad:
        raise ToolError("E_RESEARCH_CHART", f"invalid charts: {bad}")
    s.ledger.set("charts", "completed" if s.charts else "skipped",
                 f"{len(s.charts)} chart(s) from registered evidence" if s.charts else "no chartable evidence",
                 sorted({e for c in s.charts for e in c["usermeta"]["sfmeridian"]["evidence_ids"]}))
    return {"charts": [c["usermeta"]["sfmeridian"]["chart_id"] for c in s.charts]}


def _recommend(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    s = session(ctx)
    s.recommendations = build_recommendations(s)
    s.ledger.set("recommendations", "completed", f"{len(s.recommendations)} recommendation(s)",
                 sorted({e for r in s.recommendations for e in r["evidence_ids"]}))
    return {"recommendations": [{"recommendation_id": r["recommendation_id"], "priority": r["priority"],
                                 "category": r["category"], "evidence_ids": r["evidence_ids"]}
                                for r in s.recommendations]}


def _finish(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    s = session(ctx)
    stop = args.get("stop_reason", "completed")
    if stop != "budget_exhausted":
        try:
            end = _probe(s)
            start = s.facts.get("probe_start", {})
            s.facts["probe_end"] = end
            if end != start:
                s.limitation(f"Source changed during the run: rows {start.get('n')} → {end.get('n')}"
                             + (f", {s.context.change_column} max {start.get('max_change')} → {end.get('max_change')}"
                                if s.context.change_column else "")
                             + ". Queries may describe different states; no consistent snapshot.")
        except (BudgetExhausted, SourceError):
            s.limitation("Source consistency was not re-checked at the end of the run (budget or read failure).")
    else:
        s.limitation("Source consistency was not re-checked: the run stopped at a budget.")
    if s.dataset.is_view and s.dataset.version is None and len(s.executor.log) > 1:
        s.limitation("The object is an unpinned view: each query re-evaluates it, so results may not share one "
                     "snapshot.")
    s.stop_reason = stop
    s.ledger.close(stop)
    root = ctx.config.resolve_path(ctx.config.data.get("research", {}).get("output_dir", ".sfmeridian/research"))
    bundle = write_bundle(s, root)
    s.bundle_dir = str(bundle)
    s.executor.close()
    return {"bundle": str(bundle), "stop_reason": stop,
            "findings": [f.as_dict() for f in s.findings], "recommendations": s.recommendations,
            "coverage": s.ledger.as_list(), "evidence_ids": sorted(s.evidence.records)}


def register(reg: ToolRegistry) -> None:
    col = {"type": "string", "maxLength": 128}
    specs = [
        ToolSpec("research.start", "Open a research session on a configured dataset with a research context.",
                 _obj({"dataset": col, "context": {"type": "object"}}, ["dataset", "context"]), "execute_read", _start),
        ToolSpec("research.intake", "POC file-intake checks (files only; skipped for databases).", _obj({}),
                 "execute_read", _family("intake")),
        ToolSpec("research.inspect_schema", "Declared columns and inferred types.", _obj({}), "execute_read",
                 _family("inspect_schema")),
        ToolSpec("research.summarize_columns", "Pushed-down counts, nulls, distinct, min, max, mean.", _obj({}),
                 "execute_read", _family("summarize_columns")),
        ToolSpec("research.check_grain", "Business-grain missing and repeated keys; optional wider-grain probe.",
                 _obj({"extra_columns": {"type": "array", "items": col}}), "execute_read", _family("check_grain")),
        ToolSpec("research.inspect_missingness", "Missingness of one column by date or segment.",
                 _obj({"column": col, "by": {"type": "string", "enum": ["date", "segment"]}, "segment": col},
                      ["column", "by"]), "execute_read", _family("inspect_missingness")),
        ToolSpec("research.inspect_time", "Rows by date; gaps against the supplied calendar.", _obj({}),
                 "execute_read", _family("inspect_time")),
        ToolSpec("research.check_domain_rules", "Securities-finance rule pack counts, optionally by segment.",
                 _obj({"rule_id": col, "by": col}), "execute_read", _family("check_domain_rules")),
        ToolSpec("research.inspect_numeric", "Distribution of a numeric column on the ordered extract.",
                 _obj({"column": col}, ["column"]), "execute_read", _family("inspect_numeric")),
        ToolSpec("research.inspect_categories", "Category frequencies (values withheld for sensitive columns).",
                 _obj({"column": col}, ["column"]), "execute_read", _family("inspect_categories")),
        ToolSpec("research.inspect_relationships", "Bounded numeric associations on the extract (descriptive).",
                 _obj({}), "execute_read", _family("inspect_relationships")),
        ToolSpec("research.compare_segments", "Numeric column across a segment (pushed down).",
                 _obj({"column": col, "segment": col}, ["column"]), "execute_read", _family("compare_segments")),
        ToolSpec("research.inspect_target", "Target summary when a target is declared.", _obj({}), "execute_read",
                 _family("inspect_target")),
        ToolSpec("research.inspect_availability", "Point-in-time availability against the as-of and timezone.",
                 _obj({}), "execute_read", _family("inspect_availability")),
        ToolSpec("research.compare_reference", "Compare with a versioned reference profile.", _obj({}),
                 "execute_read", _family("compare_reference")),
        ToolSpec("research.render_charts", "Vega-Lite charts from registered evidence.", _obj({}), "read", _charts),
        ToolSpec("research.recommend_actions", "Ranked, evidence-linked recommendations.", _obj({}), "read",
                 _recommend),
        ToolSpec("research.finish", "Re-probe the source, close coverage, and write the run bundle.",
                 _obj({"stop_reason": {"type": "string", "enum": ["completed", "budget_exhausted", "blocked",
                                                                  "no_productive_action", "tool_failure",
                                                                  "cancelled"]}}),
                 "report", _finish),
    ]
    for spec in specs:
        reg.register(spec)
