# Spec: Alert Delivery Executable Providers (Email, Webhook)

- **ID:** 0032-alert-delivery-providers
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-08-10

## Problem & Context

`adapters/alert_delivery/` documents a channel-neutral delivery contract
(`adapter_contract.md`) and seven provider profiles (email, Slack, Teams,
webhook, PagerDuty/Opsgenie, ticketing, SMS/push) — but every one of them
is documentation only. `agents/alerts/alert_router/` can produce a
`RoutedAlert`, but nothing in the SDK turns a delivery event into the
actual, provider-shaped payload the contract describes, the way
`adapters/dashboard_render/` (specs `0017`/`0018`) turns a rendered
dashboard payload into a real file. This spec ships the first two
executable providers, in the order `adapters/alert_delivery/README.md`'s
own "Recommended Starting Set" already calls for: **email** (default
delivery, nightly draft packs) and **webhook** (the universal integration
fallback).

Alert delivery is a different shape of "executable" than dashboard
rendering: a dashboard provider's whole job is done once it writes a
local file, but an alert provider's contract also includes an actual
network send to an external system with a real credential. This SDK is a
scaffold copied into other repos — it does not, and should not, own an
adopter's SMTP/webhook credentials or network client. So the honest scope
here is the same boundary already drawn for credentials
(`agents/secrets_management/credential_access` resolves a `credential_ref`
at runtime, the SDK never holds the value) and for the model plugin
contract (spec `0026`, dispatch is deferred to a concrete invocation
target): this slice makes the **payload construction, validation, and
redaction deterministic and testable**, and exposes an explicit,
injectable transport hook for the actual send — defaulting to `dry_run`,
which never performs I/O.

## Goals

- Add `src/quantsmith/adapters/alert_delivery/`: a `result.py` (delivery
  result type, checksum-style evidence, a `contains_secret` guard,
  mirroring `adapters/dashboard_render/result.py`'s shape), `email.py`, and
  `webhook.py`.
- Each provider validates an `AlertDeliveryEvent` (a dataclass mirroring
  `adapter_contract.md`'s Input schema) against the contract's required
  fields, builds the exact provider-shaped payload per `email.md`'s /
  `webhook.md`'s own Payload Mapping tables, and applies redaction per
  `privacy.redaction_level`.
- Support `dry_run` (default true): return the constructed payload and a
  `DeliveryResult` with no network call. When `dry_run=False`, call an
  injected `transport` callable (the adopter's own send function) rather
  than performing I/O inside this SDK.
- Classify failures as retryable or terminal per `adapter_contract.md`'s
  Failure Handling section.
- Guarantee no credential or secret-shaped value ever appears in a
  constructed payload or `DeliveryResult`.
- Update `adapters/alert_delivery/README.md`, `email.md`, and `webhook.md`
  to point at the new executable providers, matching how
  `adapters/dashboard_render/README.md` documents its shipped providers.

## Non-Goals

- No actual network transport code (`smtplib`, an HTTP client call, a
  Slack/Teams/PagerDuty SDK) inside this SDK — that is the adopter's
  `transport` callable, supplied at the point of use, exactly as
  `credential_access` resolves a credential at the point of use rather
  than the SDK holding one.
- No Slack, Teams, PagerDuty/Opsgenie, ticketing, or SMS/push providers in
  this slice — `adapters/alert_delivery/README.md`'s own Recommended
  Starting Set puts those after email and webhook; they are the natural
  next slice, not this one.
- No change to `adapters/alert_delivery/adapter_contract.md`'s schema, or
  to `agents/alerts/*`'s existing contracts — this slice is additive
  runtime beneath an unchanged contract.
- No deduplication, suppression, cooldown, or escalation logic — that is
  `alert_router`'s job (`src/quantsmith/pipelines/alerting.py`, spec
  `0020`); a provider assumes it is being called with an already-routed,
  already-deduplicated event.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The system shall provide an `AlertDeliveryEvent` dataclass mirroring `adapter_contract.md`'s Input schema, with validation of required fields. | must |
| REQ-002 | The system shall provide an email provider that maps an `AlertDeliveryEvent` to an email payload (to/cc, subject, body) per `email.md`'s Payload Mapping. | must |
| REQ-003 | The system shall provide a webhook provider that maps an `AlertDeliveryEvent` to a generic HTTP JSON payload per `webhook.md`'s Payload Mapping. | must |
| REQ-004 | Both providers shall default to `dry_run=True` (construct and return the payload, no I/O) and, when `dry_run=False`, invoke an injected `transport` callable rather than performing a network call themselves. | must |
| REQ-005 | Both providers shall redact fields per `privacy.redaction_level` and shall never place a credential or secret-shaped value in the constructed payload or result. | must |
| REQ-006 | Both providers shall classify a transport failure as retryable or terminal per `adapter_contract.md`'s Failure Handling categories. | must |
| REQ-007 | `adapters/alert_delivery/README.md`, `email.md`, and `webhook.md` shall document the executable providers and their location. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Determinism | The same `AlertDeliveryEvent` and redaction level yield the same constructed payload on every call. |
| NFR-002 | Dependency isolation | Both providers are standard-library only; no network or provider-SDK dependency is added to this SDK. |
| NFR-003 | No secrets | Generated payloads and results contain no embedded credential value; a `contains_secret`-style check (reusing the pattern from `adapters/dashboard_render/result.py`) guards this. |
| NFR-004 | Repository hygiene | `spec`, `agent-catalog`, `docs-link`, `spec-index` gates and the full pytest suite pass. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given an `AlertDeliveryEvent` missing a required contract field, when a provider validates it, then it raises with the specific missing field named. | REQ-001 |
| AC-002 | Given a valid event, when the email provider runs with `dry_run=True` (the default), then it returns the constructed email payload and a `DeliveryResult` with `status="skipped"` (per the contract's dry-run behavior) and no transport call occurs. | REQ-002, REQ-004 |
| AC-003 | Given a valid event, when the webhook provider runs with `dry_run=True`, then it returns the constructed JSON payload and a `DeliveryResult` with `status="skipped"` and no transport call occurs. | REQ-003, REQ-004 |
| AC-004 | Given a valid event and an injected `transport` callable, when a provider runs with `dry_run=False`, then the provider calls `transport` with the constructed payload (never performing I/O itself) and returns a `DeliveryResult` reflecting the callable's outcome. | REQ-004 |
| AC-005 | Given an event with `privacy.redaction_level` set, when a provider constructs the payload, then the specified fields are redacted in the output. | REQ-005 |
| AC-006 | Given an event whose fields contain a credential-shaped value (e.g. an API-key pattern), when a provider constructs the payload, then the check flags it and the value never appears verbatim in the returned payload/result. | REQ-005, NFR-003 |
| AC-007 | Given a `transport` callable that raises a designated retryable vs. terminal error, when a provider handles the failure, then the resulting `DeliveryResult.retryable` matches the failure category from `adapter_contract.md`. | REQ-006 |
| AC-008 | Given the same event and redaction level, when a provider constructs the payload twice, then the two payloads are identical. | NFR-001 |
| AC-009 | Given `adapters/alert_delivery/README.md`, `email.md`, and `webhook.md`, when inspected, then each documents the executable provider and its module path. | REQ-007 |
| AC-010 | Given the full gate suite, when run, then `spec`, `agent-catalog`, `docs-link`, `spec-index` all pass. | NFR-004 |

## Data & Dependencies

- Input: `AlertDeliveryEvent`, constructed by whatever calls the provider
  (typically `alert_router`'s or `incident_notification`'s output, enriched
  to the full contract shape — that enrichment is the caller's job, not
  this slice's).
- Contract: `adapters/alert_delivery/adapter_contract.md`, `email.md`,
  `webhook.md`.
- No optional dependency; both providers are standard-library only (no
  `smtplib` connection is opened, no HTTP client is called — those live in
  the adopter's injected `transport`).
- No private data or credentials are written to this repository.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | An adopter mistakes the deterministic payload builder for a working send path and expects a real message to be delivered with no `transport` wired up. | An alert is silently never delivered while the adopter believes it was. | `dry_run=True` is the explicit default and every provider function's docstring and the wired README sections state plainly that a real send requires supplying `transport`; `DeliveryResult.status="skipped"` (not `"delivered"`) makes a dry run's non-delivery visible in the return value itself, not just in documentation. |
| RISK-002 | A credential or secret-shaped value passed into an `AlertDeliveryEvent` field (e.g. accidentally put in `body_markdown`) leaks into a constructed payload. | A secret is exposed in a log or a returned payload. | Reuses the `contains_secret` pattern already proven in `adapters/dashboard_render/result.py`; every constructed payload is checked before being returned (AC-006). |
| RISK-003 | Redaction rules are inconsistently applied between the email and webhook providers, one under-redacting relative to the other. | The same event redacts differently depending on channel, confusing an operator. | Both providers share the same `result.py` redaction helper rather than each reimplementing redaction independently. |

## Assumptions & Open Questions

- Assumption: email and webhook are the right first two providers,
  matching `adapters/alert_delivery/README.md`'s own pre-existing
  Recommended Starting Set rather than a new ordering invented for this
  spec.
- Assumption: an injectable `transport` callable is the right boundary for
  "real send," mirroring how `credential_access` and the model-plugin
  contract already defer the actual external call to the adopter.
- Open question: once Slack/Teams/ticketing/PagerDuty/SMS providers are
  built (deliberately out of scope here), should they share a common
  `transport`-injection helper module, or does each provider's payload
  shape differ enough that duplication is clearer than a shared
  abstraction? Deferred to that slice.

## Exceptions

None.
