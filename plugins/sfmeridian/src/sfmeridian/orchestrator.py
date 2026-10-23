"""``sfmeridian_orchestrator`` loop agent (coverage C-04, spec 0116 REQ-014)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .agent import (
    AgentManifest,
    AgentRun,
    Escalate,
    Finish,
    LoopState,
    ToolCall,
    Verdict,
    load_manifest,
    run_agent,
)
from .handoff import HandoffError, HandoffRequest, SpecialistHandoff, build_handoff
from .tools import ToolContext, ToolRegistry, default_registry

__all__ = ["VERIFIERS", "OrchestratorPolicy", "prepare_handoff", "run_orchestrator"]

_TERMINAL = {
    "governed_answer", "governed_clarification", "governed_unavailable",
    "no_governed_match", "tail_failed", "writeback_requested",
}


class OrchestratorPolicy:
    name = "deterministic"

    def decide(self, state: LoopState):
        validation = state.last("config.validate")
        if validation is None:
            return ToolCall("config.validate", {}, "validate configuration before routing")
        if not validation.ok or validation.output.get("valid") is not True:
            return Escalate("configuration is invalid", {"issues": validation.output.get("issues", [])})
        asked = state.last("ask")
        if asked is None:
            required = ("question", "as_of", "profile")
            missing = [name for name in required if not state.inputs.get(name)]
            if missing:
                return Escalate("ask inputs are incomplete", {"missing": missing})
            args: dict[str, Any] = {name: state.inputs[name] for name in (
                "question", "as_of", "profile", "caller", "params", "pit_columns",
                "default_window_periods", "max_repairs", "action") if name in state.inputs}
            return ToolCall("ask", args, "use the governed-first runtime; never answer from memory")
        if not asked.ok:
            if asked.error_code == "E_WRITEBACK_DISABLED":
                output: dict[str, Any] = {
                    "route": "writeback_requested", "tier": None, "reason": asked.error or "",
                    "error_code": asked.error_code, "citations": [], "trace": [],
                }
                return Finish("write-back refused", output)
            return Escalate("ask failed", {"error_code": asked.error_code, "reason": asked.error})
        output = dict(asked.output)
        route = output.get("route")
        if route not in _TERMINAL:
            return Escalate("ask returned an unknown route", {"route": route})
        if route in ("governed_unavailable", "tail_failed"):
            return Escalate(str(output.get("reason") or "required evidence is unavailable"), output)
        return Finish(f"route {route} completed at tier {output.get('tier')}", output)


def verify_tier(state: LoopState, finish: Finish) -> Verdict:
    route, tier = finish.outputs.get("route"), finish.outputs.get("tier")
    problems = []
    if route not in _TERMINAL:
        problems.append(f"unknown terminal route {route!r}")
    if route in ("governed_answer", "governed_clarification", "governed_unavailable") and tier != "governed":
        problems.append(f"{route} must record tier governed")
    if route == "no_governed_match" and tier not in ("reuse", "adapt", "generate"):
        problems.append("successful tail must record reuse, adapt, or generate")
    if tier is None and not finish.outputs.get("reason"):
        problems.append("an outcome without a tier needs a reason")
    return Verdict(not problems, tuple(problems))


def verify_grounded(state: LoopState, finish: Finish) -> Verdict:
    route = finish.outputs.get("route")
    citations = finish.outputs.get("citations") or []
    needs_run = route in ("governed_answer", "no_governed_match")
    problems = []
    if needs_run and not any(isinstance(item, str) and item.startswith("run:") for item in citations):
        problems.append(f"{route} has no execution run citation")
    if route == "no_governed_match" and "execution" not in finish.outputs:
        problems.append("tail result has no execution evidence")
    return Verdict(not problems, tuple(problems))


def verify_no_fallthrough(state: LoopState, finish: Finish) -> Verdict:
    route = finish.outputs.get("route")
    events = [item.get("event") for item in finish.outputs.get("trace", [])]
    problems = []
    if route in ("governed_answer", "governed_clarification", "governed_unavailable"):
        forbidden = {"no_governed_match", "composed", "verified", "executed"} & set(events)
        if forbidden:
            problems.append(f"governed route fell through to tail events {sorted(forbidden)}")
    return Verdict(not problems, tuple(problems))


def verify_writeback(state: LoopState, finish: Finish) -> Verdict:
    action = state.inputs.get("action", "read")
    problems = []
    if action != "read" and (finish.outputs.get("route") != "writeback_requested"
                             or finish.outputs.get("error_code") != "E_WRITEBACK_DISABLED"):
        problems.append("write-back request was not refused with E_WRITEBACK_DISABLED")
    return Verdict(not problems, tuple(problems))


VERIFIERS = {
    "orchestrator.tier_recorded": verify_tier,
    "orchestrator.answer_grounded": verify_grounded,
    "orchestrator.no_governed_fallthrough": verify_no_fallthrough,
    "orchestrator.writeback_refused": verify_writeback,
}


def run_orchestrator(ctx: ToolContext, *, policy=None, registry: ToolRegistry | None = None,
                     inputs: Mapping[str, Any] | None = None, manifest: AgentManifest | None = None) -> AgentRun:
    return run_agent(manifest or load_manifest("sfmeridian_orchestrator"), policy or OrchestratorPolicy(),
                     registry or default_registry(), ctx, inputs=inputs, verifiers=VERIFIERS)


def prepare_handoff(
    run: AgentRun,
    *,
    workflow: str,
    receiver: str,
    request: str,
    pit_basis: str,
    metric_citations: tuple[str, ...] = (),
) -> SpecialistHandoff:
    """Create inert specialist evidence from a completed orchestrator run."""
    if run.status != "completed":
        raise HandoffError("E_HANDOFF_ORIGIN", "only a completed orchestrator run may produce a handoff")
    output = run.outputs
    evidence = output.get("execution") or output.get("governed_evidence")
    if not isinstance(evidence, Mapping) or not isinstance(evidence.get("provenance"), Mapping):
        raise HandoffError("E_HANDOFF_EVIDENCE", "orchestrator output has no execution provenance")
    provenance = evidence["provenance"]
    run_id = provenance.get("run_id")
    as_of = provenance.get("as_of")
    profile = provenance.get("profile")
    snapshot_id = provenance.get("snapshot_id")
    clearance = provenance.get("clearance")
    required = (run_id, as_of, profile, snapshot_id, clearance)
    if not all(isinstance(value, str) and value for value in required):
        raise HandoffError("E_HANDOFF_EVIDENCE", "execution provenance is incomplete")
    structured = ("run:", "query:", "metric:", "catalog:", "exemplar:", "pack:")
    citations = tuple(str(item) for item in output.get("citations", ())
                      if isinstance(item, str) and item.startswith(structured))
    metric = evidence.get("metric")
    if isinstance(metric, str) and metric:
        citations += (f"metric:{metric}",)
    citations += metric_citations
    withheld = provenance.get("withheld_columns")
    withheld_count = len(withheld) if isinstance(withheld, list) else 0
    return build_handoff(HandoffRequest(
        workflow=workflow,
        receiver=receiver,
        request=request,
        originating_run_id=run.run_id,
        execution_run_ids=(run_id,),
        as_of=as_of,
        pit_basis=pit_basis,
        profile=profile,
        snapshot_id=snapshot_id,
        citations=citations,
        clearance=clearance,
        withheld_column_count=withheld_count,
        parameters_redacted=True,
    ))
