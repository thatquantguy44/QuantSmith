"""Tests for spec 0058 -- viewer access control.

One test per acceptance criterion, named for the AC it verifies (see
``specs/0058-viewer-access-control/tasks.md``). Roster/identity tests use a
scratch ``tmp_path`` tree -- nothing writes to the real, committed
``access/roster.yml``.
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

from quantsmith.knowledge_console import model as m
from quantsmith.knowledge_console import research as r
from quantsmith.pipelines import access_control as ac
from quantsmith.pipelines import workflow_memory as wm

REPO_ROOT = Path(__file__).resolve().parents[1]
AS_OF = datetime.date(2026, 1, 1)


# --------------------------------------------------------------------------
# Fixture helpers
# --------------------------------------------------------------------------

def _write_roster(root: Path, entries=(), default: str = "public") -> None:
    access_dir = root / "access"
    access_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"default_clearance: {default}", "", "people:"]
    for handle, label, clearance in entries:
        lines.append(f"  - handle: {handle}")
        lines.append(f"    label: {label}")
        lines.append(f"    clearance: {clearance}")
    (access_dir / "roster.yml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _record(id_: str, access_level: str, **overrides) -> wm.Record:
    fields = dict(
        id=id_, scope="s", type="finding", statement="x", confidence="high",
        first_seen=AS_OF, last_confirmed=AS_OF, status="active",
        pit_scope="as_of_2026-01-01",
    )
    fields.update(overrides)
    return wm.build_record(fields, file="f", access_level=access_level)


def _loaded(id_: str, access_level: str, workflow: str = "w") -> m.LoadedRecord:
    return m.LoadedRecord(record=_record(id_, access_level), workflow=workflow)


def _store(loaded) -> m.Store:
    return m.Store(records=tuple(loaded), freshness_days=90, files=(), root="memory")


def _research_item(id_: str, access_level: str, **overrides) -> r.ResearchItem:
    fields = dict(
        id=id_, title="t", source_type="user_note", author_or_publisher="a",
        asset_class="equities", access_level=access_level, entitlement_class="",
        publication_date=AS_OF, ingestion_date=AS_OF, review_status="approved",
        summary="s", citation="c", domain="d",
    )
    fields.update(overrides)
    return r.ResearchItem(**fields)


def _kc_cli(*args, cwd: Path = REPO_ROOT, env_extra=None):
    env = {"PYTHONPATH": str(REPO_ROOT / "src"), "PATH": os.environ.get("PATH", "")}
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, "-m", "quantsmith.knowledge_console", *args],
        cwd=str(cwd), capture_output=True, text=True, env=env,
    )


def _wm_cli(*args, cwd: Path = REPO_ROOT):
    return subprocess.run(
        [sys.executable, "-m", "quantsmith.pipelines.workflow_memory_cli", *args],
        cwd=str(cwd), capture_output=True, text=True,
        env={"PYTHONPATH": str(REPO_ROOT / "src"), "PATH": os.environ.get("PATH", "")},
    )


# --- AC-001: clearance ordering -------------------------------------------------

def test_clearance_ordering_AC_001():
    assert ac.access_level_allows("public", "public")
    assert ac.access_level_allows("public", "internal")
    assert ac.access_level_allows("public", "restricted")
    assert not ac.access_level_allows("internal", "public")
    assert ac.access_level_allows("internal", "internal")
    assert ac.access_level_allows("internal", "restricted")
    assert not ac.access_level_allows("restricted", "public")
    assert not ac.access_level_allows("restricted", "internal")
    assert ac.access_level_allows("restricted", "restricted")


# --- AC-002: no roster -> unfiltered ---------------------------------------------

def test_no_roster_is_unfiltered_AC_002(tmp_path):
    assert ac.resolve_viewer_clearance(root=tmp_path) is None
    store = _store([_loaded("r-pub", "public"), _loaded("r-int", "internal"),
                    _loaded("r-res", "restricted")])
    model = m.build_model(store, as_of=AS_OF,
                          viewer_clearance=ac.resolve_viewer_clearance(root=tmp_path))
    assert model["counts"]["total"] == 3
    assert {rv["id"] for rv in model["records"]} == {"r-pub", "r-int", "r-res"}


# --- AC-003: empty roster -> unfiltered, same as no roster ----------------------

def test_empty_roster_is_unfiltered_AC_003(tmp_path):
    _write_roster(tmp_path, entries=())
    roster = ac.load_roster(tmp_path)
    assert roster.enforced is False
    assert ac.resolve_viewer_clearance(root=tmp_path) is None


# --- AC-004: one entry activates enforcement for everyone -----------------------

def test_one_entry_activates_enforcement_for_everyone_AC_004(tmp_path):
    _write_roster(tmp_path,
                  entries=[("u-listedhandle0000000000", "listed", "internal")],
                  default="public")
    # The listed viewer gets their roster clearance.
    assert ac.resolve_viewer_clearance(override="u-listedhandle0000000000",
                                       root=tmp_path) == "internal"
    # An unlisted viewer is filtered too -- falls back to default_clearance,
    # never left unfiltered just because they aren't named.
    assert ac.resolve_viewer_clearance(override="u-someoneelse0000000000",
                                       root=tmp_path) == "public"


# --- AC-005: env override resolves roster clearance, no git/OS lookup -----------

def test_env_override_resolves_roster_clearance_AC_005(tmp_path, monkeypatch):
    _write_roster(tmp_path,
                  entries=[("u-envhandle00000000000000", "env-user", "restricted")])
    monkeypatch.setenv("QF_MEMORY_AUTHOR", "u-envhandle00000000000000")
    assert ac.resolve_viewer_clearance(root=tmp_path) == "restricted"


# --- AC-006: unlisted resolved handle -> default_clearance ----------------------

def test_unlisted_handle_gets_default_clearance_AC_006(tmp_path, monkeypatch):
    _write_roster(tmp_path,
                  entries=[("u-otherhandle000000000000", "other", "internal")],
                  default="public")
    monkeypatch.setenv("QF_MEMORY_AUTHOR", "u-unlistedhandle00000000000")
    assert ac.resolve_viewer_clearance(root=tmp_path) == "public"


# --- AC-007: unresolvable identity -> default_clearance, never an exception -----

def test_unresolvable_identity_gets_default_clearance_AC_007(tmp_path, monkeypatch):
    _write_roster(tmp_path,
                  entries=[("u-someone0000000000000000", "someone", "internal")],
                  default="public")
    monkeypatch.delenv("QF_MEMORY_AUTHOR", raising=False)
    monkeypatch.setattr("quantsmith.pipelines.access_control._git_identity", lambda: None)
    monkeypatch.setattr("quantsmith.pipelines.access_control._os_identity", lambda: None)
    assert ac.resolve_viewer_clearance(root=tmp_path) == "public"


# --- AC-008: email-shaped handle rejected ----------------------------------------

def test_email_shaped_handle_is_rejected_AC_008():
    roster = ac.Roster(
        entries=(ac.RosterEntry(handle="someone@example.com", label="x",
                                clearance="internal"),),
        default_clearance="public", enforced=True, source_file="access/roster.yml",
    )
    findings = ac.validate_roster(roster)
    assert len(findings) == 1
    assert findings[0].entry_handle == "someone@example.com"
    assert "pseudonymous handle" in findings[0].message


# --- AC-009: duplicate handle and unrecognized clearance each yield a finding ----

def test_duplicate_handle_and_bad_clearance_rejected_AC_009():
    dup_roster = ac.Roster(
        entries=(
            ac.RosterEntry(handle="u-samehandle000000000000", label="a", clearance="internal"),
            ac.RosterEntry(handle="u-samehandle000000000000", label="b", clearance="internal"),
        ),
        default_clearance="public", enforced=True, source_file="access/roster.yml",
    )
    dup_findings = ac.validate_roster(dup_roster)
    assert len(dup_findings) == 1
    assert "duplicate" in dup_findings[0].message

    bad_clearance_roster = ac.Roster(
        entries=(ac.RosterEntry(handle="u-onehandle0000000000000", label="c",
                                clearance="super-secret"),),
        default_clearance="public", enforced=True, source_file="access/roster.yml",
    )
    bad_findings = ac.validate_roster(bad_clearance_roster)
    assert len(bad_findings) == 1
    assert "unknown clearance" in bad_findings[0].message


# --- AC-010: query() filters by viewer_clearance ---------------------------------

def test_query_filters_by_viewer_clearance_AC_010():
    records = [_record("r-pub", "public"), _record("r-int", "internal"),
              _record("r-res", "restricted")]
    assert {rec.id for rec in wm.query(records, viewer_clearance="internal")} == \
        {"r-pub", "r-int"}
    assert {rec.id for rec in wm.query(records)} == {"r-pub", "r-int", "r-res"}


# --- AC-011: view-model builders exclude restricted content everywhere ----------

def test_view_model_builders_exclude_restricted_content_AC_011():
    store = _store([_loaded("r-pub", "public"), _loaded("r-int", "internal"),
                    _loaded("r-res", "restricted")])
    model = m.build_model(store, as_of=AS_OF, viewer_clearance="internal")

    assert {rv["id"] for rv in model["records"]} == {"r-pub", "r-int"}
    assert model["counts"]["total"] == 2
    assert "restricted" not in model["counts"]["by_access_level"]
    assert "rec:r-res" not in {n["id"] for n in model["graph"]["nodes"]}
    assert "r-res" not in {q["record_id"] for q in model["review_queue"]}

    research_store = r.ResearchStore(items=(
        _research_item("i-pub", "public"),
        _research_item("i-int", "internal"),
        _research_item("i-res", "restricted"),
    ))
    rmodel = r.build_research_model(research_store, as_of=AS_OF, viewer_clearance="internal")
    assert {iv["id"] for iv in rmodel["items"]} == {"i-pub", "i-int"}
    assert rmodel["counts"]["total"] == 2


# --- AC-012: the snapshot's JSON (what a JS build embeds verbatim) excludes it ---

def test_snapshot_build_excludes_restricted_content_AC_012(tmp_path, monkeypatch):
    mem_shared = tmp_path / "memory" / "_shared"
    mem_shared.mkdir(parents=True)
    (mem_shared / "index.yaml").write_text(
        "access_level: internal\n"
        "records:\n"
        "  - id: r-pub\n"
        "    scope: s\n    type: finding\n    statement: x\n    confidence: high\n"
        "    first_seen: 2026-01-01\n    last_confirmed: 2026-01-01\n"
        "    status: active\n    pit_scope: as_of_2026-01-01\n"
        "    access_level: public\n"
        "  - id: r-res\n"
        "    scope: s\n    type: finding\n    statement: y\n    confidence: high\n"
        "    first_seen: 2026-01-01\n    last_confirmed: 2026-01-01\n"
        "    status: active\n    pit_scope: as_of_2026-01-01\n"
        "    access_level: restricted\n",
        encoding="utf-8",
    )
    _write_roster(tmp_path, entries=[("u-snaphandle00000000000000", "snap", "internal")])
    monkeypatch.setenv("QF_MEMORY_AUTHOR", "u-snaphandle00000000000000")

    model = m.build_model_from_root(str(mem_shared.parent), with_changes=False)
    ids = {rv["id"] for rv in model["records"]}
    assert "r-res" not in ids
    assert "r-pub" in ids

    # The snapshot CLI serializes exactly this model -- a JS build step embeds
    # its stdout verbatim as window.__KB_MODEL__, so proving the JSON is
    # already filtered proves the embedded snapshot is too.
    result = _kc_cli("snapshot", "--root", str(mem_shared.parent),
                     env_extra={"QF_MEMORY_AUTHOR": "u-snaphandle00000000000000"})
    assert result.returncode == 0, result.stderr
    snapshot_model = json.loads(result.stdout)
    snapshot_ids = {rv["id"] for rv in snapshot_model["records"]}
    assert "r-res" not in snapshot_ids
    assert "r-pub" in snapshot_ids


# --- AC-013: a visible item still shows its own access_level --------------------

def test_visible_item_still_shows_its_access_level_AC_013():
    store = _store([_loaded("r-pub", "public"), _loaded("r-int", "internal")])
    model = m.build_model(store, as_of=AS_OF, viewer_clearance="internal")
    by_id = {rv["id"]: rv for rv in model["records"]}
    assert by_id["r-pub"]["access_level"] == "public"
    assert by_id["r-int"]["access_level"] == "internal"


# --- AC-014: whoami matches resolve_author ---------------------------------------

def test_whoami_matches_resolve_author_AC_014():
    result = _wm_cli("whoami")
    assert result.returncode == 0, result.stderr
    printed = result.stdout.strip()
    assert printed == wm.resolve_author()


# --- AC-015: preview reports effective visibility --------------------------------

def test_preview_reports_effective_visibility_AC_015(tmp_path):
    mem_shared = tmp_path / "memory" / "_shared"
    mem_shared.mkdir(parents=True)
    (mem_shared / "index.yaml").write_text(
        "access_level: internal\n"
        "records:\n"
        "  - id: r-pub\n"
        "    scope: s\n    type: finding\n    statement: x\n    confidence: high\n"
        "    first_seen: 2026-01-01\n    last_confirmed: 2026-01-01\n"
        "    status: active\n    pit_scope: as_of_2026-01-01\n"
        "    access_level: public\n"
        "  - id: r-res\n"
        "    scope: s\n    type: finding\n    statement: y\n    confidence: high\n"
        "    first_seen: 2026-01-01\n    last_confirmed: 2026-01-01\n"
        "    status: active\n    pit_scope: as_of_2026-01-01\n"
        "    access_level: restricted\n",
        encoding="utf-8",
    )
    _write_roster(tmp_path,
                  entries=[("u-previewhandle0000000000", "preview", "internal")])
    research_root = tmp_path / "research"

    result = _kc_cli(
        "preview-access",
        "--root", str(mem_shared.parent),
        "--research-root", str(research_root),
        "--viewer-override", "u-previewhandle0000000000",
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["enforced"] is True
    assert summary["resolved_clearance"] == "internal"
    assert summary["memory"]["total"] == 2
    assert summary["memory"]["visible"] == 1


# --- AC-016: the access gate reports one finding per structural problem ---------

def test_gate_reports_roster_validation_findings_AC_016(tmp_path):
    _write_roster(
        tmp_path,
        entries=[
            ("u-dupehandle00000000000000", "one", "internal"),
            ("u-dupehandle00000000000000", "two", "internal"),
            ("not a valid handle", "three", "internal"),
            ("u-badclearance000000000000", "four", "super-secret"),
        ],
    )
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    gate = REPO_ROOT / "hooks" / "stages" / "access-check.sh"
    result = subprocess.run(
        ["sh", str(gate)], cwd=str(tmp_path),
        env={**os.environ, "QF_STAGE_ENFORCE": "1"},
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "3 finding(s)" in result.stdout
    assert "access/roster.yml" in result.stdout


# --- AC-017: the safety scan flags an email embedded outside the handle field ---

def test_gate_flags_embedded_email_in_roster_file_AC_017(tmp_path):
    access_dir = tmp_path / "access"
    access_dir.mkdir(parents=True)
    (access_dir / "roster.yml").write_text(
        "# contact alice.smith@example.com if this file looks wrong\n"
        "default_clearance: public\n\n"
        "people:\n"
        "  - handle: u-cccccccccccccccccccccccc\n"
        "    label: dave\n"
        "    clearance: internal\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    gate = REPO_ROOT / "hooks" / "stages" / "access-check.sh"
    result = subprocess.run(
        ["sh", str(gate)], cwd=str(tmp_path),
        env={**os.environ, "QF_STAGE_ENFORCE": "1"},
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "possible PII (email)" in result.stdout
