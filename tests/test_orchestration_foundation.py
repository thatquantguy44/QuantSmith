"""Acceptance tests for spec 0070 - orchestration evidence foundation."""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
from pathlib import Path

from quantsmith.orchestration import (
    INTEGRATION_SURFACES,
    REQUIRED_HARNESS_LAYERS,
    discover_envelopes,
    load_json,
    load_jsonl,
    replay_envelope_file,
    sha256_file,
    validate_assumption_ledger,
    validate_audit_events,
    validate_context_manifest,
    validate_discovered_envelopes,
    validate_evaluation_harness,
    validate_prompt_manifest,
    validate_run_envelope_file,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "orchestration"
DETERMINISTIC = EXAMPLES / "deterministic_quant_run"
LLM_FIXTURE = EXAMPLES / "fixture_backed_llm_run"
TEMPLATES = ROOT / "templates" / "orchestration"


def _codes(report):
    return {finding.code for finding in report.findings}


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows) -> None:
    text = "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


# AC-001: valid run envelope resolves references and hashes offline.


def test_run_envelope_resolves_artifacts_and_hashes_AC_001():
    report = validate_run_envelope_file(DETERMINISTIC / "run_envelope.json")

    assert report.ok, [finding.to_dict() for finding in report.findings]
    assert report.counts["envelopes"] == 1
    assert report.counts["artifacts"] == 1


# AC-002: invalid prompt manifest field failures are actionable.


def test_prompt_manifest_rejects_unversioned_hashless_or_unauthorized_AC_002():
    manifest = load_json(DETERMINISTIC / "prompt_manifest.json")
    manifest.pop("version")
    manifest["source"].pop("hash")
    manifest["rendered_variables"]["undeclared"] = "surprise"
    manifest["requested_tools"].append({"name": "shell.exec"})

    report = validate_prompt_manifest(manifest, base_dir=DETERMINISTIC)

    assert not report.ok
    codes = _codes(report)
    assert "required" in codes
    assert "undeclared-variable" in codes
    assert "unauthorized-tool" in codes


# AC-003: context access, stale freshness, and future-known records are blocked.


def test_context_manifest_blocks_access_stale_and_future_known_context_AC_003():
    manifest = load_json(DETERMINISTIC / "context_manifest.json")
    item = manifest["items"][0]
    item["access_level"] = "restricted"
    item["known_at"] = "2026-09-07T00:00:00Z"
    item["expires_at"] = "2026-09-05T00:00:00Z"
    item["freshness"] = "current"

    report = validate_context_manifest(manifest, base_dir=DETERMINISTIC)

    assert not report.ok
    codes = _codes(report)
    assert "access-denied" in codes
    assert "future-known" in codes
    assert "stale-current" in codes


# AC-004: material assumptions must carry governance and dependency fields.


def test_assumption_ledger_requires_owner_evidence_review_and_dependents_AC_004():
    assumptions = load_jsonl(DETERMINISTIC / "assumptions.jsonl")
    assumption = dict(assumptions[0])
    assumption.pop("owner")
    assumption["evidence"] = []
    assumption.pop("review_due_at")
    assumption["dependent_artifacts"] = []

    report = validate_assumption_ledger([assumption], base_dir=DETERMINISTIC)

    assert not report.ok
    fields = {finding.field for finding in report.findings}
    assert any(field.endswith(".owner") for field in fields)
    assert any(field.endswith(".evidence") for field in fields)
    assert any(field.endswith(".review_due_at") for field in fields)
    assert any(field.endswith(".dependent_artifacts") for field in fields)


# AC-005: evaluation harness covers each required orchestration layer.


def test_evaluation_harness_covers_every_required_layer_AC_005():
    harness = load_json(DETERMINISTIC / "evaluation_harness.json")

    report = validate_evaluation_harness(harness, base_dir=DETERMINISTIC)

    assert report.ok, [finding.to_dict() for finding in report.findings]
    assert set(REQUIRED_HARNESS_LAYERS) <= {entry["layer"] for entry in harness["layers"]}


# AC-006: audit event shape, ordering, and override reasons are validated.


def test_audit_events_reject_malformed_relationships_and_unreasoned_overrides_AC_006():
    events = load_jsonl(DETERMINISTIC / "audit_events.jsonl")
    bad_events = copy.deepcopy(events)
    bad_events[1]["timestamp"] = "2026-09-05T00:00:01Z"
    bad_events[2]["parent_event_ids"] = ["evt-missing"]
    bad_events.append(copy.deepcopy(bad_events[0]))
    bad_events.append(
        {
            "schema_version": "quantsmith.orchestration.audit_event.v1",
            "event_id": "evt-override",
            "run_id": "orch-det-0063-golden-repo-specialness",
            "event_type": "override",
            "timestamp": "2026-09-06T00:00:05Z",
            "actor": "codex",
            "parent_event_ids": ["evt-det-004"],
            "payload_ref": {
                "kind": "redacted_metadata",
                "hash": "sha256:8888888888888888888888888888888888888888888888888888888888888888",
            },
            "artifact_refs": [],
            "finding_refs": [],
        }
    )

    report = validate_audit_events(
        bad_events,
        run_id="orch-det-0063-golden-repo-specialness",
        base_dir=DETERMINISTIC,
    )

    assert not report.ok
    codes = _codes(report)
    assert "non-monotonic" in codes
    assert "broken-parent" in codes
    assert "duplicate" in codes
    assert "required" in codes


# AC-007: deterministic replay is repeatable.


def test_replay_command_reproduces_deterministic_fixture_AC_007():
    first = replay_envelope_file(DETERMINISTIC / "run_envelope.json").to_dict()
    second = replay_envelope_file(DETERMINISTIC / "run_envelope.json").to_dict()

    assert first == second
    assert first["status"] == "replayed"
    assert first["output_diffs"] == []
    assert first["non_reproducible_dependencies"] == []


# AC-008: LLM replay uses a fixture or reports a non-reproducible dependency.


def test_replay_uses_llm_fixture_or_reports_non_reproducible_call_AC_008(tmp_path):
    replay = replay_envelope_file(LLM_FIXTURE / "run_envelope.json", fixture_mode=True)
    assert replay.status == "replayed"
    assert replay.fixture_substitutions[0]["event_id"] == "evt-llm-003"

    copied = tmp_path / "llm-no-fixture"
    shutil.copytree(LLM_FIXTURE, copied)
    events_path = copied / "audit_events.jsonl"
    events = load_jsonl(events_path)
    for event in events:
        if event["event_type"] == "model_invocation":
            event["payload_ref"].pop("fixture_path")
            event["payload_ref"].pop("fixture_hash")
    _write_jsonl(events_path, events)
    envelope_path = copied / "run_envelope.json"
    envelope = load_json(envelope_path)
    envelope["audit_events"]["hash"] = sha256_file(events_path)
    _write_json(envelope_path, envelope)

    non_replay = replay_envelope_file(envelope_path, fixture_mode=True)

    assert non_replay.status == "non_reproducible"
    assert non_replay.non_reproducible_dependencies[0]["event_id"] == "evt-llm-003"


# AC-009: orchestration gate is discoverable through run-stage.


def test_orchestration_gates_are_discoverable_through_run_stage_AC_009():
    env = os.environ.copy()
    env["QF_STAGE_ENFORCE"] = "1"
    result = subprocess.run(
        ["sh", "hooks/stages/run-stage.sh", "orchestration"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "ok - validated 2 orchestration envelope(s)" in result.stdout


# AC-010: existing SDK ownership surfaces are referenced rather than replaced.


def test_foundation_references_existing_surfaces_without_owning_them_AC_010():
    harness = load_json(LLM_FIXTURE / "evaluation_harness.json")

    assert set(INTEGRATION_SURFACES) <= set(harness["integration_surfaces"])


# AC-011: committed examples and templates cover deterministic and LLM runs.


def test_examples_include_deterministic_and_fixture_backed_envelopes_AC_011():
    envelopes = discover_envelopes(EXAMPLES)

    assert DETERMINISTIC / "run_envelope.json" in envelopes
    assert LLM_FIXTURE / "run_envelope.json" in envelopes
    assert (TEMPLATES / "run_envelope.template.json").exists()
    assert (TEMPLATES / "prompt_manifest.template.json").exists()
    assert validate_discovered_envelopes(EXAMPLES).ok


# AC-012: clean checkout validation path is offline and credential-free.


def test_orchestration_cli_validates_examples_offline_AC_012():
    result = subprocess.run(
        [
            "python3",
            "-m",
            "quantsmith.orchestration",
            "validate",
            "--discover",
            "examples/orchestration",
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "ok - validated 2 orchestration envelope(s)" in result.stdout
