"""Webhook provider -- construct and (optionally) send a generic HTTP alert payload.

Implements ``adapters/alert_delivery/webhook.md``. This module never makes an HTTP
call itself: it builds the exact channel-neutral JSON payload the contract
describes (plus ``provider_context``) and, when ``dry_run=False``, hands it to an
injected ``transport`` callable -- the adopter's own HTTP client, signing, retry,
and timeout policy. ``dry_run=True`` (the default) never performs I/O.
"""

from __future__ import annotations

from typing import Dict, Optional

from .result import (
    AlertDeliveryEvent,
    DeliveryResult,
    Transport,
    assert_no_secret,
    deliver_via,
    redact_text,
)


def build_webhook_payload(event: AlertDeliveryEvent) -> Dict[str, object]:
    """Map an ``AlertDeliveryEvent`` to a webhook JSON payload per ``webhook.md``.

    Preserves the channel-neutral contract as JSON, with provider-specific
    metadata under ``provider_context``. Deterministic: the same event always
    yields the same payload.
    """
    payload: Dict[str, object] = {
        "event_id": event.event_id,
        "workflow_id": event.workflow_id,
        "run_id": event.run_id,
        "source": event.source,
        "environment": event.environment,
        "severity": event.severity,
        "status": event.status,
        "owner": event.owner,
        "title": event.title,
        "summary": redact_text(event.summary, event.privacy),
        "body_markdown": redact_text(event.body_markdown, event.privacy),
        "observed_at_utc": event.observed_at_utc,
        "as_of_utc": event.as_of_utc,
        "correlation_id": event.correlation_id,
        "dedupe_key": event.dedupe_key,
        "evidence": [{"label": e.label, "uri": e.uri} for e in event.evidence],
        "artifacts": [{"label": a.label, "uri": a.uri} for a in event.artifacts],
        "runbook_uri": event.runbook_uri,
        "dashboard_uri": event.dashboard_uri,
        "provider_context": {
            "method": "POST",
            "content_type": "application/json",
            "signature_header": None,
        },
    }
    assert_no_secret(payload)
    return payload


def deliver_webhook(
    event: AlertDeliveryEvent,
    transport: Optional[Transport] = None,
    dry_run: bool = True,
) -> DeliveryResult:
    """Build the webhook payload and, unless ``dry_run``, hand it to ``transport``.

    ``dry_run=True`` (default): construct and return the payload with no I/O;
    ``DeliveryResult.status`` is ``"skipped"``. ``dry_run=False`` requires a
    ``transport`` callable (the adopter's own HTTP client); this provider never
    performs the network call itself.
    """
    payload = build_webhook_payload(event)
    return deliver_via("webhook", payload, event, transport, dry_run)
