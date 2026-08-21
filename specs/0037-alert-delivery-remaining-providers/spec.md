# Spec: Alert Delivery — Remaining Executable Providers

- **ID:** 0037-alert-delivery-remaining-providers
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-08-10

## Problem & Context

`specs/0032-alert-delivery-providers/` shipped the first two executable
providers behind `adapters/alert_delivery/` — email and webhook — per that
adapter's own pre-existing Recommended Starting Set, and left five
documented-only providers as explicit follow-ups: Slack, Teams, ticketing
(Jira/ServiceNow/Linear), PagerDuty/Opsgenie, and SMS/push. This spec
ships all five, completing the adapter's own starting set end to end.

Building five more providers on the exact `dry_run`/`transport`/
`DeliveryResult` wrapper `0032` established would mean five more copies of
the same ~20-line pattern already duplicated once between `email.py` and
`webhook.py`. This spec also **factors that wrapper into a shared helper**
(`result.py::deliver_via`) and updates `email.py`/`webhook.py` to use it —
a behavior-preserving refactor, verified by `0032`'s own existing test
suite continuing to pass unchanged, not a new capability.

Two of the five new providers have delivery rules that are more than
documentation in their source `*.md` files — `pagerduty_opsgenie.md`
states "only route `high` and `critical` alerts unless a workflow
explicitly opts in," and `sms_push.md` states "restrict to `critical`
alerts by default" and implies short-message length limits. This spec
enforces both **structurally** (a validation that raises unless
explicitly overridden, and an actual length cap that truncates) rather
than leaving them as narrative-only rules a caller could silently ignore
— the same "correct by construction over a rule stated in prose" pattern
already used for `0034`/`0035`/`0036`'s eligibility and capacity
constraints.

## Goals

- Add `src/quantsmith/adapters/alert_delivery/{slack,teams,ticketing,
  pagerduty_opsgenie,sms_push}.py`, each with a `build_*_payload` (per
  that provider's own `*.md` Payload Mapping table) and a `deliver_*`
  function, following `0032`'s `dry_run=True` default / injected-
  `transport` pattern.
- Add `result.py::deliver_via`, a shared helper for the dry-run/transport/
  `DeliveryResult` wrapper; refactor `email.py` and `webhook.py` to call
  it, with no behavior change.
- Structurally enforce `pagerduty_opsgenie`'s "high/critical only unless
  opted in" rule and `sms_push`'s "critical only unless opted in" rule via
  an `allow_all_severities` parameter that defaults to `False` and raises
  otherwise — not just documented.
- Structurally enforce a short-message length cap in `sms_push` (truncate
  with an explicit marker, never silently send an oversized payload).
- Update `adapters/alert_delivery/README.md` and each of the five
  providers' own `*.md` files to point at their executable module,
  matching how `email.md`/`webhook.md` were updated in `0032`.

## Non-Goals

- No actual network/API client code for any provider (Slack SDK, Microsoft
  Graph, Jira/ServiceNow/Linear clients, PagerDuty/Opsgenie Events API
  clients, an SMS/push gateway) — the same boundary `0032` already drew:
  this SDK builds the deterministic, validated, redacted payload and
  exposes an injectable `transport` seam; the real send is the adopter's
  own authenticated client.
- No ticketing create-vs-update decision logic. `ticketing.md` states an
  existing ticket sharing a `dedupe_key` should be updated rather than
  duplicated, but that decision requires querying provider state this SDK
  doesn't hold; the payload carries `dedupe_key` so the adopter's
  `transport` can make that call, matching how `alert_router` (spec
  `0020`) already owns deduplication logic upstream of delivery.
- No change to `adapter_contract.md`'s schema, `agents/alerts/*`'s
  contracts, or `email.py`/`webhook.py`'s external behavior — the
  `deliver_via` refactor is internal deduplication only.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The system shall provide `slack`, `teams`, and `ticketing` providers, each mapping an `AlertDeliveryEvent` to that provider's payload per its own `*.md` Payload Mapping table. | must |
| REQ-002 | The system shall provide a `pagerduty_opsgenie` provider that, by default, raises unless the event's severity is `high` or `critical`; an `allow_all_severities=True` parameter shall override this. | must |
| REQ-003 | The system shall provide an `sms_push` provider that, by default, raises unless the event's severity is `critical` (same override parameter), and truncates the title/body to a stated short-message length cap rather than sending an oversized payload. | must |
| REQ-004 | All five providers shall default to `dry_run=True` (no I/O) and, when `dry_run=False`, invoke an injected `transport` callable rather than performing a network call themselves, matching `0032`'s pattern. | must |
| REQ-005 | All five providers shall redact per `privacy.redaction_level` and guard against a credential-shaped value ever appearing in a constructed payload, reusing `result.py`'s existing `redact_text`/`assert_no_secret`. | must |
| REQ-006 | `result.py` shall provide a shared `deliver_via` helper for the dry-run/transport/`DeliveryResult` wrapper; `email.py` and `webhook.py` shall be refactored to use it with no behavior change, verified by `0032`'s existing tests passing unchanged. | must |
| REQ-007 | `adapters/alert_delivery/README.md` and each of the five providers' `*.md` files shall document the executable module. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Determinism | The same event and parameters yield the same constructed payload on every call. |
| NFR-002 | Dependency isolation | All five providers are standard-library only; no network or provider-SDK dependency is added. |
| NFR-003 | No secrets | Every constructed payload is guarded by `assert_no_secret` before being returned. |
| NFR-004 | Repository hygiene | `spec`, `agent-catalog`, `docs-link`, `spec-index` gates and the full pytest suite (including `0032`'s existing tests, unchanged) pass. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a valid event, when each of `build_slack_payload`/`build_teams_payload`/`build_ticketing_payload` runs, then the returned payload maps the fields per that provider's own `*.md` table. | REQ-001 |
| AC-002 | Given an event with `severity="warning"`, when `build_pagerduty_payload` runs with default parameters, then it raises; when run with `allow_all_severities=True`, then it succeeds. | REQ-002 |
| AC-003 | Given an event with `severity="high"` (not `"critical"`), when `build_sms_push_payload` runs with default parameters, then it raises; when run with `allow_all_severities=True`, then it succeeds. | REQ-003 |
| AC-004 | Given an event whose title/summary exceeds the stated short-message length cap, when `build_sms_push_payload` runs, then the returned title/body is truncated to the cap with a visible truncation marker, never silently sent oversized. | REQ-003 |
| AC-005 | Given a valid event, when each provider's `deliver_*` runs with `dry_run=True` (the default), then it returns a `DeliveryResult` with `status="skipped"` and no transport call occurs. | REQ-004 |
| AC-006 | Given a valid event and an injected `transport`, when a provider's `deliver_*` runs with `dry_run=False`, then `transport` is called with the constructed payload and the result reflects its outcome. | REQ-004 |
| AC-007 | Given an event with `privacy.redaction_level` requiring redaction, when any of the five providers constructs a payload, then the specified fields are redacted. | REQ-005 |
| AC-008 | Given an event containing a credential-shaped value, when any of the five providers constructs a payload, then the value never appears verbatim in the result. | REQ-005, NFR-003 |
| AC-009 | Given `0032`'s existing test suite (`test_email_dry_run_default_AC_002`, etc.), when run after the `deliver_via` refactor, then every test still passes unchanged. | REQ-006 |
| AC-010 | Given `adapters/alert_delivery/README.md` and each of the five providers' `*.md` files, when inspected, then each documents its executable module and path. | REQ-007 |
| AC-011 | Given the full gate suite, when run, then `spec`, `agent-catalog`, `docs-link`, `spec-index` all pass. | NFR-004 |

## Data & Dependencies

No data dependencies. Standard-library only; no new dependency. Reuses
`AlertDeliveryEvent`/`DeliveryResult`/`Transport`/`TransportError`/
`redact_text`/`assert_no_secret` from `result.py` (spec `0032`) directly.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | The `deliver_via` refactor subtly changes `email.py`/`webhook.py`'s existing behavior. | A previously-passing integration silently breaks. | `0032`'s existing test suite (`test_alert_delivery_adapters.py`) is run unchanged after the refactor and must still pass in full (AC-009) — the refactor is not considered done until it does. |
| RISK-002 | A caller routes a low-severity alert through PagerDuty/Opsgenie or SMS/push, paging someone unnecessarily. | Alert fatigue; an on-call engineer is paged for a non-critical event. | REQ-002/REQ-003 enforce the severity restriction structurally (raises by default) rather than as a caller-followed convention — the same "correct by construction" pattern already used for `0034`'s long-only validation. |
| RISK-003 | An oversized SMS/push payload is silently sent, truncated by the carrier in an unpredictable way. | The recipient sees a garbled or cut-off message with no indication content was lost. | REQ-003 truncates deterministically with a visible marker before the payload is ever returned, so truncation is predictable and visible, not carrier-dependent. |

## Assumptions & Open Questions

- Assumption: `allow_all_severities` as an explicit, named override parameter
  is the right mechanism for opting into broader routing — matching
  `instructions/alerting.md`'s own "muted rules and windows suppress
  noise" philosophy of making an exception a deliberate, visible choice.
- Assumption: a 160-character cap (a common SMS single-segment length) is
  a reasonable default short-message length; the exact cap can move if a
  concrete provider integration needs a different one.
- Open question: once a real provider integration exists behind one of
  these `transport` seams, should ticketing's create-vs-update lookup
  move into a small shared helper here, or stay entirely the adopter's
  `transport` responsibility as scoped in this slice's Non-Goals?

## Exceptions

None.
