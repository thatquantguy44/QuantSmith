"""``lending_data_researcher`` (coverage row C-10): adaptive dataset research loop.

Spec ``0121`` REQ-010. The deterministic :class:`ResearchPolicy` recomputes
its agenda from the evidence gathered so far, so follow-ups appear when the
evidence calls for them:

* missing values in a column → missingness by date and by segment;
* repeated keys with probe columns configured → a wider-grain probe;
* a domain-rule violation with a segment configured → the rule by segment;

then distributions, relationships, segments, target, availability, reference,
charts, recommendations, and finish. A budget stop finishes the run with
``stop_reason: budget_exhausted`` (never as completed coverage). A model
policy (``sfmeridian.agent.ModelPolicy``) can drive the same manifest.

Verifiers: findings and recommendations resolve to registered evidence;
coverage is accounted for; extract-scoped evidence never backs a population
claim; recommendations satisfy the contract and never execute.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .. import CONTRACT_VERSION, __version__
from ..agent import (
    AgentRun,
    Escalate,
    Finish,
    LoopState,
    ToolCall,
    Verdict,
    load_manifest,
    run_agent,
)
from ..tools import ToolContext, ToolRegistry, default_registry
from .analysis import analysis_columns
from .bundle import write_manifest

__all__ = ["VERIFIERS", "ResearchPolicy", "run_research"]

MAX_MISSING_FOLLOWUPS = 6
MAX_NUMERIC = 8
MAX_CATEGORICAL = 8
_REC_FIELDS = ("recommendation_id", "priority", "category", "action", "evidence_ids", "scope", "counts",
               "observation", "confidence", "limitations", "business_consequence", "next_diagnostic",
               "dependencies", "effort", "verification")


def _key(name: str, args: Mapping[str, Any]) -> str:
    return json.dumps({"n": name, "a": args}, sort_keys=True, default=str)


class ResearchPolicy:
    name = "deterministic-research-v1"

    def __init__(self, ctx: ToolContext) -> None:
        self.ctx = ctx
        self._calls: dict[int, dict[str, Any]] = {}
        self._retried: set = set()

    def _agenda(self, state: LoopState) -> list[tuple[str, dict[str, Any]]]:
        s = self.ctx.session.get("research")
        if s is None:
            return [("research.start", {"dataset": state.inputs["dataset"], "context": state.inputs["context"]})]
        c = s.context
        types = s.facts.get("types", {})
        agenda: list[tuple[str, dict[str, Any]]] = [
            ("research.intake", {}), ("research.inspect_schema", {}), ("research.summarize_columns", {}),
            ("research.check_grain", {})]
        grain = next((f for f in s.findings if f.kind == "grain_repeats"), None)
        if grain is not None and grain.follow_up:
            agenda.append((grain.follow_up["tool"], grain.follow_up["args"]))
        agenda.append(("research.inspect_time", {}))
        summaries = s.facts.get("summaries", {})
        missing_cols = sorted((c_ for c_, v in summaries.items() if v["nulls"]),
                              key=lambda c_: (-summaries[c_]["nulls"], c_))[:MAX_MISSING_FOLLOWUPS]
        for col in missing_cols:
            if c.time_column and col != c.time_column:
                agenda.append(("research.inspect_missingness", {"column": col, "by": "date"}))
            if c.segments and col not in c.segments:
                agenda.append(("research.inspect_missingness", {"column": col, "by": "segment"}))
        if not missing_cols:
            agenda.append(("_mark", {"family": "missingness", "reason": "no missing values in analysis columns"}))
        elif not c.time_column and not c.segments:
            agenda.append(("_mark", {"family": "missingness", "reason": "missing values found (see univariate) but no "
                                     "time column or segment is configured to diagnose where they concentrate"}))
        agenda.append(("research.check_domain_rules", {}))
        for f in s.findings:
            if f.kind.startswith("rule:") and f.follow_up:
                agenda.append((f.follow_up["tool"], f.follow_up["args"]))
        cols = [x for x in analysis_columns(s) if x != c.time_column]
        numeric = [x for x in cols if types.get(x) == "numeric"][:MAX_NUMERIC]
        categorical = [x for x in cols if types.get(x) == "text_or_mixed"][:MAX_CATEGORICAL]
        agenda += [("research.inspect_numeric", {"column": x}) for x in numeric]
        if not numeric:
            agenda.append(("_mark", {"family": "numeric", "reason": "no numeric analysis columns"}))
        agenda += [("research.inspect_categories", {"column": x}) for x in categorical]
        if not categorical:
            agenda.append(("_mark", {"family": "categorical", "reason": "no categorical analysis columns"}))
        agenda.append(("research.inspect_relationships", {}))
        if numeric:
            agenda += [("research.compare_segments", {"column": x}) for x in numeric[:3]]
        else:
            agenda.append(("_mark", {"family": "segments", "reason": "no numeric column to compare across segments"}))
        agenda += [("research.inspect_target", {}), ("research.inspect_availability", {}),
                   ("research.compare_reference", {}), ("research.render_charts", {}),
                   ("research.recommend_actions", {}), ("research.finish", {"stop_reason": "completed"})]
        return agenda

    def decide(self, state: LoopState):
        action = self._decide(state)
        if isinstance(action, ToolCall):
            self._calls[state.step] = action.args
        return action

    def _decide(self, state: LoopState):
        s = self.ctx.session.get("research")
        last = state.observations[-1] if state.observations else None
        if last is not None and last.kind == "tool" and not last.ok:
            if last.error_code == "E_BUDGET_EXHAUSTED":
                if last.name == "research.finish" or s is None:
                    return Escalate("stopped at a budget", {"stop_reason": "budget_exhausted"})
                return ToolCall("research.finish", {"stop_reason": "budget_exhausted"}, "a budget is exhausted")
            if last.name == "research.start":
                return Escalate(f"research cannot start: {last.error}", {"error_code": last.error_code})
            if last.name == "research.finish":
                return Escalate(f"the bundle could not be written: {last.error}", {"error_code": last.error_code})
            if last.error_code == "E_SOURCE_TRANSIENT" and last.step not in self._retried:
                self._retried.add(last.step)
                return ToolCall(last.name, dict(self._calls.get(last.step, {})), "one retry after a transient read")
        if last is not None and last.kind == "tool" and last.name == "research.finish" and last.ok:
            out = last.output
            if out["stop_reason"] == "budget_exhausted":
                return Escalate("stopped at a budget; coverage is incomplete", {**out, "stop_reason": "budget_exhausted"})
            return Finish(f"{len(out['findings'])} finding(s), {len(out['recommendations'])} recommendation(s)", out)
        if state.pending_verifier_problems():
            return Escalate("verifiers failed on a deterministic run: " + "; ".join(state.pending_verifier_problems()))
        attempted = {_key(o.name, self._calls.get(o.step, {})) for o in state.observations if o.kind == "tool"}
        for name, args in self._agenda(state):
            if name == "_mark":
                if s is not None and s.ledger.entries[args["family"]]["status"] == "pending":
                    s.ledger.set(args["family"], "skipped", args["reason"])
                continue
            if _key(name, args) not in attempted:
                return ToolCall(name, args, "next item on the evidence-driven agenda")
        return ToolCall("research.finish", {"stop_reason": "no_productive_action"}, "agenda exhausted")


# --------------------------------------------------------------------------
# Verifiers
# --------------------------------------------------------------------------

def verify_evidence(state: LoopState, finish: Finish) -> Verdict:
    out = finish.outputs
    known = set(out.get("evidence_ids", []))
    problems = []
    for f in out.get("findings", []):
        if not f["evidence_ids"] or not set(f["evidence_ids"]) <= known:
            problems.append(f"{f['finding_id']} cites unregistered evidence")
    findings = {f["finding_id"]: f for f in out.get("findings", [])}
    for r in out.get("recommendations", []):
        if not r["evidence_ids"] or not set(r["evidence_ids"]) <= known:
            problems.append(f"{r['recommendation_id']} cites unregistered evidence")
        f = findings.get(r.get("finding_id"))
        if f is None or set(r["evidence_ids"]) != set(f["evidence_ids"]):
            problems.append(f"{r['recommendation_id']} evidence does not match its finding")
    return Verdict(not problems, tuple(problems))


def verify_coverage(state: LoopState, finish: Finish) -> Verdict:
    out = finish.outputs
    problems = [f"{c['family']} is still pending" for c in out.get("coverage", []) if c["status"] == "pending"]
    problems += [f"{c['family']} has no reason" for c in out.get("coverage", [])
                 if c["status"] in ("blocked", "skipped", "budget_exhausted") and not c.get("reason")]
    return Verdict(not problems, tuple(problems))


def verify_scope(state: LoopState, finish: Finish) -> Verdict:
    problems = []
    for f in finish.outputs.get("findings", []):
        if f["scope"] == "ordered_extract" and "filtered population" in f["observation"]:
            problems.append(f"{f['finding_id']} states a population claim from an extract")
    return Verdict(not problems, tuple(problems))


def verify_recommendations(state: LoopState, finish: Finish) -> Verdict:
    problems = []
    for r in finish.outputs.get("recommendations", []):
        missing = [k for k in _REC_FIELDS if k not in r]
        if missing:
            problems.append(f"{r.get('recommendation_id')} lacks {missing}")
        if r.get("executes") is not False or r.get("next_diagnostic", {}).get("executes", False):
            problems.append(f"{r.get('recommendation_id')} must not execute")
    return Verdict(not problems, tuple(problems))


VERIFIERS = {
    "research.findings_resolve_to_evidence": verify_evidence,
    "research.coverage_accounted": verify_coverage,
    "research.scope_honest": verify_scope,
    "research.recommendations_contract": verify_recommendations,
}


def run_research(ctx: ToolContext, *, dataset: str, context: Mapping[str, Any], policy=None,
                 registry: ToolRegistry | None = None) -> AgentRun:
    """Run ``lending_data_researcher`` and write the bundle's run manifest."""
    registry = registry or default_registry()
    manifest = load_manifest("lending_data_researcher")
    budgets = dict(context.get("budgets") or {})
    if "max_steps" in budgets:
        manifest = type(manifest).from_dict({**manifest.as_dict(), "max_steps": int(budgets["max_steps"]),
                                             "max_tool_calls": int(budgets["max_steps"])})
    inputs = {"dataset": dataset, "context": dict(context)}
    run = run_agent(manifest, policy or ResearchPolicy(ctx), registry, ctx, inputs=inputs, verifiers=VERIFIERS)
    s = ctx.session.get("research")
    if s is not None and s.bundle_dir:
        timings = {"queries": [{"query_id": q["query_id"], "elapsed_seconds": q["elapsed_seconds"]}
                               for q in s.executor.log]}
        write_manifest(Path(s.bundle_dir), {
            "run_id": run.run_id, "agent": run.agent, "policy": run.policy, "status": run.status,
            "stop_reason": s.stop_reason, "summary": run.summary, "config_hash": ctx.config.hash,
            "sfmeridian_version": __version__, "contract_version": CONTRACT_VERSION,
            "dataset": s.dataset.describe(), "context": s.context.raw, "as_of": s.context.as_of,
            "tool_calls": [{"step": t["step"], "name": t["name"], "args": t.get("args")} for t in run.trace
                           if t["event"] == "decide"],
            "budgets": {"limits": s.context.budgets, "used": s.budget.used(), "steps": run.steps},
            "rerun": "python analysis/rerun.py --config <your sfmeridian config>",
        }, timings)
    return run
