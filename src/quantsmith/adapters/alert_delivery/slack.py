"""Slack provider -- construct and (optionally) send a Slack alert message.

Implements ``adapters/alert_delivery/slack.md``. This module never calls the Slack
API itself: it builds the exact payload the contract describes and, when
``dry_run=False``, hands it to an injected ``transport`` callable -- the adopter's
own authenticated Slack client. ``dry_run=True`` (the default) never performs I/O.
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


def build_slack_payload(event: AlertDeliveryEvent) -> Dict[str, object]:
    """Map an ``AlertDeliveryEvent`` to a Slack payload per ``slack.md``.

    Deterministic: the same event always yields the same payload.
    """
    blocks: List[Dict[str, object]] = [
        {"type": "section", "text": redact_text(event.summary, event.privacy)},
    ]
    body = redact_text(event.body_markdown, event.privacy)
    if body:
        blocks.append({"type": "section", "text": body})
    for item in event.evidence:
        blocks.append({"type": "link", "label": item.label, "uri": item.uri})
    for item in event.artifacts:
        blocks.append({"type": "link", "label": item.label, "uri": item.uri})

    payload: Dict[str, object] = {
        "channel": event.route,
        "header": event.title,
        "blocks": blocks,
        "correlation_id": event.correlation_id,
        "dedupe_key": event.dedupe_key,
    }
    if event.acknowledgement.acknowledgement_uri:
        payload["acknowledgement_uri"] = event.acknowledgement.acknowledgement_uri
    assert_no_secret(payload)
    return payload


def deliver_slack(
    event: AlertDeliveryEvent,
    transport: Optional[Transport] = None,
    dry_run: bool = True,
) -> DeliveryResult:
    """Build the Slack payload and, unless ``dry_run``, hand it to ``transport``.

    ``dry_run=True`` (default): construct and return the payload with no I/O;
    ``DeliveryResult.status`` is ``"skipped"``. ``dry_run=False`` requires a
    ``transport`` callable (the adopter's own Slack client); this provider never
    calls the Slack API itself.
    """
    payload = build_slack_payload(event)
    return deliver_via("slack", payload, event, transport, dry_run)
