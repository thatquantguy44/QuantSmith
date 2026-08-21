"""Email provider -- construct and (optionally) send an alert delivery email.

Implements ``adapters/alert_delivery/email.md``. This module never opens an SMTP
connection itself: it builds the exact payload the contract describes and, when
``dry_run=False``, hands it to an injected ``transport`` callable -- the adopter's
own authenticated mail client. ``dry_run=True`` (the default) never performs I/O.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .result import (
    AlertDeliveryEvent,
    DeliveryResult,
    Transport,
    assert_no_secret,
    deliver_via,
    redact_text,
)

_SUBJECT_PREFIX = "[QuantSmith Alert]"


def build_email_payload(event: AlertDeliveryEvent) -> Dict[str, object]:
    """Map an ``AlertDeliveryEvent`` to an email payload per ``email.md``.

    Deterministic: the same event always yields the same payload.
    """
    body_lines: List[str] = [
        f"Severity: {event.severity}",
        f"Owner: {event.owner}",
        f"Status: {event.status}",
    ]
    if event.as_of_utc:
        body_lines.append(f"As of: {event.as_of_utc}")
    if event.runbook_uri:
        body_lines.append(f"Runbook: {event.runbook_uri}")
    body = redact_text(event.body_markdown, event.privacy)
    if body:
        body_lines.append("")
        body_lines.append(body)
    if event.evidence:
        body_lines.append("")
        body_lines.append("Evidence:")
        body_lines.extend(f"- {e.label}: {e.uri}" for e in event.evidence)
    if event.artifacts:
        body_lines.append("")
        body_lines.append("Artifacts:")
        body_lines.extend(f"- {a.label}: {a.uri}" for a in event.artifacts)
    body_lines.append("")
    body_lines.append(f"[correlation_id: {event.correlation_id}]")

    payload: Dict[str, object] = {
        "to": event.route,
        "subject": f"{_SUBJECT_PREFIX} {event.title}",
        "preview": redact_text(event.summary, event.privacy),
        "body": "\n".join(body_lines),
        "correlation_id": event.correlation_id,
        "dedupe_key": event.dedupe_key,
    }
    assert_no_secret(payload)
    return payload


def deliver_email(
    event: AlertDeliveryEvent,
    transport: Optional[Transport] = None,
    dry_run: bool = True,
) -> DeliveryResult:
    """Build the email payload and, unless ``dry_run``, hand it to ``transport``.

    ``dry_run=True`` (default): construct and return the payload with no I/O;
    ``DeliveryResult.status`` is ``"skipped"``. ``dry_run=False`` requires a
    ``transport`` callable (the adopter's own send function); this provider never
    performs the network call itself.
    """
    payload = build_email_payload(event)
    return deliver_via("email", payload, event, transport, dry_run)
