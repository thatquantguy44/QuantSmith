# Plan: Data-engineering tooling

- **Spec:** 0112-data-engineering-tooling (`spec.md`)
- **Status:** Draft
- **Author:** QuantSmith
- **Last updated:** 2026-10-10

> HOW. Requires the approved `spec.md`.

## Approach

Extend `0101`'s exporter family with two functions that follow its rule (render
from the declaration, warn on every lossy mapping), and add two small review
modules that read artifacts teams already have: dbt's compiled `manifest.json`
and their PySpark/Dask source. Standard library only.

## Agent Routing

```text
data_engineering/pipeline_concurrency (0101) -> tooling/dag_orchestration
    profiles: dagster.md, mage.md, airflow.md, prefect.md  (to_airflow / to_prefect)
data_engineering/data_modeling -> tooling/dbt              (review_manifest)
data_engineering/pipeline_builder -> tooling/spark | tooling/ray_dask
    (plan_partitions, skew_report, salting_plan, lint_determinism)
```

## Architecture & Components

- `to_airflow(fleet)`: `airflow_cfg.core.parallelism`; pools `quantsmith_<pool>` and
  `quantsmith_key_<key>` (1 slot) with `airflow pools set` commands; per DAG
  `max_active_runs: 1` and `default_args` (`priority_weight` + `weight_rule:
  absolute`, `retries`, `pool`, `pool_slots`, `owner`); key pool wins, else tightest pool.
- `to_prefect(fleet)`: `work_pool.concurrency_limit`; global limits
  `quantsmith-pool-<pool>` / `quantsmith-key-<key>` with `prefect gcl create`; work
  queues `quantsmith-p<priority>` ranked 1..n; per flow `concurrency` acquisitions
  (one call when slot counts are equal, else one per limit in name order), `retries`.
- `dbt_review.review_manifest(manifest, mart_dirs)`: tests indexed by
  `attached_node` (fallback: single model in `depends_on`); rules ownership,
  primary_key, contract, incremental_unique_key, incremental_filter,
  incremental_schema_change, wall_clock, source_freshness, snapshot.
- `distributed_compute`: `plan_partitions`, `partition_of` (SHA-256), `skew_report`
  (max/median, hot keys > fair share), `salting_plan` (ceil(count/fair) salts,
  rejected if worse), `lint_determinism` (rule table with per-line fix patterns).

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Exporters derive from the declaration; salting cannot worsen balance. |
| P6 Observability | yes | Findings carry node/line, rule, severity, and reason. |
| P9 Security & data | yes | No network, credentials, or tool installs. |
| P10 Honest reporting | yes | Lossy mappings warned; heuristics labeled (NFR-001). |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `to_airflow` | T-001 |
| REQ-002 | `to_prefect` | T-001 |
| REQ-003 | `review_manifest` rules | T-002 |
| REQ-004 | `_tests_by_model` | T-002 |
| REQ-005 | `plan_partitions`, `skew_report` | T-003 |
| REQ-006 | `salting_plan` | T-003 |
| REQ-007 | `lint_determinism` | T-003 |
| NFR-001..003 | warnings; sorted outputs; stdlib only | T-001..T-004 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Airflow multi-pool jobs | Key pool, else tightest, plus warning | Pick the first pool | Exclusion protects data integrity; the tightest pool is the likeliest to overrun. |
| Prefect mixed slots | One call per limit, name order | Calls grouped by slot count | Grouping by slot count lets two jobs acquire in opposite orders (deadlock). |
| dbt input | Compiled manifest | Parse `.sql`/`.yml` | The manifest is the resolved truth dbt itself uses. |
| Skew hash | SHA-256 | Reimplement Murmur3 | Balance statistics are representative; exact ids are engine-specific. |
| Determinism check | Line heuristic | AST analysis | Small, dependency-free; findings are reviewed by the agent. |

## Validation Strategy

AC-001..AC-007 map to `tests/test_data_eng_tooling.py` (see `tasks.md`).

## Rollout, Observability & Rollback

Library functions and agent guidance. Exported orchestrator config is dry-run via
`pipeline_deployment` before promotion; dbt review runs in CI on the project's
manifest. Rollback is reverting the generated config.
