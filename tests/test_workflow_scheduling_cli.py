"""Acceptance tests for spec 0060 -- scheduler monitoring.

Covers what spec 0055's own Follow-ups named as missing:
``deliver_routed_alerts`` (the alert-delivery wiring) and
``workflow_scheduling_cli.py`` (render-report / alerts), one test per
acceptance criterion. CLI commands are exercised as a real subprocess, the
same pattern ``test_workflow_memory_write_path.py`` uses for spec 0049's CLI.
"""

from __future__ import annotations

import datetime as dt
import os
import pathlib
import subprocess
import sys

import pytest

from quantsmith.adapters.alert_delivery.result import DeliveryResult
from quantsmith.pipelines import alerting
from quantsmith.pipelines.workflow_scheduling import (
    ExecutionLedger,
    RunRecord,
    deliver_routed_alerts,
    render_daily_operations_report,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc


def _routed(rule_id="workflow-failed", metric="daily-brief", severity="critical",
            channel_map=None):
    alert = alerting.Alert(rule_id, metric, severity,
                           f"{metric}:{rule_id}", f"{metric} {rule_id}")
    routing = alerting.Routing(channels=channel_map or {})
    return alerting.route([alert], routing)


def _fake_sender(calls):
    def sender(event):
        calls.append(event)
        return DeliveryResult(
            adapter_name="fake", provider="email", status="delivered",
            correlation_id=event.correlation_id, dedupe_key=event.dedupe_key,
            timestamp_utc="2026-08-24T00:00:00Z",
        )
    return sender


# --- AC-001: delivers through the sender registered for the alert's channel ---

def test_deliver_routed_alerts_calls_matching_sender_AC_001():
    routed = _routed(channel_map={"critical": "email"})
    calls = []
    results = deliver_routed_alerts(
        routed, job_id="daily-brief", correlation_id="corr-1",
        senders={"email": _fake_sender(calls)}, alert_route="oncall@example.com",
    )
    assert len(results) == 1
    assert results[0].status == "delivered"
    event = calls[0]
    assert event.workflow_id == "daily-brief"
    assert event.correlation_id == "corr-1"
    assert event.route == "oncall@example.com"
    assert event.owner == routed[0].owner
    assert event.dedupe_key == routed[0].alert.dedup_key


# --- AC-002: unregistered channel raises, never silently drops ---

def test_deliver_routed_alerts_unmapped_channel_raises_AC_002():
    routed = _routed(channel_map={"critical": "slack"})
    with pytest.raises(ValueError, match="slack"):
        deliver_routed_alerts(routed, job_id="j", correlation_id="c", senders={},
                              alert_route="x")


# --- AC-003: multiple alerts route to their own channel's sender ---

def test_deliver_routed_alerts_multiple_channels_AC_003():
    email_alert = alerting.Alert("rule-a", "m1", "warning", "m1:rule-a", "m1 warn")
    slack_alert = alerting.Alert("rule-b", "m2", "critical", "m2:rule-b", "m2 crit")
    routing = alerting.Routing(channels={"warning": "email", "critical": "slack"})
    routed = alerting.route([email_alert, slack_alert], routing)

    email_calls, slack_calls = [], []
    deliver_routed_alerts(
        routed, job_id="j", correlation_id="c",
        senders={"email": _fake_sender(email_calls), "slack": _fake_sender(slack_calls)},
        alert_route="route",
    )
    assert len(email_calls) == 1 and len(slack_calls) == 1
    assert email_calls[0].dedupe_key == "m1:rule-a"
    assert slack_calls[0].dedupe_key == "m2:rule-b"


# --- AC-004/AC-005/AC-006: the CLI, invoked as a real subprocess ---

def _run_cli(*args, env):
    return subprocess.run(
        [sys.executable, "-m", "quantsmith.pipelines.workflow_scheduling_cli", *args],
        capture_output=True, text=True, env=env,
    )


def _ledger_with_failure(path):
    ledger = ExecutionLedger(path=str(path))
    now = dt.datetime(2026, 8, 24, 9, 0, tzinfo=UTC)
    ledger.append(RunRecord(
        run_id="r1", job_id="daily-brief", correlation_id="c1", idempotency_key="k1",
        scheduled_for_utc=now.isoformat(), started_at_utc=now.isoformat(),
        ended_at_utc=now.isoformat(), status="failed", attempt=1,
        error_message_redacted="boom",
    ))
    return ledger


def test_cli_render_report_matches_library_output_AC_004(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    _ledger_with_failure(ledger_path)
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    r = _run_cli("render-report", "--ledger", str(ledger_path),
                "--report-date", "2026-08-24", env=env)
    assert r.returncode == 0, r.stderr

    expected = render_daily_operations_report(
        ExecutionLedger(path=str(ledger_path)).records(), (),
        report_date=dt.date(2026, 8, 24),
    )
    assert r.stdout.rstrip("\n") == expected.rstrip("\n")


def test_cli_alerts_previews_without_delivering_AC_005(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    _ledger_with_failure(ledger_path)
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    r = _run_cli("alerts", "--ledger", str(ledger_path), "--as-of", "2026-08-24", env=env)
    assert r.returncode == 0, r.stderr
    assert "workflow-failed" in r.stdout
    assert "owner=" in r.stdout and "channel=" in r.stdout
    # Never touches adapters/alert_delivery -- no delivery vocabulary in output.
    assert "delivered" not in r.stdout.lower()


def test_cli_degrades_gracefully_on_empty_ledger_AC_006(tmp_path):
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    missing = tmp_path / "does-not-exist.jsonl"

    r = _run_cli("render-report", "--ledger", str(missing), env=env)
    assert r.returncode == 0, r.stderr
    assert "Daily Operations Report" in r.stdout

    r = _run_cli("alerts", "--ledger", str(missing), env=env)
    assert r.returncode == 0, r.stderr
    assert "(no alerts)" in r.stdout
