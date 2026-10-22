"""``semantic_mapping_steward`` (coverage row C-02): catalog, drift, and meaning.

Spec ``0115`` REQ-014. Goal: keep each profile's catalog snapshot current,
exclude drifted exemplars, validate every concept binding and metric source
against the catalog and the ``0081``/``0063`` vocabulary, account for every
governed pack metric (bound, or unbound with the missing evidence), and stage
the pack amendments the mapping and the query repository need for the named
pack reviewer.

The deterministic :class:`StewardPolicy` runs the loop offline:
``config.validate`` → ``repos.index`` → ``catalog.snapshot`` →
``catalog.diff`` (each profile) → ``catalog.reconcile`` → ``mapping.validate``
→ ``metrics.list`` → ``mapping.amendments`` → ``mapping.propose_amendment``
(each needed, unstaged proposal) → finish. It escalates when the
configuration is invalid or no catalog could be taken. Four verifiers gate
``completed``:

* every binding reported ``bound`` resolves in a catalog snapshot observed in
  this run;
* every bound binding declares its viewpoint and unit;
* every concept the report uses is in the observed vocabulary (pack,
  proposed amendment, or ``0063``), and every amendment stays ``proposed``;
* every governed pack metric is accounted for.

Never: invents a mapping, edits the pack or its review block, defines a
concept privately, or decides whether a breaking catalog change is safe
(``schema_evolution`` does).
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

__all__ = ["VERIFIERS", "StewardPolicy", "build_report", "run_steward"]


def _out(state: LoopState, tool: str) -> dict[str, Any]:
    obs = state.last(tool)
    return obs.output if obs and obs.ok else {}


def _calls(state: LoopState, tool: str) -> list[Any]:
    return [o for o in state.observations if o.kind == "tool" and o.name == tool]


def build_report(state: LoopState, profiles: list[str]) -> dict[str, Any]:
    """The stewardship report, built only from this run's observations."""
    snapshot = _out(state, "catalog.snapshot")
    diffs = [o.output for o in _calls(state, "catalog.diff") if o.ok]
    drift = _out(state, "catalog.reconcile")
    mapping = _out(state, "mapping.validate")
    amend = _out(state, "mapping.amendments")
    proposed = [o.output["proposal"]["amendment"]["amendment_id"] for o in _calls(state, "mapping.propose_amendment")
                if o.ok]
    findings: list[dict[str, Any]] = []

    def add(severity: str, kind: str, message: str, evidence: list[dict[str, str]], action: str) -> None:
        findings.append({"id": f"F-{len(findings) + 1:03d}", "severity": severity, "kind": kind,
                         "message": message, "evidence": evidence, "action": action})

    for e in snapshot.get("errors", []):
        add("high", "catalog_unavailable", f"{e['profile']}: {e['message']}", [{"type": "profile", "ref": e["profile"]}],
            "Inject a connection for the profile or fix the declared catalog file.")
    handoffs = []
    for d in diffs:
        if d.get("classification") == "breaking":
            add("high", "breaking_catalog_change",
                f"{d['profile']}: {sum(c['breaking'] for c in d['changes'])} breaking change(s) from {d['from']} to {d['to']}",
                [{"type": "snapshot", "ref": d["to"]}], "schema_evolution decides whether downstream loads and queries are safe.")
            handoffs.append({**d["handoff"], "profile": d["profile"], "snapshot": d["to"]})
    for x in drift.get("drifted", []):
        add("high" if x["review_status"] == "reviewed" else "low", "drifted_exemplar",
            f"{x.get('query_id') or x['exemplar_id']} ({x['path']}) references missing "
            f"{', '.join(x['missing_tables'] + x['missing_columns'])}; {x['status']}",
            [{"type": "exemplar", "ref": x["exemplar_id"]}], x["action"])
    for b in mapping.get("bindings", []):
        if b["status"] != "bound":
            add("high", "invalid_binding", f"{b['profile']}.{b['concept']}: "
                + "; ".join(f"{p['code']} {p['message']}" for p in b["problems"]),
                [{"type": "binding", "ref": f"{b['profile']}.{b['concept']}"}],
                "Fix the binding in semantic_mapping, or propose a pack amendment for an unknown concept.")
    for g in mapping.get("governed_metrics", []):
        if g["status"] != "bound":
            add("medium", f"{g['status']}_governed_metric", f"{g['metric']} is {g['status']}; missing: "
                + "; ".join(g["missing"]), [{"type": "metric", "ref": g["metric"]}],
                "A metric owner binds it with evidence, or records that the deployment does not serve it.")
    for s in mapping.get("metric_sources", []):
        if s["status"] != "available":
            add("high", "metric_source_unavailable", f"{s['metric']} via {s['exemplar_id']}: "
                + "; ".join(r["message"] for r in s["reasons"]), [{"type": "metric", "ref": s["metric"]}],
                "The governed tier will not serve this metric until its source query is fixed and reviewed.")
    for a in amend.get("amendments", []):
        if a["needed_by"]:
            add("low", "pack_amendment_proposed", f"{a['name']} ({a['amendment_id']}) is needed by "
                + ", ".join(a["needed_by"]) + f"; proposed for review by {amend.get('reviewer')}",
                [{"type": "amendment", "ref": a["amendment_id"]}],
                "The named pack reviewer accepts or rejects it through the 0081 review flow.")
    pack = mapping.get("pack", {})
    return {"profiles": profiles, "snapshots": snapshot.get("snapshots", []), "diffs": diffs,
            "drift": drift.get("drifted", []), "bindings": mapping.get("bindings", []),
            "governed_metrics": mapping.get("governed_metrics", []),
            "metric_sources": mapping.get("metric_sources", []),
            "amendments": [{**a, "staged": a["staged"] or a["amendment_id"] in proposed}
                           for a in amend.get("amendments", [])],
            "pack": pack, "caveats": [pack["caveat"]] if pack.get("caveat") else [], "handoffs": handoffs,
            "findings": findings}


class StewardPolicy:
    name = "deterministic"

    def decide(self, state: LoopState):
        validate = state.last("config.validate")
        if validate is None:
            return ToolCall("config.validate", {}, "check configuration first")
        if not validate.ok or not validate.output.get("valid", False):
            return Escalate("configuration is invalid; a person must fix it", {"issues": validate.output.get("issues", [])})
        if not state.called("repos.index"):
            return ToolCall("repos.index", {}, "refresh the exemplars reconciliation checks")
        if not state.called("catalog.snapshot"):
            return ToolCall("catalog.snapshot", {}, "take each profile's catalog snapshot")
        snap = state.last("catalog.snapshot")
        if not snap.ok:
            return Escalate("no catalog snapshot could be taken; a person must supply a connection or catalog file",
                            {"error": snap.error})
        profiles = [s["profile"] for s in snap.output.get("snapshots", [])]
        diffed = len(_calls(state, "catalog.diff"))          # one diff per profile, in snapshot order
        if diffed < len(profiles):
            p = profiles[diffed]
            return ToolCall("catalog.diff", {"profile": p}, f"classify catalog changes for {p}")
        for tool in ("catalog.reconcile", "mapping.validate", "metrics.list", "mapping.amendments"):
            if not state.called(tool):
                return ToolCall(tool, {}, f"gather {tool} evidence")
        if not _out(state, "mapping.validate").get("pack", {}).get("pack_id"):
            return Escalate("no 0081 pack was resolved for governed_tier.domain_tags; a person must install the "
                            "QuantSmith SDK or set governed_tier.packs_root", {"pack": _out(state, "mapping.validate")
                                                                              .get("pack", {})})
        staged = {o.output["proposal"]["amendment"]["amendment_id"] for o in _calls(state, "mapping.propose_amendment")
                  if o.ok}
        for a in _out(state, "mapping.amendments").get("amendments", []):
            if a["needed_by"] and not a["staged"] and a["amendment_id"] not in staged:
                return ToolCall("mapping.propose_amendment", {"amendment_id": a["amendment_id"],
                                                              "needed_by": a["needed_by"]},
                                f"stage {a['name']} for the pack reviewer")
        report = build_report(state, profiles)
        g = report["governed_metrics"]
        summary = (f"{sum(x['status'] == 'bound' for x in g)}/{len(g)} governed metrics bound; "
                   f"{len(report['drift'])} drifted exemplar(s); "
                   f"{sum(1 for a in report['amendments'] if a['needed_by'])} amendment(s) proposed; "
                   f"{len(report['findings'])} finding(s)")
        return Finish(summary, report)


# --------------------------------------------------------------------------
# Verifiers
# --------------------------------------------------------------------------

def verify_resolves(state: LoopState, finish: Finish) -> Verdict:
    snapshots = {s["profile"]: s["snapshot_id"] for s in _out(state, "catalog.snapshot").get("snapshots", [])}
    observed = {(b["profile"], b["concept"]): b for b in _out(state, "mapping.validate").get("bindings", [])}
    problems = []
    for b in finish.outputs.get("bindings", []):
        if b.get("status") != "bound":
            continue
        seen = observed.get((b.get("profile"), b.get("concept")))
        if seen is None or seen["status"] != "bound":
            problems.append(f"{b.get('profile')}.{b.get('concept')} is reported bound but mapping.validate did not bind it")
        elif seen.get("snapshot_id") != snapshots.get(b.get("profile")):
            problems.append(f"{b.get('profile')}.{b.get('concept')} was not validated against this run's snapshot")
        elif not seen.get("columns"):
            problems.append(f"{b.get('profile')}.{b.get('concept')} resolves to no catalog column")
    return Verdict(not problems, tuple(problems))


def verify_declared(state: LoopState, finish: Finish) -> Verdict:
    problems = [f"{b.get('profile')}.{b.get('concept')} lacks {k}" for b in finish.outputs.get("bindings", [])
                if b.get("status") == "bound" for k in ("viewpoint", "unit") if not b.get(k)]
    return Verdict(not problems, tuple(problems))


def verify_vocabulary(state: LoopState, finish: Finish) -> Verdict:
    listed = _out(state, "metrics.list")
    known = {m["name"] for m in listed.get("metrics", []) + listed.get("proposed_metrics", [])}
    known |= {d["name"] for d in listed.get("dimensions", []) + listed.get("proposed_dimensions", [])}
    problems = []
    for b in finish.outputs.get("bindings", []):
        if b.get("status") == "bound" and b.get("concept") not in known and b.get("vocabulary") != "taxonomy":
            problems.append(f"{b.get('concept')} is not in the pack, the proposed amendments, or 0063")
    for a in finish.outputs.get("amendments", []):
        if a.get("status") != "proposed":
            problems.append(f"amendment {a.get('amendment_id')} is {a.get('status')!r}; only a person accepts amendments")
    if not listed:
        problems.append("metrics.list was never consulted")
    return Verdict(not problems, tuple(problems))


def verify_accounted(state: LoopState, finish: Finish) -> Verdict:
    pack = {m["name"] for m in _out(state, "metrics.list").get("metrics", [])}
    reported = {g.get("metric"): g for g in finish.outputs.get("governed_metrics", [])}
    problems = [f"governed metric {m} is not accounted for" for m in sorted(pack - set(reported))]
    problems += [f"{m} is {g.get('status')} without the missing evidence" for m, g in sorted(reported.items())
                 if g.get("status") != "bound" and not g.get("missing")]
    return Verdict(not problems, tuple(problems))


VERIFIERS = {
    "mapping.every_binding_resolves_in_catalog": verify_resolves,
    "mapping.viewpoint_and_unit_declared": verify_declared,
    "mapping.no_private_concepts": verify_vocabulary,
    "mapping.every_governed_metric_accounted": verify_accounted,
}


def run_steward(ctx: ToolContext, *, policy=None, registry: ToolRegistry | None = None,
                inputs: Mapping[str, Any] | None = None, manifest: AgentManifest | None = None) -> AgentRun:
    registry = registry or default_registry()
    return run_agent(manifest or load_manifest("semantic_mapping_steward"), policy or StewardPolicy(), registry, ctx,
                     inputs=inputs, verifiers=VERIFIERS)
