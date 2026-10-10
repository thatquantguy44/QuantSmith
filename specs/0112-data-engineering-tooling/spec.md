# Spec: Data-engineering tooling

- **ID:** 0112-data-engineering-tooling
- **Status:** Draft
- **Author:** QuantSmith
- **Approver:** (pending)
- **Last updated:** 2026-10-10

> WHAT and WHY only. Implementation lives in `plan.md`.
> Slice B of the data-engineering expansion (`docs/handoff.md` → reserved `0107`):
> the tools data pipelines actually run on.

## Problem & Context

`0101` declares fleet concurrency once and renders it for Dagster and Mage; teams
on Airflow or Prefect still hand-type pools and limits, which is how limits drift
from what the platform can take. The tooling README has long planned `dbt/`,
`spark/`, and `ray_dask/` agents: dbt projects ship models without primary-key
tests, enforced contracts, or safe incremental settings; distributed jobs stall on
one hot key; and partition- or order-dependent operations make backtests
irreproducible in ways no unit test notices.

## Goals

- Render `0101` fleet limits as Airflow and Prefect configuration, listing every
  limit the target cannot enforce natively.
- Review a dbt project from its compiled `manifest.json` for ownership, primary
  keys, contracts, incremental safety, wall-clock reads, source freshness, and
  snapshot configuration.
- Size partitions, measure skew, size salting for hot keys, and flag determinism
  hazards in PySpark and Dask code.
- Add `tooling/dbt`, `tooling/spark`, `tooling/ray_dask` agents, and Airflow and
  Prefect profiles to `tooling/dag_orchestration`.

## Non-Goals

- Running dbt, Spark, Dask, Ray, Airflow, or Prefect, or importing them.
- Parsing SQL or Python ASTs (manifest fields and line heuristics only).
- Cost modeling (slice C, `0107`).

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The system shall render fleet limits as Airflow config: `parallelism`, one pool per fleet pool and per concurrency key, and per-DAG `pool`, `pool_slots`, `priority_weight`, `retries`, `max_active_runs`; a job needing more than one pool gets its key pool (else tightest pool) with a warning. | must |
| REQ-002 | The system shall render fleet limits as Prefect config: a work-pool limit, a global concurrency limit per pool and per key, priority work queues, and per-flow `concurrency()` acquisitions with deadlock-safe ordering, with a warning where acquisition is not all-or-nothing. | must |
| REQ-003 | The system shall review a dbt `manifest.json` for model ownership, primary-key tests, enforced contracts on public/mart models, incremental `unique_key` / `is_incremental()` / `on_schema_change`, wall-clock reads, source freshness, and snapshot configuration. | must |
| REQ-004 | The system shall attribute dbt tests only to the node they are attached to. | must |
| REQ-005 | The system shall size partitions from bytes and bounds, and report partition skew and the keys too large for any repartition to fix. | must |
| REQ-006 | The system shall size per-key salting that never increases the maximum partition load and conserves row counts. | must |
| REQ-007 | The system shall flag determinism hazards in PySpark/Dask code with line, rule, and reason, suppressing a match when the line shows the fix. | should |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Honest reporting | Every limit an exporter cannot enforce natively appears in `warnings`; heuristics are labeled as heuristics. |
| NFR-002 | Determinism | Same inputs produce the same config, findings, and plans. |
| NFR-003 | No dependencies | Standard library only; no tool installs needed to review or render. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a fleet with pools, slot weights, a key, priorities, retries, and a dependency, when exported to Airflow, then pools, CLI, parallelism, and task args are correct, the key pool wins over capacity pools, the tightest pool is chosen otherwise, and each non-enforced pool and the dependency are warned. | REQ-001, NFR-001 |
| AC-002 | Given the same fleet, when exported to Prefect, then the work-pool limit, global limits, and priority queues are correct; equal-slot jobs get one call; mixed-slot jobs get name-ordered calls with a warning; the dependency is warned. | REQ-002, NFR-001 |
| AC-003 | Given a manifest with clean and defective models, sources, and a snapshot, when reviewed, then every defect is reported with node, rule, and severity, clean nodes are not, and findings are sorted. | REQ-003 |
| AC-004 | Given tests on one model, when another model is reviewed, then they do not count; the `depends_on` fallback works when `attached_node` is absent. | REQ-004 |
| AC-005 | Given sizes and key counts, when planned, then partition counts honor target and bounds, a hot-key distribution is reported skewed with its hot keys, and an even one is not. | REQ-005 |
| AC-006 | Given hot keys, when salted, then each salted share fits a fair partition, max load and skew fall, totals are conserved, and the plan is deterministic; a flat distribution gets no salting. | REQ-006, NFR-002 |
| AC-007 | Given PySpark/Dask code with hazards and their fixes, when linted, then exactly the hazard lines are flagged and fixed lines and comments are not. | REQ-007 |

## Data & Dependencies

- Runtimes: `src/quantsmith/pipelines/pipeline_fleet.py` (`to_airflow`, `to_prefect`),
  `dbt_review.py`, `distributed_compute.py` (standard library only).
- Builds on `0101` (fleet declarations), `0111` (change safety), `0102` (lineage).
- Agents: new `tooling/dbt`, `tooling/spark`, `tooling/ray_dask`; updated
  `tooling/dag_orchestration` (Airflow and Prefect profiles).
- No private data or credentials are written to this repository.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | Airflow's one-pool-per-task drops a limit silently. | Overrun warehouse or API. | Key pool first, tightest pool otherwise, warning for the rest (AC-001). |
| RISK-002 | Prefect sequential acquisitions deadlock. | Stalled flows. | Global name order; all-or-nothing when slots are equal (AC-002). |
| RISK-003 | dbt incremental models duplicate rows on backfill. | Inflated facts. | `unique_key` rule (AC-003). |
| RISK-004 | Salting makes balance worse. | Slower job. | Plan rejected if max load rises (AC-006). |
| RISK-005 | Lint heuristics produce false positives or miss hazards. | Noise or false comfort. | Labeled heuristic; per-line fix suppression; agent reviews matches (AC-007). |
| RISK-006 | Orchestrator or dbt field names drift by version. | Config ignored; rules miss. | Profiles state version assumptions; dry-run before promotion. |

## Assumptions & Open Questions

- Assumption: dbt manifest v10+ field names (`attached_node`, `contract.enforced`).
- Open question: a CLI (`quantsmith-dbt-review target/manifest.json`); Spark plan
  (`EXPLAIN`) parsing for shuffle sizing.

## Exceptions

None.
