# Agent Catalog

The SDK's agents fall into three groups: the **orchestrator** that drives the
whole spec-driven flow, the **lifecycle agents** that own one SDLC stage each, and
the **domain agents** that supply quant expertise the lifecycle agents draw on.

Every agent follows the same contract: `README.md`, `prompt.md`, `instructions.md`,
`tasks.md`. See `instructions/spec_driven_development.md` for the flow and
`instructions/engineering_principles.md` for the constitution every agent upholds.

## Orchestrator

| Agent | Role |
| --- | --- |
| `workflow_orchestrator/` | Routes a change through `Specify → Plan → Tasks → Implement → Verify → Operate`, enforcing the gate between stages. Uses this catalog as its routing table. |

## Lifecycle Agents (one per SDLC stage)

| Stage | Agent | Spec artifact owned | Companion hook |
| --- | --- | --- | --- |
| 1. Planning / Requirements | `planning_requirements/` | `spec.md` | `planning-check` |
| 2. Design | `design_architecture/` | `plan.md` | `design-check` |
| 3. Coding / Implementation | `implementation/` | `tasks.md` + code | `implementation-check` |
| 4. Testing | `testing_validation/` | AC evidence | `testing-check` |
| 5. Deployment | `deployment_release/` | release record | `deployment-check` |
| 6. Maintenance | `maintenance_monitoring/` | living spec | `maintenance-check` |

Cross-cutting: the `spec-check` hook enforces the traceability chain across all
stages.

## Domain Agents (quant expertise)

| Agent | Supplies | Feeds mainly |
| --- | --- | --- |
| `research_analyst/` | Hypothesis → research plan, assumptions, go/no-go | Planning |
| `quant_analyst/` | End-to-end quant workflow routing across research, data, modeling, financing, risk, and runtime handoff | Planning, Design, Implementation |
| `data_quality/` | Lineage, joins, timestamps, missingness, leakage review | Planning, Design |
| `feature_engineering/` | Point-in-time features, normalization-leakage review, stability | Design, Implementation |
| `modeling/` | Model selection, leakage-free validation, error analysis | Design, Testing |
| `backtest_review/` | Bias, costs, robustness, production-readiness of simulations | Testing |
| `risk/` | Exposure, concentration, drawdown, tail/stress, risk limits | Testing, Deployment |
| `portfolio_management/` | End-to-end portfolio lifecycle routing across mandate, universe, signal intake, allocation, implementation, risk, compliance, attribution, liquidity, tax, and governance | Planning, Design, Testing, Maintenance |
| `git_release/` | Conventional commits, spec-traceable PRs, changelogs | Deployment |

## Ingestion Agents (`data_ingestion/`)

Grouped in the `data_ingestion/` category folder; they bring external data into a
workflow as typed, validated, reproducible datasets with a data contract.

| Agent | Handles | Feeds mainly |
| --- | --- | --- |
| `data_ingestion/database_connectivity/` | SQL databases & warehouses: connections, safe queries, point-in-time pulls, snapshots | Planning, Design |
| `data_ingestion/file_ingestion/` | Files (CSV, Parquet, Excel, JSON, XML, fixed-width, …): typed loading, validation | Planning, Design |
| `data_ingestion/api_ingestion/` | REST / streaming / vendor APIs: auth, pagination, retries, as-of capture | Planning, Design |

## Data Engineering Agents (`data_engineering/`)

Grouped in the `data_engineering/` category folder (see
[`data_engineering/README.md`](data_engineering/README.md)); they turn raw sources
into modeled, orchestrated, contract-backed, observable data — the **Data Engineer**
role, downstream of ingestion.

| Agent | Handles | Feeds mainly |
| --- | --- | --- |
| `data_engineering/pipeline_orchestration/` | DAG design and execution — dependency ordering, per-step data contracts, idempotent partitioned runs, retries, backfill, run manifest | Design, Implementation, Testing |
| `data_engineering/pipeline_observability/` | Freshness, SLAs, lineage, and data-downtime detection from the run manifest | Maintenance, Testing |
| `data_engineering/data_modeling/` | Dimensional/warehouse modeling: grain, keys, star/snowflake, slowly-changing and conformed dimensions | Design |
| `data_engineering/pipeline_builder/` | Compile source→transform→sink intent into a reviewable DAG with contracts, schedules, retries, tests, ownership, deployment plan | Design, Implementation |
| `data_engineering/pipeline_deployment/` | Environment promotion, dry runs, canaries, rollback, state migration, scheduler deployment | Deployment |
| `data_engineering/data_governance/` | Catalog, lineage, access policy, ownership, classification | Maintenance |

Runtimes: `src/quantsmith/pipelines/data_pipeline.py` (`0011`) and
`src/quantsmith/pipelines/pipeline_observability.py` (`0019`); specs:
`specs/0011-data-pipeline-orchestration/`, `specs/0019-pipeline-observability/`;
standard: `instructions/pipeline_engineering.md`.

## Secrets Management Agents (`secrets_management/`)

Grouped in the `secrets_management/` category folder; they handle secret keys,
credentials, and custom key/values safely across their lifecycle, enforcing
constitution P9 (secrets never enter the repo).

| Agent | Handles | Feeds mainly |
| --- | --- | --- |
| `secrets_management/secret_storage/` | Choosing/provisioning a secret store: naming, structure, access policy, encryption | Design, Deployment |
| `secrets_management/credential_access/` | Reading secrets at runtime safely: least privilege, no logging, safe caching | Implementation |
| `secrets_management/secret_rotation/` | Writing/updating/rotating and revoking credentials and custom keys | Deployment, Maintenance |
| `secrets_management/secret_scanning/` | Detecting leaked secrets in code/history/logs; remediation and prevention | Implementation, Maintenance |

## Technology & Tooling Agents (`tooling/`)

Grouped in the `tooling/` category folder; they bring the SDK's discipline to the
platforms quants work in (spreadsheets, BI/reporting, and growing to compute/data
stores).

| Agent | Handles | Feeds mainly |
| --- | --- | --- |
| `tooling/excel/` | Excel models: structure, formula audit, reproducibility, model-risk, VBA safety | Implementation, Testing |
| `tooling/power_bi/` | Power BI datasets/reports: data model, DAX, refresh, RLS, performance | Implementation, Maintenance |
| `tooling/tableau/` | Tableau workbooks/data sources: LOD/table calcs, extracts, honest visuals, publishing | Implementation, Maintenance |
| `tooling/react/` | Web dashboards in React: honest/accessible charts, state/data, secrets out of the bundle; renders the shared dashboard spec (`0016`) | Implementation, Maintenance |
| `tooling/streamlit_dash/` | Python-native Streamlit apps: caching/state, honest charts; renders + scaffolds the shared spec (`0018`) | Implementation, Maintenance |
| `tooling/looker/` | Looker: LookML semantic model, explores, caching; renders the shared spec (`0018`) | Implementation, Maintenance |
| `tooling/qlik/` | Qlik: associative model, set analysis, section access; renders the shared spec (`0018`) | Implementation, Maintenance |
| `tooling/superset/` | Apache Superset: SQL/dataset governance, Jinja safety, caching; renders the shared spec (`0018`) | Implementation, Maintenance |

The planned technology matrix is maintained in
[`tooling/README.md`](tooling/README.md#planned-coverage). It prioritizes Python,
SQL, C/C++, R, Jupyter, kdb+/q, dbt, and DAG orchestration, then expands through
additional languages, BI tools, data platforms, distributed compute, production
engineering, optimization/GPU, and market connectivity.

## Monitoring Agents (`monitoring/`)

Keep live pipelines, models, and infrastructure healthy and hand a clean signal to
the alerts agents (see [`monitoring/README.md`](monitoring/README.md)).

| Agent | Handles | Feeds mainly |
| --- | --- | --- |
| `monitoring/pipeline_monitoring/` | DAG status, freshness, latency, backlogs, retries, idempotency, SLOs (via `0019`) | Maintenance |
| `monitoring/model_signal_monitoring/` | Drift, calibration, alpha decay, turnover/capacity, regime change (runtime `signal_monitoring`, `0021`) | Maintenance |
| `monitoring/infrastructure_cost_monitoring/` | Compute, memory, storage, API quota, market-data spend, cost-per-run guardrails | Maintenance |

## Alerting Agents (`alerts/`)

Turn monitoring observations into actionable, routed notifications without coupling to
a delivery vendor (see [`alerts/README.md`](alerts/README.md#group-workflow)).

| Agent | Handles | Feeds mainly |
| --- | --- | --- |
| `alerts/alert_policy/` | Threshold/anomaly/composite/missing rules with severity, suppression; evaluate to alerts (runtime `alerting`, `0020`) | Maintenance |
| `alerts/alert_router/` | Ownership, dedup, grouping, rate limits, escalation, channel selection | Maintenance |
| `alerts/incident_notification/` | Actionable payloads, ack/recovery lifecycle, runbook/evidence links | Maintenance |

Runtimes: `src/quantsmith/pipelines/signal_monitoring.py` (`0021`),
`src/quantsmith/pipelines/alerting.py` (`0020`); standards:
`instructions/monitoring.md`, `instructions/alerting.md`; delivery via
[`../adapters/alert_delivery/README.md`](../adapters/alert_delivery/README.md).

## Portfolio Management Agents (`portfolio_management/`)

Grouped in the `portfolio_management/` category folder; these agents cover the
full portfolio operating lifecycle around the existing construction optimizer.
They define the mandate, universe, signal intake, allocation policy, construction
oversight, implementation, risk budget, compliance, attribution, liquidity, tax,
monitoring, and governance responsibilities before target weights or trades are
treated as controlled outputs.

| Agent | Handles |
| --- | --- |
| `portfolio_management/pm_orchestrator/` | Routes portfolio-management work across mandate, universe, signal intake, allocation, construction, implementation, risk, attribution, and governance specialists. |
| `portfolio_management/mandate_objectives/` | Portfolio objective, benchmark, horizon, constraints, fiduciary limits, stakeholder approvals, and non-goals. |
| `portfolio_management/universe_selection/` | Eligible assets, filters, liquidity screens, corporate-action handling, survivorship controls, and coverage gaps. |
| `portfolio_management/data_signal_intake/` | Forecasts, alphas, risk-model inputs, benchmark data, holdings, prices, point-in-time readiness, and confidence. |
| `portfolio_management/allocation_policy/` | Capital allocation rules, risk budgets, sizing logic, factor tilts, rebalancing bands, and fallback baselines. |
| `portfolio_management/construction_oversight/` | Optimization-ready objectives, constraints, costs, diagnostics, feasibility checks, and optimizer handoff. |
| `portfolio_management/rebalance_trade_implementation/` | Target-weight-to-trade conversion, cash impacts, turnover controls, execution constraints, operations, and rollback. |
| `portfolio_management/risk_budgeting/` | Factor, sector, issuer, liquidity, leverage, drawdown, stress, scenario, and tracking-error risk budgets. |
| `portfolio_management/compliance_constraints/` | Investment guidelines, restricted lists, concentration rules, client exclusions, approvals, and exception handling. |
| `portfolio_management/performance_attribution/` | Return, risk, cost, timing, sizing, selection, factor, benchmark, and residual attribution. |
| `portfolio_management/liquidity_cash_management/` | Cash buffers, subscriptions/redemptions, liquidity tiers, funding, borrow, income, and forced-trade risk. |
| `portfolio_management/tax_transition_management/` | Tax lots, wash-sale constraints, transition trades, legacy positions, realization budgets, and after-tax trade-offs. |
| `portfolio_management/monitoring_governance/` | Live monitoring, breach triage, model/portfolio review cadence, run cards, ownership, and governance evidence. |

Standard: `instructions/portfolio_management.md`. Construction math routes to
`optimization/portfolio_construction/`; execution scheduling routes to
`optimization/execution_optimization/`.

## Optimization Agents (`optimization/`)

Grouped in the `optimization/` category folder; these agents classify constrained decision problems, choose formulation families, review solver behavior, and hand work to specs/runtime only after objectives and constraints are explicit.

| Agent | Handles |
| --- | --- |
| `optimization/optimization_orchestrator/` | Routes optimization requests across formulation, solver, domain, validation, and deployment agents. |
| `optimization/problem_formulation/` | Turns an ambiguous decision into variables, objective functions, constraints, data contracts, and acceptance criteria. |
| `optimization/model_plugin_registration/` | Ingests a registered internal-model manifest entry, checks contract compliance, and flags unverifiable claims before routing to it. |
| `optimization/linear_programming/` | LPs for allocation, blending, transportation, cash, collateral, balance-sheet, and capacity problems. |
| `optimization/quadratic_programming/` | Convex QPs for mean-variance, tracking error, turnover penalties, and regularized allocation. |
| `optimization/conic_optimization/` | SOCP/SDP-style risk, norm, robust, covariance, and chance-constraint formulations. |
| `optimization/mixed_integer_optimization/` | Binary/integer decisions, fixed charges, lot sizes, assignment, facility, and cardinality constraints. |
| `optimization/nonlinear_optimization/` | Smooth constrained nonlinear programs, gradients, scaling, local minima, and KKT diagnostics. |
| `optimization/global_optimization/` | Nonconvex search, multi-start, branch-and-bound, Bayesian optimization, evolutionary methods, and heuristics. |
| `optimization/stochastic_optimization/` | Scenario, sample-average, recourse, and simulation-backed optimization under uncertainty. |
| `optimization/robust_optimization/` | Uncertainty sets, stress-aware objectives, robust counterparts, and fragile-estimate mitigation. |
| `optimization/dynamic_programming/` | Sequential decisions, Bellman recursions, approximate DP, inventory/rebalancing policies, and control. |
| `optimization/network_flow/` | Min-cost flow, max-flow, matching, circulation, funding ladders, collateral chains, and graph routing. |
| `optimization/routing_scheduling/` | Routing, scheduling, order batching, job/crew allocation, market windows, and latency-aware placement. |
| `optimization/inventory_supply_chain/` | Replenishment, allocation, service levels, safety stock, and multi-echelon supply decisions. |
| `optimization/portfolio_construction/` | Portfolio weights, factor/risk constraints, turnover, tax lots, capacity, and rebalancing. |
| `optimization/collateral_margin_optimization/` | Eligibility, haircuts, margin, cheapest-to-deliver, substitutions, liquidity buffers, and regulation. |
| `optimization/execution_optimization/` | Trading schedules, participation, venue choice, order slicing, impact, slippage, and fill-risk trade-offs. |
| `optimization/resource_capacity_optimization/` | Compute, staffing, capital, balance-sheet, quota, cloud, API, and throughput allocation. |
| `optimization/pricing_revenue_optimization/` | Bid/ask, rebates, fee schedules, markdowns, elasticity, acceptance probabilities, and revenue risk. |
| `optimization/simulation_optimization/` | Monte Carlo, digital twins, response surfaces, and simulation-backed objective comparisons. |
| `optimization/solver_diagnostics_sensitivity/` | Solver status, infeasibility, duals, shadow prices, slacks, degeneracy, scaling, and sensitivity. |


## Machine Learning Agents (`machine_learning/`)

Grouped in the `machine_learning/` category folder; these agents cover ML framing, feature systems, predictive modeling, causal/ranking/online methods, validation, and production monitoring.

| Agent | Handles |
| --- | --- |
| `machine_learning/ml_orchestrator/` | Routes ML work from framing through features, validation, deployment, monitoring, and retraining. |
| `machine_learning/problem_framing_labeling/` | Targets, labels, horizons, decision times, leakage boundaries, class balance, and label quality. |
| `machine_learning/feature_store_engineering/` | Reusable features, point-in-time joins, entity keys, offline/online parity, and provenance. |
| `machine_learning/supervised_learning/` | Regression/classification, baselines, calibration, imbalance, metric choice, and segment errors. |
| `machine_learning/time_series_forecasting/` | Forecasting, temporal validation, hierarchical series, exogenous drivers, revisions, and reconciliation. |
| `machine_learning/ranking_recommendation/` | Ranking, recommendation, candidate generation, retrieval, learning-to-rank, and evaluation at rank. |
| `machine_learning/causal_uplift/` | Treatment effects, uplift, experiments, observational bias, instruments, diff-in-diff, and identification. |
| `machine_learning/unsupervised_anomaly/` | Clustering, dimensionality reduction, outliers, novelty detection, drift probes, and alert quality. |
| `machine_learning/model_selection_validation/` | Baselines, validation design, hyperparameter search, leakage controls, robustness, and error analysis. |
| `machine_learning/automl_experimentation/` | Broad searches, experiment tracking, multiple-testing control, reproducibility, and search-space discipline. |
| `machine_learning/online_learning_bandits/` | Contextual bandits, exploration/exploitation, delayed feedback, guardrails, regret, and online updates. |
| `machine_learning/mlops_monitoring/` | Packaging, serving, drift, calibration, retraining triggers, run cards, and production ownership. |


## Deep Learning Agents (`deep_learning/`)

Grouped in the `deep_learning/` category folder; these agents cover neural architectures, training systems, modality specialists, reinforcement learning, generative models, and serving constraints.

| Agent | Handles |
| --- | --- |
| `deep_learning/dl_orchestrator/` | Routes DL work across architecture, data, training, evaluation, compression, serving, and monitoring. |
| `deep_learning/training_systems/` | Data loaders, distributed training, mixed precision, checkpointing, determinism, accelerators, and cost. |
| `deep_learning/neural_tabular/` | Tabular neural nets, embeddings, categorical features, calibration, baselines, and tree-model trade-offs. |
| `deep_learning/sequence_transformers/` | Temporal, transformer, attention, and sequence models for markets, logs, language, and streams. |
| `deep_learning/graph_neural_networks/` | GNNs for networks, collateral chains, counterparties, supply graphs, ownership graphs, and message passing. |
| `deep_learning/reinforcement_learning/` | MDP framing, reward design, simulators, offline RL, policy constraints, safety, and evaluation. |
| `deep_learning/computer_vision/` | Image, document, screenshot, and visual workflows, including augmentation, labeling, and quality checks. |
| `deep_learning/nlp_llm/` | Text classification, retrieval, embeddings, reranking, prompt/eval design, RAG boundaries, and LLM controls. |
| `deep_learning/representation_metric_learning/` | Embeddings, contrastive learning, similarity search, clustering, and representation evaluation. |
| `deep_learning/generative_models/` | Diffusion, VAEs, GANs, synthetic data, scenario generation, augmentation, and privacy/risk limits. |
| `deep_learning/deep_time_series/` | Deep forecasting, temporal fusion, sequence-to-sequence, regime conditioning, and probabilistic forecasts. |
| `deep_learning/compression_serving/` | Distillation, quantization, pruning, batching, latency, memory, GPU utilization, and serving contracts. |
| `deep_learning/deep_portfolio_optimization/` | Direct neural allocation, differentiable portfolio objectives, allocation constraints, baselines, and validation. |
| `deep_learning/portfolio_volatility_costs/` | Volatility scaling, turnover, transaction costs, leverage, after-cost robustness, and implementation frictions. |
| `deep_learning/portfolio_stress_explainability/` | Stress-window allocation behavior, feature attribution, regime explanations, and monitoring hooks. |

## Git Workflow Agent (`git/`)

| Agent | Handles |
| --- | --- |
| `git/` | Branch hygiene, Conventional Commits, hooks, CI guidance, and GitHub workflow support. |

## Knowledge Management Agents (`knowledge/`)

Grouped in the `knowledge/` category folder; they absorb, organize, retrieve, and
persist a company's unstructured institutional knowledge across domains — with
grounding, citations, access control, and provenance.

| Agent | Handles | Feeds mainly |
| --- | --- | --- |
| `knowledge/knowledge_ingestion/` | Absorbing internal sources (wiki, docs, tickets, chat, code) with provenance, access, and PII/secret/MNPI flagging | Planning, cross-cutting |
| `knowledge/knowledge_curation/` | Taxonomy, tagging, deduplication, canonical sources, conflict resolution, staleness/gap detection | Cross-cutting |
| `knowledge/knowledge_retrieval/` | Grounded, cited answers respecting the asker's access level and information barriers | Cross-cutting |
| `knowledge/institutional_memory/` | Persisting decisions, lessons, glossary, and FAQs as durable, referenceable artifacts | Maintenance, cross-cutting |

## Role Operations Agents (`role_operations/`)

Grouped in the `role_operations/` category folder (see
[`role_operations/README.md`](role_operations/README.md)); a quant/data-science
lead's operational overhead — meeting follow-ups, status updates, prototype
setup, first-pass research scans, demo prep — absorbed so more time goes to
model scoping and research. Configurable via a local, gitignored
`role_context.yml`; this repository never carries real platform, client, or
personal data (`role-context` gate). All three phases of the four-pillar
roster are shipped: Phase 1 (spec `0024`), Phase 2 (spec `0029`), and Phase 3
(spec `0030`, governance-adjacent) — fourteen agents in total.

| Agent | Handles | Feeds mainly |
| --- | --- | --- |
| `role_operations/meeting_to_action/` | Notes/transcript → decisions, owners, open items, a draft follow-up | Cross-cutting |
| `role_operations/status_rollup/` | Recent activity → a draft status update, blocked items stated plainly | Cross-cutting |
| `role_operations/rapid_scaffolder/` | New idea → repo skeleton, data-contract stub, naive baseline plan | Planning, Implementation |
| `role_operations/prior_art_scanner/` | Hypothesis → related approaches, failure modes, open questions | Planning |
| `role_operations/demo_narrative_packager/` | Prototype results → situation/insight/recommendation narrative + one-pager | Client & Stakeholder Engagement |
| `role_operations/tough_question_rehearsal/` | Demo material → persona-grouped tough questions with suggested answers | Client & Stakeholder Engagement |
| `role_operations/experiment_ledger/` | Every prototype variant tried → an append-only, no-survivorship-bias log | Implementation |
| `role_operations/model_card_drafter/` | Model info → a draft model card, gaps flagged not fabricated | Testing & Validation |
| `role_operations/audit_trail_keeper/` | A decision as it's made → an append-only decision-log entry | Cross-cutting |
| `role_operations/governance_readiness_checklist/` | Artifact state → each readiness item evidenced, a gap, or n/a | Testing & Validation |
| `role_operations/second_look_backtest_reviewer/` | A backtest result → a fast pre-check, deferring to `backtest_review` | Testing & Validation |
| `role_operations/build_handoff_writer/` | Project state → a draft handoff memo, unresolved items always stated | Deployment & Release |
| `role_operations/alert_triage/` | Routed alerts → a personal priority pass, deferring to `alert_router` | Maintenance & Monitoring |

## Trading Strategy Agents (`trading_strategies/`)

Grouped in the `trading_strategies/` category folder; they operationalize the
strategy archetypes catalogued in *151 Trading Strategies* (Kakushadze & Serur) as
design-and-review roles, each with its own economic rationale, leakage, cost, and
risk concerns.

| Agent | Archetype |
| --- | --- |
| `trading_strategies/momentum_trend/` | Cross-sectional & time-series momentum, trend-following |
| `trading_strategies/mean_reversion_statarb/` | Mean reversion, pairs/stat-arb, index & ETF arbitrage |
| `trading_strategies/carry/` | Carry and roll-down (FX, rates, commodity, dividend) |
| `trading_strategies/value_factor/` | Value, quality, size, low-vol and other factor styles |
| `trading_strategies/volatility_options/` | Variance risk premium, vol arbitrage, options overlays |
| `trading_strategies/event_driven_arbitrage/` | Merger/risk arb, index rebalancing, earnings, convertibles |
| `trading_strategies/macro_multi_asset/` | Global macro, allocation, risk parity, tactical tilts |
| `trading_strategies/market_making_microstructure/` | Liquidity provision, execution alpha, order-book strategies |

## Asset Class Mechanics Agents (`asset_classes/`)

Grouped in the `asset_classes/` category folder (see
[`asset_classes/README.md`](asset_classes/README.md)); mechanics-only agents, one
per asset class, that hand `trading_strategies/` and `securities_financing/` clean,
point-in-time-correct market-structure and data inputs instead of duplicating
mechanics guidance inside every archetype.

| Agent | Handles | Typical strategy handoff |
| --- | --- | --- |
| `asset_classes/equities/` | Venues/sessions, corporate-action adjustment, point-in-time index membership, short-sale mechanics, settlement | `trading_strategies/momentum_trend`, `mean_reversion_statarb`, `value_factor`, `event_driven_arbitrage`; `securities_financing/securities_lending` |
| `asset_classes/fixed_income_rates/` | Day-count/accrual conventions, clean vs dirty price, point-in-time curve construction, credit spreads/ratings, on-the-run status | `trading_strategies/carry`, `macro_multi_asset`, `event_driven_arbitrage`; `optimization/` |
| `asset_classes/fx/` | Spot/forward/swap conventions, settlement/value dates, fixing-window risk, regional session structure | `trading_strategies/carry`, `macro_multi_asset` |
| `asset_classes/commodities/` | Futures curve shape, roll mechanics and roll yield, physical delivery vs cash settlement, storage/carry cost, seasonality | `trading_strategies/carry`, `momentum_trend`, `macro_multi_asset` |
| `asset_classes/digital_assets/` | Venue fragmentation, custody/counterparty risk, perpetual-funding mechanics, 24/7 session structure, on-chain/oracle risk | `trading_strategies/market_making_microstructure`, `momentum_trend`; `securities_financing/collateral_management` |

## Economists Agents (`economists/`)

Grouped in the `economists/` category folder (see
[`economists/README.md`](economists/README.md)); give a quant or
portfolio-management workflow a grounded macro backdrop to start from —
indicator tracking, policy reads, regime classification, cross-asset
translation, forward scenarios, and two report writers (a recurring brief
and a periodic outlook). Analysis and synthesis only: strategy design stays
`trading_strategies/macro_multi_asset`'s job, and live-model regime-change
detection stays `monitoring/model_signal_monitoring`'s job — neither is
duplicated here. Backed by `instructions/macro_economic_analysis.md` and
`sources/{fred,bls,bea,census,eia}.yml` (spec `0033`).

| Agent | Handles | Feeds mainly |
| --- | --- | --- |
| `economists/macro_indicator_analyst/` | Core releases → a vintage-aware, surprise-vs-consensus read | `macro_regime_classifier`, `macro_backdrop_summarizer` |
| `economists/monetary_policy_analyst/` | Central bank stance, rate path, balance sheet → a policy read | `macro_regime_classifier`, `research_analyst` |
| `economists/macro_regime_classifier/` | Indicators + policy → a classified regime, distinct from `model_signal_monitoring`'s regime-change alerts | `macro_multi_asset`, `portfolio_management/allocation_policy` |
| `economists/cross_asset_macro_linkages/` | A regime → cross-asset expression (rates/FX/credit/equities/commodities), no sizing | `research_analyst`, `trading_strategies/*` |
| `economists/macro_scenario_analyst/` | A regime → forward stress scenarios with quantified indicator paths | `risk`, `backtest_review` |
| `economists/macro_backdrop_summarizer/` | All of the above → a concise, recurring macro brief | `research_analyst`, `modeling`, `portfolio_management/*` |
| `economists/economic_outlook_report_writer/` | All of the above → a longer periodic outlook report | `portfolio_management/*`, IC-facing review |
| `economists/morning_brief_writer/` | Real pulled market commentary (spec `0059`) → grounded Views & Analysis for a personal daily brief | staged `pending_review` via `market_brief.candidates_from_brief` |

## Securities Financing Agents (`securities_financing/`)

Grouped in the `securities_financing/` category folder; they make financing a
first-class part of a strategy's economics — borrow, funding, collateral, and their
costs and risks.

| Agent | Handles | Feeds mainly |
| --- | --- | --- |
| `securities_financing/securities_lending/` | Stock loan/borrow: locates, GC vs specials, rebate, recalls, buy-ins, corporate actions | Testing |
| `securities_financing/repo_financing/` | Repo/reverse repo funding, rates, term, haircuts, roll and counterparty risk | Testing |
| `securities_financing/collateral_management/` | Eligibility, haircuts, margin, collateral optimization, rehypothecation, regulatory impact | Deployment |
| `securities_financing/financing_cost_analysis/` | All-in cost of carry, borrow/rebate/funding netting, financing-aware backtesting | Testing |

`securities_lending/` has a tested runtime (spec `0023-securities-lending-workflow`):
`src/quantsmith/quant/agentic_quant/sec_lending_workflow.py` — universe
construction, GC/WARM/HTB classification, LP inventory optimization, and
concentration risk; run via `quantsmith-sec-lending`. `financing_cost_analysis/`
also has a tested runtime (spec `0028-financing-cost-analysis`):
`src/quantsmith/pipelines/financing_cost_analysis.py` — cost-of-carry
decomposition, financing-aware returns, understated-backtest flags,
rate-shock sensitivity, and capacity findings, reconciling with
`securities_lending`'s rate/classification vocabulary by value.

## Formulaic Alpha Agents (`formulaic_alphas/`)

Grouped in the `formulaic_alphas/` category folder; they operationalize the
formulaic-alpha methodology of *101 Formulaic Alphas* (Kakushadze, 2016) — building
tradable signals as formulas from an operator library, combining them, and evaluating
them.

| Agent | Handles | Feeds mainly |
| --- | --- | --- |
| `formulaic_alphas/alpha_construction/` | Building alphas from the operator library, neutralization, point-in-time correctness | Research, Testing |
| `formulaic_alphas/alpha_combination/` | Combining alphas: correlation, spanning, weighting, diversification | Research, Testing |
| `formulaic_alphas/alpha_evaluation/` | Holding period, turnover, volatility dependence, correlation, capacity, decay | Testing |

## Analytics Agents (`analytics/`)

Specialist roles that make **Data Analyst** work consistent (see
[`analytics/README.md`](analytics/README.md)). They sit mid-chain between EDA and the
dashboard/reporting agents.

| Agent | Handles | Feeds mainly |
| --- | --- | --- |
| `analytics/metrics_semantic_layer/` | Canonical KPI definitions — one source of truth, point-in-time computation, declared dimensions, ratio metrics | Reporting, Dashboards, Testing |
| `analytics/experimentation/` | A/B test design and readout — power/sample-size, sample-ratio-mismatch validity, p-value/CI consistency, power-gated verdict | Reporting, Testing |
| `analytics/data_storytelling/` | Governed `Report` → audience-tailored narrative (situation → insight → action); reuse-only, evidence-bounded | Reporting, Dashboards |
| `analytics/dashboard_design/` | Tool-agnostic dashboard spec (hierarchy, chart selection, drill paths, accessibility) | Dashboards, Reporting |

The last two are the communication layer (spec `0014-data-analyst-storytelling`) — they
compose `0008`/`0009`/`0010` outputs and hand off to `reporting-agent` and the
tool-specific dashboard agents. Runtimes:
`src/quantsmith/pipelines/metrics_semantic_layer.py`,
`src/quantsmith/pipelines/experimentation.py`; specs:
`specs/0008-metrics-semantic-layer/`, `specs/0009-experimentation/`,
`specs/0014-data-analyst-storytelling/`; standards:
`instructions/metrics_semantic_layer.md`, `instructions/data_storytelling.md`,
`instructions/model_validation.md`.

## Analytics Pipeline Agents

A runtime multi-agent analytics/dashboard pipeline (consolidated from other
projects and normalized to the four-file contract). Each also keeps its original
`SKILL.md`. They form a chain: orchestrate → query → prep → explore → visualize →
guard → report.

| Agent | Handles |
| --- | --- |
| `orchestrator-agent/` | Routes a natural-language analytics request across the pipeline agents |
| `sql-integration-agent/` | Safe, parameterized SQL querying and schema discovery |
| `data-prep-agent/` | Cleaning, profiling, transformation, and lineage |
| `eda-specialist-agent/` | Exploratory data analysis and hypothesis generation |
| `tableau-dashboard-agent/` | Schema-validated Tableau dashboard payloads |
| `powerbi-dashboard-agent/` | Schema-validated Power BI report payloads with governance |
| `quality-guard-agent/` | Contract, schema, and policy quality gates before release |
| `reporting-agent/` | Stakeholder-ready report artifacts with provenance |

These overlap conceptually with SDK agents (`workflow_orchestrator`,
`data_ingestion/`, `tooling/`, `testing_validation`) but are a distinct runtime
pipeline; the SDK agents are design-and-review roles.

## How They Fit Together

1. The **orchestrator** determines the lifecycle position and the next gate.
2. It routes to the **lifecycle agent** that owns the current stage.
3. That agent pulls in **domain agents** for the expertise it needs.
4. The **hooks** verify the gate mechanically before the orchestrator advances.
5. The **spec** carries state between stages as the single source of truth.
6. The **adapters** connect approved payloads to providers without changing agent
   logic.
7. Runtime Python belongs under `src/quantsmith/`; agent directories describe
   roles, prompts, instructions, and tasks.

## Adding An Agent

- Create the agent directory with all four contract files (the pre-commit,
  pre-push, and CI checks require them). A public agent is any directory
  containing `prompt.md`, at any depth under `agents/`.
- Related agents may be grouped in a **category folder** (e.g.
  `agents/data_ingestion/`) with its own `README.md` describing the group; the
  category folder itself is not an agent (it has no `prompt.md`).
- Give each agent a narrow, inspectable responsibility.
- Add a `Spec-Driven Role` section to its `instructions.md`.
- Add a row to the relevant table above.
