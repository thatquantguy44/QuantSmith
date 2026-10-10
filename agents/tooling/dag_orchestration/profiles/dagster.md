# Dagster Profile

Concurrency, priority, retry, and backfill guidance for running many pipelines on
Dagster. Rendered by `pipeline_fleet.to_dagster` (spec `0101`).

> **Version assumption:** Dagster 1.10+ (unified `concurrency:` block in
> `dagster.yaml`, op/asset `pool=`). Older deployments use `run_queue:` (same keys)
> or `run_coordinator.config` and op tag `dagster/concurrency_key`. Verify against
> the installed version before deploying.

## Concurrency Levels

| Level | Mechanism | Bounds |
| --- | --- | --- |
| Deployment runs | `concurrency.runs.max_concurrent_runs` | Total in-progress runs (queued run coordinator + daemon). |
| Runs by tag | `concurrency.runs.tag_concurrency_limits` | Runs carrying a tag, e.g. `quantsmith/pool/warehouse`. `value: {applyLimitPerUniqueValue: true}` gives one limit per distinct value (mutual exclusion per sink). |
| Ops/assets across runs | `pool="warehouse"` on `@asset`/`@op`; limit via `dagster instance concurrency set warehouse 8` or `concurrency.pools.default_limit` | Steps touching a resource, across all runs. One pool per op. |
| Ops inside one run | `multiprocess_executor` `max_concurrent`, executor `tag_concurrency_limits` | Fan-out within a run. |
| Cluster | Run launcher (K8s/ECS/Docker) resources | Pods/containers; treat as a pool too. |

## What `to_dagster` Emits

```yaml
# dagster.yaml (instance)
concurrency:
  runs:
    max_concurrent_runs: 32
    tag_concurrency_limits:
      - key: quantsmith/pool/warehouse
        limit: 12
      - key: quantsmith/pool/vendor_api
        limit: 4
      - key: quantsmith/concurrency_key
        value: {applyLimitPerUniqueValue: true}
        limit: 1
run_retries:
  enabled: true
```

Per job, attach the emitted run tags (`tags=` on the job, schedule, or sensor
`RunRequest`): `dagster/priority`, `dagster/max_retries`, `quantsmith/pool/<name>`,
`quantsmith/concurrency_key`, `quantsmith/owner`.

## Rules

- **Two levels, one plan.** `max_concurrent_runs` × per-run fan-out must fit the
  fleet plan. Bound in-run fan-out with the executor's `max_concurrent`.
- **Run tags vs. op pools.** Run tag limits hold a slot for the whole run (simple,
  multi-pool). Op/asset pools hold it only while the step touching the resource
  runs (higher throughput, one pool per op). Prefer pools for long runs that touch
  the warehouse briefly.
- **Slot weights.** Tag limits count one per run; a run that opens N connections is
  under-counted — `to_dagster` warns. Use op pools per step or a dedicated tag.
- **Backfills.** Backfill runs carry `dagster/backfill`; add a tag limit on that key
  so history cannot take every slot. Prefer `BackfillPolicy.multi_run(
  max_partitions_per_run=N)` or `single_run()` over one run per partition when
  hundreds of partitions are requested.
- **Priority.** `dagster/priority` (higher dequeues first) applies to queued runs only;
  it does not pre-empt running ones.
- **Retries.** Run retries (`dagster/max_retries`) re-queue and count against limits.
  Op `RetryPolicy` retries in place and holds the run's slots — use
  `Backoff.EXPONENTIAL` with `Jitter` and small `max_retries`.
- **Schedules and sensors.** Stagger cron minutes/seconds with `stagger_offsets`;
  give `RunRequest`s a `run_key` so ticks are idempotent; cap sensor fan-out per tick.
- **Cross-pipeline dependencies** are asset dependencies (with declarative
  automation) or run-status sensors — not concurrency config. `to_dagster` warns.
- **Daemon health.** The queue only drains while `dagster-daemon` runs; monitor the
  queued-run count and daemon heartbeats in `pipeline_observability`.

## Failure Modes To Look For

- `max_concurrent_runs: -1` (unlimited) in production.
- Tag limits configured but jobs never tagged (limit never matches).
- Per-partition backfill of years of history with no backfill tag limit.
- Op retries without backoff against a rate-limited vendor.
