"""PagerDuty/Opsgenie provider -- construct and (optionally) send a paging event.

Implements ``adapters/alert_delivery/pagerduty_opsgenie.md``. This module never
calls the PagerDuty/Opsgenie API itself: it builds the exact payload the contract
describes and, when ``dry_run=False``, hands it to an injected ``transport``
callable -- the adopter's own authenticated incident-management client.
``dry_run=True`` (the default) never performs I/O.

Per ``pagerduty_opsgenie.md``'s own delivery rule ("only route high and critical
alerts unless a workflow explicitly opts in"), routing is restricted to
``severity in {"high", "critical"}`` by default -- enforced here, not left as
prose a caller could ignore. Pass ``allow_all_severities=True`` to override.
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

_ROUTABLE_SEVERITIES = ("high", "critical")

_EVENT_ACTION = {
    "triggered": "trigger",
    "updated": "trigger",
    "acknowledged": "acknowledge",
    "resolved": "resolve",
    "closed": "resolve",
}


def build_pagerduty_payload(
    event: AlertDeliveryEvent,
    allow_all_severities: bool = False,
) -> Dict[str, object]:
    """Map an ``AlertDeliveryEvent`` to a PagerDuty/Opsgenie payload.

    Raises unless ``event.severity`` is ``"high"``/``"critical"`` or
    ``allow_all_severities=True`` -- enforcing ``pagerduty_opsgenie.md``'s own
    "only route high and critical" rule structurally. Deterministic.
    """
    if not allow_all_severities and event.severity not in _ROUTABLE_SEVERITIES:
        raise ValueError(
            f"pagerduty_opsgenie only routes {_ROUTABLE_SEVERITIES} alerts by default "
            f"(got severity='{event.severity}'); pass allow_all_severities=True to override"
        )

    links: List[Dict[str, str]] = [
        {"label": item.label, "uri": item.uri} for item in event.evidence
    ]
    links.extend({"label": item.label, "uri": item.uri} for item in event.artifacts)

    payload: Dict[str, object] = {
        "dedupe_key": event.dedupe_key,
        "urgency": event.severity,
        "title": event.title,
        "description": redact_text(event.body_markdown or event.summary, event.privacy),
        "event_action": _EVENT_ACTION.get(event.status, "trigger"),
        "links": links,
        "runbook_uri": event.runbook_uri,
        "correlation_id": event.correlation_id,
    }
    assert_no_secret(payload)
    return payload


def deliver_pagerduty(
    event: AlertDeliveryEvent,
    transport: Optional[Transport] = None,
    dry_run: bool = True,
    allow_all_severities: bool = False,
) -> DeliveryResult:
    """Build the PagerDuty/Opsgenie payload and, unless ``dry_run``, send it.

    ``dry_run=True`` (default): construct and return the payload with no I/O;
    ``DeliveryResult.status`` is ``"skipped"``. ``dry_run=False`` requires a
    ``transport`` callable (the adopter's own incident-management client); this
    provider never calls the PagerDuty/Opsgenie API itself.
    """
    payload = build_pagerduty_payload(event, allow_all_severities=allow_all_severities)
    return deliver_via("pagerduty_opsgenie", payload, event, transport, dry_run)
