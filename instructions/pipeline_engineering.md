# Pipeline Engineering Standard

How to build data pipelines that are ordered, contract-backed, idempotent, retry-safe,
backfillable, and observable. This is the standard behind the
`data_engineering/pipeline_orchestration` agent and the
`specs/0011-data-pipeline-orchestration/` runtime.

## Why This Standard

Ad-hoc load scripts fail in predictable ways: they run steps before their inputs are
ready, let bad data flow into derived tables, double-count on re-run, retry forever
(or not at all), and leave no record of what ran. This standard makes those failure
modes structurally impossible in a QuantSmith pipeline.

## The Pipeline Contract

1. **DAG, not a script.** Each step declares its dependencies. The graph is acyclic
   and complete (no references to unknown steps), and execution follows dependency
   order. A step whose inputs are not ready does not run.
2. **A data contract per step.** Every step's output declares its schema — columns,
   types, and required (non-null) fields. Output is validated against the contract
   *before* any downstream step consumes it.
3. **Contract violations fail fast.** A violation fails the step and is recorded. It
   is never retried (bad data is not transient) and never passed downstream.
4. **Idempotent partitions.** Execution is partitioned (e.g., by date). A completed
   partition is skipped on re-run; a forced recompute is deterministic — no
   duplication, no drift.
5. **Bounded retries.** Transient failures are retried up to a max attempt count; a
   persistent failure is recorded, not swallowed.
6. **Partition isolation.** A failure in one partition stops that partition's
   downstream steps but does not block other partitions.
7. **Backfill the gaps only.** A backfill runs only the partitions that are missing,
   not the whole history.
8. **Observability by default.** Every run emits a manifest recording the status of
   each (step, partition), the attempts, and any violations — the surface a freshness
   or SLA check reads.

## Checklist

- [ ] Dependency graph is acyclic and complete.
- [ ] Execution is in dependency order.
- [ ] Every step has an output data contract, enforced before downstream use.
- [ ] Contract violations fail the step and are not retried.
- [ ] Re-running a completed partition is a no-op; recompute is deterministic.
- [ ] Retries are bounded; persistent failures are recorded.
- [ ] Backfill runs only missing partitions.
- [ ] A run manifest records per-(step, partition) status.

## Concurrency At Fleet Scale

The contract above makes *one* pipeline correct. Production runs hundreds at once
against the same warehouse, vendor quotas, and sink tables, and the failures change
character: connection-pool exhaustion, rate-limit bans, two writers on one
partition, retry storms, starved large jobs. The fleet contract (spec `0101`):

1. **Declare the fleet.** A global run limit, a named pool for every scarce shared
   resource (with slot weights for heavy jobs), and a mutual-exclusion key for
   every sink more than one pipeline writes. Limits come from real capacity minus
   headroom, never orchestrator defaults.
2. **All-or-nothing admission.** A run starts only when the global limit, every pool
   it needs, and its key all have room. Nothing holds one resource while waiting
   for another, so the fleet cannot deadlock. A job whose demand exceeds its pool is
   rejected at declaration, not left to hang.
3. **Priority without starvation.** Higher priority dequeues first and small jobs
   may use idle capacity, but a job overtaken too often jumps the queue and
   reserves capacity.
4. **Retries re-enter admission.** Bounded attempts; a retry waits for capacity like
   a first attempt, so an outage does not multiply load.
5. **Failure isolation.** A permanent failure marks its transitive dependents
   `upstream_failed`; unrelated pipelines keep running.
6. **Stagger schedules.** Hash-based start offsets spread the fleet over a window and
   do not move when pipelines are added or removed.
7. **Plan before deploy.** A deterministic capacity plan reports makespan vs. a lower
   bound, per-pool utilization, and which constraint caused the queue wait.
8. **Render, don't retype.** Orchestrator config (Dagster, Mage) is generated from
   the same declaration; every limit the orchestrator cannot enforce natively is
   listed and mitigated, never silently dropped.

Fleet checklist:

- [ ] Every shared resource is a pool; every multi-writer sink has a key.
- [ ] No job's slot demand exceeds its pool.
- [ ] Retries are bounded and go back through admission.
- [ ] Dependents of a failed pipeline are `upstream_failed`, not run on stale inputs.
- [ ] Schedules are staggered; the capacity plan fits the window.
- [ ] Rendered orchestrator config has every warning resolved.

## Change-Safe Pipelines

Data changes after it lands: streams replay and arrive late, vendors change
schemas, and sources are restated. The change-safety contract (spec `0111`):

1. **CDC by sequence.** Apply each change event only if its per-key sequence is
   newer than the one already applied; replays and stale events are counted, not
   applied. Prefer full row images; partial updates are order-safe only in sequence.
2. **Windows on event time, under a watermark.** Emit a window only when the
   watermark (max event time minus allowed lateness) passes its end. Every late
   event goes to a side output or a numbered restatement recorded with its
   knowledge time — never dropped.
3. **Classify every schema change.** Know whether it breaks new readers on old data
   (backward) or old readers on new data (forward); enforce the mode that matches
   the upgrade order; replay history only under a backward-compatible schema.
4. **Check drift before load.** Unknown, missing, null, and mistyped columns are
   counted per delivery; drifting files are quarantined, not coerced.
5. **Reprocess from lineage.** A restatement re-runs exactly what is downstream of
   it, under fleet limits, as new immutable versions.
6. **Publish all-or-nothing.** Compare old and new by key; move every published
   pointer at once only when every gate passes; keep the previous pointers.

Change-safety checklist:

- [ ] CDC events carry a per-key sequence and are applied through the guard.
- [ ] Windows use event time and a justified allowed lateness; late data is accounted for.
- [ ] Schema changes are classified and checked against the declared mode.
- [ ] Deliveries are drift-checked before load.
- [ ] Restatements are reprocessed from lineage and published atomically.

## Runtime & Spec

- Runtime: `src/quantsmith/pipelines/data_pipeline.py`
  (`Pipeline`, `Step`, `DataContract`, `run`, `backfill`, `RunManifest`).
- Spec: `specs/0011-data-pipeline-orchestration/`.
- Design-time runtime: `src/quantsmith/pipelines/pipeline_builder.py`
  (`compile_intent`, `review_readiness`, `render_pipeline_manifest`,
  `to_pipeline`), spec `specs/0042-pipeline-builder/` — checks an intent against
  this checklist before implementations exist, and renders the manifest below.
  It reviews *declarations*, not implementations.
- Contract template: `templates/data/data_contract.md`.
- Manifest template: `templates/data/pipeline_manifest.md`; worked example at
  `specs/0042-pipeline-builder/pipeline_manifest.md`.
- Consumers/handoffs: `data_ingestion/*`, `data-prep-agent`, `data_quality`, and a
  future `pipeline_observability` node.
- Fleet runtime: `src/quantsmith/pipelines/pipeline_fleet.py` (`Fleet`, `FleetJob`,
  `Pool`, `FleetConfig`, `simulate`, `run_fleet`, `stagger_offsets`, `to_dagster`,
  `to_mage`), spec `specs/0101-concurrent-pipeline-fleet/`; agents
  `data_engineering/pipeline_concurrency` and `tooling/dag_orchestration`
  (Dagster and Mage profiles).
- Change-safety runtimes: `src/quantsmith/pipelines/streaming_cdc.py`,
  `schema_evolution.py`, `reprocessing.py`, spec
  `specs/0111-change-safe-data-engineering/`; agents
  `data_engineering/streaming_cdc`, `schema_evolution`, `backfill_reprocessing`.
