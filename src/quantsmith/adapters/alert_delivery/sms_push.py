"""SMS/push provider -- construct and (optionally) send a short critical-alert message.

Implements ``adapters/alert_delivery/sms_push.md``. This module never calls an
SMS/push gateway itself: it builds the exact payload the contract describes and,
when ``dry_run=False``, hands it to an injected ``transport`` callable -- the
adopter's own authenticated gateway client. ``dry_run=True`` (the default) never
performs I/O.

Per ``sms_push.md``'s own delivery rules: routing is restricted to
``severity == "critical"`` by default (pass ``allow_all_severities=True`` to
override), and the title/body are truncated to a short-message length cap rather
than sent oversized -- both enforced here, not left as prose a caller could
ignore.
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

_ROUTABLE_SEVERITIES = ("critical",)
TITLE_MAX_LEN = 40
BODY_MAX_LEN = 160
_TRUNCATION_MARKER = "…"  # visible ellipsis, never a silent cut


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - len(_TRUNCATION_MARKER)].rstrip() + _TRUNCATION_MARKER


def build_sms_push_payload(
    event: AlertDeliveryEvent,
    allow_all_severities: bool = False,
) -> Dict[str, object]:
    """Map an ``AlertDeliveryEvent`` to an SMS/push payload.

    Raises unless ``event.severity == "critical"`` or ``allow_all_severities=True``
    -- enforcing ``sms_push.md``'s own "restrict to critical" rule structurally.
    Title/body are truncated to ``TITLE_MAX_LEN``/``BODY_MAX_LEN`` with a visible
    marker rather than sent oversized. Deterministic.
    """
    if not allow_all_severities and event.severity not in _ROUTABLE_SEVERITIES:
        raise ValueError(
            f"sms_push only routes {_ROUTABLE_SEVERITIES} alerts by default "
            f"(got severity='{event.severity}'); pass allow_all_severities=True to override"
        )

    title = _truncate(redact_text(event.title, event.privacy), TITLE_MAX_LEN)
    body = _truncate(redact_text(event.summary, event.privacy), BODY_MAX_LEN)

    payload: Dict[str, object] = {
        "route": event.route,
        "urgency": event.severity,
        "title": title,
        "body": body,
        "correlation_id": event.correlation_id,
    }
    if event.acknowledgement.acknowledgement_uri:
        payload["acknowledgement_uri"] = event.acknowledgement.acknowledgement_uri
    assert_no_secret(payload)
    return payload


def deliver_sms_push(
    event: AlertDeliveryEvent,
    transport: Optional[Transport] = None,
    dry_run: bool = True,
    allow_all_severities: bool = False,
) -> DeliveryResult:
    """Build the SMS/push payload and, unless ``dry_run``, send it.

    ``dry_run=True`` (default): construct and return the payload with no I/O;
    ``DeliveryResult.status`` is ``"skipped"``. ``dry_run=False`` requires a
    ``transport`` callable (the adopter's own gateway client); this provider
    never calls an SMS/push gateway itself.
    """
    payload = build_sms_push_payload(event, allow_all_severities=allow_all_severities)
    return deliver_via("sms_push", payload, event, transport, dry_run)
