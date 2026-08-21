# Plan: Workflow scheduling operations

- **Spec:** 0055-workflow-scheduling-operations (`spec.md`)
- **Status:** Draft
- **Author:** QuantSmith
- **Last updated:** 2026-08-21

> HOW. This plan requires an approved `spec.md`.

## Approach

Add a provider-neutral operational control plane above the existing scheduler
adapters. The registry defines what should run and when; adapters validate or
deploy the provider schedule; a dispatcher invokes scripts, Python modules, pipeline
runtimes, or agentic workflows; a ledger records what happened; and a daily report
turns the ledger plus manual task queue into an owner-facing operating summary.

The first implementation should be local and dependency-free: YAML/Markdown
registry, JSONL or SQLite ledger, deterministic report generation, dry-run schedule
validation, and shell/Python dispatch wrappers. Later implementations can swap in
Airflow, Dagster, Prefect, GitHub Actions, database-backed ledgers, and delivery
providers through adapters.

## Architecture & Components

```text
schedule_registry
  -> scheduler_adapter(dry-run/deploy)
  -> dispatcher(script | python_module | pipeline | agentic_workflow)
  -> execution_ledger
  -> daily_status_report
  -> alert_delivery / manual_task_queue / workflow_memory
```

- **Schedule registry:** declarative catalog of jobs, owners, schedules, targets,
  parameters, retries, backfill, runbooks, alert routes, and manual follow-ups.
- **Scheduler adapter bridge:** validates timing and provider metadata using
  `adapters/schedulers/adapter_contract.md`; deploys later through cron/GitHub
  Actions/Airflow/Dagster/Prefect profiles.
- **Dispatcher:** invokes a command, Python module/function, QuantSmith pipeline, or
  agentic workflow with correlation and idempotency metadata.
- **Execution ledger:** append-only record of each scheduled, started, completed,
  failed, skipped, missed, or manual-pending event.
- **Manual task queue:** first-class reminders linked to a job or report, with owner,
  due date, reminder cadence, acknowledgement, completion, and evidence URI.
- **Daily report generator:** reads ledger and task queue to produce a daily
  operations report by status, owner, workflow, and next-run window.
- **Alert handoff:** turns failed/missed/overdue events into `0020-alerting` payloads.
- **Memory handoff:** proposes recurring failure patterns, decisions, and runbook
  updates as candidates for workflow memory or institutional memory.

## Interfaces & Data Contracts

### Schedule Registry Entry

```yaml
job_id: string
owner: string
environment: dev | staging | prod
target:
  type: shell | python_module | python_function | quantsmith_pipeline | agentic_workflow
  ref: string
  args: []
  kwargs: {}
schedule:
  timezone: string
  calendar: trading | business | daily | custom
  trigger:
    type: cron | interval | event | manual
    expression: string
retry_policy:
  max_attempts: integer
  backoff_seconds: integer
backfill_policy:
  allowed: boolean
  max_lookback_days: integer
  idempotency_key_template: string
runbook_uri: string
alert_route: string
manual_followups:
  - task_id: string
    owner: string
    due_offset: string
    reminder_cadence: string
```

### Execution Ledger Record

```yaml
run_id: string
job_id: string
correlation_id: string
idempotency_key: string
scheduled_for_utc: string
started_at_utc: string | null
ended_at_utc: string | null
status: scheduled | running | completed | failed | skipped | missed | manual_pending
attempt: integer
exit_code: integer | null
exception_class: string | null
error_message_redacted: string | null
artifact_uris: []
log_uri: string | null
manual_task_ids: []
code_version: string | null
```

### Daily Operations Report

Sections:

- Completed jobs.
- Failed jobs with owner, failure class, retry state, and runbook.
- Skipped or missed jobs.
- Manual tasks open, overdue, acknowledged, and completed.
- Next scheduled runs.
- Owner/workflow summary.
- Memory candidates from repeated failures or runbook decisions.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Registry requires timezone, calendar, idempotency, retry, runbook, and owner metadata before deployment. |
| P5 Reversibility | yes | Deployment supports dry-run and disable/update semantics; reruns are idempotent or forced explicitly. |
| P6 Observability | yes | Ledger, report, alert handoff, owner rollups, and next-run evidence make status visible. |
| P9 Security & data | yes | Reports link to artifacts/logs and use redacted errors; no secrets or raw private data in registry/report. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | Schedule registry schema and validation | T-001, T-002 |
| REQ-002 | Scheduler adapter bridge and dry-run validation | T-003 |
| REQ-003 | Dispatcher with correlation, idempotency, retry, and backfill controls | T-004 |
| REQ-004 | Append-only execution ledger | T-005 |
| REQ-005 | Daily operations report generator | T-006 |
| REQ-006 | Manual task queue and reminder lifecycle | T-007 |
| REQ-007 | Alerting/delivery handoff | T-008 |
| REQ-008 | Workflow memory / institutional memory handoff | T-009 |
| NFR-001 | Provider-neutral registry and adapter boundary | T-001, T-003 |
| NFR-002 | Timezone/calendar validation and next-run evidence | T-003 |
| NFR-003 | Ledger and daily report | T-005, T-006 |
| NFR-004 | Code/version reference and idempotency key | T-004, T-005 |
| NFR-005 | Redaction checks and artifact-link-only reporting | T-005, T-006, T-008 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Scheduler ownership | Adapter-backed control plane | Hard-code cron only | Keeps local cron simple but allows migration to Airflow/Prefect/GitHub Actions. |
| First ledger store | Local append-only file or SQLite | Provider logs only | Provider logs are fragmented; QuantSmith needs one reportable status model. |
| Manual work | First-class queue | Free-text notes in report | Manual completion is part of the workflow and must be tracked like a run. |
| Report cadence | Daily report with owner rollups | Only real-time alerts | Daily reporting catches non-critical misses, manual carry-forward, and status drift. |
| Memory updates | Candidate handoff | Auto-write all failures to memory | Prevents noisy or low-confidence operational notes from polluting durable knowledge. |

## Validation Strategy

- AC-001: Registry validator tests required fields, target types, and provider-neutral
  schedule metadata.
- AC-002: Dry-run scheduler tests next-run evidence and no-execution behavior.
- AC-003: Dispatcher tests idempotent duplicate partition handling and forced reruns.
- AC-004: Ledger tests status coverage and redaction.
- AC-005: Report tests daily sections and owner/workflow rollups.
- AC-006: Manual task tests overdue carry-forward, acknowledgement, completion, and
  evidence handling.
- AC-007: Alert handoff tests payload generation without invoking delivery providers.
- AC-008: Memory handoff tests recurring-failure candidate creation with provenance.

## Rollout, Observability & Rollback

Roll out advisory-first:

1. Validate registries and generate dry-run reports without deploying schedules.
2. Enable local cron/GitHub Actions deployment for low-risk reports.
3. Add failure routing through alert payloads.
4. Persist durable ledgers and memory candidates after report review.

Rollback is disabling the provider schedule and leaving the ledger intact. A bad
schedule definition is superseded by a new registry version; historical runs remain
auditable.

## Open Questions

- Choose JSONL vs SQLite for the first local ledger.
- Decide whether provider schedule writes require an explicit approval gate.
- Decide whether daily reports should be Markdown-only first or also emit HTML/PDF.
