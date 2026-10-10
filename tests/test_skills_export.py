"""Acceptance tests for spec 0110 — skills export and registry.

Each test is named for the acceptance criterion it covers (see
``specs/0110-skills-export-registry/tasks.md``). Standard-library only.
"""

from __future__ import annotations

import json
import re
import subprocess
import zipfile
from pathlib import Path

import pytest

from quantsmith.skills_export import (
    build,
    check,
    load_registry,
    mark_published,
    package_plugin,
    package_zips,
    pending,
    render_all,
)
from quantsmith.skills_export.cli import main as cli_main

ROOT = Path(__file__).resolve().parents[1]


def make_agent(root: Path, rel: str, purpose: str = "Does a thing.", extra: str = "") -> None:
    d = root / "agents" / rel
    d.mkdir(parents=True, exist_ok=True)
    (d / "README.md").write_text(
        f"# {rel} Agent\n\n## Purpose\n\n{purpose}\n\n## Use When\n\n"
        f"- A first case applies.\n- A second case applies.\n\n## Inputs\n\n- in\n\n"
        f"## Outputs\n\n- out\n{extra}",
        encoding="utf-8",
    )
    (d / "prompt.md").write_text(f"You are the {rel} agent.\n", encoding="utf-8")
    (d / "instructions.md").write_text("# I\n\n## Operating Rules\n\n- rule\n", encoding="utf-8")
    (d / "tasks.md").write_text("# T\n\n## Do It\n\nInput: x.\n", encoding="utf-8")


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    (tmp_path / "specs").mkdir()
    make_agent(tmp_path, "group/alpha_one")
    make_agent(tmp_path, "group/beta")
    make_agent(tmp_path, "solo")
    return tmp_path


# AC-001 ---------------------------------------------------------------------


def test_repository_export_is_fresh_AC_001():
    assert check(ROOT) == [], "stale: run PYTHONPATH=src python3 -m quantsmith.skills_export build"
    reg = load_registry(ROOT)
    agents = sorted(p.parent.relative_to(ROOT / "agents").as_posix()
                    for p in (ROOT / "agents").rglob("prompt.md"))
    excluded = set(json.loads((ROOT / "config/skills_export.json").read_text())["exclude"])
    active = sorted(e["agent"] for e in reg["skills"] if e["status"] == "active")
    assert active == sorted(a for a in agents if a not in excluded)
    assert all((ROOT / e["path"]).is_file() for e in reg["skills"] if e["status"] == "active")


# AC-002 ---------------------------------------------------------------------


def test_rendered_skill_format_AC_002():
    docs = {d.agent: d for d in render_all(ROOT)}
    for d in docs.values():
        assert re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", d.name) and len(d.name) <= 64
        assert "claude" not in d.name and "anthropic" not in d.name
        assert 0 < len(d.description) <= 1024
        assert "<" not in d.description and ">" not in d.description
        assert d.text.startswith(f"---\nname: {d.name}\ndescription: ")
    lc = docs["provenance/lineage_capture"]
    assert lc.name == "provenance-lineage-capture"
    assert "Use when" in lc.description
    prompt = (ROOT / "agents/provenance/lineage_capture/prompt.md").read_text().strip()
    assert prompt in lc.text
    assert "### Operating Rules" in lc.text and "## Tasks" in lc.text
    # Hand-authored SKILL.md names and procedures are preserved.
    orch = docs["orchestrator-agent"]
    assert orch.name == "orchestrator-agent" and "## Procedure" in orch.text


def test_gitignored_agents_are_never_exported_AC_002(repo: Path):
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    make_agent(repo, "regional/local_only")
    (repo / ".gitignore").write_text("/agents/regional/\n", encoding="utf-8")
    build(repo, "2026-01-01")
    names = {e["name"] for e in load_registry(repo)["skills"]}
    assert names == {"group-alpha-one", "group-beta", "solo"}
    assert not (repo / ".claude/skills/regional-local-only").exists()
    assert "local_only" not in (repo / ".claude/skills/registry.json").read_text()
    assert check(repo) == []


# AC-003 ---------------------------------------------------------------------


def test_registry_lifecycle_AC_003(repo: Path):
    r1 = build(repo, "2026-01-01")
    assert r1.generation == 1 and len(r1.added) == 3
    reg_path = repo / ".claude/skills/registry.json"
    before = reg_path.read_bytes()

    r2 = build(repo, "2026-01-02")  # nothing changed: idempotent, no date churn
    assert not r2.changed_anything and r2.generation == 1
    assert reg_path.read_bytes() == before

    (repo / "agents/group/beta/prompt.md").write_text("You are better.\n", encoding="utf-8")
    r3 = build(repo, "2026-02-01")
    assert r3.changed == ("group-beta",) and r3.generation == 2
    e = {x["name"]: x for x in load_registry(repo)["skills"]}
    assert e["group-beta"]["revision"] == 2 and e["group-beta"]["updated"] == "2026-02-01"
    assert e["group-beta"]["introduced"] == "2026-01-01"
    assert e["solo"]["revision"] == 1 and e["solo"]["updated_generation"] == 1

    import shutil
    shutil.rmtree(repo / "agents/solo")
    r4 = build(repo, "2026-03-01")
    assert r4.removed == ("solo",) and r4.generation == 3
    e = {x["name"]: x for x in load_registry(repo)["skills"]}
    assert e["solo"]["status"] == "removed" and e["solo"]["removed"] == "2026-03-01"
    assert not (repo / ".claude/skills/solo").exists()

    make_agent(repo, "solo")
    r5 = build(repo, "2026-04-01")
    e = {x["name"]: x for x in load_registry(repo)["skills"]}
    assert r5.changed == ("solo",)
    assert e["solo"]["status"] == "active" and e["solo"]["revision"] == 2
    assert e["solo"]["removed"] is None
    assert check(repo) == []


# AC-004 ---------------------------------------------------------------------


def test_check_detects_drift_and_build_repairs_AC_004(repo: Path):
    assert check(repo)[0].endswith("missing: run quantsmith-skills build")
    build(repo, "2026-01-01")
    assert check(repo) == []
    skill = repo / ".claude/skills/group-beta/SKILL.md"
    skill.write_text(skill.read_text() + "\nhand edit\n", encoding="utf-8")
    assert any("hand edit or stale" in f for f in check(repo))
    (repo / "agents/solo/tasks.md").write_text("# T\n\nchanged\n", encoding="utf-8")
    assert any("solo: agents/solo/ changed" in f for f in check(repo))
    r = build(repo, "2026-01-05")
    assert r.changed == ("solo",)  # hand edit repaired without a revision bump
    assert {x["name"]: x for x in load_registry(repo)["skills"]}["group-beta"]["revision"] == 1
    assert check(repo) == []
    (repo / ".claude/skills/stray").mkdir()  # hand-made skills are left alone
    assert check(repo) == []


# AC-005 ---------------------------------------------------------------------


def test_name_validation_and_overrides_AC_005(repo: Path):
    long = "a_very_long_group_name/with_a_very_long_agent_name_that_overflows_it"
    make_agent(repo, long)
    with pytest.raises(ValueError, match="invalid skill name"):
        build(repo)
    cfg = repo / "config/skills_export.json"
    cfg.parent.mkdir()
    cfg.write_text(json.dumps({"name_overrides": {long: "long-agent"}}), encoding="utf-8")
    build(repo, "2026-01-01")
    assert (repo / ".claude/skills/long-agent/SKILL.md").is_file()

    make_agent(repo, "group_beta")  # collides with group/beta -> "group-beta"
    with pytest.raises(ValueError, match="produced by both"):
        build(repo)
    cfg.write_text(json.dumps({"name_overrides": {long: "long-agent"},
                               "exclude": ["group_beta", "ghost"]}), encoding="utf-8")
    assert any("unknown agent 'ghost'" in f for f in check(repo))

    cfg.write_text(json.dumps({"name_overrides": {long: "long-agent"},
                               "exclude": ["group_beta"]}), encoding="utf-8")
    make_agent(repo, "taken")
    (repo / ".claude/skills/taken").mkdir()
    with pytest.raises(ValueError, match="not a generated skill"):
        build(repo)


# AC-006 ---------------------------------------------------------------------


def test_pending_and_publication_marks_AC_006(repo: Path):
    build(repo, "2026-01-01")
    p = pending(repo, "claude_ai")
    assert p.since_generation == 0 and len(p.upload) == 3 and p.delete == ()
    assert mark_published(repo, "claude_ai", "2026-01-02") == 1
    assert pending(repo, "claude_ai").upload == ()
    assert check(repo) == []  # publication marks do not make the export stale

    (repo / "agents/group/beta/prompt.md").write_text("v2\n", encoding="utf-8")
    import shutil
    shutil.rmtree(repo / "agents/solo")
    with pytest.raises(ValueError, match="stale"):
        mark_published(repo, "claude_ai")
    build(repo, "2026-02-01")
    p = pending(repo, "claude_ai")
    assert p.upload == ("group-beta",) and p.delete == ("solo",)
    assert pending(repo, "never_published").delete == ()
    with pytest.raises(ValueError, match="invalid target"):
        mark_published(repo, "Bad Target")


# AC-007 ---------------------------------------------------------------------


def test_packaging_plugin_and_zips_AC_007(repo: Path, tmp_path: Path):
    build(repo, "2026-01-01")
    out = package_plugin(repo, tmp_path / "plugin", "1.2.3")
    mp = json.loads((out / ".claude-plugin/marketplace.json").read_text())
    assert mp["plugins"][0]["source"] == "./quantsmith-skills"
    manifest = json.loads((out / "quantsmith-skills/.claude-plugin/plugin.json").read_text())
    assert manifest["version"] == "1.2.3+g1" and manifest["skills"] == "./skills"
    skills = sorted(p.parent.name for p in (out / "quantsmith-skills/skills").glob("*/SKILL.md"))
    assert skills == ["group-alpha-one", "group-beta", "solo"]

    zips = package_zips(repo, tmp_path / "zips")
    assert len(zips) == 3
    with zipfile.ZipFile(zips[0]) as zf:
        assert zf.namelist() == ["group-alpha-one/SKILL.md"]
    first = zips[0].read_bytes()
    package_zips(repo, tmp_path / "zips")
    assert zips[0].read_bytes() == first  # deterministic archives
    with pytest.raises(ValueError, match="not active"):
        package_zips(repo, tmp_path / "zips", ["ghost"])


# AC-008 ---------------------------------------------------------------------


def test_cli_and_gate_AC_008(repo: Path, capsys):
    assert cli_main(["--root", str(repo), "check"]) == 1
    assert cli_main(["--root", str(repo), "build", "--date", "2026-01-01"]) == 0
    assert cli_main(["--root", str(repo), "check"]) == 0
    assert "fresh: 3 active skills" in capsys.readouterr().out
    gate = subprocess.run(
        ["sh", "hooks/stages/skills-export-check.sh"], cwd=ROOT, capture_output=True, text=True,
        env={"QF_STAGE_ENFORCE": "1", "PATH": "/usr/bin:/bin"}, check=False,
    )
    assert gate.returncode == 0, gate.stdout + gate.stderr
    assert "no findings" in gate.stdout
