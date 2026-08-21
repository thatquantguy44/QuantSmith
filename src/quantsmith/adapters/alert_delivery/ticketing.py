"""Ticketing provider -- construct and (optionally) create/update a work-tracking ticket.

Implements ``adapters/alert_delivery/ticketing.md``. This module never calls a
ticketing API itself: it builds the exact payload the contract describes and,
when ``dry_run=False``, hands it to an injected ``transport`` callable -- the
adopter's own authenticated ticketing client, which owns the create-vs-update
decision (via ``dedupe_key``) since this SDK holds no provider-side ticket state.
``dry_run=True`` (the default) never performs I/O.
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


def build_ticketing_payload(event: AlertDeliveryEvent) -> Dict[str, object]:
    """Map an ``AlertDeliveryEvent`` to a ticket payload per ``ticketing.md``.

    Deterministic: the same event always yields the same payload. Carries
    ``dedupe_key`` as the ticket's external ID so an adopter's ``transport`` can
    decide whether to update an existing open ticket or create a new one.
    """
    links: List[Dict[str, str]] = [
        {"label": item.label, "uri": item.uri} for item in event.evidence
    ]
    links.extend({"label": item.label, "uri": item.uri} for item in event.artifacts)

    payload: Dict[str, object] = {
        "project": event.route,
        "summary": event.title,
        "description": redact_text(event.body_markdown or event.summary, event.privacy),
        "priority": event.severity,
        "assignee": event.owner,
        "links": links,
        "runbook_uri": event.runbook_uri,
        "external_id": event.correlation_id,
        "dedupe_key": event.dedupe_key,
    }
    assert_no_secret(payload)
    return payload


def deliver_ticketing(
    event: AlertDeliveryEvent,
    transport: Optional[Transport] = None,
    dry_run: bool = True,
) -> DeliveryResult:
    """Build the ticket payload and, unless ``dry_run``, hand it to ``transport``.

    ``dry_run=True`` (default): construct and return the payload with no I/O;
    ``DeliveryResult.status`` is ``"skipped"``. ``dry_run=False`` requires a
    ``transport`` callable (the adopter's own ticketing client); this provider
    never calls a ticketing API itself.
    """
    payload = build_ticketing_payload(event)
    return deliver_via("ticketing", payload, event, transport, dry_run)
