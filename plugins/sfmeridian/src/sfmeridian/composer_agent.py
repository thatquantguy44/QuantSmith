"""``sql_composer`` loop agent (coverage C-03, spec 0116 REQ-013).

The agent is allowed to retrieve, compose, and verify.  It cannot execute,
call ``ask``, promote evidence, or use a human-only tool.  Completion is gated
on a recorded no-governed-match route, observed source citations, coherent
composition path provenance, and a token returned by ``sql.verify``.
"""

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
from .tools import ToolContext, ToolRegistry, default_registry

__all__ = ["VERIFIERS", "ComposerPolicy", "run_composer"]


def _calls(state: LoopState, name: str) -> list[Any]:
    return [item for item in state.observations if item.kind == "tool" and item.name == name]


class ComposerPolicy:
    name = "deterministic"

    def decide(self, state: LoopState):
        if state.inputs.get("route_outcome") != "no_governed_match":
            return Escalate("SQL composition requires a recorded no-governed-match route",
                            {"route_outcome": state.inputs.get("route_outcome")})
        required = ("question", "profile")
        missing = [name for name in required if not state.inputs.get(name)]
        if missing:
            return Escalate("composer inputs are incomplete", {"missing": missing})
        if not state.called("queries.search"):
            return ToolCall("queries.search", {
                "query": state.inputs["question"], "profile": state.inputs["profile"],
                "include_hints": False, "limit": 5,
            }, "retrieve reviewed evidence before composition")
        if not state.called("sql.compose"):
            args: dict[str, Any] = {name: state.inputs[name] for name in (
                "question", "profile", "route_outcome", "params", "as_of", "pit_columns", "tags")
                    if name in state.inputs}
            return ToolCall("sql.compose", args, "compose only after the governed no-match route")
        composed = state.last("sql.compose")
        if not composed or not composed.ok:
            return Escalate("composition failed", {"error_code": composed.error_code if composed else None,
                                                    "error": composed.error if composed else "no observation"})
        sources = [item["id"] for item in composed.output.get("source_exemplars", [])]
        fetched = {call.output.get("exemplar", {}).get("exemplar_id") for call in _calls(state, "queries.get")
                   if call.ok}
        remaining = [source for source in sources if source not in fetched]
        if remaining:
            return ToolCall("queries.get", {"exemplar_id": remaining[0]}, "resolve every cited source")
        if not state.called("sql.verify"):
            return ToolCall("sql.verify", {"composition_id": composed.output["composition_id"]},
                            "obtain the mandatory exact-context token")
        checked = state.last("sql.verify")
        if not checked or not checked.ok or checked.output.get("ok") is not True:
            return Escalate("verification refused the composition", {
                "findings": checked.output.get("findings", []) if checked else [],
                "error_code": checked.error_code if checked else None,
            })
        searched = state.last("queries.search")
        output = {
            "route_outcome": state.inputs["route_outcome"],
            "retrieval": searched.output if searched else {"hits": []},
            "composition": composed.output,
            "verification": checked.output,
            "citations": [
                f"exemplar:{item.get('query_id') or item['id']}@{item['repo']}:{item['ref']}"
                for item in composed.output.get("source_exemplars", [])
            ],
        }
        return Finish(f"{composed.output['path']} composition verified", output)


def verify_route(state: LoopState, finish: Finish) -> Verdict:
    problems = []
    if state.inputs.get("route_outcome") != "no_governed_match":
        problems.append("route_outcome is not no_governed_match")
    forbidden = [item.name for item in state.observations
                 if item.kind == "tool" and item.name in ("ask", "sql.execute")]
    problems.extend(f"forbidden tool {name} was called" for name in forbidden)
    if finish.outputs.get("route_outcome") != "no_governed_match":
        problems.append("finish does not preserve the route outcome")
    return Verdict(not problems, tuple(problems))


def verify_citations(state: LoopState, finish: Finish) -> Verdict:
    searched = state.last("queries.search")
    observed = {item["exemplar_id"] for item in searched.output.get("hits", [])} if searched and searched.ok else set()
    fetched = {item.output.get("exemplar", {}).get("exemplar_id") for item in _calls(state, "queries.get")
               if item.ok}
    composition = finish.outputs.get("composition", {})
    sources = {item.get("id") for item in composition.get("source_exemplars", [])}
    problems = []
    if not sources <= observed:
        problems.append(f"composition cites unobserved source(s): {sorted(sources - observed)}")
    if not sources <= fetched:
        problems.append(f"composition source(s) were not fetched: {sorted(sources - fetched)}")
    path = composition.get("path")
    if path in ("reuse", "adapt") and not sources:
        problems.append(f"{path} has no source exemplar")
    if path == "generate" and sources:
        problems.append("generate claims source exemplars")
    if path not in ("reuse", "adapt", "generate"):
        problems.append("composition path is missing or unknown")
    return Verdict(not problems, tuple(problems))


def verify_token(state: LoopState, finish: Finish) -> Verdict:
    observed = state.last("sql.verify")
    returned = finish.outputs.get("verification", {})
    problems = []
    if observed is None or not observed.ok or observed.output.get("ok") is not True:
        problems.append("sql.verify did not return a successful verification")
    elif (not isinstance(observed.output.get("token"), str)
          or returned.get("token") != observed.output.get("token")):
        problems.append("finish does not carry the observed verification token")
    composition = finish.outputs.get("composition", {})
    if returned.get("query_id") != composition.get("query_id"):
        problems.append("verification query identity differs from composition")
    return Verdict(not problems, tuple(problems))


VERIFIERS = {
    "compose.route_permits_composition": verify_route,
    "compose.path_and_sources_recorded": verify_citations,
    "compose.verified_before_return": verify_token,
}


def run_composer(ctx: ToolContext, *, policy=None, registry: ToolRegistry | None = None,
                 inputs: Mapping[str, Any] | None = None, manifest: AgentManifest | None = None) -> AgentRun:
    return run_agent(manifest or load_manifest("sql_composer"), policy or ComposerPolicy(),
                     registry or default_registry(), ctx, inputs=inputs, verifiers=VERIFIERS)
