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
| T-001 | Add `templates/data/schedule_registry.md` with provider-neutral job fields, target types, ownership, timing, retry, backfill, runbook, alert, and manual-follow-up sections. | REQ-001, NFR-001 | todo | |
| T-002 | Implement schedule registry validation for required fields, target types, calendar/timezone fields, owner/runbook metadata, and provider-neutral portability. | REQ-001, NFR-001 | todo | Candidate runtime: `src/quantsmith/pipelines/workflow_scheduling.py`. |
| T-003 | Add scheduler adapter bridge tests for dry-run validation, next-run UTC evidence, provider schedule IDs, and timezone/calendar correctness. | REQ-002, NFR-002 | todo | Reuse `adapters/schedulers/adapter_contract.md`. |
| T-004 | Implement dispatcher semantics for shell, Python module/function, QuantSmith pipeline, and agentic workflow targets with correlation IDs, retries, backfill windows, and idempotency keys. | REQ-003, NFR-004 | todo | |
| T-005 | Implement append-only execution ledger records for completed, failed, skipped, missed, running, scheduled, and manual-pending states with redacted errors and artifact/log URIs. | REQ-004, NFR-003, NFR-004, NFR-005 | todo | |
| T-006 | Add daily operations report generation with completed, failed, skipped/missed, manual, overdue, next-run, and owner/workflow rollup sections. | REQ-005, NFR-003, NFR-005 | todo | Candidate template: `templates/docs/daily_operations_report.md`. |
| T-007 | Implement manual task queue lifecycle: create, remind, acknowledge, complete, carry forward, and attach evidence URI. | REQ-006 | todo | |
| T-008 | Add alert/delivery handoff payloads for failed runs, missed runs, and overdue manual tasks without invoking delivery providers directly. | REQ-007, NFR-005 | todo | Route through `0020-alerting`. |
| T-009 | Add memory handoff for recurring failures, runbook changes, and durable decisions as provenance-backed workflow-memory candidates. | REQ-008 | todo | Reuse `0002-workflow-memory`. |
| T-010 | Update docs and workflow maps to show scheduled operations as the cross-cutting layer above reports, pipelines, monitoring, and content workflows. | REQ-001, REQ-005 | todo | |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

Every acceptance criterion must be named by at least one test.

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_schedule_registry_validation_ac001` | todo |
| AC-002 | `test_scheduler_dry_run_next_run_ac002` | todo |
| AC-003 | `test_dispatch_idempotency_ac003` | todo |
| AC-004 | `test_execution_ledger_status_redaction_ac004` | todo |
| AC-005 | `test_daily_operations_report_sections_ac005` | todo |
| AC-006 | `test_manual_task_carry_forward_ac006` | todo |
| AC-007 | `test_alert_handoff_payload_ac007` | todo |
| AC-008 | `test_memory_candidate_from_recurring_failure_ac008` | todo |

## Follow-ups

- Choose the first durable ledger backend (JSONL, SQLite, or pluggable interface).
- Add a concrete low-risk worked example, such as a daily report script scheduled by
  cron and summarized in a Markdown operations report.
- Decide when schedule deployment becomes enforceable rather than advisory.
