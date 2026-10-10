# Airflow Profile

Concurrency, priority, retry, and backfill guidance for running many pipelines on
Apache Airflow. Rendered by `pipeline_fleet.to_airflow` (spec `0112`).

> **Version assumption:** Airflow 2.x/3.x (`pool`, `pool_slots`, `priority_weight`,
> `weight_rule`, `max_active_runs`, `[core] parallelism`). Datasets were renamed
> Assets in Airflow 3. Verify against the installed version before deploying.

## Concurrency Levels

| Level | Mechanism | Bounds |
| --- | --- | --- |
| Deployment | `[core] parallelism` | Running task instances across all DAGs. |
| Per DAG | `max_active_runs`, `max_active_tasks` | Concurrent runs and tasks of one DAG. |
| Shared resource | Pools (`airflow pools set NAME SLOTS DESC`) + task `pool`, `pool_slots` | Tasks holding a resource; `pool_slots` weights heavy tasks. |
| Executor | Celery/Kubernetes worker concurrency | Worker capacity — treat as a pool. |

## What `to_airflow` Emits

- `airflow_cfg.core.parallelism` = the fleet's global limit.
- One pool per fleet pool (`quantsmith_<pool>`) and per concurrency key
  (`quantsmith_key_<key>`, 1 slot), with the `airflow pools set` commands.
- Per DAG: `max_active_runs: 1` and `default_args` with `pool`, `pool_slots`,
  `priority_weight` and `weight_rule: absolute`, `retries`, `owner`.

## Rules

- **One pool per task.** A task needing a key and a pool, or several pools, gets the
  key pool (correctness first) or its tightest pool; `to_airflow` warns about the rest.
  Split the work into tasks per resource, or dispatch through `run_fleet`.
- **`weight_rule: absolute`.** The default (`downstream`) sums weights along the DAG,
  so priorities stop meaning what the fleet declared.
- **Backfills.** Run backfills in their own pool so history cannot take every slot;
  cap `max_active_runs` on backfill DAG runs.
- **Retries** re-queue the task and count against the same pool.
- **Cross-DAG dependencies** are dataset/asset schedules or `ExternalTaskSensor`;
  sensors in `reschedule` mode so they do not hold a slot while waiting.
- **Staggering.** Offset cron minutes with `stagger_offsets`.

## Failure Modes To Look For

- Pools defined but tasks never assigned (default pool has 128 slots).
- `priority_weight` set without `weight_rule: absolute`.
- Sensors in `poke` mode holding worker slots for hours.
- Backfills sharing the production pool.
