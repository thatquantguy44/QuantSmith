# Future Features

The running backlog of features to build. Add new ideas as rows; promote one to a
full `specs/NNNN-slug/` when work starts (see `docs/handoffs/README.md`).

**Status:** `proposed` → `in-progress` → `done`.
**Priority:** P0 (highest) · P1 (high) · P2 (medium) · P3 (nice-to-have).

## Agents

| Feature | What it adds | Priority | Status |
| --- | --- | --- | --- |
| `agents/optimization/*`, `agents/machine_learning/*`, `agents/deep_learning/*` | Highest-priority optimizer-agent expansion plus ML/DL specialist surfaces for stringing finance, operations, and technology workflows into specs and runtime handoffs. Runtime workflows shipped: `specs/0006-ml-return-forecasting/` (ML/DL), `specs/0007-portfolio-construction/` (QP), `specs/0013-optimization-solvers/` (LP/MILP/flow/DP), `specs/0034-cardinality-constrained-portfolio/` (MILP selects, `0007`'s QP sizes, a disclosed two-stage heuristic), `specs/0035-funding-ladder/` (bipartite tenor-to-obligation network on `0013`'s `min_cost_flow`; general treasury/cash, not securities-financing), `specs/0036-multi-period-rebalancing/` (discretized single-position DP on `0013`'s `solve_dp`) — every `0013` solver now has a shipped application — and `specs/0041-ranking-forecast/` (pairwise ranking-loss variant of `0006`, composing its labels/features/folds/evaluation unmodified). Optional follow-ups: a listwise ranking loss, an RL-flavored example | P0 | done |
| `agents/portfolio_management/*` | End-to-end portfolio lifecycle agents for mandate, universe, signal intake, allocation policy, construction oversight, rebalance implementation, risk budgeting, compliance, attribution, liquidity/cash, tax/transition, monitoring, and governance. Shipped with shared standard `instructions/portfolio_management.md`; runtime specs can promote specific workflows as needed | P0 | done |
| `agents/data_engineering/data_modeling/` | Dimensional/warehouse modeling: star/snowflake schemas, slowly-changing dimensions, grain. Agent shipped (spec `0019` group build-out); executable runtime as needed | P1 | in-progress |
| `agents/data_engineering/pipeline_orchestration/` | dbt-style models, DAGs, scheduling, incremental loads, backfills, idempotency. Shipped: agent + `instructions/pipeline_engineering.md` + spec `specs/0011-data-pipeline-orchestration/` + tested runtime `src/quantsmith/pipelines/data_pipeline.py` (DAG, contracts, idempotency, retries, backfill, run manifest) | P1 | done |
| `agents/data_engineering/pipeline_observability/` | Data freshness, SLAs, lineage, data-downtime detection. Shipped: agent + spec `specs/0019-pipeline-observability/` + tested runtime `src/quantsmith/pipelines/pipeline_observability.py` (consumes the `0011` run manifest) | P2 | done |
| `agents/data_engineering/data_governance/` | Catalog, lineage, access policy, ownership. Agent shipped; executable runtime as needed | P3 | in-progress |
| `agents/data_engineering/pipeline_builder/` | Compile a source/transform/sink intent into a reviewable DAG, data contracts, schedules, retries, backfills, tests, ownership, and deployment plan. **Shipped**: agent + spec `specs/0042-pipeline-builder/` + tested runtime `src/quantsmith/pipelines/pipeline_builder.py` (`compile_intent` validating via `0011`'s own toposort, `review_readiness`, `render_pipeline_manifest`, `to_pipeline`). Ships the repo's first pipeline-manifest artifact, so the `pipeline-contract` gate validates real content instead of no-opping | P1 | done |
| `agents/data_engineering/pipeline_deployment/` | Environment promotion, dry runs, canaries, rollback, state migration, and scheduler-specific deployment adapters. Agent shipped; executable runtime as needed | P1 | in-progress |
| `agents/analytics/metrics_semantic_layer/` | Canonical KPI/metric definitions (semantic layer) — the biggest data-analyst consistency win. Shipped: agent + `instructions/metrics_semantic_layer.md` + spec `specs/0008-metrics-semantic-layer/` + tested runtime `src/quantsmith/pipelines/metrics_semantic_layer.py` | P1 | done |
| `agents/analytics/experimentation/` | A/B testing, power analysis, causal caveats. Shipped: agent + spec `specs/0009-experimentation/` + tested runtime `src/quantsmith/pipelines/experimentation.py` (power/sample-size, SRM guard, p-value/CI consistency, power-gated verdict). Follow-ups: continuous-metric (t-test), sequential/Bayesian, CUPED | P2 | done |
| `agents/analytics/data_storytelling/` + `dashboard_design/` | Data Analyst communication layer — narrative (situation → insight → action) and tool-agnostic dashboard spec. Shipped: two agents + `instructions/data_storytelling.md` + spec `specs/0014-data-analyst-storytelling/`; reuse `0008`/`0009`/`0010`, hand off to `reporting-agent` and tool dashboard agents | P1 | done |
| BI-tool profiles: `tooling/streamlit_dash`, `tooling/looker`, `tooling/qlik`, `tooling/superset` | Thin profiles that render the shared dashboard spec from `dashboard_design`. **Shipped** (`specs/0018-remaining-dashboard-profiles/`): renderers + four agents; Streamlit also has an executable scaffolder. With Power BI/Excel/React (`0015`/`0016`), the shared spec now renders to seven targets. Remaining: executable emitters for Looker/Superset/Qlik | P2 | done |
| `adapters/dashboard_render/` provider implementations | Executable providers behind the contract. Shipped: `scaffold_react`, `write_xlsx` (specs `0017`), and `scaffold_streamlit` (`0018`). Remaining: `powerbi_publish`, Looker/Superset/Qlik emitters, and a hosted-deploy step | P2 | in-progress |
| `agents/analytics/data_visualization/` | Single-chart encoding/color/accessibility, split from `dashboard_design` if it grows too broad (spec `0014` track) | P3 | proposed |
| `agents/alerts/alert_policy/` | Threshold, anomaly, composite, and missing-event policies with severity, suppression, cooldown, and market-calendar rules. **Shipped**: agent + `instructions/alerting.md` + spec `specs/0020-alerting/` + tested runtime `src/quantsmith/pipelines/alerting.py` (`evaluate_policies`) | P1 | done |
| `agents/alerts/alert_router/` | Ownership, deduplication, grouping, rate limits, escalation, and channel selection. **Shipped**: agent + `route` (spec `0020`); delivery via `adapters/alert_delivery/` | P1 | done |
| `agents/alerts/incident_notification/` | Actionable notifications, acknowledgement/recovery lifecycle, evidence and runbook links. **Shipped**: agent (spec `0020`) | P1 | done |
| Provider implementations for `adapters/alert_delivery/` | Executable email, Slack, Teams, PagerDuty/Opsgenie, SMS/push, webhook, Jira/ServiceNow/Linear integrations behind the adapter contract. **All seven shipped**: email + webhook (spec `0032`), then Slack, Teams, ticketing, PagerDuty/Opsgenie, SMS/push (spec `0037`) — completing the adapter's own Recommended Starting Set. Deterministic payload construction, redaction, secret guard, injectable `transport` seam (`dry_run=True` default, no network code in the SDK itself); `pagerduty_opsgenie`/`sms_push` structurally enforce their own severity-routing rules, `sms_push` also enforces a short-message length cap | P1 | done |
| `agents/monitoring/pipeline_monitoring/` | DAG status, dependencies, freshness, latency, backlogs, retries, partial writes, idempotency, and SLOs. **Shipped**: agent (reads the `0019` run manifest) | P1 | done |
| `agents/monitoring/model_signal_monitoring/` | Quality, calibration, feature drift, alpha decay, turnover/capacity, and regime change. **Shipped**: agent + `instructions/monitoring.md` + spec `specs/0021-signal-monitoring/` + tested runtime `src/quantsmith/pipelines/signal_monitoring.py` | P1 | done |
| `agents/monitoring/infrastructure_cost_monitoring/` | Compute, memory, storage, API quota, market-data spend, and cost-per-run guardrails. Agent shipped; executable cost runtime is a follow-up | P2 | in-progress |
| Normalize `agents/quant_analyst/` | Keep `agents/quant_analyst/` as a four-file agent contract and promote runtime Python into `src/quantsmith/` | P2 | shipped |
| `agents/role_operations/*` | 14-agent roster absorbing a quant/data-science lead's operational toil (meetings, status, scaffolding, research scans, demo prep, governance docs) so more time goes to model scoping and research. **Phase 1 shipped** (spec `0024`): `meeting_to_action`, `status_rollup`, `rapid_scaffolder`, `prior_art_scanner`, configurable via a local-only `role_context.yml` (never committed; `role-context` gate). Data-provenance guardrail also shipped (spec `0025`). **Phase 2 shipped** (spec `0029`): `demo_narrative_packager`, `tough_question_rehearsal`, `experiment_ledger`. **Phase 3 shipped** (spec `0030`): `model_card_drafter`, `audit_trail_keeper`, `governance_readiness_checklist`, `second_look_backtest_reviewer`, `build_handoff_writer`, `alert_triage` — added `templates/docs/decision_log.md`; the two handoff-style agents defer to (never replace) `agents/backtest_review/` and `agents/alerts/alert_router/`/`incident_notification/`. Roster complete | P1 | done |
| `agents/optimization/model_plugin_registration/` | Register an already-built internal optimization model so `optimization/` agents can route to and review it, without the SDK holding its logic. **Shipped**: agent + `adapters/model_plugin/` contract + spec `specs/0026-model-plugin-adapter/`. Remaining: an executable dispatcher once a concrete invocation target exists | P2 | in-progress |
| `sources/` data source catalog | Centralized, per-source registry (APIs/DBs/feeds) with quality, point-in-time, and credential-pointer metadata. **Shipped**: schema template + gate + spec `specs/0027-source-catalog/`, populated with six public sources (FRED, BLS, EIA, BEA, Census, SEC EDGAR); wired into `data_contract.md`, `credential_access`, `data_ingestion` | P2 | in-progress |
| `agents/securities_financing/financing_cost_analysis/` | All-in cost-of-carry decomposition, financing-aware returns, understated-backtest flags, rate-shock sensitivity, capacity findings. **Shipped**: tested runtime `src/quantsmith/pipelines/financing_cost_analysis.py` + spec `specs/0028-financing-cost-analysis/`, reconciling with `0023`'s securities-lending vocabulary by value. `repo_financing`/`collateral_management` remain agent-contract-only | P1 | done |
| `agents/asset_classes/*` | Mechanics-only agents (equities, fixed income/rates/credit, FX, commodities, digital assets) feeding `trading_strategies/` and `securities_financing/` with point-in-time-correct market-structure inputs. **Shipped**: 5 agents + `instructions/asset_class_mechanics.md` + spec `specs/0022-asset-class-mechanics-agents/` | P1 | done |
| `agents/economists/*` | Macro backdrop for quant/PM workflows: indicator tracking, policy reads, regime classification, cross-asset translation, forward scenarios, and two report writers (recurring brief + periodic outlook). **Shipped**: 7 agents + `instructions/macro_economic_analysis.md` + `templates/docs/macro_backdrop_report.md` + spec `specs/0033-economists-agents/`; reclaims a stray, unwired `agents/economists/` placeholder left by an earlier parallel merge. Draws on `sources/{fred,bls,bea,census,eia}.yml` (`0027`); hands off to `trading_strategies/macro_multi_asset`, `portfolio_management/*`, and `risk` rather than replacing them | P1 | done |
| `agents/securities_financing/securities_lending/` runtime | Borrow-rate classification, LP inventory optimization, concentration risk. **Shipped**: promoted the existing `quant/agentic_quant/sec_lending_workflow.py` to a tested spec (`specs/0023-securities-lending-workflow/`), fixing a balance-sheet-cap bug in the greedy fallback along the way | P1 | done |
| `instructions/data_provenance.md` + `templates/docs/synthetic_data_disclosure.md` | Real-data-first priority stack and complete synthetic-data disclosure for any agent-produced data/visual content. **Shipped**: standard + template + `data-provenance` gate, spec `specs/0025-data-provenance-guardrail/`; wired into `role_operations` and cross-referenced from `dashboard_design`/`data_storytelling` | P1 | done |

## Technology & Tooling

Tooling agents are grouped by distinct risk and review contracts. Vendor variants
belong under profiles/adapters unless they require materially different behavior.

| Feature | What it adds | Priority | Status |
| --- | --- | --- | --- |
| `agents/tooling/python/` | Packaging, typing, vectorization, numerical stability, testing, environments, profiling | P1 | proposed |
| `agents/tooling/sql/` | Dialect-aware query design, temporal joins, plans, parameterization, transactions, warehouse cost | P1 | proposed |
| `agents/tooling/cpp/` | C/C++ numerical correctness, memory/undefined behavior, concurrency, profiling, Python bindings | P1 | proposed |
| `agents/tooling/r/` | Reproducible environments, statistical workflows, packages, testing, R/Python interoperability | P1 | proposed |
| `agents/tooling/jupyter/` | Execution order, hidden state, parameterized runs, environment capture, notebook graduation | P1 | proposed |
| `agents/tooling/kdb_q/` | Tick/time-series storage, temporal joins, partitioning, symbology, query performance | P1 | proposed |
| `agents/tooling/dbt/` | Model contracts, tests, incremental models, snapshots, lineage, semantic definitions | P1 | proposed |
| `agents/tooling/dag_orchestration/` | Airflow/Dagster/Prefect/cloud scheduler profiles; DAGs, retries, backfills, idempotency | P1 | proposed |
| `agents/tooling/julia/`, `matlab/`, `java_jvm/`, `dotnet_csharp/` | Additional research, numerical, and enterprise-runtime coverage | P2 | proposed |
| `agents/tooling/looker/`, `qlik/`, `superset/`, `streamlit_dash/` | Remaining common governed BI and Python-native analytics surfaces — **shipped** (spec `0018`); each renders the shared dashboard spec | P2 | done |
| `agents/tooling/warehouse_lakehouse/` | Snowflake, Databricks, BigQuery, Redshift profiles with PIT, partition, cost, and governance review | P1 | proposed |
| `agents/tooling/columnar_data/` | Parquet/Arrow/Polars/DuckDB profiles; schema, partitioning, lazy execution, interoperability | P2 | proposed |
| `agents/tooling/spark/`, `ray_dask/` | Distributed compute plans, skew/shuffle diagnostics, determinism, memory and cost | P2 | proposed |
| `agents/tooling/git_ci/`, `containers/`, `cloud_quant_platform/` | CI/CD, containers/Kubernetes, and AWS/Azure/GCP deployment profiles | P2 | proposed |
| `agents/tooling/optimization_solvers/`, `gpu_compute/` | Solver diagnostics and accelerated numerical-compute rigor | P2 | proposed |
| `agents/tooling/market_data_execution/` | FIX/vendor feeds, timestamps, calendars, throttling, replay, order safety, audit | P1 | proposed |

## Instructions (backing standards)

| Feature | What it adds | Priority | Status |
| --- | --- | --- | --- |
| `instructions/risk_management.md` | Standard behind the `risk` agent (exposure, concentration, tail/drawdown, stress, monitorable limits). **Shipped** (spec `0031`) | P2 | done |
| `instructions/data_ingestion.md` | Shared standard behind `data_ingestion/*` (source-catalog lookup, credential resolution, snapshotting, PIT, load-time validation), replacing three independently-restated copies of the same rules. **Shipped** (spec `0031`) | P2 | done |
| `instructions/reproducibility.md` | Operationalizes P4 for the `repro` gate and run card, stating the gate's actual (heuristic) mechanism honestly. **Shipped** (spec `0031`) | P2 | done |
| `instructions/monitoring.md` | Standard behind `maintenance_monitoring` and the monitoring plan | P3 | proposed |
| `instructions/pipeline_engineering.md` | DAG, idempotency, retry/backfill, environment, data-contract, lineage, and deployment standard | P1 | proposed |
| `instructions/alerting.md` | Channel-neutral alert schema, severity, routing, suppression, acknowledgement, escalation, and privacy. **Shipped** (spec `0020`) | P1 | done |
| `instructions/portfolio_management.md` | Standard behind the portfolio-management lifecycle agents, including mandate, universe, signal intake, allocation, implementation, risk, compliance, attribution, liquidity, tax, and governance checks | P0 | done |

## Gates

| Feature | What it adds | Priority | Status |
| --- | --- | --- | --- |
| `hooks/stages/ingestion-snapshot-check.sh` | Verify ingestion captures a snapshot/checksum | P3 | proposed |
| `hooks/stages/pipeline-contract-check.sh` | Verify DAG ownership, inputs/outputs, schedule, retry/backfill, idempotency, and runbook metadata. **Shipped**: validates a pipeline manifest (`templates/data/pipeline_manifest.md`); enforced in CI, skips when absent | P2 | done |
| `hooks/stages/alert-contract-check.sh` | Verify event schema, owner, severity, deduplication, runbook, redaction, and test route. **Shipped** (`templates/data/alert_policy.md`; enforced in CI, skips when absent) | P2 | done |
| `hooks/stages/monitoring-coverage-check.sh` | Verify each production risk has a metric, threshold/baseline, owner, alert, runbook, and review cadence. **Shipped** (`templates/docs/model_monitoring_plan.md`; enforced in CI, skips when absent) | P2 | done |
| Stricter notebook-output gate | Beyond the current `implementation` check | P3 | proposed |
| Enforce `leakage` in CI | Currently advisory (heuristic); revisit once patterns are tuned | P3 | proposed |

## Docs & Packaging

| Feature | What it adds | Priority | Status |
| --- | --- | --- | --- |
| Expand `docs/adoption_guide.md` | Full walkthrough with per-project-type recipes — **shipped** (covers the `quantsmith` package and the scaffold, gate wiring, and recipes) | P1 | done |
| Copier-style sync CLI | Selective install + update per `docs/packaging.md` | P2 | proposed |
| More worked examples | **Done.** Forecast spec shipped (`specs/0006-ml-return-forecasting/`). Risk-model spec shipped (`specs/0038-factor-risk-model/`, `factor_risk_model.py`): variance decomposition, Euler risk attribution, concentration, linear stress loss, operationalizing `instructions/risk_management.md`. Ingestion example shipped (`specs/0039-ingestion-data-contract/`, `ingestion_data_contract.py`): validates a pulled row set against a declared contract and renders a `data_contract.md` populated with real, computed results | P2 | done |
| `CHANGELOG.md` + versioning policy | **Shipped** — Keep a Changelog format + a SemVer-style policy in `CHANGELOG.md`; `docs/packaging.md` updated to the active package phase | P2 | done |
| Visual workflow diagram | A rendered diagram of `docs/workflows.md` | P3 | proposed |

## Recently Shipped (for reference)

- **Data Analyst role complete**: `analytics/metrics_semantic_layer` (spec `0008`),
  `analytics/experimentation` (spec `0009`), and the end-to-end capstone
  `specs/0010-analytics-pipeline/` — all with dependency-free, tested reference
  runtimes under `src/quantsmith/pipelines/`.
- ML/DL and optimization runtime workflows: `specs/0006-ml-return-forecasting/`,
  `specs/0007-portfolio-construction/` (QP), `specs/0012-execution-scheduling/`
  (Almgren-Chriss), and `specs/0013-optimization-solvers/` (LP, MILP, min-cost flow,
  dynamic programming), with tested reference pipelines. The quant chain runs
  signal → forecast → portfolio → execution.
- Data Engineer first slice: `specs/0011-data-pipeline-orchestration/` — a DAG runner
  with contracts, idempotency, retries, backfill, and a run manifest.
- Dashboard render adapters (`adapters/dashboard_render/`): the contract plus `xlsx`
  and `react_scaffold` providers that turn a rendered dashboard payload into a live
  artifact.
- Adapter catalog contracts (`adapters/`) for alert delivery, schedulers, artifact
  delivery, data access, and LLM runtimes.
- Persistent workflow memory (`memory/`, `instructions/workflow_memory.md`,
  `memory-check` gate) — spec `specs/0002-workflow-memory/`.
- Model-development standard (`instructions/model_development.md`) and the
  consolidated workflow map (`docs/workflows.md`).
- Portfolio-management lifecycle agents (`agents/portfolio_management/`) plus
  `instructions/portfolio_management.md`.
- Securities financing, formulaic alphas, trading strategies, tooling, knowledge,
  and secrets agent groups.
- The consolidation pass (refreshed `sdk_plan`, `handoff`, `agentic_dictionary`;
  added the adoption guide).
- Monitoring → alerting chain (`agents/monitoring/`, `agents/alerts/`,
  `adapters/alert_delivery/`; specs `0019`–`0021`).
- Asset-class mechanics agents, securities-lending runtime, and financing-cost-
  analysis runtime (specs `0022`, `0023`, `0028`) — the securities-financing
  chain end to end except `repo_financing`/`collateral_management`, which
  remain agent-contract-only by choice.
- Role-operations agent roster, all three phases, plus the
  data-provenance guardrail (specs `0024`, `0025`, `0029`, `0030`) —
  fourteen agents complete; see the dedicated "Agents" table row for
  detail.
- Model plugin adapter (spec `0026`) and the data source catalog (spec
  `0027`).
- Financing cost analysis promoted to a tested runtime (spec `0028`).
- The last three backing instructions — `risk_management`, `data_ingestion`
  (a shared standard replacing three duplicated copies), and
  `reproducibility` (spec `0031`).
- The first two executable `adapters/alert_delivery/` providers — email and
  webhook (spec `0032`), following the adapter's own pre-existing
  Recommended Starting Set.
- The `economists/` agent group (spec `0033`) — seven agents giving a
  quant/PM workflow a grounded macro backdrop, reclaiming a stray
  placeholder directory left by an earlier parallel merge.
- Cardinality-constrained portfolio construction (spec `0034`) — the
  SDK's only standing `P0` item: an application actually built on the
  `0013` solver toolkit, composing it with `0007`'s QP as a documented
  two-stage heuristic rather than a from-scratch MIQP solver.
- The funding ladder (spec `0035`) — a second `0013`-toolkit application
  (`min_cost_flow`), matching cash obligations to funding tenors at
  minimum cost; a general treasury/cash tool, explicitly not
  securities-financing.
- Multi-period rebalancing (spec `0036`) — the third and last `0013`-
  toolkit application (`solve_dp`): a discretized single-position DP
  trading transaction cost against tracking-error cost over a horizon.
  Every `0013` solver now has a shipped application.
- The remaining five `adapters/alert_delivery/` providers — Slack, Teams,
  ticketing, PagerDuty/Opsgenie, SMS/push (spec `0037`) — completing all
  seven providers end to end, plus a `deliver_via` dedup refactor of the
  original email/webhook providers (`0032`), verified behavior-preserving.
- The factor risk model (spec `0038`) — variance decomposition, Euler risk
  attribution, concentration, and a linear factor-shock stress loss,
  closing the standing "risk-model spec end to end" worked-example gap.
- Ingestion data contract emission (spec `0039`) — validates a pulled row
  set against a declared schema/key/quality-rule contract and renders a
  `data_contract.md` populated with real, computed results, closing the
  standing "ingestion example that emits a data contract" worked-example
  gap. Item 8's worked-examples backlog is now fully closed.
- The README index/runtime sync gate (spec `0040`,
  `hooks/stages/readme-sync-check.sh`) — closes the third leg
  `agent-catalog`/`spec-index` didn't cover: a spec whose `specs/README.md`
  row names a real, tested pytest module but whose ID is missing from root
  `README.md`'s own runtime table.
- Ranking-loss forecasting (spec `0041`, `ranking_forecast.py`) — a
  pairwise (RankNet-style) ranking-loss variant of `0006`, composing its
  labels/features/folds/evaluation unmodified; the sole remaining `P0`
  backlog line ("additional ML/DL examples") is now shipped.
- The downstream consumer contract (spec `0047`) — `schema_version` on
  `DashboardSpec` with a compatibility check, a release-notify workflow,
  and a copyable `quantsmith-version` gate. Makes SemVer something a
  separate app repository can rely on rather than a documentation claim,
  and lands before that repo exists rather than after.
- The walk-forward backtest harness (spec `0046`, `walk_forward.py`) —
  composes `0006`'s purged/embargoed `make_folds` with `0044`'s engine,
  refitting per fold and evaluating on held-out periods, and reports the
  out-of-sample fold distribution rather than one in-sample number.
  Closes the gap `0044`'s own report admitted to.
- The FRED point-in-time panel adapter (spec `0045`,
  `fred_point_in_time.py`) — reads `gold_fred_point_in_time` from the FRED
  bronze-to-gold pipeline's local SQLite output and selects vintages by
  `realtime_start`/`realtime_end` window containment, so a revision
  published later can never leak backwards into an earlier as-of date.
  Closes the input-side half of the gap `0044` left open. The real run
  still needs `fred_local.db` from the operator.
- The backtest engine (spec `0044`, `backtesting.py`) — net-of-cost
  simulation with no look-ahead by construction, turnover-scaled costs,
  financing charged on shorts only, drawdown, and a probabilistic Sharpe
  on every run. Ships the repo's first backtest artifact, so the
  CI-enforced `backtest` gate validates real content instead of
  no-opping. First half of a two-step build; the real point-in-time FRED
  vertical slice is the second, blocked on an operator-held
  `FRED_API_KEY`.
- The documented-count drift gate (spec `0043`,
  `hooks/stages/doc-counts-check.sh`) — derives the true agent, gate, and
  instruction-standard counts from the filesystem and flags stated counts
  that disagree. Prompted by finding all three stale at once (agents
  documented as 131/122 against 161, gates as 23/21 against 26,
  instruction standards as 26 against 33) because no gate can check a
  number written in prose.
- The pipeline builder (spec `0042`, `pipeline_builder.py`) — the
  design-time layer ahead of `0011`'s runtime: compile a declared intent
  into a DAG validated by `0011`'s own toposort, review it against the
  pipeline-engineering checklist, render a manifest, and bind
  implementations back into a runnable `0011` `Pipeline`. Also ships the
  repository's first pipeline-manifest artifact, making the previously
  dormant `pipeline-contract` gate live.
- A documentation audit and refresh pass: stale counts in `docs/handoff.md`
  and `docs/sdk_plan.md` corrected, a missing "Adapter" dictionary entry
  added, and a missing `adapters/data_access/external_apis/eia.md` profile
  written.
