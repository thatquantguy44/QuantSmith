"""Governance validators: roster, handoff map, tooling catalog, agent manifests, imports.

Spec ``0114`` REQ-009 (realizing ``0113`` REQ-015, REQ-021, REQ-027, REQ-028).
The machine-readable catalogs under ``data/`` are generated from, and must
agree with, the approved ``0113`` documents:

* ``coverage.json`` — the nine SFMeridian agents (C-01…C-09), each with a
  distinct workflow, a never-boundary, its creating child spec, and its loop
  (tools, verifiers, human checkpoints, stop condition);
* ``handoffs.json`` — the 34 existing agents SFMeridian hands work to;
* ``tooling_catalog.json`` — the screened third-party catalog;
* ``agents/*.json`` — manifests of built loop agents.

``validate_all`` returns a report instead of raising, so the CLI, the tests,
and the ``governance.validate`` tool share it.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

__all__ = ["CONTRACT_TOOLS", "PACKAGE_DIR", "check_imports", "load", "validate_all"]

PACKAGE_DIR = Path(__file__).parent
DATA_DIR = PACKAGE_DIR / "data"
RINGS = ("adopt", "trial", "assess", "hold", "exclude")
WORKFLOWS = tuple(f"W{i}" for i in range(1, 14))
CHILD_SPECS = tuple(f"{n:04d}" for n in range(114, 122))
ADMISSION_FIELDS = ("reviewer", "reviewed_on", "license_verified", "version", "sha256", "advisory_scan")

#: The 0113 tool contract (built in 0114, 0115, and 0121, or planned for a later child).
CONTRACT_TOOLS = frozenset({
    # 0114
    "config.validate", "repos.index", "repos.status", "queries.search", "queries.get", "index.rejections",
    "index.findings", "index.metrics", "index.joins", "feedback.propose", "feedback.list",
    "feedback.promote", "feedback.discard", "governance.validate",
    # 0115
    "catalog.snapshot", "catalog.describe", "catalog.diff", "catalog.reconcile", "metrics.list", "glossary.lookup",
    "mapping.validate", "mapping.amendments", "mapping.propose_amendment", "access.describe",
    # 0116-0118
    "sql.compose", "sql.verify", "sql.execute", "answer.ground", "ask", "eval.run",
    # 0121
    "research.start", "research.intake", "research.inspect_schema", "research.summarize_columns",
    "research.check_grain", "research.inspect_missingness", "research.inspect_time", "research.check_domain_rules",
    "research.inspect_numeric", "research.inspect_categories", "research.inspect_relationships",
    "research.compare_segments", "research.inspect_target", "research.inspect_availability",
    "research.compare_reference", "research.render_charts", "research.recommend_actions", "research.finish",
})
#: The only package allowed to import the QuantSmith SDK, and only from ``governed/`` (0113 NFR-003).
GOVERNED_IMPORTS = {"quantsmith": "governed"}


def load(name: str) -> Any:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def check_imports(package_dir: Path = PACKAGE_DIR) -> list[str]:
    """Imports outside the standard library (``quantsmith`` only under ``governed/``)."""
    problems: list[str] = []
    stdlib = set(sys.stdlib_module_names)
    for path in sorted(package_dir.rglob("*.py")):
        rel = path.relative_to(package_dir).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            for name in names:
                top = name.split(".")[0]
                if top in stdlib or top == "sfmeridian" or top == "__future__":
                    continue
                allowed_dir = GOVERNED_IMPORTS.get(top)
                if allowed_dir and rel.startswith(allowed_dir + "/"):
                    continue
                problems.append(f"{rel}: imports {name!r}, which is not in the standard library")
    return problems


def _agent_dirs(agents_root: Path) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for prompt in agents_root.rglob("prompt.md"):
        rel = prompt.parent.relative_to(agents_root).as_posix()
        out.setdefault(prompt.parent.name, []).append(rel)
    return out


def _validate_coverage(coverage: dict[str, Any], agents_root: Path, errors: list[str]) -> dict[str, Any]:
    rows = coverage.get("rows", [])
    group = coverage.get("group_path", "")
    dirs = _agent_dirs(agents_root)
    seen_ids, seen_agents, seen_workflows = set(), set(), set()
    built = {}
    for row in rows:
        rid, agent = row.get("id"), row.get("agent")
        tag = f"coverage {rid} ({agent})"
        for key in ("id", "agent", "child_spec", "status", "workflow", "never", "loop"):
            if not row.get(key):
                errors.append(f"{tag}: missing {key}")
        if rid in seen_ids or agent in seen_agents:
            errors.append(f"{tag}: duplicate id or agent")
        if row.get("workflow") in seen_workflows:
            errors.append(f"{tag}: workflow duplicates another row")
        seen_ids.add(rid)
        seen_agents.add(agent)
        seen_workflows.add(row.get("workflow"))
        if row.get("child_spec") not in CHILD_SPECS:
            errors.append(f"{tag}: child_spec must be one of {', '.join(CHILD_SPECS)}")
        loop = row.get("loop") or {}
        for key in ("tools", "verifiers", "human_checkpoints", "stop_condition"):
            if not loop.get(key):
                errors.append(f"{tag}: loop needs {key}")
        for tool in loop.get("tools", []):
            if tool not in CONTRACT_TOOLS:
                errors.append(f"{tag}: tool {tool!r} is not in the 0113 tool contract")
        expected = f"{group}/{agent}"
        elsewhere = [d for d in dirs.get(agent, []) if d != expected]
        if elsewhere:
            errors.append(f"{tag}: duplicates existing agent(s) {elsewhere}")
        exists = expected in dirs.get(agent, [])
        if row.get("status") == "built":
            built[agent] = row
            if not exists:
                errors.append(f"{tag}: status built but agents/{expected}/ is missing")
            else:
                for f in ("README.md", "instructions.md", "tasks.md"):
                    if not (agents_root / expected / f).exists():
                        errors.append(f"{tag}: agents/{expected}/{f} is missing")
                if "## Spec-Driven Role" not in (agents_root / expected / "instructions.md").read_text(encoding="utf-8"):
                    errors.append(f"{tag}: instructions.md needs a 'Spec-Driven Role' section")
        elif row.get("status") == "planned":
            if exists:
                errors.append(f"{tag}: agents/{expected}/ exists but the row says planned")
        else:
            errors.append(f"{tag}: status must be built or planned")
    return built


def _validate_handoffs(handoffs: dict[str, Any], agents_root: Path, coverage_agents: set,
                       errors: list[str]) -> int:
    count = 0
    for h in handoffs.get("handoffs", []):
        tag = f"handoff {h.get('agent')}"
        count += 1
        for key in ("group", "agent", "path", "trigger", "evidence", "output", "never", "workflows"):
            if not h.get(key):
                errors.append(f"{tag}: missing {key}")
        if not (agents_root / h.get("path", "") / "prompt.md").exists():
            errors.append(f"{tag}: agents/{h.get('path')}/prompt.md not found")
        bad = [w for w in h.get("workflows", []) if w not in WORKFLOWS]
        if bad:
            errors.append(f"{tag}: unknown workflows {bad}")
        if h.get("agent") in coverage_agents:
            errors.append(f"{tag}: an SFMeridian agent may not duplicate a handoff agent's workflow")
    return count


def _validate_tooling(catalog: dict[str, Any], strict: bool, errors: list[str]) -> list[str]:
    pending: list[str] = []
    names = set()
    for e in catalog.get("entries", []):
        tag = f"tooling {e.get('name')}"
        if e.get("name") in names:
            errors.append(f"{tag}: duplicate entry")
        names.add(e.get("name"))
        if e.get("ring") not in RINGS:
            errors.append(f"{tag}: ring must be one of {', '.join(RINGS)}")
        for key in ("language", "use", "license"):
            if not e.get(key):
                errors.append(f"{tag}: missing {key}")
        if e.get("ring") in ("adopt", "trial"):
            if not e.get("component"):
                errors.append(f"{tag}: adopt/trial entries name the SFMeridian component or agent using them")
            if "Python" in e.get("language", "") and not e.get("extra") and e.get("license") != "Python standard library":
                errors.append(f"{tag}: adopt/trial Python entries ship as an optional extra")
            admission = e.get("admission") or {}
            if not all(admission.get(k) for k in ADMISSION_FIELDS):
                pending.append(e["name"])
    if strict and pending:
        errors.extend(f"tooling {n}: admission review pending (strict mode)" for n in pending)
    return pending


def _validate_manifests(built: dict[str, Any], registry: Any, errors: list[str]) -> int:
    count = 0
    for path in sorted((DATA_DIR / "agents").glob("*.json")):
        count += 1
        manifest = json.loads(path.read_text(encoding="utf-8"))
        tag = f"manifest {path.name}"
        name = manifest.get("name")
        row = built.get(name)
        if row is None:
            errors.append(f"{tag}: no built coverage row for {name!r}")
            continue
        if manifest.get("coverage_row") != row["id"]:
            errors.append(f"{tag}: coverage_row {manifest.get('coverage_row')} != {row['id']}")
        if sorted(manifest.get("tools", [])) != sorted(row["loop"]["tools"]):
            errors.append(f"{tag}: tools differ from coverage.json")
        if sorted(manifest.get("verifiers", [])) != sorted(row["loop"]["verifiers"]):
            errors.append(f"{tag}: verifiers differ from coverage.json")
        for tool in manifest.get("tools", []):
            if registry is not None:
                try:
                    effect = registry.get(tool).effect
                except Exception:  # noqa: BLE001 — any lookup failure is reported as unregistered
                    errors.append(f"{tag}: tool {tool!r} is not registered")
                    continue
                if effect == "human_only":
                    errors.append(f"{tag}: grants human_only tool {tool!r}")
        for key in ("max_steps", "max_tool_calls"):
            if not isinstance(manifest.get(key), int) or manifest[key] <= 0:
                errors.append(f"{tag}: {key} must be a positive integer")
    return count


def validate_all(agents_root: Path, *, strict: bool = False, registry: Any | None = None) -> dict[str, Any]:
    errors: list[str] = []
    coverage = load("coverage.json")
    built = _validate_coverage(coverage, Path(agents_root), errors)
    handoffs = _validate_handoffs(load("handoffs.json"), Path(agents_root),
                                  {r["agent"] for r in coverage.get("rows", [])}, errors)
    pending = _validate_tooling(load("tooling_catalog.json"), strict, errors)
    manifests = _validate_manifests(built, registry, errors)
    errors.extend(check_imports())
    return {"ok": not errors, "errors": errors, "pending_admissions": pending,
            "counts": {"coverage_rows": len(coverage.get("rows", [])), "built_agents": len(built),
                       "handoffs": handoffs, "manifests": manifests,
                       "tooling_entries": len(load("tooling_catalog.json").get("entries", []))}}
