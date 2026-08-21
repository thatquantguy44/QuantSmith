# Specs

Each unit of work lives in its own directory here, following Spec-Driven
Development (see `instructions/spec_driven_development.md`).

```
specs/
  NNNN-short-slug/
    spec.md    # WHAT and WHY  — requirements, acceptance criteria, non-goals
    plan.md    # HOW           — architecture, data contracts, trade-offs
    tasks.md   # WORK          — ordered, traceable, testable tasks
```

- `NNNN` is a zero-padded sequence number; the slug is short kebab-case.
- Start from `templates/spec/`.
- The `spec-check` hook (`hooks/stages/spec-check.sh`) validates the chain and
  traceability across these directories.

## Index

Specs `0001`, `0006`–`0013`, `0015`, `0016`, `0018`–`0021`, `0028`, `0034`–`0036`, `0038`, `0039`, `0041`, `0042`, `0044`–`0046`, and `0048` have dependency-free reference runtimes under
`src/quantsmith/pipelines/` (catalogued in
[`../src/quantsmith/pipelines/README.md`](../src/quantsmith/pipelines/README.md)),
each with a matching test module under `tests/`.

| ID | Feature | Runtime (`src/quantsmith/pipelines/`) | Tests (`tests/`) | Status |
| --- | --- | --- | --- | --- |
| [0001-daily-momentum-signal](0001-daily-momentum-signal/) | Daily cross-sectional momentum signal | `momentum_signal.py` | `test_momentum_signal.py` | Approved (reference) |
| [0002-workflow-memory](0002-workflow-memory/) | Persistent workflow memory scaffold | `memory/` scaffold | `memory` gate | Approved |
| [0004-optimizer-ml-dl-agent-expansion](0004-optimizer-ml-dl-agent-expansion/) | Optimizer, ML, and DL agent expansion | — (agent contracts) | catalog/docs gates | Approved |
| [0006-ml-return-forecasting](0006-ml-return-forecasting/) | Cross-sectional short-horizon return forecasting | `return_forecasting.py` | `test_return_forecasting.py` | Approved |
| [0041-ranking-forecast](0041-ranking-forecast/) | Cross-sectional ranking forecast — a pairwise (RankNet-style) ranking-loss variant of `0006`, composing `0006`'s labels/features/folds/evaluation unmodified | `ranking_forecast.py` | `test_ranking_forecast.py` | Approved |
| [0047-downstream-contract](0047-downstream-contract/) | Downstream consumer contract — `DashboardSpec.schema_version` + `check_schema_compatibility`, a release-notify workflow dispatching to downstream repositories, and a copyable `quantsmith-version` gate flagging a consumer's unpinned or drifted dependency; makes SemVer real before a second repo depends on it | `dashboard_spec.py` (extended) | `test_dashboard_contract.py` | Approved |
| [0048-workflow-memory-runtime](0048-workflow-memory-runtime/) | Workflow memory runtime & author attribution — read path for the *Company knowledge over time* initiative (`docs/handoff.md` item 15; scaffold is `0002`, write path planned as `0049`) — makes `0002`'s store machine-readable: typed records, a type-aware point-in-time rule (mechanical facts are timeless, claims about what worked are bounded by `last_confirmed`), contradiction and supersession validation, derived corroboration, decay against the `freshness_days` nothing has ever read, and an author handle structurally incapable of being an email | `workflow_memory.py` | `test_workflow_memory.py` | Approved |
| [0046-walk-forward](0046-walk-forward/) | Walk-forward backtest harness — composes `0006`'s purged/embargoed `make_folds` with `0044`'s engine, refitting per fold and evaluating on held-out periods; reports the fold distribution (dispersion, positive fraction) rather than one in-sample number | `walk_forward.py` | `test_walk_forward.py` | Approved |
| [0045-fred-point-in-time](0045-fred-point-in-time/) | FRED point-in-time panel adapter — reads `gold_fred_point_in_time` from the FRED bronze-to-gold pipeline's local SQLite output and answers vintage-correct questions via `realtime_start`/`realtime_end`, so a revision published later can never leak backwards into an earlier as-of date | `fred_point_in_time.py` | `test_fred_point_in_time.py` | Approved |
| [0044-backtesting](0044-backtesting/) | Backtest engine — net-of-cost simulation with no look-ahead by construction (`weights[i]` meets `returns[i+lag]`, `lag >= 1`), turnover-scaled costs, financing on shorts, drawdown, and a probabilistic Sharpe on every run; ships the repo's first backtest artifact, making the CI-enforced `backtest` gate live | `backtesting.py` | `test_backtesting.py` | Approved |
| [0043-doc-counts-gate](0043-doc-counts-gate/) | Documented-count drift gate — derives the true agent, gate, and instruction-standard counts from the filesystem and flags every stated count in the narrative docs that disagrees; the class of drift `agent-catalog`/`spec-index`/`readme-sync` cannot see, because it lives in prose | — (gate only) | `doc-counts` gate | Approved |
| [0042-pipeline-builder](0042-pipeline-builder/) | Pipeline builder — compiles a declared source→transform→sink intent into a DAG validated by `0011`'s own toposort, reviews it against the pipeline-engineering checklist, and renders a `pipeline_manifest.md`; ships the repo's first manifest artifact, making the `pipeline-contract` gate live | `pipeline_builder.py` | `test_pipeline_builder.py` | Approved |
| [0007-portfolio-construction](0007-portfolio-construction/) | Constrained portfolio construction (QP) | `portfolio_construction.py` | `test_portfolio_construction.py` | Approved |
| [0008-metrics-semantic-layer](0008-metrics-semantic-layer/) | Metrics semantic layer | `metrics_semantic_layer.py` | `test_metrics_semantic_layer.py` | Approved |
| [0009-experimentation](0009-experimentation/) | Experiment (A/B test) analysis | `experimentation.py` | `test_experimentation.py` | Approved |
| [0010-analytics-pipeline](0010-analytics-pipeline/) | End-to-end analytics pipeline | `analytics_pipeline.py` | `test_analytics_pipeline.py` | Approved |
| [0011-data-pipeline-orchestration](0011-data-pipeline-orchestration/) | Data-pipeline orchestration (DAG runner) | `data_pipeline.py` | `test_data_pipeline.py` | Approved |
| [0012-execution-scheduling](0012-execution-scheduling/) | Optimal execution scheduling (Almgren-Chriss) | `execution_optimization.py` | `test_execution_optimization.py` | Approved |
| [0013-optimization-solvers](0013-optimization-solvers/) | Optimization solvers (LP/MILP/flow/DP) | `optimization_solvers.py` | `test_optimization_solvers.py` | Approved |
| [0014-data-analyst-storytelling](0014-data-analyst-storytelling/) | Data Analyst storytelling & dashboard expansion | — (agents; reuses `0010` Report) | catalog/docs gates | Approved |
| [0015-powerbi-dashboard-profile](0015-powerbi-dashboard-profile/) | Power BI dashboard profile (renders the shared dashboard spec) | `dashboard_spec.py`, `powerbi_profile.py` | `test_powerbi_profile.py` | Approved |
| [0016-excel-react-dashboard-profiles](0016-excel-react-dashboard-profiles/) | Excel and React dashboard profiles (render the shared dashboard spec) | `excel_profile.py`, `react_profile.py` | `test_excel_react_profiles.py` | Approved |
| [0017-dashboard-render-adapters](0017-dashboard-render-adapters/) | Executable render adapters — React scaffold + `.xlsx` writer | `adapters/dashboard_render/` (not `pipelines/`) | `test_dashboard_render_adapters.py` | Approved |
| [0018-remaining-dashboard-profiles](0018-remaining-dashboard-profiles/) | Streamlit/Looker/Superset/Qlik renderers + Streamlit scaffolder | `bi_profiles.py`, `adapters/dashboard_render/streamlit_scaffold.py` | `test_bi_profiles.py` | Approved |
| [0019-pipeline-observability](0019-pipeline-observability/) | Data-pipeline observability — freshness, downtime, SLA, lineage | `pipeline_observability.py` | `test_pipeline_observability.py` | Approved |
| [0020-alerting](0020-alerting/) | Alerting — policy evaluation + routing (dedup, suppress, escalate) | `alerting.py` | `test_alerting.py` | Approved |
| [0021-signal-monitoring](0021-signal-monitoring/) | Model/signal monitoring — drift, calibration, decay, regime | `signal_monitoring.py` | `test_signal_monitoring.py` | Approved |
| [0022-asset-class-mechanics-agents](0022-asset-class-mechanics-agents/) | Asset class mechanics agent expansion (equities, fixed income/rates/credit, FX, commodities, digital assets) | — (agent contracts) | catalog/docs gates | Approved |
| [0023-securities-lending-workflow](0023-securities-lending-workflow/) | Securities lending workflow — borrow classification, LP inventory optimization, concentration risk | `quantsmith/quant/agentic_quant/sec_lending_workflow.py` (not `pipelines/`) | `test_sec_lending_workflow.py` | Approved |
| [0024-role-operations-agents](0024-role-operations-agents/) | Role operations agent expansion, Phase 1 (meeting/status/scaffolding/research-scan toil, configurable, no company data) | — (agent contracts) | catalog/docs gates, `role-context` gate | Approved |
| [0025-data-provenance-guardrail](0025-data-provenance-guardrail/) | Data provenance guardrail — real-data-first priority stack + synthetic-data disclosure | — (standard/template/gate) | `data-provenance` gate | Approved |
| [0026-model-plugin-adapter](0026-model-plugin-adapter/) | Model plugin adapter — register a prebuilt internal optimization model as a reviewed, contract-bound plugin | `adapters/model_plugin/` (contract only, not `pipelines/`) | `model-plugin` gate | Approved |
| [0027-source-catalog](0027-source-catalog/) | Data source catalog — centralized, per-source registry of APIs/DBs/feeds with quality, point-in-time, and credential-pointer metadata | `sources/` (catalog only, not `pipelines/`) | `source-catalog` gate | Approved |
| [0028-financing-cost-analysis](0028-financing-cost-analysis/) | Financing cost analysis — cost-of-carry decomposition, financing-aware returns, understated-backtest flags, rate-shock sensitivity, capacity findings | `financing_cost_analysis.py` | `test_financing_cost_analysis.py` | Approved |
| [0029-role-operations-agents-phase2](0029-role-operations-agents-phase2/) | Role operations agent expansion, Phase 2 (prototype accelerators: demo narrative, tough-question rehearsal, experiment ledger) | — (agent contracts) | catalog/docs gates | Approved |
| [0030-role-operations-agents-phase3](0030-role-operations-agents-phase3/) | Role operations agent expansion, Phase 3 (governance-adjacent: model card, decision log, governance readiness, backtest pre-check, build handoff, alert triage) — roster complete | — (agent contracts) | catalog/docs gates | Approved |
| [0031-remaining-backing-instructions](0031-remaining-backing-instructions/) | Remaining backing instructions — risk management, data ingestion (shared standard), reproducibility (operationalizes P4 for the `repro` gate) | — (standards only) | catalog/docs gates | Approved |
| [0032-alert-delivery-providers](0032-alert-delivery-providers/) | Alert delivery executable providers — email and webhook, deterministic payload construction, redaction, and an injectable transport seam (no network code in the SDK) | `adapters/alert_delivery/` (not `pipelines/`) | `test_alert_delivery_adapters.py` | Approved |
| [0033-economists-agents](0033-economists-agents/) | Economists agent expansion — indicator tracking, policy reads, regime classification, cross-asset translation, forward scenarios, and two report writers (brief + outlook) giving a macro backdrop to quant/PM workflows | — (agent contracts) | catalog/docs gates | Approved |
| [0034-cardinality-constrained-portfolio](0034-cardinality-constrained-portfolio/) | Cardinality-constrained portfolio construction — a two-stage heuristic composing `0013`'s MILP (select) and `0007`'s QP (size), long-only, honestly disclosed as non-joint-optimal | `cardinality_portfolio.py` | `test_cardinality_portfolio.py` | Approved |
| [0035-funding-ladder](0035-funding-ladder/) | Funding ladder min-cost flow — matches cash obligations to funding tenors at minimum cost via `0013`'s `min_cost_flow`; general treasury/cash tool, not securities-financing | `funding_ladder.py` | `test_funding_ladder.py` | Approved |
| [0036-multi-period-rebalancing](0036-multi-period-rebalancing/) | Multi-period rebalancing — a discretized single-position DP via `0013`'s `solve_dp`, trading transaction cost against tracking-error cost over a horizon; closes out every `0013` solver having a shipped application | `multi_period_rebalancing.py` | `test_multi_period_rebalancing.py` | Approved |
| [0037-alert-delivery-remaining-providers](0037-alert-delivery-remaining-providers/) | Alert delivery — Slack, Teams, ticketing, PagerDuty/Opsgenie, SMS/push executable providers, completing the adapter's Recommended Starting Set; structural severity gating + SMS length cap | `adapters/alert_delivery/{slack,teams,ticketing,pagerduty_opsgenie,sms_push}.py` (not `pipelines/`) | `test_alert_delivery_adapters.py` | Approved |
| [0038-factor-risk-model](0038-factor-risk-model/) | Factor risk model — variance decomposition, Euler risk attribution, concentration, linear stress loss; operationalizes `instructions/risk_management.md` (`0031`) with a tested runtime | `factor_risk_model.py` | `test_factor_risk_model.py` | Approved |
| [0039-ingestion-data-contract](0039-ingestion-data-contract/) | Ingestion data contract emission — validates a pulled row set against a declared schema/key/quality-rule contract and renders a `data_contract.md` populated with real, computed results; closes the worked-example gap `docs/handoff.md` had carried since `0006` | `ingestion_data_contract.py` | `test_ingestion_data_contract.py` | Approved |
| [0040-readme-sync-gate](0040-readme-sync-gate/) | README index/runtime sync gate — verifies every spec with a tested runtime (a `test_*.py` module named in this index's Tests column) also appears in root `README.md`'s runtime table; the sync check `agent-catalog`/`spec-index` didn't cover | — (gate only) | `readme-sync` gate | Approved |

`0001-daily-momentum-signal/` is a filled-in reference showing the ID scheme and
traceability end to end. Copy its structure, not its content.

### Chains & themes

- **Quant research:** `0001` signal → `0006` forecast (`0041` ranking-loss variant) → `0007` portfolio → `0012` execution → `0038` factor risk (decomposition, attribution, stress) → `0044` backtest (net of costs, probabilistic Sharpe, no look-ahead by construction) → `0046` walk-forward (purged/embargoed folds, out-of-sample distribution). The chain now ends in a measured, out-of-sample result rather than a design.
- **Optimization toolkit:** `0007` (QP), `0013` (LP/MILP/flow/DP), `0012` (control), `0026` (plugin contract for prebuilt internal models), `0034` (cardinality-constrained portfolio — `0013`'s MILP composed with `0007`'s QP), `0035` (funding ladder — `0013`'s min-cost flow, general treasury/cash, not securities-financing), `0036` (multi-period rebalancing — `0013`'s DP, a discretized single position over a horizon). Every `0013` solver now has a shipped application.
- **Data foundations:** `0027` source catalog (registry) → `data_contract.md` (per-dataset) → `agents/data_ingestion/` (ingestion) → `0039` ingestion data contract emission (validates real rows, renders a populated contract) → `data_quality`/`point_in_time` (review).
- **Data Analyst:** `0008` metrics → `0009` experimentation → `0010` end-to-end
  pipeline → `0014` storytelling & dashboards → `0015`/`0016` dashboard profiles (Power BI, Excel, React) → `0017` executable render adapters → `0018` remaining BI profiles (communication layer).
- **Data Engineer:** `0042` pipeline builder (design-time: compile intent → readiness review → manifest) → `0011` pipeline orchestration (execution) → `0019` pipeline observability.
- **Monitoring & alerting:** `0021` signal monitoring → `0020` alerting → `adapters/alert_delivery/` (`0032` ships email + webhook; `0037` ships Slack, Teams, ticketing, PagerDuty/Opsgenie, SMS/push — all seven providers now executable).
- **Securities financing:** `0022` asset-class mechanics (equities shorts) → `0023` securities lending workflow → `0028` financing cost analysis (`repo_financing`/`collateral_management` remain agent-contract only) → `backtest_review`/`risk`.
- **Macro & economics:** `0027` source catalog (FRED/BLS/BEA/Census/EIA) → `0033` economists agents (indicators → policy → regime → cross-asset/scenario → brief/outlook reports) → `trading_strategies/macro_multi_asset`, `portfolio_management/allocation_policy`, `risk`.
- **Cross-cutting:** `0002` workflow memory; `0004` agent expansion; `0022` asset-class mechanics agents (feed `trading_strategies/` and `securities_financing/`); `0024` role-operations agents Phase 1 → `0025` data-provenance guardrail (real-data-first + synthetic-data disclosure, backing `0024`'s `rapid_scaffolder` and cross-referenced by `dashboard_design`/`data_storytelling`) → `0029` role-operations agents Phase 2 → `0030` role-operations agents Phase 3 (governance-adjacent: model card, decision log, governance readiness, backtest pre-check, build handoff, alert triage — hands off to `backtest_review`/`alert_router`/`incident_notification` rather than replacing them). Fourteen-agent roster complete, configurable via a local-only `role_context.yml`.

**Next free spec number: `0055`** (`0003`/`0005` belong to the local-only pack).
`0049`–`0054` are **reserved but not yet written** — see the *Planned specs*
table in [`../docs/handoff.md`](../docs/handoff.md) for what each covers and
what it depends on.
