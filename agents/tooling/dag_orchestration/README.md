# DAG Orchestration Agent

## Purpose

The DAG Orchestration Agent brings the SDK's pipeline discipline to the
orchestrators that actually run data pipelines in production. It reviews and
configures orchestrator deployments for concurrency, priority, retries,
backfills, scheduling, and idempotency, and renders a tool-neutral fleet
declaration (`0101`) into orchestrator config via `to_dagster` / `to_mage`. It
ships four profiles — **Dagster**, **Mage**, **Airflow**, and **Prefect** (spec
`0112` adds `to_airflow` / `to_prefect`).

## Use When

- A Dagster, Mage, Airflow, or Prefect deployment needs concurrency limits for many pipelines.
- An approved fleet declaration (`data_engineering/pipeline_concurrency`) must be
  rendered as `dagster.yaml` / Mage `metadata.yaml` settings.
- Backfills, partitions, or dynamic fan-out are flooding the run queue.
- Runs exceed warehouse or vendor limits even though "limits are configured".
- Choosing between Dagster and Mage for a quant data platform.

## Inputs

- A `Fleet` declaration (`src/quantsmith/pipelines/pipeline_fleet.py`, spec `0101`).
- The orchestrator, its version, and its run launcher / executor (local, Docker,
  Kubernetes, ECS, Cloud Run).
- Existing orchestrator config (`dagster.yaml`, definitions; Mage project and
  pipeline `metadata.yaml`, triggers).

## Outputs

- Orchestrator config rendered by `to_dagster` / `to_mage` / `to_airflow` / `to_prefect`, with its `warnings`.
- A profile review (`profiles/dagster.md`, `mage.md`, `airflow.md`, `prefect.md`): run vs. task
  concurrency, priority, retries, backfill throttling, schedule staggering.
- A mitigation for every limit the orchestrator cannot enforce natively.
- Handoffs to `pipeline_concurrency`, `pipeline_deployment`, and
  `pipeline_observability`.

## Example Requests

- "Render our 300-pipeline fleet as Dagster run-queue limits."
- "Mage keeps starting 40 runs at once and our Postgres falls over — fix the config."
- "A 2-year Dagster backfill is starving the daily pipelines. Throttle it."
- "Dagster or Mage for 200 vendor ingestion pipelines? Compare concurrency control."

## Required Review Themes

- Run-level and task-level concurrency are both bounded, and agree with the fleet plan.
- Every pool and mutual-exclusion key is enforced natively or by a stated mitigation.
- Backfills and dynamic fan-out are throttled separately from scheduled runs.
- Retries are bounded and do not bypass the queue; schedules are staggered.
- Config keys are checked against the installed orchestrator version.
