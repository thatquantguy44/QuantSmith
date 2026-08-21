# Workflow Map

The single place to see how the SDK's agents, gates, and instructions compose into
end-to-end workflows. It does not replace the flow definitions it links to — it
unifies them and adds role-based and scenario workflows.

## The Backbone: Spec-Driven Development

Every workflow runs on top of the SDD lifecycle (the canonical map lives in
`instructions/spec_driven_development.md`):

```
Constitution → Specify → Plan → Tasks → Implement → Verify → Operate
```

Each step has an owning stage agent and a companion gate:

| Step | Stage agent | Gate |
| --- | --- | --- |
| Specify | `planning_requirements` | `planning`, `spec` |
| Plan | `design_architecture` | `design`, `spec` |
| Tasks + Implement | `implementation` | `implementation`, `leakage`, `secret-scan` |
| Verify | `testing_validation` | `testing`, `backtest` |
| Operate (release) | `deployment_release` | `deployment` |
| Operate (run) | `maintenance_monitoring` | `maintenance` |

The `workflow_orchestrator` agent drives this flow and enforces the gate between
stages. Agents marked **(planned)** below are on the roadmap — see
`docs/handoffs/future_features.md`.

## Role & Scenario Workflows

Each workflow is an ordered chain of agents plus the gates that check the work. They
all sit on the SDD backbone above.

### Quant Researcher

Idea → reviewed, reproducible, risk-checked signal or model.

```
research_analyst → data_quality → feature_engineering → modeling
  → backtest_review → risk → git_release
```

- Standard: `instructions/quant_research.md`, `instructions/model_development.md`.
- Gates: `leakage`, `backtest`, `repro`, `spec`.
- Strategy/alpha variants slot in `trading_strategies/*` or `formulaic_alphas/*`
  between `research_analyst` and `modeling`.

### Quant Model Build

Approved design → reproducible, validatable model implementation.

```
design_architecture (plan) → implementation (build) → testing_validation (verify)
```

- Standard: `instructions/model_development.md` (how to build) +
  `instructions/model_validation.md` (how to validate).
- Gates: `implementation`, `leakage`, `repro`, `testing`, `backtest`.
- Reproducibility is captured in a run card (`templates/docs/run_card.md`).

### Securities Lending & Financing

Lending-desk data → classified borrow rates, optimized inventory, and a
concentration-risk-flagged report; financing costs feed backtest and risk review.

```text
asset_classes/equities (shorts mechanics) → securities_financing/securities_lending
  → securities_financing/financing_cost_analysis → backtest_review → risk
```

- Standard: `instructions/securities_financing.md`, `instructions/asset_class_mechanics.md`.
- Gates: `spec`, `repro`, `secret-scan`; the `backtest` gate's financing theme prices
  shorts realistically.
- Group workflow (agent-contract steps, all three financing agents feed into
  `financing_cost_analysis`): [Securities
  Financing](../agents/securities_financing/README.md#group-workflow).
- Worked example: `specs/0023-securities-lending-workflow/` runs the lending-desk
  chain end to end — universe construction → GC/WARM/HTB borrow-rate
  classification → LP inventory optimization under a balance-sheet cap →
  counterparty/single-name concentration risk → optional ML demand forecast and
  anomaly detection → report
  (`src/quantsmith/quant/agentic_quant/sec_lending_workflow.py`; CLI:
  `quantsmith-sec-lending`).
- Worked example: `specs/0028-financing-cost-analysis/` closes the chain's
  quant bridge — per-position cost-of-carry decomposition (borrow fee,
  rebate, funding, margin) → financing-aware returns → understated-backtest
  flags → rate-shock sensitivity → GC/WARM/HTB-keyed capacity findings
  (`src/quantsmith/pipelines/financing_cost_analysis.py`, dependency-free;
  reconciles with `0023`'s rate/classification vocabulary by value).
  `repo_financing` and `collateral_management` remain agent-contract-only —
  `financing_cost_analysis` accepts their financing legs as structured
  input rather than requiring either to have a runtime first.

### Data Analyst

Business question → validated, communicated answer.

```
planning_requirements → sql-integration-agent → eda-specialist-agent
  → analytics/metrics_semantic_layer → tooling/tableau | tooling/power_bi
  → quality-guard-agent → reporting-agent
```

- Experimentation/A-B work uses `analytics/experimentation` — design (power/sample
  size), validity (sample-ratio mismatch), and a power-gated readout.
- Communication layer (spec `0014`): from a governed `Report`,
  `analytics/data_storytelling` writes the narrative (situation → insight → action)
  and `analytics/dashboard_design` writes a tool-agnostic dashboard spec, both handed
  to `reporting-agent` / `tableau`/`powerbi` dashboard agents to render.
- Standard: `instructions/metrics_semantic_layer.md`, `instructions/data_storytelling.md`,
  `instructions/model_validation.md`.
- Gates: `data-contract`, `secret-scan`.
- Worked examples: `specs/0008-metrics-semantic-layer/` — canonical, point-in-time
  metric definitions with governance and reconciliation
  (`src/quantsmith/pipelines/metrics_semantic_layer.py`); and
  `specs/0009-experimentation/` — disciplined A/B test design and readout
  (`src/quantsmith/pipelines/experimentation.py`).

### Data Engineer

Source → modeled, orchestrated, monitored, contract-backed data.

```
data_ingestion/* (or sql-integration-agent) → data_engineering/data_modeling
  → pipeline_builder → data_engineering/pipeline_orchestration → data-prep-agent
  → data_quality + quality-guard-agent → data_engineering/pipeline_observability
  → pipeline_deployment ; data_governance (cross-cutting)
```

- Standard: `instructions/data_quality.md`, `instructions/pipeline_engineering.md`,
  `templates/data/data_contract.md`.
- Gates: `data-contract`, `repro`, `secret-scan`.
- Secrets/access via `secrets_management/*`.
- Worked examples: `specs/0011-data-pipeline-orchestration/` — a DAG runner with data
  contracts, idempotency, retries, backfill, and a run manifest
  (`src/quantsmith/pipelines/data_pipeline.py`); and
  `specs/0019-pipeline-observability/` — reads that run manifest for freshness, data
  downtime, SLA, and lineage (`src/quantsmith/pipelines/pipeline_observability.py`).

### Production Pipeline, Monitoring & Alerts

Pipeline definition → deployed DAG → monitored service → actionable alert →
acknowledged incident or recovery.

```text
pipeline_builder → pipeline_orchestration → pipeline_deployment
  → monitoring/* → alerts/alert_policy → alerts/alert_router
  → alert_delivery adapter → alerts/incident_notification → maintenance_monitoring
```

- Detection: `monitoring/*` — `pipeline_monitoring` (via `0019`),
  `model_signal_monitoring` (runtime `signal_monitoring`, `0021`), and
  `infrastructure_cost_monitoring` — emit observations.
- Alerting (`0020`): `alert_policy` evaluates policies → `alert_router` dedups/routes →
  the `alert_delivery` adapter delivers → `incident_notification` owns the lifecycle.
- Channels are adapters (email, Slack, Teams, PagerDuty-style systems, SMS/push,
  webhooks, and ticketing), not separate agents. See
  [`../adapters/alert_delivery/README.md`](../adapters/alert_delivery/README.md).
- Standards: `instructions/monitoring.md`, `instructions/alerting.md`.
- Gates: `pipeline-contract`, `monitoring-coverage`, `alert-contract` (skip when the
  artifact is absent), plus `data-contract`, `repro`, `secret-scan`.
- Automated remediation remains opt-in and runbook-governed; notification alone
  never authorizes a portfolio, data, model, or production mutation.

## Optimization Problem Build

Ambiguous constrained decision -> formulated optimization spec -> solver-ready design -> reviewed implementation.

```text
optimization_orchestrator -> problem_formulation -> optimization specialist
  -> solver_diagnostics_sensitivity -> risk -> testing_validation
  -> deployment_release -> maintenance_monitoring
```

- Standard: `instructions/optimization.md`.
- Specialist families: LP, QP, conic, MIP, nonlinear, global, stochastic, robust,
  dynamic programming, network flow, routing/scheduling, inventory/supply chain,
  portfolio, collateral/margin, execution, capacity, pricing, simulation, and
  solver diagnostics.
- Gates: `spec`, `repro`, `data-contract`, `testing`; future runtime specs should
  add solver-specific evidence for feasibility, objective value, slacks, duals,
  sensitivity, and solve-time limits.
- Runtime code belongs under `src/quantsmith/`; the agent contracts define routing
  and review responsibilities.
- Worked examples: `specs/0007-portfolio-construction/` runs this chain end to end —
  a constrained mean-variance allocation from the `0006` forecast, with feasibility,
  turnover, and risk-aversion sensitivity diagnostics
  (`src/quantsmith/pipelines/portfolio_construction.py`); and
  `specs/0012-execution-scheduling/` — Almgren-Chriss optimal execution of the target
  trade, trading cost against variance
  (`src/quantsmith/pipelines/execution_optimization.py`); and
  `specs/0013-optimization-solvers/` — the core solver toolkit by mathematical form
  (LP, MILP, min-cost flow, dynamic programming) in
  `src/quantsmith/pipelines/optimization_solvers.py`.

### Portfolio Management Lifecycle

Mandate -> universe -> signal intake -> allocation policy -> construction oversight -> rebalance implementation -> monitored governance.

```text
pm_orchestrator -> mandate_objectives -> universe_selection
  -> data_signal_intake -> allocation_policy -> construction_oversight
  -> rebalance_trade_implementation -> monitoring_governance
```

- Standard: `instructions/portfolio_management.md`.
- Specialist reviews cover mandate, universe, signal readiness, allocation policy,
  construction oversight, implementation, risk budgeting, compliance, attribution,
  liquidity/cash, tax/transition, monitoring, and governance.
- Construction-specific optimization still routes through
  `optimization/portfolio_construction`; execution scheduling routes through
  `optimization/execution_optimization`.
- Gates: `spec`, `data-contract`, `leakage`, `backtest`, `testing`, and
  `maintenance`, depending on whether the workflow is research-only, target-weight
  generation, trade implementation, or live monitoring.

### Machine Learning Build

Decision -> label/feature design -> validated model -> monitored production candidate.

```text
ml_orchestrator -> problem_framing_labeling -> feature_store_engineering
  -> ML specialist -> model_selection_validation -> mlops_monitoring
```

- Standard: `instructions/machine_learning.md` plus `instructions/model_development.md`
  and `instructions/model_validation.md`.
- Specialists cover supervised learning, forecasting, ranking/recommendation,
  causal/uplift, unsupervised/anomaly detection, AutoML, online learning/bandits,
  validation, and MLOps.
- Gates: `leakage`, `repro`, `backtest` where applicable, `testing`, `data-contract`.
- Worked example: `specs/0006-ml-return-forecasting/` runs this chain end to end
  (labeling → PIT feature store → gradient-boosted baseline → purged/embargoed
  validation → monitored candidate), with a deep-learning challenger.

### Deep Learning Build

Modality/problem -> architecture/training plan -> robust evaluation -> compression/serving plan.

```text
dl_orchestrator -> training_systems -> DL specialist
  -> compression_serving -> model_selection_validation -> mlops_monitoring
```

- Standard: `instructions/deep_learning.md` plus model-development and validation
  standards.
- Specialists cover tabular neural nets, transformers/sequences, GNNs, RL, vision,
  NLP/LLM, representation learning, generative models, deep time series, and serving.
- Gates: `leakage`, `repro`, `testing`, model validation, and production monitoring.
- Worked example: `specs/0006-ml-return-forecasting/` uses this chain as the
  challenger loop (`training_systems → deep_time_series → compression_serving`),
  evaluated on the same folds and net-of-cost bar as the ML baseline.

### Analytics Pipeline (runtime)

The consolidated multi-agent analytics copilot (full blueprint in
`agents/agentic_workflow_blueprint.md`):

```
orchestrator-agent → sql-integration-agent → data-prep-agent
  → eda-specialist-agent → tableau-dashboard-agent | powerbi-dashboard-agent
  → quality-guard-agent → reporting-agent
```

- Worked example: `specs/0010-analytics-pipeline/` runs the chain end to end
  (query → prepare → profile → metrics via the `0008` semantic layer → quality guard
  → report with provenance), in `src/quantsmith/pipelines/analytics_pipeline.py`.

### Persistent Workflow Memory (cross-cutting)

Each workflow primes from and writes back to `memory/` so it arrives already knowing
a dataset's kinks. Facts about a source live in `memory/_shared/`; workflow-specific
usage in `memory/<workflow>/`.

- Standard: `instructions/workflow_memory.md`; design: `specs/0002-workflow-memory/`.
- Served by the `knowledge/` agents; gate: `memory`. Research runs use only
  point-in-time-scoped records (leakage firewall).

### Knowledge & Institutional Memory (cross-cutting)

Use the [Knowledge Management group workflow](../agents/knowledge/README.md#group-workflow)
for the ingestion, curation, retrieval, and persistence sequence.

- Standard: `instructions/knowledge_base.md`; sources in `knowledge_sources.yml`.
- Gate: `knowledge`.

## Group Workflows

Role and scenario workflows above compose capabilities across groups. For groups
with a meaningful internal sequence, the co-located README is the canonical
mini-map:

| Pipeline-shaped group | Internal flow |
| --- | --- |
| [Formulaic Alpha](../agents/formulaic_alphas/README.md#group-workflow) | Construct → combine → evaluate |
| [Knowledge Management](../agents/knowledge/README.md#group-workflow) | Ingest → curate → retrieve or persist |
| [Data Ingestion](../agents/data_ingestion/README.md#group-workflow) | Ingest → validate → emit data contract |
| [Securities Financing](../agents/securities_financing/README.md#group-workflow) | Model financing inputs → all-in cost → backtest and risk |
| [Secrets Management](../agents/secrets_management/README.md#group-workflow) | Store → access → rotate, with scanning throughout |
| [Analytics](../agents/analytics/README.md#group-workflow) | Define metrics → design/read out experiments; feeds dashboards and reports |

Parallel catalogs such as `trading_strategies/`, `asset_classes/`, and `tooling/`
intentionally do not have workflow maps: their members are alternatives, not
ordered stages. A request naming both a strategy archetype and an asset class
routes through the matching `asset_classes/` agent first (mechanics), then the
matching `trading_strategies/` agent (design/review) — see
`agents/asset_classes/README.md`. The lifecycle agents use the SDD backbone above,
and the analytics pipeline retains its dedicated blueprint.

## Related Maps

- `instructions/spec_driven_development.md` — the SDD lifecycle (the backbone).
- `agents/README.md` — the agent catalog and "How They Fit Together".
- `agents/agentic_workflow_blueprint.md` — the analytics-pipeline blueprint.
- `../adapters/README.md` — the adapter catalog for provider boundaries.
- `README.md` — the "Suggested Quant Workflow" narrative.

## Composing A Role Agent

To build (or "convert") an agent that performs a role, compose the chain above from
the listed agents, apply their backing instructions, and run the named gates as the
definition of done. Where a step names a **(planned)** agent, that capability is
tracked in `docs/handoffs/future_features.md`.
