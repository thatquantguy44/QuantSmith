# Airflow Scheduler Adapter

## Use For

- Production DAGs with explicit dependencies.
- Backfills and catchup logic.
- Shared operational visibility.
- Data pipelines with SLAs, sensors, and retry policy.

## Delivery Rules

- Map `workflow_id` to DAG ID and `schedule_id` to DAG schedule metadata.
- Preserve task ownership, runbook, data contract, and alert route.
- Use idempotent task design for retries and backfills.
- Emit dataset, artifact, and run-card locations as XCom or metadata records.
- Avoid task-level secrets in DAG files; use approved connections or secret
  backends.

## Risks

- Catchup/backfill can create duplicate outputs without idempotency keys.
- DAG parse errors can silently block deployment.
- Airflow connection sprawl can bypass secrets-management standards.

## Concurrency At Fleet Scale

- Render pools and task arguments from the fleet declaration with
  `pipeline_fleet.to_airflow` (spec `0112`); resolve every warning. See
  `agents/tooling/dag_orchestration/profiles/airflow.md`.
- A task takes one pool (`pool_slots` weights it); keys become 1-slot pools.
- Set `weight_rule: absolute` with `priority_weight`; run backfills in their own pool.
