"""Acceptance tests for spec 0055 -- workflow scheduling operations."""

from __future__ import annotations

import datetime as dt

from quantsmith.pipelines.workflow_scheduling import (
    BackfillPolicy,
    ExecutionLedger,
    ManualFollowup,
    ManualTaskQueue,
    RetryPolicy,
    Schedule,
    ScheduleJob,
    Target,
    Trigger,
    alert_handoffs,
    dispatch_job,
    dry_run_schedule,
    memory_candidates_from_failures,
    render_daily_operations_report,
    validate_registry,
)


UTC = dt.timezone.utc


def job(**overrides) -> ScheduleJob:
    base = dict(
        job_id="daily-report",
        owner="ops",
        environment="prod",
        target=Target("python_module", "jobs.daily_report"),
        schedule=Schedule("America/New_York", "business", Trigger("cron", "30 6 * * 1-5")),
        retry_policy=RetryPolicy(2, 0),
        backfill_policy=BackfillPolicy(True, 30, "{job_id}:{partition}"),
        runbook_uri="runbooks/daily-report.md",
        alert_route="ops-alerts",
        manual_followups=(ManualFollowup("review-report", "ops", 0, "daily", "Review generated report"),),
    )
    base.update(overrides)
    return ScheduleJob(**base)


# --- AC-001: registry validation ---


def test_schedule_registry_validation_ac001():
    valid = validate_registry([job()])
    assert valid.is_valid is True
    assert valid.findings == ()

    bad = validate_registry([
        job(owner="", schedule=Schedule("Not/AZone", "business", Trigger("cron", "bad cron")))
    ])
    codes = {f.code for f in bad.findings}
    assert bad.is_valid is False
    assert {"missing-owner", "bad-timezone", "bad-cron"} <= codes


# --- AC-002: dry-run provider evidence, no execution ---


def test_scheduler_dry_run_next_run_ac002():
    now = dt.datetime(2026, 8, 21, 9, 0, tzinfo=UTC)  # Friday 05:00 NY
    result = dry_run_schedule(job(), now)
    assert result.status == "scheduled"
    assert result.provider == "cron"
    assert result.provider_schedule_id == "dry-run:cron:daily-report"
    assert result.next_run_utc == "2026-08-21T10:30:00+00:00"  # 06:30 New York
    assert result.correlation_id


# --- AC-003: idempotent duplicate dispatch ---


def test_dispatch_idempotency_ac003():
    ledger = ExecutionLedger()
    calls = []

    def run_report():
        calls.append("ran")
        return "artifact://daily-report"

    scheduled = dt.datetime(2026, 8, 21, 10, 30, tzinfo=UTC)
    first = dispatch_job(job(), ledger, scheduled, partition="2026-08-21", handlers={"jobs.daily_report": run_report})
    second = dispatch_job(job(), ledger, scheduled, partition="2026-08-21", handlers={"jobs.daily_report": run_report})

    assert first.status == "completed"
    assert second.status == "skipped"
    assert second.artifact_uris == (f"existing_run:{first.run_id}",)
    assert calls == ["ran"]


# --- AC-004: ledger status metadata and redaction ---


def test_execution_ledger_status_redaction_ac004(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = ExecutionLedger(path)
    scheduled = dt.datetime(2026, 8, 21, 10, 30, tzinfo=UTC)

    dispatch_job(job(), ledger, scheduled, handlers={"jobs.daily_report": lambda: "artifact://ok"})

    def fail():
        raise RuntimeError("password=super-secret-token")

    failed = dispatch_job(
        job(job_id="failing-report", target=Target("python_module", "jobs.fail")),
        ledger,
        scheduled,
        handlers={"jobs.fail": fail},
    )
    reloaded = ExecutionLedger(path).records()

    assert {r.status for r in reloaded} == {"completed", "failed"}
    assert failed.exception_class == "RuntimeError"
    assert "super-secret-token" not in failed.error_message_redacted
    assert "[REDACTED]" in failed.error_message_redacted
    for record in reloaded:
        assert record.run_id
        assert record.correlation_id
        assert record.scheduled_for_utc


# --- AC-005: daily report sections and owner/workflow rollups ---


def test_daily_operations_report_sections_ac005():
    ledger = ExecutionLedger()
    scheduled = dt.datetime(2026, 8, 21, 10, 30, tzinfo=UTC)
    dispatch_job(job(), ledger, scheduled, handlers={"jobs.daily_report": lambda: "artifact://ok"})
    duplicate = dispatch_job(job(), ledger, scheduled, partition="2026-08-21", handlers={"jobs.daily_report": lambda: "artifact://new"})
    queue = ManualTaskQueue()
    queue.add_for_job(job(), dt.date(2026, 8, 21))

    report = render_daily_operations_report(ledger.records(), queue.tasks(), report_date=dt.date(2026, 8, 21))

    for section in (
        "## Completed Jobs",
        "## Failed Jobs",
        "## Skipped Or Missed Jobs",
        "## Manual Tasks",
        "## Overdue Reminders",
        "## Next Runs",
        "## Owner / Workflow Rollup",
    ):
        assert section in report
    assert duplicate.status == "skipped"
    assert "daily-report" in report
    assert "manual:ops" in report


# --- AC-006: manual tasks carry forward and remain reminder-eligible ---


def test_manual_task_carry_forward_ac006():
    queue = ManualTaskQueue()
    created = queue.add_for_job(job(), dt.date(2026, 8, 21))
    assert created[0].status == "open"
    assert queue.overdue(dt.date(2026, 8, 22))[0].task_id == "review-report"

    acknowledged = queue.acknowledge("review-report", "2026-08-22T12:00:00+00:00")
    assert acknowledged.status == "acknowledged"
    assert queue.overdue(dt.date(2026, 8, 23))[0].status == "acknowledged"

    completed = queue.complete("review-report", "2026-08-23T12:00:00+00:00", "evidence://review")
    assert completed.status == "completed"
    assert queue.overdue(dt.date(2026, 8, 24)) == ()


# --- AC-007: alert handoff payload, no provider delivery ---


def test_alert_handoff_payload_ac007():
    ledger = ExecutionLedger()
    scheduled = dt.datetime(2026, 8, 21, 10, 30, tzinfo=UTC)

    def fail():
        raise RuntimeError("boom")

    dispatch_job(job(target=Target("python_module", "jobs.fail")), ledger, scheduled, handlers={"jobs.fail": fail})
    queue = ManualTaskQueue()
    queue.add_for_job(job(), dt.date(2026, 8, 20))
    alerts = alert_handoffs(ledger.records(), queue.tasks(), as_of=dt.date(2026, 8, 22))

    assert {a.rule_id for a in alerts} == {"workflow-failed", "manual-task-overdue"}
    assert all(a.dedup_key for a in alerts)
    assert all("provider" not in a.message.lower() for a in alerts)


# --- AC-008: recurring failure becomes memory candidate ---


def test_memory_candidate_from_recurring_failure_ac008():
    ledger = ExecutionLedger()
    scheduled = dt.datetime(2026, 8, 21, 10, 30, tzinfo=UTC)

    def fail():
        raise RuntimeError("boom")

    failing_job = job(job_id="fragile-job", target=Target("python_module", "jobs.fail"))
    dispatch_job(failing_job, ledger, scheduled, partition="p1", handlers={"jobs.fail": fail})
    dispatch_job(failing_job, ledger, scheduled + dt.timedelta(days=1), partition="p2", handlers={"jobs.fail": fail})

    candidates = memory_candidates_from_failures(ledger.records())
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.scope == "workflow:fragile-job"
    assert candidate.type == "pitfall"
    assert candidate.evidence["corroboration_count"] == "2"
