"""Tests for spec 0049 -- workflow memory write path.

One test per acceptance criterion, named for the AC it verifies (see
``specs/0049-workflow-memory-write-path/tasks.md``). Everything here uses a
scratch ``tmp_path`` tree for ``memory/`` -- nothing writes to the real,
committed store.
"""

from __future__ import annotations

import datetime
import os
import subprocess
import sys
from pathlib import Path

import pytest

from quantsmith.pipelines.ingestion_data_contract import (
    ColumnSpec,
    QualityRule,
    candidates_from_validation,
    validate_ingestion,
)
from quantsmith.pipelines.workflow_memory import (
    Candidate,
    CandidateSpec,
    MemoryWriteError,
    derive_handle,
    discard,
    load_inbox,
    load_records,
    point_in_time_filter,
    promote,
    propose_records,
    query,
    resolve_author,
    stage_candidates,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET = "_shared/datasets/example_prices/provenance.yaml"


def _mem(tmp_path: Path) -> Path:
    root = tmp_path / "memory"
    (root / "_shared" / "datasets" / "example_prices").mkdir(parents=True)
    return root


def _spec(**overrides) -> CandidateSpec:
    fields = dict(
        scope="field:test", type="quirk", statement="A test observation.",
        confidence="low", pit_scope="<= run date",
        evidence=({"source_run": "run-1"},), target_catalog=TARGET,
    )
    fields.update(overrides)
    return CandidateSpec(**fields)


# --- AC-001: env override short-circuits resolution ---------------------------

def test_env_override_short_circuits_resolution_AC_001(monkeypatch):
    monkeypatch.setenv("QF_MEMORY_AUTHOR", "explicit-handle")
    assert resolve_author() == "explicit-handle"


# --- AC-002: git-derived handle matches pattern, no @, stable ------------------

def test_git_derived_handle_matches_pattern_and_is_stable_AC_002(monkeypatch):
    from quantsmith.pipelines.workflow_memory import _AUTHOR_RE
    monkeypatch.delenv("QF_MEMORY_AUTHOR", raising=False)
    h = derive_handle("someone@example.com")
    assert _AUTHOR_RE.match(h)
    assert "@" not in h
    assert derive_handle("someone@example.com") == h


# --- AC-003: different identities -> different handles ------------------------

def test_different_identities_derive_different_handles_AC_003():
    assert derive_handle("alice@example.com") != derive_handle("bob@example.com")


# --- AC-004: no identity resolves to None without raising ----------------------

def test_no_identity_resolves_to_none_without_raising_AC_004(monkeypatch, tmp_path):
    monkeypatch.delenv("QF_MEMORY_AUTHOR", raising=False)
    monkeypatch.setattr(
        "quantsmith.pipelines.workflow_memory._git_identity", lambda: None)
    monkeypatch.setattr(
        "quantsmith.pipelines.workflow_memory._os_identity", lambda: None)
    assert resolve_author(root=str(tmp_path)) is None


# --- AC-005: propose_records writes nothing ------------------------------------

def test_propose_records_writes_nothing_to_disk_AC_005(tmp_path):
    mem = _mem(tmp_path)
    before = sorted(p.relative_to(mem) for p in mem.rglob("*") if p.is_file())
    candidates = propose_records([_spec()], workflow="w", source_run="run-x")
    after = sorted(p.relative_to(mem) for p in mem.rglob("*") if p.is_file())
    assert len(candidates) == 1
    assert before == after == []


# --- AC-006: staged file parses with the 0048 parser ---------------------------

def test_staged_inbox_file_parses_with_0048_parser_AC_006(tmp_path):
    mem = _mem(tmp_path)
    candidates = propose_records([_spec()], workflow="w", source_run="run-x")
    path = stage_candidates(candidates, root=mem)
    loaded = load_inbox(root=mem)
    assert len(loaded) == 1
    cand, source_file = loaded[0]
    assert source_file == str(path)
    assert cand.spec.statement == "A test observation."


# --- AC-007: restaging identical batch is byte-identical ----------------------

def test_restaging_identical_batch_is_byte_identical_AC_007(tmp_path):
    mem = _mem(tmp_path)
    candidates = propose_records([_spec()], workflow="w", source_run="run-x")
    path = stage_candidates(candidates, root=mem)
    before = path.read_bytes()
    stage_candidates(candidates, root=mem)
    after = path.read_bytes()
    assert before == after


# --- AC-008: inbox never leaks into live query/point_in_time_filter -----------

def test_inbox_never_leaks_into_live_query_or_pit_filter_AC_008(tmp_path):
    mem = _mem(tmp_path)
    c1 = propose_records([_spec()], workflow="w1", source_run="run-1")
    c2 = propose_records([_spec(scope="field:other")], workflow="w2", source_run="run-2")
    stage_candidates(c1, root=mem)
    stage_candidates(c2, root=mem)

    inbox = load_inbox(root=mem)
    assert len(inbox) == 2

    live_records = load_records((mem / TARGET).read_text()) if (mem / TARGET).exists() else []
    queried = query(live_records, status=None)
    filtered = point_in_time_filter(live_records, datetime.date.today())
    assert queried == []
    assert filtered == []


# --- AC-009: promote stamps id/author/dates, preserves siblings ---------------

def test_promote_stamps_id_author_dates_preserves_siblings_AC_009(tmp_path):
    mem = _mem(tmp_path)
    target = mem / TARGET
    target.write_text(
        "access_level: internal\n\n"
        "records:\n"
        "  - id: MEM-9001\n"
        "    scope: field:existing\n"
        "    type: schema\n"
        '    statement: "Pre-existing record."\n'
        "    evidence:\n"
        "      source_run: run-preexisting\n"
        "    confidence: high\n"
        "    corroboration_count: 2\n"
        "    first_seen: 2026-01-01\n"
        "    last_confirmed: 2026-01-01\n"
        "    status: active\n"
        '    pit_scope: "<= run date"\n',
        encoding="utf-8",
    )
    before = {r.id: (r.scope, r.type, r.statement, r.confidence, r.corroboration_count,
                     r.first_seen, r.last_confirmed, r.status, r.pit_scope)
             for r in load_records(target.read_text())}

    candidates = propose_records([_spec(scope="field:new")], workflow="w", source_run="run-new")
    stage_candidates(candidates, root=mem)
    cand, src = load_inbox(root=mem)[0]
    result = promote(cand, source_file=src, root=mem, author="tester-1",
                     as_of=datetime.date(2026, 8, 21))

    assert result.record.id
    assert result.record.author == "tester-1"
    assert result.record.first_seen == datetime.date(2026, 8, 21)
    assert result.record.last_confirmed == datetime.date(2026, 8, 21)

    after_records = load_records(target.read_text())
    after = {r.id: (r.scope, r.type, r.statement, r.confidence, r.corroboration_count,
                    r.first_seen, r.last_confirmed, r.status, r.pit_scope)
            for r in after_records}
    assert after["MEM-9001"] == before["MEM-9001"]
    assert result.record.id in after


# --- AC-010: promote removes only the promoted candidate ----------------------

def test_promote_removes_only_the_promoted_candidate_AC_010(tmp_path):
    mem = _mem(tmp_path)
    candidates = propose_records(
        [_spec(scope="field:a"), _spec(scope="field:b")], workflow="w", source_run="run-x")
    stage_candidates(candidates, root=mem)
    inbox = load_inbox(root=mem)
    first, src = inbox[0]
    promote(first, source_file=src, root=mem, author="tester-1")

    remaining = load_inbox(root=mem)
    assert len(remaining) == 1
    assert remaining[0][0].candidate_id != first.candidate_id


# --- AC-011: promote refuses missing required field ----------------------------

def test_promote_refuses_missing_required_field_AC_011(tmp_path):
    mem = _mem(tmp_path)
    candidates = propose_records([_spec(statement="")], workflow="w", source_run="run-x")
    path = stage_candidates(candidates, root=mem)
    cand, src = load_inbox(root=mem)[0]
    with pytest.raises(MemoryWriteError, match="statement"):
        promote(cand, source_file=src, root=mem, author="tester-1")
    assert not (mem / TARGET).exists()
    assert path.exists()
    assert len(load_inbox(root=mem)) == 1


# --- AC-012: promote refuses id collision --------------------------------------

def test_promote_refuses_id_collision_AC_012(tmp_path):
    mem = _mem(tmp_path)
    target = mem / TARGET
    target.write_text(
        "access_level: internal\n\nrecords:\n"
        "  - id: MEM-0001\n"
        "    scope: field:existing\n"
        "    type: schema\n"
        '    statement: "Existing."\n'
        "    evidence:\n"
        "      source_run: run-x\n"
        "    confidence: high\n"
        "    corroboration_count: 1\n"
        "    first_seen: 2026-01-01\n"
        "    last_confirmed: 2026-01-01\n"
        "    status: active\n"
        '    pit_scope: "<= run date"\n',
        encoding="utf-8",
    )
    candidates = propose_records([_spec()], workflow="w", source_run="run-x")
    stage_candidates(candidates, root=mem)
    cand, src = load_inbox(root=mem)[0]

    import quantsmith.pipelines.workflow_memory as wm
    original = wm._next_id
    try:
        wm._next_id = lambda existing_ids, *, workflow: "MEM-0001"
        with pytest.raises(MemoryWriteError, match="MEM-0001"):
            promote(cand, source_file=src, root=mem, author="tester-1")
    finally:
        wm._next_id = original


# --- AC-013: promote warns on contradiction but still promotes ----------------

def test_promote_warns_on_contradiction_but_still_promotes_AC_013(tmp_path):
    mem = _mem(tmp_path)
    c1 = propose_records([_spec(scope="field:dup")], workflow="w", source_run="run-1")
    stage_candidates(c1, root=mem)
    cand1, src1 = load_inbox(root=mem)[0]
    res1 = promote(cand1, source_file=src1, root=mem, author="tester-1")
    assert res1.contradiction_warning is None

    c2 = propose_records([_spec(scope="field:dup")], workflow="w", source_run="run-2")
    stage_candidates(c2, root=mem)
    cand2, src2 = [x for x in load_inbox(root=mem) if x[0].source_run == "run-2"][0]
    res2 = promote(cand2, source_file=src2, root=mem, author="tester-1")
    assert res2.contradiction_warning is not None
    assert res1.record.id in res2.contradiction_warning


# --- AC-014: discard removes one, leaves rest ----------------------------------

def test_discard_removes_one_leaves_rest_AC_014(tmp_path):
    mem = _mem(tmp_path)
    candidates = propose_records(
        [_spec(scope="field:a"), _spec(scope="field:b")], workflow="w", source_run="run-x")
    stage_candidates(candidates, root=mem)
    inbox = load_inbox(root=mem)
    target, src = inbox[0]
    discard(target, source_file=src, root=mem)

    remaining = load_inbox(root=mem)
    assert len(remaining) == 1
    assert remaining[0][0].candidate_id != target.candidate_id
    assert not (mem / TARGET).exists()


# --- AC-015: candidates built from a real validation result -------------------

def test_candidates_from_real_validation_result_AC_015():
    rows = [
        {"id": 1, "close_adj": 10.5},
        {"id": 1, "close_adj": 11.0},   # duplicate key
        {"id": 2, "close_adj": None},   # null in non-nullable
    ]
    schema = [
        ColumnSpec(name="id", type="int", nullable=False),
        ColumnSpec(name="close_adj", type="float", nullable=False),
    ]
    rules = [QualityRule(name="duplicate keys", threshold="0", action_on_breach="block")]
    result = validate_ingestion(rows, schema, ["id"], rules)

    specs = candidates_from_validation(
        result, dataset_scope="example_prices", source_run="run-validate-1",
        target_catalog=TARGET)

    assert len(specs) == 2  # one schema-violation shape + one failed rule
    scopes = {s.scope for s in specs}
    assert "field:close_adj" in scopes
    for s in specs:
        assert "run-validate-1" in s.statement


# --- AC-016: CLI propose/list-inbox/promote/discard ----------------------------

def _run_cli(*args, cwd, env):
    return subprocess.run(
        [sys.executable, "-m", "quantsmith.pipelines.workflow_memory_cli", *args],
        cwd=str(cwd), capture_output=True, text=True, env=env,
    )


def test_cli_propose_list_promote_discard_AC_016(tmp_path):
    mem = _mem(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src"),
          "QF_MEMORY_AUTHOR": "cli-tester"}

    r = _run_cli("propose", "--root", str(mem), "--workflow", "w",
                "--source-run", "run-cli", "--scope", "field:cli",
                "--type", "quirk", "--statement", "CLI test.",
                "--confidence", "low", "--pit-scope", "<= run date",
                "--target-catalog", TARGET, "--evidence-run", "run-cli",
                cwd=tmp_path, env=env)
    assert r.returncode == 0, r.stderr
    assert "staged w/run-cli/001" in r.stdout

    r = _run_cli("list-inbox", "--root", str(mem), cwd=tmp_path, env=env)
    assert r.returncode == 0
    assert "w/run-cli/001" in r.stdout

    r = _run_cli("promote", "--root", str(mem), "--candidate-id", "w/run-cli/001",
                cwd=tmp_path, env=env)
    assert r.returncode == 0, r.stderr
    assert "promoted w/run-cli/001" in r.stdout

    r = _run_cli("list-inbox", "--root", str(mem), cwd=tmp_path, env=env)
    assert "empty" in r.stdout

    r2 = _run_cli("propose", "--root", str(mem), "--workflow", "w",
                 "--source-run", "run-cli-2", "--scope", "field:cli2",
                 "--type", "pitfall", "--statement", "To discard.",
                 "--confidence", "low", "--pit-scope", "<= run date",
                 "--target-catalog", TARGET, "--evidence-run", "run-cli-2",
                 cwd=tmp_path, env=env)
    assert r2.returncode == 0
    r3 = _run_cli("discard", "--root", str(mem), "--candidate-id", "w/run-cli-2/001",
                 cwd=tmp_path, env=env)
    assert r3.returncode == 0
    assert "discarded" in r3.stdout


# --- AC-017: run card template has a Memory proposed field --------------------

def test_run_card_template_has_memory_proposed_field_AC_017():
    text = (REPO_ROOT / "templates" / "docs" / "run_card.md").read_text()
    idx_used = text.index("Memory version / snapshot used")
    idx_proposed = text.index("Memory proposed")
    assert idx_proposed > idx_used


# --- AC-018: gate reports a malformed inbox candidate --------------------------

def test_gate_reports_malformed_inbox_candidate_AC_018(tmp_path):
    mem = tmp_path / "memory"
    (mem / "_shared" / "datasets" / "example_prices").mkdir(parents=True)
    (mem / "manifest.yaml").write_text("version: 1\n", encoding="utf-8")
    inbox_dir = mem / "inbox" / "w"
    inbox_dir.mkdir(parents=True)
    (inbox_dir / "run-bad.yaml").write_text(
        "candidates:\n"
        "  - candidate_id: w/run-bad/001\n"
        "    scope: field:x\n"
        "    type: quirk\n"
        "    confidence: low\n"
        '    pit_scope: "<= run date"\n'
        "    target_catalog: _shared/datasets/example_prices/provenance.yaml\n",
        encoding="utf-8",
    )
    # A live git repo is required for hooks/stages/common.sh's QF_ROOT
    # resolution; run the gate against tmp_path with git initialised there so
    # QF_ROOT resolves to the fixture, never the real repo.
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    gate = REPO_ROOT / "hooks" / "stages" / "memory-check.sh"
    r = subprocess.run(
        ["sh", str(gate)], cwd=str(tmp_path),
        env={**os.environ, "QF_STAGE_ENFORCE": "1"},
        capture_output=True, text=True,
    )
    assert r.returncode == 1
    assert "run-bad.yaml" in r.stdout
    assert "statement" in r.stdout
