# Plan: Concurrent pipeline fleet

- **Spec:** 0101-concurrent-pipeline-fleet (`spec.md`)
- **Status:** Approved
- **Author:** QuantSmith
- **Last updated:** 2026-10-10

> HOW. Requires the approved `spec.md`.

## Approach

One admission policy, three surfaces. `_Admission` (slot accounting) and `_select`
(ordering, skip-ahead, starvation guard) are shared by the capacity plan
(`simulate`), the real run (`run_fleet`), and — through the same declarations — the
orchestrator exporters (`to_dagster`, `to_mage`). The plan cannot promise something
the run would not do, and the exported config is derived from the same `Fleet`
object rather than retyped by hand. Pure standard library so the reference runs
anywhere and imports neither orchestrator.

## Agent Routing

```text
data_engineering/pipeline_builder            # per-pipeline intent and contracts (0042)
  -> data_engineering/pipeline_orchestration  # one pipeline, correct (0011)
  -> data_engineering/pipeline_concurrency    # many pipelines, safely concurrent (0101)
  -> tooling/dag_orchestration                # Dagster / Mage profiles (to_dagster / to_mage)
  -> data_engineering/pipeline_deployment     # dry-run, canary, promote the config
  -> data_engineering/pipeline_observability  # observed durations feed est_seconds back
```

## Architecture & Components

- `Pool(name, limit)`, `FleetJob(name, fn, deps, pools, concurrency_key, priority,
  max_attempts, est_seconds, owner)`, `FleetConfig(max_concurrent, pools, max_bypass)`.
- `Fleet(jobs, config)` — validation at construction (REQ-001), deterministic
  topological order (Kahn's algorithm, submission order as tie-break).
- `_Admission` — global, per-pool (slot-weighted), and key accounting; `blocker`
  names the first constraint that does not fit; `acquire`/`release` are
  all-or-nothing (REQ-002).
- `_select` — priority then submission order; jobs that do not fit are skipped so
  idle capacity is used; each skipped job counts how often it is overtaken; at
  `max_bypass` it jumps the queue and reserves capacity (REQ-003).
- `simulate(fleet) -> SchedulePlan` — discrete-event simulation over `est_seconds`;
  time-weighted wait attribution per constraint; lower bound =
  max(critical path, total work / global limit, per-pool slot-seconds / limit) (REQ-005).
- `run_fleet(fleet) -> FleetManifest` — single coordinator thread owns admission;
  a `ThreadPoolExecutor` only runs job functions; `FIRST_COMPLETED` wakeups; retries
  re-queued through `_select`; permanent failures cascade `upstream_failed` (REQ-004).
- `stagger_offsets(names, window)` — SHA-256 of the name modulo the window (REQ-006).
- `to_dagster(fleet)`, `to_mage(fleet)` — config dicts plus `warnings` (REQ-007).

## Interfaces & Data Contracts

- Dagster: `dagster_yaml.concurrency.runs.{max_concurrent_runs, tag_concurrency_limits}`
  with one tag limit per pool (`quantsmith/pool/<name>`) and a per-unique-value limit
  of 1 on `quantsmith/concurrency_key`; per-job run tags `dagster/priority`,
  `dagster/max_retries`, pool and key tags; `run_retries.enabled`.
- Mage: `project_metadata.queue_config.concurrency`; per pipeline
  `concurrency_config.{on_pipeline_run_limit_reached, pipeline_run_limit_all_triggers}`
  and `retry_config.retries`.
- Both: `warnings: list[str]` naming every semantic not enforced natively.
- Key names follow current Dagster (1.10+ `concurrency:` block) and Mage project
  metadata docs; the profiles say to verify against the installed version.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Unfittable jobs rejected at construction; all-or-nothing admission; one shared policy. |
| P5 Reversibility | yes | Config is generated, diffable, and regenerated from the declaration. |
| P6 Observability | yes | Manifest peaks per pool, admission order, attempts; plan attributes wait. |
| P9 Security & data | yes | Error class only in manifests; no credentials, no network calls. |
| P10 Honest reporting | yes | Lossy exporter mappings are listed, never dropped. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `Fleet.__init__`, `Fleet._toposort` | T-001 |
| REQ-002 | `_Admission` | T-002 |
| REQ-003 | `_select` ordering + overtake guard | T-002 |
| REQ-004 | `run_fleet` retry and cascade | T-003 |
| REQ-005 | `simulate`, `SchedulePlan` | T-004 |
| REQ-006 | `stagger_offsets` | T-005 |
| REQ-007 | `to_dagster`, `to_mage` | T-006 |
| NFR-001 | shared admission; 300-pipeline gauge test | T-002, T-003 |
| NFR-002 | pure discrete-event simulation | T-004 |
| NFR-003 | `warnings`; `JobResult.error_type` | T-003, T-006 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Admission | All-or-nothing reservation | Acquire pools one at a time | Partial holds deadlock under contention (RISK-001). |
| Ordering | Priority + skip-ahead + overtake guard | Strict head-of-line FIFO | FIFO idles capacity behind a blocked wide job; pure skip-ahead starves it. |
| Executor | Threads, single coordinator | Processes / asyncio | Pipelines are I/O bound against external systems; one coordinator keeps accounting lock-free. |
| Dagster mapping | Run-level tag limits | Op-level `pool=` | A run may need several pools; ops take one pool. Op pools stay an option in the profile. |
| Mage gaps | Report, and dispatch through `run_fleet` | Pretend per-pipeline limits cover pools | Mage has no shared named pools or cross-pipeline keys (NFR-003). |
| Retry semantics | Re-enter admission | Retry in place holding slots | In-place retries hold capacity during outages (RISK-003). |

## Validation Strategy

- AC-001..AC-007 map one-to-one to `tests/test_pipeline_fleet.py` (see `tasks.md`).
- AC-002 measures concurrency *inside* the job functions with an independent gauge,
  so the evidence does not depend on the runtime's own peak counters.

## Rollout, Observability & Rollback

A library plus generated config. Rollout: plan → export → `pipeline_deployment`
dry-run in staging → promote. Rollback: re-render the previous fleet declaration
and redeploy. Observed durations from run manifests replace `est_seconds` estimates
so the plan converges on reality.

## Open Questions

- Durable queue backend and `quantsmith-fleet` CLI.
- Airflow and Prefect exporters behind the same interface.
