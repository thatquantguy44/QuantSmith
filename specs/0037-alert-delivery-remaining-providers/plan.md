# Plan: Alert Delivery — Remaining Executable Providers

- **Spec:** 0037-alert-delivery-remaining-providers (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-08-10

## Approach

Extract the dry-run/transport/`DeliveryResult` wrapper duplicated between
`email.py` and `webhook.py` (spec `0032`) into a shared `result.py`
helper, refactor those two to use it, then add five new provider modules
on the same shared helper — so five more providers don't mean five more
copies of the same ~20-line wrapper. Two providers additionally enforce a
severity restriction and (for SMS/push) a length cap structurally, per
their own `*.md` files' stated delivery rules.

## Architecture & Components

```text
result.py
  + now_utc_iso() -> str
  + deliver_via(provider, payload, event, transport, dry_run) -> DeliveryResult
      dry_run=True   -> status="skipped", no I/O
      dry_run=False  -> requires transport; calls it; maps outcome/TransportError
                         to status="delivered"/"failed"

email.py, webhook.py   (refactored, no external behavior change)
  build_*_payload(event) -> dict          [unchanged]
  deliver_*(event, transport, dry_run)     -> deliver_via("email"/"webhook", ...)

slack.py / teams.py / ticketing.py   (new, same shape as email/webhook)
  build_*_payload(event) -> dict           [per that provider's *.md table]
  deliver_*(event, transport, dry_run)     -> deliver_via(...)

pagerduty_opsgenie.py   (new)
  build_pagerduty_payload(event, allow_all_severities=False) -> dict
      raises unless event.severity in {"high","critical"} or allow_all_severities
  deliver_pagerduty(event, transport, dry_run, allow_all_severities=False)

sms_push.py   (new)
  _truncate(text, max_len) -> str          (deterministic, visible marker)
  build_sms_push_payload(event, allow_all_severities=False) -> dict
      raises unless event.severity == "critical" or allow_all_severities
      title/body truncated to SMS_MAX_LEN
  deliver_sms_push(event, transport, dry_run, allow_all_severities=False)
```

## Interfaces & Data Contracts

No new schema. All five providers consume the existing
`AlertDeliveryEvent` (spec `0032`) and return the existing
`DeliveryResult`. Each provider's payload dict shape is a direct
transcription of its own already-documented `*.md` Payload Mapping table
— no new design, just giving the already-documented contract a
constructor.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Severity restriction and length cap are enforced by validation/truncation inside the builder, not left as a caller-followed convention in the `*.md` prose. |
| P5 Reversibility | yes | `deliver_via` is a behavior-preserving refactor, verified by `0032`'s own unchanged test suite (AC-009); new providers are additive. |
| P9 Security & data | yes | No credential ever enters this SDK; `transport` is the adopter's own authenticated client, unchanged from `0032`'s boundary. |
| P10 Honest reporting | yes | A truncated SMS/push message carries a visible marker rather than silently losing content; `dry_run`'s `status="skipped"` (not `"delivered"`) is unchanged from `0032`. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `slack.py`, `teams.py`, `ticketing.py` | T-002 |
| REQ-002 | `pagerduty_opsgenie.py`'s `allow_all_severities` gate | T-003 |
| REQ-003 | `sms_push.py`'s `allow_all_severities` gate + `_truncate` | T-003 |
| REQ-004 | `deliver_via`'s `dry_run`/`transport` handling, reused by all five | T-001, T-002, T-003 |
| REQ-005 | `redact_text`/`assert_no_secret` reuse in every builder | T-002, T-003 |
| REQ-006 | `result.py::deliver_via`; `email.py`/`webhook.py` refactor | T-001 |
| REQ-007 | `adapters/alert_delivery/{README,slack,teams,ticketing,pagerduty_opsgenie,sms_push}.md` | T-005 |
| NFR-001 | No randomness in payload construction | T-002, T-003 |
| NFR-002 | Standard-library only | T-002, T-003 |
| NFR-003 | `assert_no_secret` in every builder | T-002, T-003 |
| NFR-004 | Validation gates + regression run | T-006 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Deduplication | Factor a shared `deliver_via` helper now, refactoring `0032`'s two existing providers | Leave `email.py`/`webhook.py` as-is and duplicate the wrapper five more times | Five more copies of the same wrapper is exactly the kind of drift risk `RISK-003` in `0031`'s own spec (data_ingestion) already argued against; deduplicating now, verified by the existing test suite, is cheaper than deduplicating later across seven copies. |
| Severity enforcement | A structural `allow_all_severities` parameter that raises by default | Leave the "only route high/critical" rule as `*.md` prose only | `pagerduty_opsgenie.md`/`sms_push.md` already state the rule; a caller-followed convention with no enforcement is exactly the gap this SDK's own "correct by construction" principle (P4) argues against, and the pattern is already proven for `0034`'s long-only validation. |
| SMS truncation | Deterministic truncation with a visible marker, inside the builder | Leave length limits undocumented/unenforced, or reject an oversized message outright | Silently sending an oversized message risks unpredictable carrier-side truncation (RISK-003); rejecting outright would be an unnecessary hard failure when truncation is a reasonable, honest default. A visible marker keeps the truncation from being invisible to the recipient. |
| Ticketing create-vs-update | Out of scope; `dedupe_key` carried in the payload for the adopter's `transport` to use | Add a lookup/state mechanism in this module | This SDK holds no provider state (no ticket database); `alert_router` (`0020`) already owns deduplication logic upstream, and inventing a parallel state mechanism here would duplicate that responsibility. |

## Validation Strategy

Extend `tests/test_alert_delivery_adapters.py` with one test per new
acceptance criterion (AC-001 through AC-010), following `0032`'s own
per-AC test naming convention, and confirm every one of `0032`'s original
eight tests still passes unchanged after the `deliver_via` refactor
(AC-009). Then `hooks/stages/run-stage.sh spec agent-catalog docs-link
spec-index`, the full `pytest tests/ -q`, and `git diff --check`. AC-011
is covered by the gate run itself.

## Rollout, Observability & Rollback

Rollout is a branch commit (and push, if requested). Rollback is
reverting the single commit; `adapter_contract.md` and `agents/alerts/*`
are unmodified. `deliver_via` is additive to `result.py`; reverting it
would require reverting `email.py`/`webhook.py`'s refactor alongside it,
which the single commit already keeps together.

## Open Questions

- Once a real provider integration exists behind one of these `transport`
  seams, should ticketing's create-vs-update lookup move into a small
  shared helper here, or stay entirely the adopter's `transport`
  responsibility?
