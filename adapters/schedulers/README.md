# Scheduler Adapters

Scheduler adapters translate a workflow schedule into the execution environment
that actually runs it. The workflow owns intent; the scheduler adapter owns
provider-specific timing, retries, permissions, and run metadata.

## Files

| File | Purpose |
| --- | --- |
| `adapter_contract.md` | Channel-neutral workflow schedule and run contract. |
| `cron.md` | Local or server cron execution. |
| `github_actions.md` | Repository-native scheduled and manually dispatched workflows. |
| `airflow.md` | Airflow DAG deployment and operational metadata. |
| `dagster_prefect.md` | Dagster and Prefect asset/flow orchestration profiles. |

## Use Cases

- Daily intelligence reports.
- Data ingestion backfills.
- Pipeline and model monitoring checks.
- Scheduled artifact generation.
