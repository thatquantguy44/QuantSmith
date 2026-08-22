"""Regression test for the spec 0055 worked example.

``examples/scheduled_daily_report/`` is the concrete, low-risk worked example
named in ``specs/0055-workflow-scheduling-operations/tasks.md``'s Follow-ups:
a daily report script scheduled by cron and summarized in a Markdown
operations report. This test runs the driver end to end against a real
target (not a mock) and checks the loop's guarantees hold -- registry
validity, idempotent dispatch, and a report that reflects both.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from examples.scheduled_daily_report import daily_review_report as job_module  # noqa: E402
from examples.scheduled_daily_report.run_example import build_job, main  # noqa: E402
from quantsmith.pipelines.workflow_scheduling import (  # noqa: E402
    ExecutionLedger,
    dispatch_job,
    dry_run_schedule,
    validate_registry,
)

UTC = dt.timezone.utc
NOW = dt.datetime(2027, 6, 1, 10, 30, tzinfo=UTC)


def test_registry_entry_is_valid():
    job = build_job("unused.md", as_of="2027-06-01")
    validation = validate_registry([job])
    assert validation.is_valid is True
    assert validation.findings == ()


def test_dry_run_matches_declared_cron_trigger():
    job = build_job("unused.md", as_of="2027-06-01")
    result = dry_run_schedule(job, NOW)
    assert result.status == "scheduled"
    assert result.provider == "cron"
    assert result.next_run_utc is not None


def test_dispatch_against_the_real_target_is_idempotent(tmp_path):
    digest_path = str(tmp_path / "digest.md")
    job = build_job(digest_path, as_of="2027-06-01")
    ledger = ExecutionLedger(tmp_path / "ledger.jsonl")

    first = dispatch_job(job, ledger, NOW, partition="2027-06-01")
    second = dispatch_job(job, ledger, NOW, partition="2027-06-01")

    assert first.status == "completed"
    assert first.artifact_uris == (f"file://{digest_path}",)
    assert Path(digest_path).exists()
    assert second.status == "skipped"
    assert second.artifact_uris == (f"existing_run:{first.run_id}",)


def test_job_output_is_a_real_review_digest(tmp_path):
    digest_path = str(tmp_path / "digest.md")
    artifact = job_module.run(root=str(REPO_ROOT / "memory"), out=digest_path,
                              as_of="2027-06-01")
    assert artifact == f"file://{digest_path}"
    text = Path(digest_path).read_text(encoding="utf-8")
    assert text.startswith("# Workflow Memory Review Digest -- 2027-06-01")
    # The real memory/ fixture has stale reference records, so the digest
    # should name at least one of them rather than reporting nothing to see.
    assert "MEM-" in text


def test_driver_runs_end_to_end_and_writes_all_three_artifacts(tmp_path):
    rc = main(["--out-dir", str(tmp_path), "--now", "2027-06-01T10:30:00+00:00"])
    assert rc == 0
    assert (tmp_path / "review_digest.md").exists()
    assert (tmp_path / "ledger.jsonl").exists()
    assert (tmp_path / "daily_operations_report.md").exists()

    ledger_lines = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(ledger_lines) == 2
    statuses = [json.loads(line)["status"] for line in ledger_lines]
    assert statuses == ["completed", "skipped"]

    report = (tmp_path / "daily_operations_report.md").read_text(encoding="utf-8")
    assert "# Daily Operations Report -- 2027-06-01" in report
    assert "memory-review-digest [completed]" in report
    assert "memory-review-digest [skipped]" in report
    assert "triage-memory-review-digest" in report


def test_committed_sample_output_is_current():
    """The checked-in sample_output/ should match a fresh run at the same --now."""
    sample_dir = REPO_ROOT / "examples" / "scheduled_daily_report" / "sample_output"
    assert (sample_dir / "review_digest.md").exists(), (
        "sample_output/ is missing; regenerate with "
        "`python examples/scheduled_daily_report/run_example.py "
        "--now 2027-06-01T10:30:00+00:00`"
    )
    committed_digest = (sample_dir / "review_digest.md").read_text(encoding="utf-8")

    fresh_digest = job_module.build_digest(str(REPO_ROOT / "memory"), dt.date(2027, 6, 1))
    assert committed_digest == fresh_digest, (
        "sample_output/review_digest.md is stale relative to memory/ -- "
        "regenerate it with run_example.py (see this example's README)"
    )
