# Schedule Registry: <registry-name>

> Provider-neutral catalog for scheduled scripts, Python jobs, QuantSmith pipelines,
> and agentic workflows. Backed by spec `0055-workflow-scheduling-operations`.

## Job

- **job_id:** <stable id>
- **owner:** <team or person>
- **environment:** dev | staging | prod
- **runbook_uri:** <runbook or playbook link>
- **alert_route:** <alert route or policy id>

## Target

- **type:** shell | python_module | python_function | quantsmith_pipeline | agentic_workflow
- **ref:** <command, module, module:function, pipeline id, or workflow id>
- **args:** []
- **kwargs:** {}

## Schedule

- **timezone:** <IANA timezone, e.g. America/New_York>
- **calendar:** trading | business | daily | custom
- **trigger type:** cron | interval | event | manual
- **trigger expression:** <e.g. `30 6 * * 1-5`>

## Reliability

- **retry max_attempts:** <integer>
- **retry backoff_seconds:** <integer>
- **backfill allowed:** true | false
- **backfill max_lookback_days:** <integer>
- **idempotency_key_template:** <e.g. `{job_id}:{partition}`>

## Manual Follow-Ups

| task_id | owner | due_offset_days | reminder_cadence | title |
| --- | --- | ---: | --- | --- |
| <manual-task-id> | <owner> | 0 | daily | <what a human must do> |

## Reporting

Daily operations reports should include completed jobs, failed jobs, skipped/missed
jobs, open manual work, overdue reminders, next runs, owner/workflow rollups, and
memory candidates for recurring failures.
