"""Executable alert-delivery providers (specs 0032, 0037).

Construct and, given an injected transport, send an alert delivery event: email,
webhook, Slack, Teams, ticketing, PagerDuty/Opsgenie, and SMS/push, per
``adapters/alert_delivery/adapter_contract.md``. Standard-library only;
``dry_run=True`` (the default) never performs I/O. This completes the adapter's
own Recommended Starting Set end to end.
"""

from __future__ import annotations

from .email import build_email_payload, deliver_email
from .pagerduty_opsgenie import build_pagerduty_payload, deliver_pagerduty
from .result import (
    AlertDeliveryEvent,
    Acknowledgement,
    DeliveryResult,
    EvidenceItem,
    Privacy,
    Transport,
    TransportError,
    assert_no_secret,
    contains_secret,
    deliver_via,
    now_utc_iso,
    redact_text,
)
from .slack import build_slack_payload, deliver_slack
from .sms_push import build_sms_push_payload, deliver_sms_push
from .teams import build_teams_payload, deliver_teams
from .ticketing import build_ticketing_payload, deliver_ticketing
from .webhook import build_webhook_payload, deliver_webhook

__all__ = [
    "Acknowledgement",
    "AlertDeliveryEvent",
    "DeliveryResult",
    "EvidenceItem",
    "Privacy",
    "Transport",
    "TransportError",
    "assert_no_secret",
    "build_email_payload",
    "build_pagerduty_payload",
    "build_slack_payload",
    "build_sms_push_payload",
    "build_teams_payload",
    "build_ticketing_payload",
    "build_webhook_payload",
    "contains_secret",
    "deliver_email",
    "deliver_pagerduty",
    "deliver_slack",
    "deliver_sms_push",
    "deliver_teams",
    "deliver_ticketing",
    "deliver_via",
    "deliver_webhook",
    "now_utc_iso",
    "redact_text",
]
