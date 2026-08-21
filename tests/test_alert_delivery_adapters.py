"""Acceptance tests for spec 0032 -- alert delivery executable providers.

Each test is named for the acceptance criterion it covers (see
``specs/0032-alert-delivery-providers/tasks.md``).
"""

from __future__ import annotations

import pytest

from quantsmith.adapters.alert_delivery import (
    AlertDeliveryEvent,
    EvidenceItem,
    Privacy,
    TransportError,
    build_email_payload,
    build_pagerduty_payload,
    build_slack_payload,
    build_sms_push_payload,
    build_teams_payload,
    build_ticketing_payload,
    build_webhook_payload,
    deliver_email,
    deliver_pagerduty,
    deliver_slack,
    deliver_sms_push,
    deliver_teams,
    deliver_ticketing,
    deliver_webhook,
)
from quantsmith.adapters.alert_delivery.sms_push import BODY_MAX_LEN, TITLE_MAX_LEN


def sample_event(**overrides) -> AlertDeliveryEvent:
    fields = dict(
        event_id="evt-1",
        workflow_id="wf-pipeline-freshness",
        source="pipeline_observability",
        severity="high",
        status="triggered",
        owner="data-eng",
        route="oncall@example.com",
        title="Freshness breach: daily_positions",
        summary="daily_positions is 4h stale",
        correlation_id="corr-1",
        dedupe_key="freshness:daily_positions",
        body_markdown="Pipeline daily_positions has not refreshed since 06:00 UTC.",
        evidence=(EvidenceItem("dashboard", "https://example.com/dash"),),
    )
    fields.update(overrides)
    return AlertDeliveryEvent(**fields)


# --- AC-001: missing required field raises ---


def test_missing_required_field_raises_AC_001():
    with pytest.raises(ValueError, match="owner"):
        sample_event(owner="")


# --- AC-002 / AC-003: dry-run default, no transport call, status skipped ---


def test_email_dry_run_default_AC_002():
    event = sample_event()
    result = deliver_email(event)
    assert result.dry_run is True
    assert result.status == "skipped"
    assert result.provider == "email"
    assert result.correlation_id == event.correlation_id


def test_webhook_dry_run_default_AC_003():
    event = sample_event()
    result = deliver_webhook(event)
    assert result.dry_run is True
    assert result.status == "skipped"
    assert result.provider == "webhook"


# --- AC-004: transport injection ---


def test_transport_injection_AC_004():
    event = sample_event()
    calls = []

    def fake_transport(payload):
        calls.append(payload)
        return {"provider_message_id": "msg-123"}

    result = deliver_email(event, transport=fake_transport, dry_run=False)
    assert result.status == "delivered"
    assert result.dry_run is False
    assert result.provider_message_id == "msg-123"
    assert len(calls) == 1
    assert calls[0] == build_email_payload(event)

    with pytest.raises(ValueError, match="transport is required"):
        deliver_webhook(event, dry_run=False)


# --- AC-005: redaction per privacy.redaction_level ---


def test_redaction_applied_AC_005():
    body = "Positions detail: AAPL 10000 shares"
    none_event = sample_event(body_markdown=body, privacy=Privacy(redaction_level="none"))
    payload_none = build_email_payload(none_event)
    assert body in payload_none["body"]

    standard_no_flag = sample_event(body_markdown=body, privacy=Privacy(redaction_level="standard"))
    payload_std_no_flag = build_email_payload(standard_no_flag)
    assert body in payload_std_no_flag["body"]

    standard_with_flag = sample_event(
        body_markdown=body,
        privacy=Privacy(redaction_level="standard", contains_restricted_positions=True),
    )
    payload_std_flag = build_email_payload(standard_with_flag)
    assert body not in payload_std_flag["body"]
    assert "REDACTED" in payload_std_flag["body"]

    strict_event = sample_event(body_markdown=body, privacy=Privacy(redaction_level="strict"))
    payload_strict = build_webhook_payload(strict_event)
    assert body not in payload_strict["body_markdown"]
    assert "REDACTED" in payload_strict["body_markdown"]


# --- AC-006: credential-shaped value never appears verbatim ---


def test_secret_shaped_value_flagged_AC_006():
    secret = "api_key=sk_live_abcdef123456"
    event = sample_event(body_markdown=f"Rotate this: {secret}")

    payload = build_email_payload(event)
    assert secret not in payload["body"]
    assert "REDACTED" in payload["body"]

    webhook_payload = build_webhook_payload(event)
    assert secret not in webhook_payload["body_markdown"]

    # A secret hiding in a field the builder doesn't proactively redact (title)
    # is still caught by the payload-wide guard before the payload is returned.
    with pytest.raises(ValueError, match="credential-shaped"):
        build_email_payload(sample_event(title=f"Leaked: {secret}"))


# --- AC-007: retryable vs terminal failure classification ---


def test_retryable_vs_terminal_failure_AC_007():
    event = sample_event()

    def flaky_transport(payload):
        raise TransportError("rate limited", retryable=True, error_code="rate_limit")

    result = deliver_email(event, transport=flaky_transport, dry_run=False)
    assert result.status == "failed"
    assert result.retryable is True
    assert result.error_code == "rate_limit"

    def bad_recipient_transport(payload):
        raise TransportError("invalid recipient", retryable=False, error_code="invalid_recipient")

    result2 = deliver_webhook(event, transport=bad_recipient_transport, dry_run=False)
    assert result2.status == "failed"
    assert result2.retryable is False
    assert result2.error_code == "invalid_recipient"


# --- AC-008: deterministic payload construction ---


def test_payload_construction_deterministic_AC_008():
    event = sample_event()
    assert build_email_payload(event) == build_email_payload(event)
    assert build_webhook_payload(event) == build_webhook_payload(event)


# =====================================================================
# Spec 0037 -- remaining providers: Slack, Teams, ticketing,
# PagerDuty/Opsgenie, SMS/push
# =====================================================================


# --- AC-001: Slack/Teams/ticketing map fields per their own *.md tables ---


def test_slack_teams_ticketing_payload_mapping_AC_001():
    event = sample_event()

    slack = build_slack_payload(event)
    assert slack["channel"] == event.route
    assert slack["header"] == event.title
    assert any(b["text"] == event.summary for b in slack["blocks"])
    assert slack["dedupe_key"] == event.dedupe_key

    teams = build_teams_payload(event)
    assert teams["route"] == event.route
    assert teams["card_title"] == event.title
    assert teams["card_summary"] == event.summary
    assert teams["card_body"] == event.body_markdown

    ticket = build_ticketing_payload(event)
    assert ticket["project"] == event.route
    assert ticket["summary"] == event.title
    assert ticket["priority"] == event.severity
    assert ticket["assignee"] == event.owner
    assert ticket["dedupe_key"] == event.dedupe_key


# --- AC-002: PagerDuty/Opsgenie only routes high/critical by default ---


def test_pagerduty_severity_gate_AC_002():
    warning_event = sample_event(severity="warning")
    with pytest.raises(ValueError, match="high.*critical|only routes"):
        build_pagerduty_payload(warning_event)
    payload = build_pagerduty_payload(warning_event, allow_all_severities=True)
    assert payload["urgency"] == "warning"

    critical_event = sample_event(severity="critical")
    payload2 = build_pagerduty_payload(critical_event)
    assert payload2["urgency"] == "critical"


# --- AC-003: SMS/push only routes critical by default ---


def test_sms_push_severity_gate_AC_003():
    high_event = sample_event(severity="high")
    with pytest.raises(ValueError, match="critical"):
        build_sms_push_payload(high_event)
    payload = build_sms_push_payload(high_event, allow_all_severities=True)
    assert payload["urgency"] == "high"

    critical_event = sample_event(severity="critical")
    payload2 = build_sms_push_payload(critical_event)
    assert payload2["urgency"] == "critical"


# --- AC-004: SMS/push truncates oversized title/body with a visible marker ---


def test_sms_push_truncation_AC_004():
    event = sample_event(severity="critical", title="T" * 100, summary="S" * 300)
    payload = build_sms_push_payload(event)
    assert len(payload["title"]) <= TITLE_MAX_LEN
    assert len(payload["body"]) <= BODY_MAX_LEN
    assert payload["title"].endswith("…")
    assert payload["body"].endswith("…")

    short_event = sample_event(severity="critical", title="short", summary="also short")
    short_payload = build_sms_push_payload(short_event)
    assert short_payload["title"] == "short"
    assert short_payload["body"] == "also short"


# --- AC-005: all five new providers default to dry_run, no transport call ---


def test_new_providers_dry_run_default_AC_005():
    event = sample_event(severity="critical")
    for deliver, provider in (
        (deliver_slack, "slack"),
        (deliver_teams, "teams"),
        (deliver_ticketing, "ticketing"),
        (deliver_pagerduty, "pagerduty_opsgenie"),
        (deliver_sms_push, "sms_push"),
    ):
        result = deliver(event)
        assert result.dry_run is True
        assert result.status == "skipped"
        assert result.provider == provider


# --- AC-006: transport injection works for all five new providers ---


def test_new_providers_transport_injection_AC_006():
    event = sample_event(severity="critical")
    calls = []

    def fake_transport(payload):
        calls.append(payload)
        return {"provider_message_id": "msg-xyz"}

    for deliver in (deliver_slack, deliver_teams, deliver_ticketing, deliver_pagerduty, deliver_sms_push):
        result = deliver(event, transport=fake_transport, dry_run=False)
        assert result.status == "delivered"
        assert result.provider_message_id == "msg-xyz"
    assert len(calls) == 5

    with pytest.raises(ValueError, match="transport is required"):
        deliver_slack(event, dry_run=False)


# --- AC-007: redaction applies across the new providers ---


def test_new_providers_redaction_AC_007():
    body = "Positions detail: AAPL 10000 shares"
    event = sample_event(
        severity="critical",
        body_markdown=body,
        privacy=Privacy(redaction_level="strict"),
    )
    assert body not in build_slack_payload(event)["blocks"][1]["text"]
    assert body not in build_teams_payload(event)["card_body"]
    assert body not in build_ticketing_payload(event)["description"]
    assert body not in build_pagerduty_payload(event)["description"]


# --- AC-008: a credential-shaped value never appears verbatim ---


def test_new_providers_secret_guard_AC_008():
    secret = "api_key=sk_live_abcdef123456"
    event = sample_event(severity="critical", body_markdown=f"Rotate this: {secret}")

    assert secret not in str(build_slack_payload(event))
    assert secret not in str(build_teams_payload(event))
    assert secret not in str(build_ticketing_payload(event))
    assert secret not in str(build_pagerduty_payload(event))

    with pytest.raises(ValueError, match="credential-shaped"):
        build_slack_payload(sample_event(severity="critical", title=f"Leaked: {secret}"))
