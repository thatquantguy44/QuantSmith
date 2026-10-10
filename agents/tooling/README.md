# Technology & Tooling Agents

This folder groups agents for the specific platforms and tools quants work in —
spreadsheets, BI/reporting, and (as the group grows) compute and data-store
technologies. They bring the SDK's engineering discipline to tools that are often
used without version control, tests, or point-in-time rigor.

## Agents

| Agent | Handles |
| --- | --- |
| `excel/` | Excel models and workbooks: structure, formula auditability, reproducibility, VBA/Power Query safety, model-risk review. Renders the shared dashboard spec via `render_excel` (spec `0016`). |
| `react/` | Web dashboards in React: honest/accessible charts, state and data fetching, secrets kept out of the bundle, reproducible builds. Renders the shared dashboard spec via `render_react` (spec `0016`, `src/quantsmith/pipelines/react_profile.py`). |
| `streamlit_dash/` | Python-native Streamlit apps: caching/state, honest charts, secrets in the environment. Renders + scaffolds the shared spec via `render_streamlit`/`scaffold_streamlit` (spec `0018`). |
| `looker/` | Looker: LookML semantic-model consistency, explores, caching. Renders the shared spec via `render_looker` (spec `0018`). |
| `qlik/` | Qlik: associative model, set analysis, section access. Renders the shared spec via `render_qlik` (spec `0018`). |
| `superset/` | Apache Superset: SQL/dataset governance, Jinja safety, caching. Renders the shared spec via `render_superset` (spec `0018`). |
| `power_bi/` | Power BI datasets and reports: data model (star schema), DAX, refresh/lineage, row-level security, performance. Renders the tool-agnostic dashboard spec via `render_powerbi` (spec `0015`, `src/quantsmith/pipelines/powerbi_profile.py`). |
| `tableau/` | Tableau workbooks and data sources: extracts vs live, LOD/table calcs, honest visualization, publishing/permissions. |
| `dag_orchestration/` | Pipeline orchestrators — `profiles/dagster.md`, `mage.md`, `airflow.md`, `prefect.md`: run- and task-level concurrency, pools, priority, retries, backfill throttling, schedule staggering. Renders a fleet declaration via `to_dagster`/`to_mage` (spec `0101`) and `to_airflow`/`to_prefect` (spec `0112`), `src/quantsmith/pipelines/pipeline_fleet.py`. |
| `dbt/` | dbt projects reviewed from `manifest.json`: ownership, primary-key tests, enforced contracts, backfill-safe incremental models, no wall-clock reads, source freshness, snapshots (`review_manifest`, spec `0112`). |
| `spark/` | Spark: partition sizing, skew and salting for hot keys, determinism lint for reproducible jobs (`src/quantsmith/pipelines/distributed_compute.py`, spec `0112`). |
| `ray_dask/` | Ray and Dask: memory-safe partitions/blocks, hot-key salting, cluster-size-independent seeding, determinism lint (spec `0112`). |

## Shared Principles

Every tooling agent upholds the constitution (`instructions/engineering_principles.md`):

- **Reproducibility (P4).** These tools resist version control and reproducibility.
  Externalize data and logic where possible, capture the inputs (snapshot/refresh
  time), and document how a result can be regenerated. Recommend graduating heavy
  logic out of the tool into tested code when the tool becomes the risk.
- **Point-in-time correctness.** Time-series layouts, refreshes, and joins must not
  introduce look-ahead; use point-in-time data and record as-of times. See
  `instructions/point_in_time.md`.
- **Auditability.** No hidden logic, no magic constants buried in formulas, no
  undocumented manual overrides. A reviewer must be able to trace every number.
- **Secrets stay out (P9).** Data-source credentials live in the platform's secret
  store or gateway, never embedded in a workbook, PBIX, or macro. See
  `agents/secrets_management/`.
- **Honest presentation (P10).** Reports and dashboards must not mislead — correct
  scales, baselines, and uncertainty.

## Where They Fit

Tooling agents span Implementation (building the model/report), Testing
(reconciliation and validation), and Maintenance (refresh, monitoring). Encode the
tool's assumptions and reconciliation checks as spec `AC-*` so the artifact is
traceable, not a black box.

## Growing This Group

Add a tooling agent only when a technology has distinct review rules, failure
modes, or artifact contracts. Libraries and vendors that share those rules should
be profiles/adapters under an agent, not new agents. This keeps selection useful
instead of creating a directory for every package.

### Planned Coverage

| Family | Planned agent or profiles | Quant-specific scope |
| --- | --- | --- |
| Languages | `python/`, `sql/`, `r/`, `cpp/`, `julia/`, `matlab/`, `java_jvm/`, `dotnet_csharp/` | Numerical correctness, performance, packaging, testing, deterministic environments, interoperability. `cpp/` covers C and C++ profiles. |
| Time-series / data stores | `kdb_q/`, `columnar_data/`, `warehouse_lakehouse/` | Temporal joins, tick data, partitioning, query plans, point-in-time semantics, Parquet/Arrow, Snowflake/Databricks/BigQuery/Redshift profiles. |
| Notebooks / research IDEs | `jupyter/`, `research_ide/` | Execution order, hidden state, environment capture, notebook-to-package graduation; VS Code, RStudio, MATLAB, and similar profiles. |
| BI / semantic analytics | `excel/`, `power_bi/`, `tableau/`, `react/`, `streamlit_dash/`, `looker/`, `qlik/`, `superset/` (all built) | Semantic models, calculations, refresh, permissions, performance, reconciliation, honest presentation. |
| Data transformation / orchestration | `dbt/`, `dag_orchestration/` (both built: dbt review; Dagster, Mage, Airflow, Prefect profiles) | Model contracts, DAGs, scheduling, retries, backfills, idempotency, lineage, fleet concurrency; cloud-orchestrator profiles still planned. |
| Distributed compute | `spark/`, `ray_dask/` (both built) | Partitioning, shuffles, skew, determinism, serialization, memory, cluster cost. |
| Dev / production | `git_ci/`, `containers/`, `cloud_quant_platform/` | Reproducible builds, CI/CD, Docker/Kubernetes, secrets, observability, and AWS/Azure/GCP deployment profiles. |
| Optimization / accelerated compute | `optimization_solvers/`, `gpu_compute/` | Solver formulation, tolerances, infeasibility diagnostics, duals; CUDA and accelerator reproducibility/performance. |
| Market connectivity | `market_data_execution/` | FIX/vendor feeds, symbology, calendars, timestamps, throttling, replay, order safety, and audit trails. |

Initial implementation priority should be `python/`, `sql/`, `cpp/`, `r/`,
`jupyter/`, `kdb_q/`, `dbt/`, and `dag_orchestration/`. They cover the highest-value
gaps while the existing Excel, Power BI, and Tableau agents cover common analyst
delivery surfaces.
