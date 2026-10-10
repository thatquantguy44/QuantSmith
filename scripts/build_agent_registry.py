#!/usr/bin/env python3
"""Generate agents/agent_registry.yaml from the agents themselves.

The registry is a machine-readable index of every public agent (a directory under
``agents/`` that contains ``prompt.md``). It is *generated*: edit an agent's
``README.md`` (or ``SKILL.md``) and re-run this script; do not edit the YAML by hand.

    python3 scripts/build_agent_registry.py           # rewrite the registry
    python3 scripts/build_agent_registry.py --check   # exit 1 if it is stale (CI runs this via pytest)

Per agent: ``name`` (path under ``agents/``, unique), ``category`` (top-level folder, or
``root``), ``purpose`` (first sentence of the README Purpose, else the first paragraph),
``path``, ``inputs`` / ``outputs`` (the README bullets, at most 6, each cut at 220
characters), ``skill_path`` when a ``SKILL.md`` exists, ``decision_path_class`` for
venture-intelligence agents (from ``knowledge/venture_intelligence/coverage.json``), and
``interface`` for the six original entries, which keep their machine identifiers.

Standard library only. Strings are emitted as JSON scalars, which are valid YAML.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "agents"
REGISTRY = AGENTS / "agent_registry.yaml"
COVERAGE = ROOT / "knowledge/venture_intelligence/coverage.json"
MAX_BULLETS = 6
MAX_CHARS = 220

# The machine identifiers the six original registry entries carried; kept so nothing
# that read them is lost. They are not derived from the README text.
LEGACY_INTERFACE: Dict[str, Dict[str, List[str]]] = {
    "orchestrator-agent": {"inputs": ["natural_language_intent", "system_context"],
                           "outputs": ["execution_plan", "delegated_tasks"]},
    "data-prep-agent": {"inputs": ["raw_dataset", "transformation_requirements"],
                        "outputs": ["transformed_dataset", "data_quality_report"]},
    "sql-integration-agent": {"inputs": ["query_intent", "database_config"],
                              "outputs": ["query_results", "schema_summary"]},
    "tableau-dashboard-agent": {"inputs": ["semantic_dashboard_request", "prepared_dataset", "dashboard_knowledge_context"],
                                "outputs": ["tableau_payload", "validation_status"]},
    "reporting-agent": {"inputs": ["dashboard_metadata", "analytical_summary"],
                        "outputs": ["report_artifacts", "distribution_manifest"]},
    "quality-guard-agent": {"inputs": ["agent_outputs", "validation_policies"],
                            "outputs": ["pass_fail_status", "remediation_instructions"]},
}


# Gitignored, local-only regional agent folders (see .gitignore). Excluded so the
# generated registry is identical whether or not they exist on this machine.
LOCAL_ONLY = (
    "venture_intelligence/central_asia/",
    "venture_intelligence/greater_china_east_asia/",
    "venture_intelligence/south_asia/",
    "venture_intelligence/southeast_asia/",
)


def agent_dirs() -> List[Path]:
    return sorted(p.parent for p in AGENTS.rglob("prompt.md")
                  if not (p.parent.relative_to(AGENTS).as_posix() + "/").startswith(LOCAL_ONLY))


def _section(text: str, heading: str) -> List[str]:
    lines = text.splitlines()
    out: List[str] = []
    inside = False
    for line in lines:
        if re.match(rf"^##\s+{re.escape(heading)}\s*$", line):
            inside = True
            continue
        if inside and re.match(r"^##\s", line):
            break
        if inside:
            out.append(line)
    return out


def _first_sentence(paragraph: str) -> str:
    para = re.sub(r"\s+", " ", paragraph).strip()
    m = re.match(r"^(.+?[.!?])(?:\s|$)", para)
    s = m.group(1) if m else para
    return s if len(s) <= 700 else s[:699].rstrip() + "…"


def _purpose(readme: str, prompt: str) -> str:
    sec = _section(readme, "Purpose")
    para: List[str] = []
    for line in sec:
        if line.strip():
            para.append(line.strip())
        elif para:
            break
    if para:
        return _first_sentence(" ".join(para))
    # No Purpose section: use the first prose paragraph after the title.
    para = []
    for line in readme.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            if para:
                break
            continue
        para.append(s)
    if para:
        return _first_sentence(" ".join(para))
    first = next((ln.strip() for ln in prompt.splitlines() if ln.strip()), "")
    return _first_sentence(first)


def _bullets(readme: str, heading: str) -> List[str]:
    out: List[str] = []
    cur: Optional[str] = None
    for line in _section(readme, heading):
        if re.match(r"^[-*]\s+", line):
            if cur is not None:
                out.append(cur)
            cur = re.sub(r"^[-*]\s+", "", line).strip()
        elif cur is not None and line.startswith((" ", "\t")) and line.strip() and not re.match(r"^\s*[-*]\s", line):
            cur += " " + line.strip()
        elif not line.strip() and cur is not None:
            out.append(cur)
            cur = None
    if cur is not None:
        out.append(cur)
    cleaned = []
    for b in out[:MAX_BULLETS]:
        b = re.sub(r"\s+", " ", b)
        cleaned.append(b if len(b) <= MAX_CHARS else b[:MAX_CHARS - 1].rstrip() + "…")
    return cleaned


def _venture_classes() -> Dict[str, str]:
    if not COVERAGE.is_file():
        return {}
    cov = json.loads(COVERAGE.read_text(encoding="utf-8"))
    return {a["path"]: a.get("decision_path_class", "analytic_support")
            for a in cov["agents"] if a.get("path")}


def entries() -> List[Dict[str, object]]:
    classes = _venture_classes()
    out: List[Dict[str, object]] = []
    for d in agent_dirs():
        rel = d.relative_to(AGENTS).as_posix()
        readme = (d / "README.md").read_text(encoding="utf-8") if (d / "README.md").is_file() else ""
        prompt = (d / "prompt.md").read_text(encoding="utf-8")
        e: Dict[str, object] = {
            "name": rel,
            "category": rel.split("/")[0] if "/" in rel else "root",
            "purpose": _purpose(readme, prompt),
            "path": f"agents/{rel}/",
            "inputs": _bullets(readme, "Inputs"),
            "outputs": _bullets(readme, "Outputs"),
        }
        if (d / "SKILL.md").is_file():
            e["skill_path"] = f"agents/{rel}/SKILL.md"
        cls = classes.get(f"agents/{rel}")
        if cls:
            e["decision_path_class"] = cls
        if rel in LEGACY_INTERFACE:
            e["interface"] = LEGACY_INTERFACE[rel]
        out.append(e)
    return out


def _s(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def render() -> str:
    lines = [
        "# Agent registry -- GENERATED by scripts/build_agent_registry.py. Do not edit by hand.",
        "#",
        "# One entry per public agent (a directory under agents/ containing prompt.md). Regenerate",
        "# after adding or changing an agent:   python3 scripts/build_agent_registry.py",
        "# The test suite and the agent-catalog gate fail when this file is stale or incomplete.",
        "# Strings are JSON scalars (valid YAML). `interface` keeps the machine identifiers the six",
        "# original entries carried. See agents/README.md for the human-readable catalog.",
        "agents:",
    ]
    for e in entries():
        lines.append(f"  - name: {_s(e['name'])}")
        for key in ("category", "purpose", "path"):
            lines.append(f"    {key}: {_s(e[key])}")
        for key in ("inputs", "outputs"):
            vals = e[key]
            if vals:
                lines.append(f"    {key}:")
                lines.extend(f"      - {_s(v)}" for v in vals)  # type: ignore[union-attr]
            else:
                lines.append(f"    {key}: []")
        if "skill_path" in e:
            lines.append(f"    skill_path: {_s(e['skill_path'])}")
        if "decision_path_class" in e:
            lines.append(f"    decision_path_class: {_s(e['decision_path_class'])}")
        if "interface" in e:
            iface = e["interface"]
            lines.append("    interface:")
            for key in ("inputs", "outputs"):
                lines.append(f"      {key}:")
                lines.extend(f"        - {_s(v)}" for v in iface[key])  # type: ignore[index]
    return "\n".join(lines) + "\n"


def main(argv: List[str]) -> int:
    text = render()
    if "--check" in argv:
        current = REGISTRY.read_text(encoding="utf-8") if REGISTRY.is_file() else ""
        if current != text:
            print("agents/agent_registry.yaml is stale; run: python3 scripts/build_agent_registry.py")
            return 1
        print(f"agent registry is current ({text.count('  - name: ')} agents)")
        return 0
    REGISTRY.write_text(text, encoding="utf-8")
    try:
        shown = REGISTRY.relative_to(ROOT)
    except ValueError:
        shown = REGISTRY
    print(f"wrote {shown} ({text.count('  - name: ')} agents)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
