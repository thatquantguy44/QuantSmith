# Mage Profile

Concurrency, retry, trigger, and backfill guidance for running many pipelines on
Mage (Mage AI). Rendered by `pipeline_fleet.to_mage` (spec `0101`).

> **Version assumption:** current Mage OSS project layout (project and per-pipeline
> `metadata.yaml`, `concurrency_config`, `queue_config`). Verify key names against
> the installed version before deploying.

## Concurrency Levels

| Level | Mechanism | Bounds |
| --- | --- | --- |
| Project jobs | `queue_config.concurrency` (project `metadata.yaml`) | Concurrent pipeline-run jobs the scheduler's job manager executes. |
| Runs per trigger | `concurrency_config.pipeline_run_limit` | Runs of one trigger at once. |
| Runs per pipeline | `concurrency_config.pipeline_run_limit_all_triggers` | Runs of one pipeline across all its triggers. |
| Blocks per run | `concurrency_config.block_run_limit` | Block runs inside one pipeline run (bounds dynamic-block fan-out). |
| When at limit | `concurrency_config.on_pipeline_run_limit_reached: wait \| skip` | Queue or drop the new run. |
| Executor | `executor_type` (local, k8s, ECS, Cloud Run, ACI) + resources | Where block runs execute; cluster capacity is a pool. |

`concurrency_config` can be set in the project `metadata.yaml` (defaults) and
overridden per pipeline.

## What `to_mage` Emits

```yaml
# project metadata.yaml
queue_config:
  concurrency: 32

# <pipeline>/metadata.yaml, for a pipeline with a concurrency key
concurrency_config:
  on_pipeline_run_limit_reached: wait
  pipeline_run_limit_all_triggers: 1
retry_config:
  retries: 2
```

## Native Gaps And Mitigations

Mage limits concurrency per project and per pipeline. It has **no shared named
pools, no cross-pipeline mutual exclusion, and no run priority**. `to_mage` lists
each gap in `warnings`. Mitigate with one of:

1. **Dispatch through `run_fleet` admission.** Disable schedule triggers for the
   fleet and start runs through Mage's trigger API from a dispatcher whose job
   functions call the API and wait for completion; pools, keys, and priority then
   hold exactly as planned.
2. **Partition by executor or project.** Put pipelines that share a scarce resource
   in a project (or executor) whose `queue_config.concurrency` equals that pool's
   limit.
3. **Merge writers.** Two pipelines writing one sink become one pipeline (then
   `pipeline_run_limit_all_triggers: 1` is exact).

## Rules

- **Two levels, one plan.** `queue_config.concurrency` × `block_run_limit` must fit
  the fleet plan; dynamic blocks multiply block runs.
- **Wait, don't skip** for loads that must complete; `skip` is for idempotent
  polling pipelines where a missed tick is harmless.
- **Retries.** `retry_config` retries blocks inside the run, so a retrying run keeps
  its slot — size `queue_config.concurrency` for retry hold time and use
  `delay`/`exponential_backoff` against rate-limited vendors.
- **Triggers.** Stagger schedule trigger start times with `stagger_offsets`; enable
  `skip_if_previous_running` for pipelines that must not overlap themselves.
- **Backfills.** Mage backfills create one run per interval; cap them with the
  pipeline's `concurrency_config` so a backfill cannot take every project slot.
- **Cross-pipeline dependencies** are triggers that start the downstream pipeline
  on upstream success (or a dispatcher), not concurrency config. `to_mage` warns.
- **Scheduler separation.** In production run the scheduler separately from the web
  server so UI load does not stall dispatch; monitor queued runs.

## Failure Modes To Look For

- No `concurrency_config` anywhere: every trigger tick starts a run.
- Dynamic blocks with no `block_run_limit` against a warehouse.
- Several pipelines writing one table, each limited only to itself.
- Assuming per-pipeline limits bound a shared database (they do not).
