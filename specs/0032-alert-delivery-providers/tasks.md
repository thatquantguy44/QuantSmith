# Tasks: Alert Delivery Executable Providers (Email, Webhook)

- **Spec:** 0032-alert-delivery-providers (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-10

## Definition of Done (applies to every task)

- Standard-library only; no dependency added.
- `dry_run=True` is the default and never performs I/O.
- No credential or secret-shaped value in a constructed payload or result.
- Determinism: the same event yields the same payload every call.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Write `result.py`: `AlertDeliveryEvent`, `DeliveryResult`, `contains_secret`, `redact`. | REQ-001, REQ-005, NFR-003 | done | Direct transcription of `adapter_contract.md`'s Input/Output YAML. |
| T-002 | Write `email.py`: `build_email_payload`, `deliver_email`. | REQ-002, REQ-004, REQ-006, NFR-001, NFR-002 | done | Payload mapping per `email.md`. |
| T-003 | Write `webhook.py`: `build_webhook_payload`, `deliver_webhook`. | REQ-003, REQ-004, REQ-006, NFR-001, NFR-002 | done | Payload mapping per `webhook.md`. |
| T-004 | Update `adapters/alert_delivery/{README,email,webhook}.md`. | REQ-007 | done | Document executable providers and module paths, matching `dashboard_render/README.md`'s pattern. |
| T-005 | Write `tests/test_alert_delivery_adapters.py` and run validation gates. | NFR-004 | done | `spec`, `agent-catalog`, `docs-link`, `spec-index`; `pytest tests/ -q`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_missing_required_field_raises_AC_001` | done |
| AC-002 | `test_email_dry_run_default_AC_002` | done |
| AC-003 | `test_webhook_dry_run_default_AC_003` | done |
| AC-004 | `test_transport_injection_AC_004` | done |
| AC-005 | `test_redaction_applied_AC_005` | done |
| AC-006 | `test_secret_shaped_value_flagged_AC_006` | done |
| AC-007 | `test_retryable_vs_terminal_failure_AC_007` | done |
| AC-008 | `test_payload_construction_deterministic_AC_008` | done |
| AC-009 | Direct inspection of `adapters/alert_delivery/{README,email,webhook}.md` | done |
| AC-010 | `hooks/stages/run-stage.sh spec agent-catalog docs-link spec-index` | done |

## Follow-ups

- Slack, Teams, ticketing (Jira/ServiceNow/Linear), PagerDuty/Opsgenie, and
  SMS/push providers remain, per `adapters/alert_delivery/README.md`'s
  Recommended Starting Set (implement after email + webhook are proven).
