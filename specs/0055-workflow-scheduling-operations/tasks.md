# Tasks: Workflow scheduling operations

- **Spec:** 0055-workflow-scheduling-operations (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-21

> Ordered, testable units of work. Every task cites the requirement(s) it advances
> and carries a Definition of Done. No task without a requirement.

## Definition of Done (applies to every task)

- Code matches the plan; deviations noted in `plan.md`.
- Tests exist and pass deterministically.
- Reproducibility preserved (pinned inputs, idempotency keys, no hidden state).
- No secrets, credentials, MNPI, PII, restricted position data, or private raw data
  introduced.
- Docs/configs updated alongside the change.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Add `templates/data/schedule_registry.md` with provider-neutral job fields, target types, ownership, timing, retry, backfill, runbook, alert, and manual-follow-up sections. | REQ-001, NFR-001 | done | |
| T-002 | Implement schedule registry validation for required fields, target types, calendar/timezone fields, owner/runbook metadata, and provider-neutral portability. | REQ-001, NFR-001 | done | Runtime: `src/quantsmith/pipelines/workflow_scheduling.py`. |
| T-003 | Add scheduler adapter bridge tests for dry-run validation, next-run UTC evidence, provider schedule IDs, and timezone/calendar correctness. | REQ-002, NFR-002 | done | Reuses `adapters/schedulers/adapter_contract.md`. |
| T-004 | Implement dispatcher semantics for shell, Python module/function, QuantSmith pipeline, and agentic workflow targets with correlation IDs, retries, backfill windows, and idempotency keys. | REQ-003, NFR-004 | done | |
| T-005 | Implement append-only execution ledger records for completed, failed, skipped, missed, running, scheduled, and manual-pending states with redacted errors and artifact/log URIs. | REQ-004, NFR-003, NFR-004, NFR-005 | done | |
| T-006 | Add daily operations report generation with completed, failed, skipped/missed, manual, overdue, next-run, and owner/workflow rollup sections. | REQ-005, NFR-003, NFR-005 | done | Template: `templates/docs/daily_operations_report.md`. |
| T-007 | Implement manual task queue lifecycle: create, remind, acknowledge, complete, carry forward, and attach evidence URI. | REQ-006 | done | |
| T-008 | Add alert/delivery handoff payloads for failed runs, missed runs, and overdue manual tasks without invoking delivery providers directly. | REQ-007, NFR-005 | done | Routes through `0020-alerting` payload shape. |
| T-009 | Add memory handoff for recurring failures, runbook changes, and durable decisions as provenance-backed workflow-memory candidates. | REQ-008 | done | Reuses `0002-workflow-memory` record vocabulary. |
| T-010 | Update docs and workflow maps to show scheduled operations as the cross-cutting layer above reports, pipelines, monitoring, and content workflows. | REQ-001, REQ-005 | done | |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

Every acceptance criterion must be named by at least one test.

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_schedule_registry_validation_ac001` | done |
| AC-002 | `test_scheduler_dry_run_next_run_ac002` | done |
| AC-003 | `test_dispatch_idempotency_ac003` | done |
| AC-004 | `test_execution_ledger_status_redaction_ac004` | done |
| AC-005 | `test_daily_operations_report_sections_ac005` | done |
| AC-006 | `test_manual_task_carry_forward_ac006` | done |
| AC-007 | `test_alert_handoff_payload_ac007` | done |
| AC-008 | `test_memory_candidate_from_recurring_failure_ac008` | done |

## Follow-ups

- ~~Add a concrete low-risk worked example, such as a daily report script scheduled by
  cron and summarized in a Markdown operations report.~~ **Done:**
  `examples/scheduled_daily_report/` -- a real target (a workflow-memory review
  digest, reusing `0048`'s `validate` and `0057`'s `build_review_queue`) run
  through the full registry → dry-run → dispatch → ledger → report loop, with
  a committed sample output and a documented real cron deployment (two
  entries: the job itself, and a later report-render step). Covered by
  `tests/test_scheduled_daily_report_example.py`.
- Decide when schedule deployment becomes enforceable rather than advisory.
- The worked example's README names the gap it deliberately doesn't close: a
  `workflow_scheduling_cli` (mirroring `workflow_memory_cli.py`'s pattern) so
  the report-render half of a real cron deployment doesn't need a bespoke
  script per team. Natural next slice if this moves from example to adopted
  practice.
