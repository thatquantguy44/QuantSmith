# Tasks: Alert Delivery — Remaining Executable Providers

- **Spec:** 0037-alert-delivery-remaining-providers (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-10

## Definition of Done (applies to every task)

- Standard-library only; no dependency added.
- `dry_run=True` is the default for every provider and never performs I/O.
- No credential or secret-shaped value in a constructed payload or result.
- `0032`'s existing tests pass unchanged after the `deliver_via` refactor.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Add `result.py::deliver_via`/`now_utc_iso`; refactor `email.py`/`webhook.py` to use them. | REQ-006, NFR-004 | done | No external behavior change. |
| T-002 | Write `slack.py`, `teams.py`, `ticketing.py`. | REQ-001, REQ-004, REQ-005, NFR-001, NFR-002, NFR-003 | done | Payload mapping per each provider's own `*.md`. |
| T-003 | Write `pagerduty_opsgenie.py`, `sms_push.py`. | REQ-002, REQ-003, REQ-004, REQ-005, NFR-001, NFR-002, NFR-003 | done | Severity gating (`allow_all_severities`); SMS truncation with a visible marker. |
| T-004 | Extend `tests/test_alert_delivery_adapters.py`. | REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, REQ-006, NFR-001 | done | One test per new acceptance criterion (AC-001 – AC-010); confirm the original eight still pass. |
| T-005 | Update `adapters/alert_delivery/{README,slack,teams,ticketing,pagerduty_opsgenie,sms_push}.md`. | REQ-007 | done | Document each executable module and path. |
| T-006 | Run validation gates. | NFR-004 | done | `spec`, `agent-catalog`, `docs-link`, `spec-index`; `pytest tests/ -q`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_slack_teams_ticketing_payload_mapping_AC_001` | done |
| AC-002 | `test_pagerduty_severity_gate_AC_002` | done |
| AC-003 | `test_sms_push_severity_gate_AC_003` | done |
| AC-004 | `test_sms_push_truncation_AC_004` | done |
| AC-005 | `test_new_providers_dry_run_default_AC_005` | done |
| AC-006 | `test_new_providers_transport_injection_AC_006` | done |
| AC-007 | `test_new_providers_redaction_AC_007` | done |
| AC-008 | `test_new_providers_secret_guard_AC_008` | done |
| AC-009 | Existing `test_alert_delivery_adapters.py` tests (AC-001 – AC-008 from spec `0032`) re-run unchanged | done |
| AC-010 | Direct inspection of `adapters/alert_delivery/*.md` | done |
| AC-011 | `hooks/stages/run-stage.sh spec agent-catalog docs-link spec-index` | done |

## Follow-ups

- Whether ticketing's create-vs-update lookup should eventually move into
  a small shared helper here, once a real provider integration exists
  (carried as an open question in `spec.md`).

This completes `adapters/alert_delivery/README.md`'s own pre-existing
Recommended Starting Set end to end: all seven providers now have an
executable module.
