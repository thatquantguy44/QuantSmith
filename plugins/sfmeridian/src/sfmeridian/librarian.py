"""``query_librarian`` (coverage row C-01): the first SFMeridian loop agent.

Spec ``0114`` REQ-014. Goal: keep the query-repository index healthy and hand
people a cited curation report — what was rejected and why, which metric
names have conflicting definitions, which files need front-matter, and what
is waiting in the review inbox.

The deterministic :class:`LibrarianPolicy` runs the loop offline:
``config.validate`` → ``repos.index`` → ``repos.status`` →
``index.rejections`` → ``index.findings`` → ``index.metrics`` →
``feedback.list`` → finish (or escalate when a repository could not be
fetched or the configuration is invalid). A model policy can drive the same
manifest; either way the three verifiers below must pass before the run is
``completed``:

* every finding cites evidence that appears in this run's observations;
* every rejected file appears in a finding (nothing silently dropped);
* drafted front-matter is never marked ``reviewed`` (only people review).

Never: promotes or discards inbox candidates, edits repository files, or
picks the canonical definition of a conflicting metric. Those are human
checkpoints, and ``feedback.promote``/``feedback.discard`` are ``human_only``.
"""

from __future__ import annotations

import re
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

__all__ = ["VERIFIERS", "LibrarianPolicy", "build_report", "run_librarian"]

_SEQUENCE = ("config.validate", "repos.index", "repos.status", "index.rejections", "index.findings",
             "index.metrics", "feedback.list")


def _slug(path: str) -> str:
    stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_") or "query"


def build_report(state: LoopState) -> dict[str, Any]:
    """The curation report, built only from this run's observations."""
    def out(tool: str) -> dict[str, Any]:
        obs = state.last(tool)
        return obs.output if obs and obs.ok else {}

    findings: list[dict[str, Any]] = []

    def add(severity: str, kind: str, message: str, evidence: list[dict[str, str]], action: str) -> None:
        findings.append({"id": f"F-{len(findings) + 1:03d}", "severity": severity, "kind": kind,
                         "message": message, "evidence": evidence, "action": action})

    for err in out("repos.index").get("errors", []):
        add("high", "repository_unreachable", f"{err['repo_id']}: {err['message']}",
            [{"type": "repository", "ref": err["repo_id"]}],
            "Fix the repository location, ref, or credential helper; the previous snapshot is still served.")
    for r in out("index.rejections").get("rejected", []):
        add("high" if r["code"].startswith("E_FRONTMATTER") else "medium", "rejected_file",
            f"{r['repo_id']}:{r['path']} rejected ({r['code']}): {r['reason']}",
            [{"type": "rejected", "ref": f"{r['repo_id']}:{r['path']}"}],
            "Correct the file's front-matter or SQL in the repository and re-index.")
    for m in out("index.metrics").get("metrics", []):
        if not m["conflict"]:
            continue
        reviewed = [d for d in m["definitions"] if "reviewed" in d["review_statuses"]]
        add("high" if len(reviewed) > 1 else "medium", "metric_conflict",
            f"metric {m['name']!r} has {len(m['definitions'])} definitions: "
            + " | ".join(d["expression"] for d in m["definitions"]),
            [{"type": "metric", "ref": m["name"]}] + [{"type": "exemplar", "ref": x}
                                                       for d in m["definitions"] for x in d["exemplar_ids"]],
            "A metric owner chooses the canonical definition (then 0115 binds it); deprecate or rename the rest.")
    suggested: list[dict[str, Any]] = []
    for e in out("index.findings").get("exemplars", []):
        ref = [{"type": "exemplar", "ref": e["exemplar_id"]}]
        if e["review_status"] == "unreviewed":
            add("medium", "unannotated", f"{e['repo_id']}:{e['path']} has no front-matter", ref,
                "Add front-matter (draft below) and have it reviewed.")
            suggested.append({"exemplar_id": e["exemplar_id"], "path": e["path"], "draft": {
                "id": f"draft.{_slug(e['path'])}", "title": _slug(e["path"]).replace("_", " "),
                "review_status": "draft", "tables": e["structure"]["tables"],
                "params": [{"name": p, "type": "string"} for p in e["structure"]["params"]],
                "needs": ["intent", "owner", "parameter types", "pit_columns", "grain", "review"]}})
        for f in e["findings"]:
            kind = "table_mismatch" if "tables" in f else "extraction_gap"
            add("medium" if kind == "table_mismatch" else "low", kind,
                f"{e['repo_id']}:{e['path']}: {f}", ref,
                "Check the declared tables against the SQL." if kind == "table_mismatch"
                else "Qualify the column or alias so the join graph can learn it.")
    staged = out("feedback.list").get("candidates", [])
    for c in staged:
        add("low", "pending_review", f"candidate {c['candidate_id']} ({c['kind']}) from {c['proposer']} awaits review",
            [{"type": "candidate", "ref": c["candidate_id"]}],
            "A configured promoter (not the proposer) promotes or discards it.")
    return {"repositories": out("repos.status").get("repositories", []), "findings": findings,
            "suggested_front_matter": suggested, "review_queue": [c["candidate_id"] for c in staged]}


class LibrarianPolicy:
    name = "deterministic"

    def decide(self, state: LoopState):
        validate = state.last("config.validate")
        if validate is None:
            return ToolCall("config.validate", {}, "check configuration before touching repositories")
        if not validate.ok or not validate.output.get("valid", False):
            return Escalate("configuration is invalid; a person must fix it",
                            {"issues": validate.output.get("issues", [])})
        for tool in _SEQUENCE[1:]:
            if not state.called(tool):
                args: dict[str, Any] = {}
                if tool == "repos.index":
                    args = {k: state.inputs[k] for k in ("repo_ids", "force") if k in state.inputs}
                elif tool == "index.metrics":
                    args = {"conflicts_only": True}
                elif tool == "feedback.list":
                    args = {"status": "staged"}
                return ToolCall(tool, args, f"gather {tool} evidence")
        report = build_report(state)
        errors = state.last("repos.index").output.get("errors", []) if state.last("repos.index") else []
        if errors:
            return Escalate(f"{len(errors)} repository fetch(es) failed; a person must fix access", report)
        counts: dict[str, int] = {}
        for f in report["findings"]:
            counts[f["severity"]] = counts.get(f["severity"], 0) + 1
        summary = (f"{len(report['findings'])} finding(s) "
                   f"({', '.join(f'{v} {k}' for k, v in sorted(counts.items())) or 'none'}); "
                   f"{len(report['review_queue'])} candidate(s) awaiting review")
        return Finish(summary, report)


# --------------------------------------------------------------------------
# Verifiers
# --------------------------------------------------------------------------

def _observed_evidence(state: LoopState) -> dict[str, set[str]]:
    seen: dict[str, set[str]] = {"rejected": set(), "exemplar": set(), "metric": set(), "candidate": set(),
                                 "repository": set()}
    for obs in state.observations:
        if obs.kind != "tool" or not obs.ok:
            continue
        o = obs.output
        for r in o.get("rejected", []):
            seen["rejected"].add(f"{r['repo_id']}:{r['path']}")
        for e in o.get("exemplars", []):
            seen["exemplar"].add(e["exemplar_id"])
        for m in o.get("metrics", []):
            seen["metric"].add(m["name"])
            for d in m["definitions"]:
                seen["exemplar"].update(d["exemplar_ids"])
        for c in o.get("candidates", []):
            seen["candidate"].add(c["candidate_id"])
        for r in o.get("repositories", []):
            seen["repository"].add(r["repo_id"])
        for err in o.get("errors", []):
            seen["repository"].add(err["repo_id"])
    return seen


def verify_cited(state: LoopState, finish: Finish) -> Verdict:
    seen = _observed_evidence(state)
    problems = []
    for f in finish.outputs.get("findings", []):
        evidence = f.get("evidence") or []
        if not evidence:
            problems.append(f"{f.get('id', '?')} cites no evidence")
        for ev in evidence:
            if ev.get("ref") not in seen.get(ev.get("type", ""), set()):
                problems.append(f"{f.get('id', '?')} cites {ev.get('type')}:{ev.get('ref')} not observed in this run")
    return Verdict(not problems, tuple(problems))


def verify_complete(state: LoopState, finish: Finish) -> Verdict:
    obs = state.last("index.rejections")
    rejected = {f"{r['repo_id']}:{r['path']}" for r in (obs.output.get("rejected", []) if obs and obs.ok else [])}
    cited = {ev.get("ref") for f in finish.outputs.get("findings", []) for ev in f.get("evidence", [])
             if ev.get("type") == "rejected"}
    missing = sorted(rejected - cited)
    if obs is None:
        return Verdict(False, ("index.rejections was never consulted",))
    return Verdict(not missing, tuple(f"rejected file {m} is missing from the report" for m in missing))


def verify_no_self_review(state: LoopState, finish: Finish) -> Verdict:
    problems = [f"draft for {s.get('path')} is marked {s['draft'].get('review_status')!r}"
                for s in finish.outputs.get("suggested_front_matter", [])
                if s.get("draft", {}).get("review_status") != "draft"]
    return Verdict(not problems, tuple(problems))


VERIFIERS = {
    "librarian.findings_cite_observed_evidence": verify_cited,
    "librarian.every_rejection_reported": verify_complete,
    "librarian.drafts_never_reviewed": verify_no_self_review,
}


def run_librarian(ctx: ToolContext, *, policy=None, registry: ToolRegistry | None = None,
                  inputs: Mapping[str, Any] | None = None, manifest: AgentManifest | None = None) -> AgentRun:
    registry = registry or default_registry()
    return run_agent(manifest or load_manifest("query_librarian"), policy or LibrarianPolicy(), registry, ctx,
                     inputs=inputs, verifiers=VERIFIERS)
