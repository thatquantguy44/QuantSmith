# Tasks: Scheduler Monitoring

- **Spec:** 0060-scheduler-monitoring (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-24

## Definition of Done (applies to every task)

- Standard library only; no new dependency.
- No network call or credential anywhere in `workflow_scheduling.py` or
  `workflow_scheduling_cli.py` — every sender is caller-injected.
- An unregistered delivery channel raises rather than dropping an alert.
- Both CLI subcommands degrade gracefully on a missing/empty ledger.
- Deterministic: the same ledger and arguments always produce the same
  output.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Write `deliver_routed_alerts`. | REQ-001, REQ-002, NFR-001, NFR-002, NFR-003 | done | `src/quantsmith/pipelines/workflow_scheduling.py`. Imports `AlertDeliveryEvent`/`DeliveryResult` from `adapters.alert_delivery.result` (no reverse dependency). |
| T-002 | Write `workflow_scheduling_cli.py` and its tests. | REQ-003, REQ-004, REQ-005, NFR-001, NFR-002 | done | `render-report`/`alerts` subcommands; `tests/test_workflow_scheduling_cli.py`, one test per AC-001–AC-006, CLI exercised via `subprocess` matching `test_workflow_memory_write_path.py`'s pattern. |
| T-003 | Resolve the enforceable-vs-advisory question and update the worked example. | REQ-006 | done | `spec.md`'s Assumptions & Open Questions; `examples/scheduled_daily_report/README.md`'s cron deployment now names a real module/command. |
| T-004 | Wire catalogs and handoff docs. | REQ-003, REQ-004 | done | `specs/README.md`, root `README.md`, `docs/handoff.md`, `specs/0055-workflow-scheduling-operations/tasks.md` (Follow-ups resolved). |
| T-005 | Run validation gates. | NFR-001, NFR-002, NFR-003 | done | `spec`, `docs-link`, `spec-index`, `readme-sync`, `doc-counts`; `pytest tests/ -q`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_deliver_routed_alerts_calls_matching_sender_AC_001` | done |
| AC-002 | `test_deliver_routed_alerts_unmapped_channel_raises_AC_002` | done |
| AC-003 | `test_deliver_routed_alerts_multiple_channels_AC_003` | done |
| AC-004 | `test_cli_render_report_matches_library_output_AC_004` | done |
| AC-005 | `test_cli_alerts_previews_without_delivering_AC_005` | done |
| AC-006 | `test_cli_degrades_gracefully_on_empty_ledger_AC_006` | done |
| AC-007 | Direct inspection of `examples/scheduled_daily_report/README.md` | done |

## Follow-ups

- A persisted manual-task file format, enabling a task-aware CLI and a
  `dispatch` subcommand (carried as an open question in `spec.md`).
- Promoting advisory-by-default to a real enforced mode once a concrete
  provider-scheduler deployment exists to enforce against.
