# Spec: Workflow scheduling operations

- **ID:** 0055-workflow-scheduling-operations
- **Status:** Approved
- **Author:** QuantSmith
- **Approver:** QuantSmith
- **Last updated:** 2026-08-21

> WHAT and WHY only. Implementation lives in `plan.md`.

## Problem & Context

QuantSmith has scheduler adapters (`cron`, GitHub Actions, Airflow, Dagster, Prefect)
and pipeline observability, but it does not yet have a first-class agentic control
plane for recurring operational work. A user should be able to register scheduled
tasks, scripts, Python modules, and multi-agent workflows; dispatch them through a
provider-neutral scheduler; track run status; generate daily completion/failure
reports; and carry forward reminders for manual work that cannot be automated.

Without this layer, scheduled jobs become scattered cron entries, ad hoc scripts,
calendar reminders, and chat memory. The goal is to make recurring quant and
operational workflows deployable, observable, and accountable.

## Goals

- Define a schedule registry for scripts, Python entry points, commands, and
  agentic workflows.
- Dispatch registered work through scheduler adapters with dry-run validation,
  provider IDs, retries, and backfill/idempotency metadata.
- Record every run in an execution ledger with status, timestamps, correlation IDs,
  artifacts, logs, failures, and redacted error messages.
- Generate daily status reports showing completed work, failed work, skipped/missed
  runs, next runs, open manual tasks, and overdue reminders.
- Support manual task reminders with owners, due dates, acknowledgement, completion,
  and carry-forward behavior.
- Route failures and overdue manual work into alerting or delivery adapters without
  coupling the scheduler to Slack, email, ticketing, or pager systems.

## Non-Goals

- Replacing provider schedulers such as cron, Airflow, Dagster, Prefect, or GitHub
  Actions. QuantSmith defines the control plane and contracts; adapters deploy to
  providers.
- Building a distributed executor in this slice.
- Owning business logic inside the scheduled task. The task remains a script,
  Python function/module, pipeline, notebook wrapper, or agentic workflow.
- Auto-remediating failed jobs or completing manual work without an explicit
  runbook and separate approval path.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The system shall define a schedule registry where each job declares owner, schedule, timezone, calendar, environment, command/workflow target, parameters, runbook, retry policy, backfill policy, alert route, and manual follow-ups. | must |
| REQ-002 | The system shall validate schedules through existing scheduler adapters and return provider schedule IDs, next-run evidence, and dry-run results before deployment. | must |
| REQ-003 | The system shall dispatch or invoke jobs idempotently with a correlation ID, idempotency key, retry policy, and explicit backfill window. | must |
| REQ-004 | The system shall record every run in an execution ledger with scheduled time, start/end time, status, attempt count, exit code or exception class, artifact URIs, log URI, redacted error message, and manual-task links. | must |
| REQ-005 | The system shall generate a daily status report listing completed jobs, failed jobs, skipped/missed jobs, open manual tasks, overdue reminders, next runs, and status by owner/workflow. | must |
| REQ-006 | The system shall track manual tasks with owner, due date, reminder cadence, acknowledgement, completion, evidence URI, and carry-forward status until resolved. | must |
| REQ-007 | The system shall route failures, missed runs, and overdue manual tasks into the alerting/delivery contracts without embedding provider-specific delivery logic. | should |
| REQ-008 | The system shall persist durable operational learnings, recurring failures, runbook updates, and resolved decisions back into workflow memory or institutional memory. | should |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Provider neutrality | A registry entry can target cron locally and later migrate to Airflow/Prefect/GitHub Actions without changing business logic. |
| NFR-002 | Time correctness | Schedules declare timezone and calendar; next-run calculations are deterministic and auditable. |
| NFR-003 | Observability | Every scheduled job has a latest status, next run, run history, and owner-visible daily report entry. |
| NFR-004 | Reproducibility | Every run records command/workflow target, parameters, code/version reference, and idempotency key. |
| NFR-005 | Security and redaction | Reports and ledgers contain no secrets, credentials, PII, MNPI, restricted position data, or raw private datasets. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a schedule registry entry, when it is validated, then required ownership, timing, target, retry, backfill, runbook, alert, and manual-task fields are present and provider-compatible. | REQ-001, NFR-001 |
| AC-002 | Given a cron-targeted job, when dry-run deployment is requested, then the scheduler adapter returns a provider schedule ID placeholder, next-run UTC timestamp, correlation ID, and validation result without executing the job. | REQ-002, NFR-002 |
| AC-003 | Given a Python module job with an idempotency key, when it dispatches twice for the same partition, then the second run is skipped or linked to the existing completed run unless forced. | REQ-003, NFR-004 |
| AC-004 | Given successful, failed, skipped, and missed runs, when the ledger is read, then each run has complete status metadata and redacted failure details. | REQ-004, NFR-003, NFR-005 |
| AC-005 | Given a day's ledger and manual-task queue, when the daily report is generated, then it lists completed, failed, skipped/missed, overdue/manual, and next-run sections with owner rollups. | REQ-005, NFR-003 |
| AC-006 | Given an unresolved manual task, when its due date passes, then it remains open, appears in the daily report, and is eligible for reminder routing until acknowledged or completed. | REQ-006 |
| AC-007 | Given a failed run or overdue manual task, when routing is enabled, then the output is an alert/delivery payload and no provider-specific delivery code is invoked by the scheduler. | REQ-007 |
| AC-008 | Given a recurring failure that is resolved by a runbook change, when the daily report is closed, then the learning is recorded as a durable memory candidate with provenance. | REQ-008 |

## Data & Dependencies

- Existing scheduler adapter contract: `adapters/schedulers/adapter_contract.md`.
- Provider profiles: `adapters/schedulers/cron.md`, `github_actions.md`,
  `airflow.md`, `dagster_prefect.md`.
- Alert routing and delivery: `specs/0020-alerting/`, `adapters/alert_delivery/`.
- Pipeline observability: `specs/0019-pipeline-observability/`.
- Workflow memory and institutional knowledge: `specs/0002-workflow-memory/`,
  `instructions/workflow_memory.md`, and `agents/knowledge/`.
- Runtime: `src/quantsmith/pipelines/workflow_scheduling.py`.
- Candidate templates: `templates/data/schedule_registry.md`,
  `templates/docs/daily_operations_report.md`, and runbook links.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | Timezone or calendar conversion schedules a job at the wrong time. | Missed trading/reporting windows. | Require timezone/calendar fields and record next-run evidence before deployment. |
| RISK-002 | Re-runs duplicate downstream effects. | Duplicate reports, trades, files, tickets, or notifications. | Idempotency keys, dry-run validation, forced rerun flags, and backfill windows. |
| RISK-003 | Failures are hidden in logs and never become accountable work. | Operational drift and silent data/report gaps. | Execution ledger, daily report, owner rollups, alert routing, and manual carry-forward. |
| RISK-004 | Manual work is treated as done because the automated job completed. | Incomplete operational workflow. | Manual tasks are first-class ledger items with owners, due dates, and completion evidence. |
| RISK-005 | Reports leak sensitive inputs or credentials. | Confidentiality breach. | Redacted errors, artifact links instead of raw data, secret/PII scanning, and access-aware delivery. |

## Assumptions & Open Questions

- Assumption: provider-specific deployment remains in scheduler adapters; this spec
  owns the registry, ledger, reporting, and agentic orchestration semantics.
- Assumption: the first runtime can be dependency-free and local-file backed; durable
  stores can be added later.
- Open question: should the first implementation persist the ledger as JSONL,
  SQLite, or a pluggable store?
- Open question: should schedule deployment be advisory-only at first, with manual
  confirmation before writing provider schedules?

## Exceptions

None.
