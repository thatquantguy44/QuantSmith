"""Shared types for alert-delivery providers.

``AlertDeliveryEvent`` and ``DeliveryResult`` are direct transcriptions of
``adapters/alert_delivery/adapter_contract.md``'s Input/Output YAML into a Python
shape -- no new schema, just giving the already-documented contract a type.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Tuple


@dataclass(frozen=True)
class EvidenceItem:
    label: str
    uri: str


@dataclass(frozen=True)
class Acknowledgement:
    required: bool = False
    acknowledgement_uri: Optional[str] = None


@dataclass(frozen=True)
class Privacy:
    contains_pii: bool = False
    contains_mnpi: bool = False
    contains_restricted_positions: bool = False
    redaction_level: str = "none"   # none | standard | strict

    def __post_init__(self) -> None:
        if self.redaction_level not in ("none", "standard", "strict"):
            raise ValueError(f"unknown redaction_level '{self.redaction_level}'")


@dataclass(frozen=True)
class AlertDeliveryEvent:
    """The contract's channel-neutral Input payload."""

    event_id: str
    workflow_id: str
    source: str
    severity: str            # info | warning | high | critical
    status: str               # triggered | updated | acknowledged | resolved | closed
    owner: str
    route: str
    title: str
    summary: str
    correlation_id: str
    dedupe_key: str
    run_id: str = ""
    environment: str = "dev"   # dev | staging | prod
    body_markdown: str = ""
    observed_at_utc: str = ""
    as_of_utc: str = ""
    cooldown_seconds: int = 0
    evidence: Tuple[EvidenceItem, ...] = field(default_factory=tuple)
    artifacts: Tuple[EvidenceItem, ...] = field(default_factory=tuple)
    runbook_uri: Optional[str] = None
    dashboard_uri: Optional[str] = None
    acknowledgement: Acknowledgement = field(default_factory=Acknowledgement)
    privacy: Privacy = field(default_factory=Privacy)

    REQUIRED_FIELDS = (
        "event_id", "workflow_id", "source", "severity", "status", "owner",
        "route", "title", "summary", "correlation_id", "dedupe_key",
    )

    def __post_init__(self) -> None:
        for name in self.REQUIRED_FIELDS:
            if not getattr(self, name):
                raise ValueError(f"AlertDeliveryEvent missing required field '{name}'")


@dataclass(frozen=True)
class DeliveryResult:
    """The contract's channel-neutral Output payload."""

    adapter_name: str
    provider: str                          # "email" | "webhook"
    status: str                            # delivered | skipped | failed
    correlation_id: str
    dedupe_key: str
    timestamp_utc: str
    retryable: bool = False
    provider_message_id: Optional[str] = None
    provider_thread_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message_redacted: Optional[str] = None
    acknowledgement_uri: Optional[str] = None
    evidence_uri: Optional[str] = None
    dry_run: bool = True


# Credential-shaped token patterns -- conservative, matches assignments, bearer
# headers, and key material, not the mere word "secret"/"password" in prose.
# Mirrors adapters/dashboard_render/result.py's contains_secret heuristic.
_SECRET_NEEDLES = (
    "api_key", "apikey", "secret_key", "client_secret", "aws_secret",
    "authorization: bearer ", "password=", "passwd=", "-----begin ",
)


def contains_secret(text: str) -> bool:
    """Conservative check for a credential-shaped value in free text."""
    if not text:
        return False
    lowered = text.lower()
    return any(n in lowered for n in _SECRET_NEEDLES)


def assert_no_secret(payload: object) -> None:
    """Recursively scan a constructed payload; raise if any string looks credential-shaped."""
    if isinstance(payload, str):
        if contains_secret(payload):
            raise ValueError("constructed payload contains a credential-shaped value")
    elif isinstance(payload, dict):
        for value in payload.values():
            assert_no_secret(value)
    elif isinstance(payload, (list, tuple)):
        for value in payload:
            assert_no_secret(value)


_STRICT_PLACEHOLDER = "[REDACTED -- strict privacy policy; see runbook/evidence links]"
_SECRET_PLACEHOLDER = "[REDACTED -- possible credential-shaped content]"


def redact_text(text: str, privacy: Privacy) -> str:
    """Redact free text per ``privacy.redaction_level``.

    A credential-shaped value is always stripped regardless of level (the
    contract's "never include credentials ... in a payload" requirement is
    unconditional). Beyond that floor:

    - ``none``: no further redaction.
    - ``standard``: redacted only when a privacy flag (PII/MNPI/restricted
      positions) is set true for this event.
    - ``strict``: always redacted, independent of the privacy flags.
    """
    if not text:
        return text
    if contains_secret(text):
        return _SECRET_PLACEHOLDER
    if privacy.redaction_level == "strict":
        return _STRICT_PLACEHOLDER
    if privacy.redaction_level == "standard" and (
        privacy.contains_pii or privacy.contains_mnpi or privacy.contains_restricted_positions
    ):
        return _STRICT_PLACEHOLDER
    return text


class TransportError(Exception):
    """Raised by an injected ``transport`` callable; ``retryable`` classifies it."""

    def __init__(self, message: str, retryable: bool, error_code: Optional[str] = None) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.error_code = error_code


Transport = Callable[[Dict[str, object]], Dict[str, object]]


def now_utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def deliver_via(
    provider: str,
    payload: Dict[str, object],
    event: AlertDeliveryEvent,
    transport: Optional[Transport],
    dry_run: bool,
) -> DeliveryResult:
    """Shared dry-run/transport/``DeliveryResult`` wrapper for every provider.

    ``dry_run=True`` (default): no I/O; ``status="skipped"``. ``dry_run=False``
    requires ``transport`` (the adopter's own send function) and never performs
    the network call itself -- this function only classifies the outcome.
    """
    timestamp = now_utc_iso()

    if dry_run:
        return DeliveryResult(
            adapter_name="alert_delivery",
            provider=provider,
            status="skipped",
            correlation_id=event.correlation_id,
            dedupe_key=event.dedupe_key,
            timestamp_utc=timestamp,
            dry_run=True,
        )

    if transport is None:
        raise ValueError("transport is required when dry_run=False")

    try:
        outcome = transport(payload)
    except TransportError as exc:
        return DeliveryResult(
            adapter_name="alert_delivery",
            provider=provider,
            status="failed",
            correlation_id=event.correlation_id,
            dedupe_key=event.dedupe_key,
            timestamp_utc=timestamp,
            retryable=exc.retryable,
            error_code=exc.error_code,
            error_message_redacted=redact_text(str(exc), event.privacy),
            dry_run=False,
        )

    return DeliveryResult(
        adapter_name="alert_delivery",
        provider=provider,
        status="delivered",
        correlation_id=event.correlation_id,
        dedupe_key=event.dedupe_key,
        timestamp_utc=timestamp,
        provider_message_id=str(outcome.get("provider_message_id")) if outcome.get("provider_message_id") else None,
        dry_run=False,
    )
