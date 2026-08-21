"""Teams provider -- construct and (optionally) send a Microsoft Teams alert card.

Implements ``adapters/alert_delivery/teams.md``. This module never calls Teams/
Graph itself: it builds the exact adaptive-card payload the contract describes
and, when ``dry_run=False``, hands it to an injected ``transport`` callable --
the adopter's own authenticated Teams client. ``dry_run=True`` (the default)
never performs I/O.
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


def build_teams_payload(event: AlertDeliveryEvent) -> Dict[str, object]:
    """Map an ``AlertDeliveryEvent`` to a Teams adaptive-card payload per ``teams.md``.

    Deterministic: the same event always yields the same payload.
    """
    actions: List[Dict[str, object]] = [
        {"label": item.label, "uri": item.uri} for item in event.evidence
    ]
    actions.extend({"label": item.label, "uri": item.uri} for item in event.artifacts)
    if event.acknowledgement.acknowledgement_uri:
        actions.append({"label": "Acknowledge", "uri": event.acknowledgement.acknowledgement_uri})

    payload: Dict[str, object] = {
        "route": event.route,
        "card_title": event.title,
        "card_summary": redact_text(event.summary, event.privacy),
        "card_body": redact_text(event.body_markdown, event.privacy),
        "actions": actions,
        "correlation_id": event.correlation_id,
        "dedupe_key": event.dedupe_key,
        "footer": f"{event.owner} | {event.severity} | {event.as_of_utc}",
    }
    assert_no_secret(payload)
    return payload


def deliver_teams(
    event: AlertDeliveryEvent,
    transport: Optional[Transport] = None,
    dry_run: bool = True,
) -> DeliveryResult:
    """Build the Teams payload and, unless ``dry_run``, hand it to ``transport``.

    ``dry_run=True`` (default): construct and return the payload with no I/O;
    ``DeliveryResult.status`` is ``"skipped"``. ``dry_run=False`` requires a
    ``transport`` callable (the adopter's own Teams client); this provider never
    calls Teams/Graph itself.
    """
    payload = build_teams_payload(event)
    return deliver_via("teams", payload, event, transport, dry_run)
