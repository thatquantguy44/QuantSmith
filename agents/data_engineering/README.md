# Data Engineering Agents (`data_engineering/`)

The Data Engineering group holds the specialist roles that turn raw sources into
modeled, orchestrated, contract-backed, observable data — the **Data Engineer** role.
It starts with pipeline orchestration, the node the whole chain hangs on.

## Group Workflow

These agents sit downstream of ingestion in the Data Engineer chain (see
`docs/workflows.md` → *Data Engineer*):

```text
data_ingestion/* (or sql-integration-agent) -> data_modeling
  -> pipeline_builder -> data_engineering/pipeline_orchestration
  -> pipeline_concurrency -> tooling/dag_orchestration (Dagster / Mage)
  -> schema_evolution + streaming_cdc (on change) -> backfill_reprocessing (on restatement)
  -> data-prep-agent + data_quality
  -> pipeline_observability (consumes the run manifest)
  -> pipeline_deployment ; data_governance (cross-cutting)
```

## Agents

| Agent | Handles |
| --- | --- |
| `pipeline_orchestration/` | DAG design and execution — dependency ordering, data contracts per step, idempotent partitioned runs, retries, backfill, and a run manifest (spec `0011`). |
| `pipeline_observability/` | Freshness, SLAs, lineage, and data-downtime detection from the run manifest (spec `0019`). |
| `data_modeling/` | Dimensional/warehouse modeling: grain, keys, star/snowflake schemas, slowly-changing and conformed dimensions. |
| `pipeline_builder/` | Compile a source → transform → sink intent into a reviewable DAG with contracts, schedules, retries, backfills, tests, ownership, and a deployment plan. |
| `pipeline_deployment/` | Environment promotion, dry runs, canaries, rollback, state migration, and scheduler-specific deployment. |
| `data_governance/` | Catalog, lineage, access policy, ownership, and classification. |
| `streaming_cdc/` | Idempotent, order-safe CDC; watermarked event-time windows; late data as side output or bitemporal restatement (spec `0111`). |
| `schema_evolution/` | Backward/forward schema-change classification, mode enforcement, safe backward reads, drift detection before load (spec `0111`). |
| `backfill_reprocessing/` | Lineage-exact reprocessing of restatements under fleet limits, old-vs-new diffs, all-or-nothing publication with rollback (spec `0111`). |
| `pipeline_concurrency/` | Hundreds of pipelines at once: global, pool, and mutual-exclusion limits; all-or-nothing admission; priority with a starvation guard; bounded retries; failure isolation; staggered schedules; capacity plan (spec `0101`). Renders to Dagster/Mage via `tooling/dag_orchestration`. |

## Standard

`instructions/pipeline_engineering.md` — DAG, idempotency, retry/backfill, data
contracts, and observability discipline.

## Rules

- Keep each specialist narrow and inspectable.
- Promote broad or risky work into `specs/NNNN-slug/` before implementation.
- Every step declares a data contract; bad data fails the step, it does not flow
  downstream.
- Runtime Python belongs under `src/quantsmith/` (the DAG runner lives at
  `src/quantsmith/pipelines/data_pipeline.py`); agent directories describe roles,
  prompts, instructions, and tasks.

## Worked Examples

- `specs/0011-data-pipeline-orchestration/` — the DAG runner as a spec-driven,
  test-backed runtime workflow.
- `specs/0019-pipeline-observability/` — reads the run manifest for freshness, data
  downtime, SLA, and lineage (`src/quantsmith/pipelines/pipeline_observability.py`).
- `specs/0101-concurrent-pipeline-fleet/` — runs hundreds of pipelines concurrently
  under shared limits, plans capacity, and renders Dagster/Mage config
  (`src/quantsmith/pipelines/pipeline_fleet.py`).
- `specs/0111-change-safe-data-engineering/` — CDC, watermarked windows, schema
  evolution and drift, and lineage-driven reprocessing with atomic publication
  (`streaming_cdc.py`, `schema_evolution.py`, `reprocessing.py`).
