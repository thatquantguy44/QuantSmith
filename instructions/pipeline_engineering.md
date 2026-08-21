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
