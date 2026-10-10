"""Skills export: one generated Claude skill per QuantSmith agent (spec 0110).

``agents/`` is the source of truth. This module renders each public agent (a
directory under ``agents/`` containing ``prompt.md``) into a self-contained
``SKILL.md`` under ``.claude/skills/<name>/`` and keeps a registry,
``.claude/skills/registry.json``, that records every skill's lifecycle:

* ``revision`` increments only when the rendered skill changes;
* ``introduced`` / ``updated`` / ``removed`` dates and the ``generation`` in which
  the skill last changed;
* ``source_hash`` (the agent files) and ``skill_hash`` (the rendered file);
* per-target publication marks (``targets``), so ``pending`` can say exactly which
  skills to upload to, or delete from, a distribution target such as claude.ai.

``build`` is idempotent: with no agent change it rewrites nothing. ``check`` is
date-free, so the gate, pre-commit hook, CI, and tests can run it any day.

Standard library only.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

GENERATOR = "quantsmith-skills/1"
SCHEMA = 1
SKILLS_DIR = Path(".claude/skills")
REGISTRY_NAME = "registry.json"
PLUGIN_NAME = "quantsmith-skills"
MARKETPLACE_NAME = "quantsmith-skills-local"
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_NAME = 64
MAX_DESCRIPTION = 1024
RESERVED_WORDS = ("anthropic", "claude")
AGENT_FILES = ("README.md", "prompt.md", "instructions.md", "tasks.md", "SKILL.md")
CONFIG = Path("config/skills_export.json")


def load_config(root: Path) -> Dict[str, object]:
    """``name_overrides`` (agent path -> skill name) and ``exclude`` (agent paths)."""
    path = root / CONFIG
    cfg = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    return {
        "name_overrides": dict(cfg.get("name_overrides", {})),
        "exclude": sorted(cfg.get("exclude", [])),
    }


# ---------------------------------------------------------------------------
# Rendering — REQ-001 / REQ-002
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SkillDoc:
    name: str
    agent: str  # path under agents/, e.g. "provenance/lineage_capture"
    category: str
    title: str
    description: str
    source_hash: str
    text: str  # full SKILL.md

    @property
    def skill_hash(self) -> str:
        return _sha(self.text)


def _sha(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _split_frontmatter(text: str) -> Tuple[Dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    meta: Dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"')
    return meta, text[end + 4 :].lstrip("\n")


def _section(text: str, heading: str) -> List[str]:
    out: List[str] = []
    inside = False
    for line in text.splitlines():
        if re.match(rf"^##\s+{re.escape(heading)}\s*$", line):
            inside = True
            continue
        if inside and re.match(r"^##\s", line):
            break
        if inside:
            out.append(line)
    while out and not out[-1].strip():
        out.pop()
    while out and not out[0].strip():
        out.pop(0)
    return out


def _bullets(lines: Sequence[str]) -> List[str]:
    out: List[str] = []
    for line in lines:
        if re.match(r"^[-*]\s+", line):
            out.append(re.sub(r"^[-*]\s+", "", line).strip())
        elif out and line.startswith((" ", "\t")) and line.strip():
            out[-1] += " " + line.strip()
    return out


def _first_paragraph(lines: Sequence[str]) -> str:
    para: List[str] = []
    for line in lines:
        if line.strip():
            para.append(line.strip())
        elif para:
            break
    return re.sub(r"\s+", " ", " ".join(para)).strip()


def _first_sentence(text: str) -> str:
    m = re.match(r"^(.+?[.!?])(?:\s|$)", text)
    return m.group(1) if m else text


def _title(readme: str, fallback: str) -> str:
    for line in readme.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _strip_title(text: str) -> str:
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines and lines[0].startswith("# "):
        lines.pop(0)
    return "\n".join(lines).strip()


def _demote(text: str) -> str:
    """Shift Markdown headings one level down so they nest under a section."""
    out = []
    fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
        if not fence and re.match(r"^#{1,5}\s", line):
            line = "#" + line
        out.append(line)
    return "\n".join(out)


def skill_name(agent: str, authored: Optional[str] = None) -> str:
    """Stable skill name: the authored ``SKILL.md`` name, else the agent path."""
    if authored:
        return authored
    name = re.sub(r"[^a-z0-9]+", "-", agent.lower()).strip("-")
    return re.sub(r"-{2,}", "-", name)


def _clean_description(text: str) -> str:
    text = re.sub(r"[`*]", "", text)
    text = text.replace("<", "(").replace(">", ")")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > MAX_DESCRIPTION:
        text = text[: MAX_DESCRIPTION - 1].rstrip() + "…"
    return text


def _description(purpose: str, use_when: Sequence[str], authored: Optional[str]) -> str:
    if authored:
        return _clean_description(authored)
    lead = _first_sentence(purpose)
    whens = [w.rstrip(".").strip() for w in use_when[:2] if w.strip()]
    if whens:
        whens = [w[0].lower() + w[1:] if w[:1].isupper() and not w[1:2].isupper() else w
                 for w in whens]
        lead = f"{lead} Use when {', or '.join(whens)}."
    return _clean_description(lead)


def _yaml_str(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render(root: Path, agent_dir: Path, override: Optional[str] = None) -> SkillDoc:
    agent = agent_dir.relative_to(root / "agents").as_posix()
    readme = _read(agent_dir / "README.md")
    prompt = _read(agent_dir / "prompt.md")
    instructions = _read(agent_dir / "instructions.md")
    tasks = _read(agent_dir / "tasks.md")
    authored_meta, authored_body = _split_frontmatter(_read(agent_dir / "SKILL.md"))

    source_hash = _sha(
        "\n\0".join(f"{f}\n{_read(agent_dir / f)}" for f in AGENT_FILES)
    )
    name = override or skill_name(agent, authored_meta.get("name"))
    title = _title(readme, agent)
    purpose = _first_paragraph(_section(readme, "Purpose")) or _first_paragraph(
        prompt.splitlines()
    )
    use_when = _bullets(_section(readme, "Use When"))
    description = _description(purpose, use_when, authored_meta.get("description"))
    category = agent.split("/")[0] if "/" in agent else "root"

    parts: List[str] = [
        "---",
        f"name: {name}",
        f"description: {_yaml_str(description)}",
        "metadata:",
        f"  source: {_yaml_str(f'agents/{agent}/')}",
        f"  category: {_yaml_str(category)}",
        f"  generator: {_yaml_str(GENERATOR)}",
        f"  source-hash: {_yaml_str(source_hash)}",
        "---",
        "",
        f"# {title}",
        "",
        f"> Generated from `agents/{agent}/` in QuantSmith by `quantsmith-skills build`",
        "> (spec `0110`). Do not edit this file; edit the agent and rebuild. Paths such",
        "> as `src/...`, `specs/...`, and `instructions/...` refer to the QuantSmith",
        "> repository.",
        "",
        "## Role",
        "",
        prompt.strip(),
    ]
    if authored_body.strip():
        parts += ["", "## Procedure", "", _demote(_strip_title(authored_body))]
    for heading in ("Use When", "Inputs", "Outputs", "Required Review Themes"):
        sec = _section(readme, heading)
        if sec:
            parts += ["", f"## {heading}", "", "\n".join(sec)]
    if instructions.strip():
        parts += ["", "## Instructions", "", _demote(_strip_title(instructions))]
    if tasks.strip():
        parts += ["", "## Tasks", "", _demote(_strip_title(tasks))]
    text = "\n".join(parts).rstrip() + "\n"
    return SkillDoc(name, agent, category, title, description, source_hash, text)


def _git_ignored(root: Path, rels: Sequence[str]) -> set:
    """The subset of ``rels`` git ignores (local-only material); empty without git."""
    if not rels or not (root / ".git").exists():
        return set()
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "check-ignore", "--stdin"],
            input="\n".join(rels) + "\n", capture_output=True, text=True, check=False,
        )
    except OSError:
        return set()
    return {line.strip() for line in proc.stdout.splitlines() if line.strip()}


def agent_dirs(root: Path) -> List[Path]:
    """Public agents, minus any directory git ignores.

    Gitignored agent folders are local-only by the owner's decision (``.gitignore``);
    exporting them would publish exactly what was kept out of the repository, so
    the export is identical whether or not they exist on this machine.
    """
    dirs = sorted(p.parent for p in (root / "agents").rglob("prompt.md"))
    rels = [d.relative_to(root).as_posix() + "/" for d in dirs]
    ignored = _git_ignored(root, rels)
    return [d for d, rel in zip(dirs, rels) if rel not in ignored]


def validate(docs: Sequence[SkillDoc]) -> List[str]:
    problems: List[str] = []
    seen: Dict[str, str] = {}
    for d in docs:
        if not NAME_RE.match(d.name) or len(d.name) > MAX_NAME:
            problems.append(f"{d.agent}: invalid skill name '{d.name}'")
        for word in RESERVED_WORDS:
            if word in d.name:
                problems.append(f"{d.agent}: skill name '{d.name}' uses reserved word '{word}'")
        if not d.description:
            problems.append(f"{d.agent}: empty description")
        if d.name in seen:
            problems.append(f"skill name '{d.name}' produced by both {seen[d.name]} and {d.agent}")
        seen[d.name] = d.agent
    return problems


def render_all(root: Path) -> List[SkillDoc]:
    cfg = load_config(root)
    overrides: Dict[str, str] = cfg["name_overrides"]  # type: ignore[assignment]
    exclude = set(cfg["exclude"])  # type: ignore[arg-type]
    dirs = agent_dirs(root)
    known = {d.relative_to(root / "agents").as_posix() for d in dirs}
    problems = [f"{CONFIG}: unknown agent '{a}'" for a in sorted(set(overrides) | exclude)
                if a not in known]
    docs = [
        render(root, d, overrides.get(d.relative_to(root / "agents").as_posix()))
        for d in dirs
        if d.relative_to(root / "agents").as_posix() not in exclude
    ]
    problems += validate(docs)
    if problems:
        raise ValueError("cannot export skills:\n  " + "\n  ".join(problems))
    return docs


# ---------------------------------------------------------------------------
# Registry — REQ-003 / REQ-004 / REQ-005
# ---------------------------------------------------------------------------


def registry_path(root: Path) -> Path:
    return root / SKILLS_DIR / REGISTRY_NAME


def load_registry(root: Path) -> Dict[str, object]:
    path = registry_path(root)
    if not path.is_file():
        return {"schema": SCHEMA, "generator": GENERATOR, "generation": 0, "updated": None,
                "targets": {}, "skills": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _dump(reg: Dict[str, object]) -> str:
    return json.dumps(reg, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


@dataclass(frozen=True)
class BuildResult:
    generation: int
    added: Tuple[str, ...]
    changed: Tuple[str, ...]
    removed: Tuple[str, ...]
    unchanged: int

    @property
    def changed_anything(self) -> bool:
        return bool(self.added or self.changed or self.removed)


def build(root: Path, today: Optional[str] = None) -> BuildResult:
    """Render every agent's skill, update the registry, remove retired skills."""
    today = today or _dt.date.today().isoformat()
    docs = render_all(root)
    reg = load_registry(root)
    skills_dir = root / SKILLS_DIR
    entries: Dict[str, Dict[str, object]] = {
        str(e["name"]): dict(e) for e in reg.get("skills", [])  # type: ignore[union-attr]
    }
    generated = {str(e["name"]) for e in entries.values()}
    for d in docs:
        target = skills_dir / d.name
        if d.name not in generated and target.exists():
            raise ValueError(
                f"{target} exists but is not a generated skill; rename it or the agent"
            )

    generation = int(reg.get("generation", 0)) + 1  # used only if something changes
    added: List[str] = []
    changed: List[str] = []
    removed: List[str] = []
    unchanged = 0
    current = {d.name for d in docs}

    for d in docs:
        path = skills_dir / d.name / "SKILL.md"
        e = entries.get(d.name)
        on_disk = _read(path)
        if e is None:
            entries[d.name] = {
                "name": d.name, "agent": d.agent, "category": d.category,
                "description": d.description, "status": "active", "revision": 1,
                "introduced": today, "updated": today, "removed": None,
                "updated_generation": generation,
                "path": (SKILLS_DIR / d.name / "SKILL.md").as_posix(),
                "source_hash": d.source_hash, "skill_hash": d.skill_hash,
            }
            added.append(d.name)
        elif e.get("status") != "active" or e.get("skill_hash") != d.skill_hash \
                or e.get("agent") != d.agent:
            e.update({
                "agent": d.agent, "category": d.category, "description": d.description,
                "status": "active", "revision": int(e.get("revision", 0)) + 1,
                "updated": today, "removed": None, "updated_generation": generation,
                "source_hash": d.source_hash, "skill_hash": d.skill_hash,
            })
            entries[d.name] = e
            changed.append(d.name)
        elif on_disk != d.text:
            pass  # a hand edit or deletion of the file is repaired below, not a revision
        else:
            unchanged += 1
        if on_disk != d.text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(d.text, encoding="utf-8")

    for name, e in entries.items():
        if name not in current and e.get("status") == "active":
            e.update({"status": "removed", "removed": today, "updated": today,
                      "updated_generation": generation})
            removed.append(name)
        if name not in current:
            shutil.rmtree(skills_dir / name, ignore_errors=True)

    if added or changed or removed:
        reg["generation"] = generation
        reg["updated"] = today
    else:
        generation = int(reg.get("generation", 0))
    reg["schema"] = SCHEMA
    reg["generator"] = GENERATOR
    reg.setdefault("targets", {})
    reg["skills"] = [entries[n] for n in sorted(entries)]
    new_text = _dump(reg)
    path = registry_path(root)
    if _read(path) != new_text:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_text, encoding="utf-8")
    return BuildResult(generation, tuple(added), tuple(changed), tuple(removed), unchanged)


def check(root: Path) -> List[str]:
    """Date-free freshness check: what ``build`` would change, as findings."""
    try:
        docs = render_all(root)
    except ValueError as exc:
        return [str(exc)]
    path = registry_path(root)
    if not path.is_file():
        return [f"{path.relative_to(root)} missing: run quantsmith-skills build"]
    reg = load_registry(root)
    findings: List[str] = []
    entries = {str(e["name"]): e for e in reg.get("skills", [])}  # type: ignore[union-attr]
    names = [str(e["name"]) for e in reg.get("skills", [])]  # type: ignore[union-attr]
    if names != sorted(names):
        findings.append("registry skills are not sorted by name")
    generation = int(reg.get("generation", 0))
    current = set()
    for d in docs:
        current.add(d.name)
        e = entries.get(d.name)
        rel = (SKILLS_DIR / d.name / "SKILL.md").as_posix()
        if e is None:
            findings.append(f"{d.agent}: no registry entry for skill '{d.name}' (stale)")
            continue
        if e.get("status") != "active":
            findings.append(f"{d.name}: agent exists but registry says {e.get('status')}")
        if e.get("skill_hash") != d.skill_hash or e.get("source_hash") != d.source_hash:
            findings.append(f"{d.name}: agents/{d.agent}/ changed since the last build (stale)")
        if _read(root / rel) != d.text:
            findings.append(f"{rel}: differs from the generated skill (hand edit or stale)")
        if int(e.get("updated_generation", 0)) > generation:
            findings.append(f"{d.name}: updated_generation is ahead of the registry generation")
    for name, e in entries.items():
        if name not in current:
            if e.get("status") == "active":
                findings.append(f"{name}: agent no longer exists but skill is active (stale)")
            if (root / SKILLS_DIR / name).exists():
                findings.append(f"{SKILLS_DIR / name}: retired skill directory still present")
    if findings:
        findings.append("fix: PYTHONPATH=src python3 -m quantsmith.skills_export build")
    return findings


# ---------------------------------------------------------------------------
# Distribution targets — REQ-006 / REQ-007
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Pending:
    target: str
    since_generation: int
    generation: int
    upload: Tuple[str, ...]
    delete: Tuple[str, ...]


def pending(root: Path, target: str) -> Pending:
    reg = load_registry(root)
    since = int(reg.get("targets", {}).get(target, {}).get("generation", 0))  # type: ignore[union-attr]
    upload: List[str] = []
    delete: List[str] = []
    for e in reg.get("skills", []):  # type: ignore[union-attr]
        if int(e.get("updated_generation", 0)) <= since:
            continue
        if e.get("status") == "active":
            upload.append(str(e["name"]))
        elif since > 0:
            delete.append(str(e["name"]))  # only targets that could have it need a delete
    return Pending(target, since, int(reg.get("generation", 0)), tuple(upload), tuple(delete))


def mark_published(root: Path, target: str, today: Optional[str] = None) -> int:
    """Record that ``target`` now holds the current generation."""
    if not re.match(r"^[a-z0-9_.-]+$", target):
        raise ValueError(f"invalid target name '{target}'")
    problems = check(root)
    if problems:
        raise ValueError("export is stale; build before marking a target published")
    reg = load_registry(root)
    gen = int(reg.get("generation", 0))
    targets = dict(reg.get("targets", {}))  # type: ignore[arg-type]
    targets[target] = {"generation": gen, "marked": today or _dt.date.today().isoformat()}
    reg["targets"] = {k: targets[k] for k in sorted(targets)}
    registry_path(root).write_text(_dump(reg), encoding="utf-8")
    return gen


def package_plugin(root: Path, out: Path, version: str) -> Path:
    """Write a local marketplace with one plugin holding every active skill."""
    problems = check(root)
    if problems:
        raise ValueError("export is stale; build before packaging")
    reg = load_registry(root)
    if out.exists():
        shutil.rmtree(out)
    plugin = out / PLUGIN_NAME
    (plugin / ".claude-plugin").mkdir(parents=True)
    (out / ".claude-plugin").mkdir(parents=True)
    active = [e for e in reg["skills"] if e["status"] == "active"]  # type: ignore[index]
    for e in active:
        src = root / str(e["path"])
        dst = plugin / "skills" / str(e["name"]) / "SKILL.md"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    manifest = {
        "name": PLUGIN_NAME,
        "version": f"{version}+g{reg['generation']}",
        "description": "QuantSmith agents as Claude skills, generated from agents/ (spec 0110).",
        "author": {"name": "QuantSmith"},
        "skills": "./skills",
    }
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    marketplace = {
        "name": MARKETPLACE_NAME,
        "owner": {"name": "QuantSmith"},
        "plugins": [{"name": PLUGIN_NAME, "source": f"./{PLUGIN_NAME}",
                     "description": manifest["description"]}],
    }
    (out / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps(marketplace, indent=2) + "\n", encoding="utf-8")
    shutil.copyfile(registry_path(root), plugin / REGISTRY_NAME)
    return out


def package_zips(root: Path, out: Path, names: Optional[Sequence[str]] = None) -> List[Path]:
    """One ``<name>.zip`` per skill (``<name>/SKILL.md`` inside), for upload."""
    problems = check(root)
    if problems:
        raise ValueError("export is stale; build before packaging")
    reg = load_registry(root)
    active = {str(e["name"]): e for e in reg["skills"] if e["status"] == "active"}  # type: ignore[index]
    wanted = list(names) if names is not None else sorted(active)
    unknown = [n for n in wanted if n not in active]
    if unknown:
        raise ValueError(f"not active skills: {', '.join(unknown)}")
    out.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for name in wanted:
        target = out / f"{name}.zip"
        info = zipfile.ZipInfo(f"{name}/SKILL.md", date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        with zipfile.ZipFile(target, "w") as zf:
            zf.writestr(info, (root / str(active[name]["path"])).read_text(encoding="utf-8"))
        written.append(target)
    return written
