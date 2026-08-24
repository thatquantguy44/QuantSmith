# QuantSmith Handoff

## Snapshot

The SDK has a working v1: a **spec-driven engineering framework** over the six
software-development stages, **162 agents** in `agents/`,
**33 quality gates**, **33 instruction standards**, and CI that
enforces the deterministic gates. It remains primarily a scaffold to be copied
into quant repos, with `src/quantsmith/pipelines/` holding runnable, dependency-free
reference pipelines for most specs (see `specs/README.md`'s index for the current
list), and `src/quantsmith/quant/agentic_quant/` holding a further runtime (spec
`0023`) with `numpy`/optional-`scipy` dependencies. `adapters/` is a first-class
SDK surface (6 groups) — the provider boundary between agent decisions and
external systems (delivery, scheduling, storage, data access, model runtimes).

- Build-out branch: `claude/dev-stages-hooks-agents-co1sjj` (open as PR #4 into `main`).
- Root `CLAUDE.md` activates the framework by default for any agent in the repo.
- `agents/README.md` is the agent catalog and the orchestrator's routing table.

## Architecture

**Spec-Driven Development** — the spec is the source of truth; everything traces to
it via stable IDs (`REQ`/`NFR`/`AC`/`RISK`/`T`).

- `instructions/engineering_principles.md` — the constitution (P1–P10).
- `instructions/spec_driven_development.md` — flow, ID scheme, gates.
- `specs/NNNN-slug/{spec,plan,tasks}.md` from `templates/spec/`; worked example at
  `specs/0001-daily-momentum-signal/`.

**Agents (162, verified by the `agent-catalog` gate — treat `agents/README.md`
as the live count, not the number here)** — all on the four-file contract
(`README`/`prompt`/`instructions`/`tasks`) with a `Spec-Driven Role`:

- Orchestrator: `workflow_orchestrator/`.
- Lifecycle (one per stage): `planning_requirements`, `design_architecture`,
  `implementation`, `testing_validation`, `deployment_release`, `maintenance_monitoring`.
- Core domain: `research_analyst`, `data_quality`, `feature_engineering`, `modeling`,
  `backtest_review`, `risk`, `git_release`.
- Groups (largest first): `optimization/`, `deep_learning/`, `machine_learning/`,
  `tooling/`, `data_engineering/`, `trading_strategies/`, `asset_classes/`,
  `secrets_management/`, `securities_financing/`, `knowledge/`, `analytics/`,
  `role_operations/`, `monitoring/`, `alerts/`, `data_ingestion/`,
  `formulaic_alphas/` — see `agents/README.md` for per-group membership and
  counts, which change more often than this file is refreshed.

**Gates (33)** in `hooks/stages/`, driven by `run-stage.sh`; advisory by default,
`QF_STAGE_ENFORCE=1` blocks:

- Cross-cutting: `spec`. Per stage: `planning`, `design`, `implementation`,
  `testing`, `deployment`, `maintenance`.
- Quant: `leakage`, `backtest` (incl. a financing theme for shorts),
  `repro`, `data-contract`, `pipeline-contract`, `alert-contract`,
  `monitoring-coverage`, `data-provenance`.
- Repo: `secret-scan`, `docs-link`, `agent-catalog`, `spec-index`, `readme-sync`,
  `doc-counts`, `quantsmith-version`, `agent-attribution`, `handoff-sync`, `upstream-drift`, `ownership`, `persistent-knowledge`, `knowledge`, `memory`, `access`, `role-context`,
  `model-plugin`, `source-catalog`.

**Instructions (33)** — constitution, SDD method, point-in-time, and the domain
standards; see `README.md`'s "Public Instructions" table for the current list
(this file lists categories, not every filename, to avoid drifting again).

**Templates & prompts** — `templates/spec/`, `templates/docs/` (research memo,
dataset/model card, backtest report, run card, model monitoring plan, incident
postmortem, handoff memo, production readiness, decision log),
`templates/data/data_contract.md`, `templates/knowledge/knowledge_sources.yml`,
and matching prompts.

**Configurable knowledge sources** — the knowledge agents plug into external
repositories declared in `knowledge_sources.yml` (subfolders as domains), validated
by the `knowledge` gate.

**Scheduled workflow operations** — spec `0055-workflow-scheduling-operations`
defines the agentic control plane for cron/jobs/scripts/Python/workflows: a schedule
registry, scheduler-adapter validation, execution ledger, manual task reminders,
daily status reports, failure routing, and memory handoff for recurring operational
learnings. It builds on `adapters/schedulers/`, `0019-pipeline-observability`,
`0020-alerting`, and `0002-workflow-memory`.

## Conventions To Preserve

- A public agent is any directory containing `prompt.md` (any depth under `agents/`)
  with all four contract files plus a `Spec-Driven Role`; group related agents in a
  category folder (its own `README.md`, no `prompt.md`). Add a catalog row.
- A domain gets a backing `instructions/*.md` standard when multiple agents/gates
  share it.
- Specs are the source of truth; assign stable IDs and keep traceability intact.
- Conventional Commits; work on the feature branch; a merged PR is finished (start
  follow-ups fresh from `main`, rebasing unmerged commits).
- Gates degrade gracefully when optional tools are missing.

## Quality Gates — Enforced vs Advisory

- **Enforced in CI:** required docs, agent contract, shell syntax, `spec`,
  `backtest`, `secret-scan`, `role-context`, `docs-link`, `agent-catalog`, `spec-index`, and the pytest suite
  (`tests/`, run against the package's declared dependencies).
- **Advisory:** `leakage` (heuristic by design) and the per-stage/quant gates not
  listed above. Graduate a gate to enforced per repo as discipline matures.

## What's Next (prioritized)

**Highest priority, in order: (1) the knowledge base, (2) scheduler
monitoring.** Everything else in this section is real, tracked work, but
these two are what should get attention first if only one thing can move at
a time:

1. **Knowledge base (item 15, "Company knowledge over time").** The
   read/write runtime and both front ends are built (`0048`/`0049`/`0057`),
   and per-person access control now closes the enforcement gap
   (`0058`) — but the store itself is still five reference records
   (`PERSISTENT_KNOWLEDGE.md`'s own honest count) and the market-research
   half (`0056`) is a fictional-content-only reference implementation, not a
   deployed knowledge base. The machinery is ahead of the content. Populating
   it with real findings, and moving `0056` from Draft to built, is
   higher-leverage than any further machinery on top of what already exists.
   MCP exposure (item 17) is the next step *after* there is real content
   worth a team reaching for over the network — building the server first
   would expose an empty store.
2. **Scheduler monitoring (spec `0055`).** The control plane itself is built
   and has a real worked example (`examples/scheduled_daily_report/`), but
   nothing yet watches it in practice: `alert_handoffs()` returns payloads,
   not delivered alerts (wiring them to a real `adapters/alert_delivery/`
   provider is unbuilt), there is no `workflow_scheduling_cli` to render a
   daily operations report without a bespoke script per team, and the
   enforceable-vs-advisory deployment decision named in
   `specs/0055-workflow-scheduling-operations/tasks.md`'s Follow-ups is still
   open. Until failed/missed runs actually page someone, the scheduling
   layer records history without doing the "watch it while it runs" job it
   exists for.

### Planned specs (reserved, not yet written)

The one place to see committed-to work that has no spec directory yet. The
`handoff-sync` gate cannot protect these: it checks that every spec *directory*
is referenced here, so work that exists only as an intention is invisible to it.
This table is the manual counterpart — if a number below never becomes a
directory, that should be a deliberate decision recorded here, not a thing
nobody noticed.

| Spec | What | Depends on | Tracked in |
| --- | --- | --- | --- |
| `0049` | Workflow memory **write path** — `propose_records()` at the runtime boundary, committed `memory/inbox/` staging, `promote()` on human review | `0048` read path (`T-002`/`T-004`) | item 15 |
| `0050` | **Portable doc-integrity gates** — parameterize against `quantsmith.conf`; collapse `agent-catalog`+`spec-index` into one `catalog-sync` | the three shapes (done, item 16) | item 16 |
| `0051` | **Conformance levels** — make `QF_CONFORMANCE_LEVEL` verified rather than declared | `0050` config contract | item 16 |
| `0052` | **MCP adapter contract + resources server** — `adapters/mcp_servers/`, serving `knowledge_sources.yml` over the resources primitive | none (reuses the existing manifest) | item 17 |
| `0053` | **MCP memory-graph server** — tools over `0048`'s store, with `as_of` honouring the type-aware point-in-time rule | `0048` `T-002`/`T-004`; ideally `0049` | item 17 |
| `0054` | **MCP RAG server** — vector search with per-access-tier indexes and cited passages | `0052` contract | item 17 |

**Next free spec number: `0060`.** Reserving a number here does not create the
directory; run `./scripts/new-spec.sh` (or copy `templates/spec/`) when the work
actually starts.


**Scheduled workflow operations control plane — built** (spec
`0055-workflow-scheduling-operations/`, `workflow_scheduling.py`). Covers cron
jobs, Python scripts/modules, QuantSmith pipelines, and agentic workflows as
deployable scheduled jobs: a registry → scheduler dry-run → dispatcher →
execution ledger → daily status report loop, with manual task reminders and
failure/overdue routing into alerting. This is the missing operating layer for
recurring desk workflows: "what ran, what completed, what failed, what needs a
human, what runs next, and what should be learned for next time." Local and
dependency-free by design; `adapters/schedulers/` (cron, GitHub Actions,
Airflow, Dagster/Prefect) remain contract-only Markdown, not executable
deploy code — the same "spec first, executable providers later" pattern
`alert_delivery` followed before specs `0032`/`0037`. A concrete worked
example now exists: `examples/scheduled_daily_report/` runs the full loop
against a real target (a workflow-memory review digest, reusing `0048`'s
`validate` and `0057`'s `build_review_queue`), with a committed sample output
and a documented two-cron-entry real deployment. See
`specs/0055-workflow-scheduling-operations/tasks.md`'s Follow-ups for what's
still open (enforceable vs. advisory deployment; a `workflow_scheduling_cli`).

1. **P0 optimizer-agent workflow expansion — every `0013` solver now has a shipped
   application.** The optimization group has runtimes for the core mathematical
   forms plus five applications: convex QP (`specs/0007-portfolio-construction/`),
   a closed-form control (`specs/0012-execution-scheduling/`), the solver toolkit
   (`specs/0013-optimization-solvers/`: LP, MILP, min-cost flow, dynamic programming),
   **cardinality-constrained portfolio construction**
   (`specs/0034-cardinality-constrained-portfolio/`, `cardinality_portfolio.py` —
   composes `0013`'s MILP with `0007`'s unmodified QP, disclosed explicitly as a
   two-stage heuristic rather than a joint MIQP solve), the **funding ladder**
   (`specs/0035-funding-ladder/`, `funding_ladder.py` — a bipartite
   tenor-to-obligation network on `0013`'s `min_cost_flow`, a general
   treasury/cash-funding tool, explicitly not securities-financing), and
   **multi-period rebalancing** (`specs/0036-multi-period-rebalancing/`,
   `multi_period_rebalancing.py` — a discretized single-position DP on `0013`'s
   `solve_dp`, trading transaction cost against tracking-error cost over a
   horizon; unlike `0034`/`0035` it has no "infeasible" outcome, since "stay put"
   is always a valid action). The quant chain runs signal → forecast → portfolio
   → execution. Next: conic/global/nonlinear solver forms when a dependency-free
   method or an optional solver dependency is chosen. (Securities-financing LP
   work is deliberately out of scope: that domain routes to an adopter's own
   models via `agents/optimization/model_plugin_registration/`, spec `0026`,
   rather than the SDK
   owning the optimization logic itself — see item 5.)
2. **Machine-learning and deep-learning workflow expansion** — the agent roster
   is specified by `specs/0004-optimizer-ml-dl-agent-expansion/` (the
   `optimization/`, `machine_learning/`, and `deep_learning/` groups as agent
   contracts, verified by the catalog/docs gates rather than a runtime). The
   first runtime workflow is shipped as `specs/0006-ml-return-forecasting/` (ML
   build chain end to end with a DL challenger, plus a runnable reference
   pipeline and tests), with `specs/0041-ranking-forecast/` as its ranking-loss
   variant. Next: add more ML/DL worked examples (RL, forecasting variants) as
   the desk needs them.
3. **Data-engineering & data-analyst spec + runtime coverage** — closing the biggest
   structural gap, role by role.
   - **Data Analyst — analysis + communication layers shipped.** Governed analysis:
     `metrics_semantic_layer/` (spec `0008`), `experimentation/` (spec `0009`), and the
     end-to-end capstone `specs/0010-analytics-pipeline/` (tested runtime that reuses
     the `0008` layer). Communication layer (spec `0014-data-analyst-storytelling`):
     `data_storytelling/` (governed `Report` → narrative) and `dashboard_design/`
     (tool-agnostic dashboard spec), backed by `instructions/data_storytelling.md` —
     both **reuse** `0008`/`0009`/`0010` and hand off to `reporting-agent` and the
     tool-specific dashboard agents (no duplication). No `(planned)` nodes remain in
     the core Data Analyst or Analytics Pipeline chains. **Dashboard profiles shipped:**
     a tool-agnostic `DashboardSpec` contract plus renderers for **Power BI**
     (`specs/0015-powerbi-dashboard-profile/`), **Excel**, and **React**
     (`specs/0016-excel-react-dashboard-profiles/`), each mapping the *same* spec to a
     validated payload; `tooling/react` was added (Excel/Power BI reuse existing
     agents). Live artifact generation is shipped: the `adapters/dashboard_render/` contract
     plus **executable providers** (specs `0017`/`0018`) — `scaffold_react`,
     `write_xlsx` (openpyxl, lazy), and `scaffold_streamlit`, all dry-run-capable with a
     checksum manifest and a no-secrets guard. **Dashboard track complete:** the shared
     `DashboardSpec` now renders to **seven targets** — Power BI, Excel, React
     (`0015`/`0016`) and Streamlit, Looker, Superset, Qlik (`0018`) — each with a
     `tooling/` agent. **Open Data Analyst track:** executable emitters for
     Looker/Superset/Qlik and a `powerbi_publish` provider (payload/agents exist), an
     optional `analytics/data_visualization` agent, and optional continuous-metric /
     sequential experiment designs.
   - **Data Engineer — group fully staffed; two runtime nodes.** The
     `agents/data_engineering/` group now has all six agents: `pipeline_orchestration`
     (DAG runner — spec `0011`, tested runtime) and `pipeline_observability` (freshness/
     downtime/SLA/lineage from the run manifest — spec `0019`, tested runtime), plus
     `data_modeling`, `pipeline_builder`, `pipeline_deployment`, and `data_governance`
     as design/review agents. The Data Engineer chain in `docs/workflows.md` has no
     remaining `(planned)` nodes. Backed by `instructions/pipeline_engineering.md`.
     Follow-ups closed: the **`pipeline-contract-check.sh` gate** (validates a pipeline
     manifest against `templates/data/pipeline_manifest.md`; enforced in CI, skips when
     absent) and **per-step SLA thresholds** in `observe` (`0019`). The four
     design/review nodes (`data_modeling`, `pipeline_builder`, `pipeline_deployment`,
     `data_governance`) get executable runtimes only when a concrete workflow needs
     one. The `src/quantsmith/agentic_code_tools/*` modules (SQL, EDA, prep, BI) remain
     runtime not tied to any spec. Backlog detail in `docs/handoffs/future_features.md`.
4. **Role-operations agent roster (Data Science Lead efficiency plan) — done.**
   All three phases of a 14-agent roster shipped, absorbing a
   quant/data-science lead's operational toil so more time goes to model
   scoping and research. Full roster and rationale: the role-efficiency
   plan this initiative implements (see `agents/role_operations/README.md`
   for the phase breakdown carried in-repo). Backlog detail also tracked
   in `docs/handoffs/future_features.md`.
   - **Phase 1 — done** (spec `0024`): `meeting_to_action`, `status_rollup`,
     `rapid_scaffolder`, `prior_art_scanner` — the lowest-risk,
     highest-frequency slice, deliberately built and used first so trust
     forms before any agent touches a client or governance committee.
     Configurable via a local-only `role_context.yml`, gitignored by
     default and enforced by the `role-context` gate — this repository
     carries no company-specific or personal data. Backed by
     `instructions/role_operations.md`.
   - **Data-provenance guardrail — done** (spec `0025`, prompted directly
     by this initiative's own guardrails): real-data-first priority stack
     and complete synthetic-data disclosure, wired into `rapid_scaffolder`
     specifically since it's the agent most likely to reach for synthetic
     data to make a scaffold runnable.
   - **Phase 2 — done** (spec `0029`): `demo_narrative_packager`,
     `tough_question_rehearsal`, `experiment_ledger` — prototype
     accelerators. `demo_narrative_packager` disclosed synthetic data per
     `instructions/data_provenance.md`; `tough_question_rehearsal` reads
     `role_context.yml`'s stakeholder personas; `experiment_ledger` runs
     alongside `rapid_scaffolder`'s iteration loop.
   - **Phase 3 — done** (spec `0030`): `model_card_drafter`,
     `audit_trail_keeper`, `governance_readiness_checklist`,
     `second_look_backtest_reviewer`, `build_handoff_writer`,
     `alert_triage` — governance-adjacent, deliberately sequenced last
     given the higher stakes. Added `templates/docs/decision_log.md` (no
     template existed yet for `agentic_dictionary.md`'s Decision Log
     term). `second_look_backtest_reviewer` and `alert_triage` are
     explicitly framed as handoff layers, not replacements — the former
     always recommends the full `agents/backtest_review/` agent before a
     production-promotion decision, the latter never suppresses,
     escalates, resolves, or re-routes an alert, deferring all of that to
     `agents/alerts/alert_router/` and
     `agents/alerts/incident_notification/`.
5. **P0 optimizer-agent workflow expansion (continued) — done.** All three
   applications (cardinality-constrained portfolio, funding ladder,
   multi-period rebalancing — specs `0034`, `0035`, `0036`) are shipped;
   every solver in the `0013` toolkit now has one. A securities-financing
   LP application remains deliberately not planned:
   `repo_financing`/`collateral_management` stay agent-contract-only, and
   that domain routes to an adopter's own optimization models via
   `agents/optimization/model_plugin_registration/` (spec `0026`) instead
   of the SDK owning securities-financing optimization logic itself.
6. **Adoption guide** — done. `docs/adoption_guide.md` is a full walkthrough of both
   layers: `pip install quantsmith` + using the runtimes, and copying the scaffold +
   wiring the gates, with per-project-type recipes.
7. **Packaging** — done (package phase active). `docs/packaging.md` records the hybrid
   (versioned `quantsmith` package for the runtimes + template for the scaffold);
   `CHANGELOG.md` and a versioning policy are in place. Remaining optional step: the
   Copier `qf` sync CLI, and an optional PyPI release when there is demand.
8. **More worked examples — done.** The forecast spec is done
   (`specs/0006-ml-return-forecasting/`). The risk-model spec is done
   (`specs/0038-factor-risk-model/`, `factor_risk_model.py`): variance
   decomposition, Euler risk attribution (assets and factors), risk
   concentration, and a linear factor-shock stress loss, operationalizing
   `instructions/risk_management.md` (`0031`) with a tested runtime. The
   ingestion example is done (`specs/0039-ingestion-data-contract/`,
   `ingestion_data_contract.py`): validates an already-pulled row set
   against a declared schema/key/quality-rule contract and renders a
   `data_contract.md` populated with real, computed results — a duplicate
   key or missingness breach appears because it was actually found, never
   because someone wrote it down.
9. **Remaining backing instructions — done** (spec `0031`).
   `instructions/risk_management.md` (backs `agents/risk/`),
   `instructions/data_ingestion.md` (shared standard behind the three
   `data_ingestion/*` agents, replacing three independently-restated
   copies of the same rules), and `instructions/reproducibility.md`
   (operationalizes P4 for the `repro` gate and `templates/docs/run_card.md`,
   backing `implementation`/`testing_validation`) — all cross-referenced
   from the agents they back. Every backing-standard gap called out in this
   section historically is now closed: `pipeline_engineering`,
   `metrics_semantic_layer`, `data_storytelling`, `monitoring`, `alerting`,
   `asset_class_mechanics`, `role_operations`, `data_provenance`,
   `risk_management`, `data_ingestion`, and `reproducibility` are all
   shipped.
10. **Economists agent group — done** (spec `0033`). Seven agents
    (`macro_indicator_analyst`, `monetary_policy_analyst`,
    `macro_regime_classifier`, `cross_asset_macro_linkages`,
    `macro_scenario_analyst`, `macro_backdrop_summarizer`,
    `economic_outlook_report_writer`) giving a quant/PM workflow a
    grounded macro backdrop — indicators through policy through a
    classified regime through cross-asset/scenario translation to a
    recurring brief and a periodic outlook report. Reclaims
    `agents/economists/`, a stray, unwired placeholder (a literal
    `"placeholder"` `README.md`) left by the earlier parallel
    `agent/portfolio-management-agents` merge. Backed by
    `instructions/macro_economic_analysis.md` and
    `templates/docs/macro_backdrop_report.md`; draws on
    `sources/{fred,bls,bea,census,eia}.yml` (`0027`). Analysis and
    synthesis only — hands off to `trading_strategies/macro_multi_asset`,
    `portfolio_management/*`, and `risk` rather than replacing them, and
    is explicitly distinguished from `monitoring/model_signal_monitoring`'s
    regime-change detection (a different, operational question from
    classifying what the current regime *is*).
11. **`CHANGELOG.md`** — done (Keep a Changelog + a SemVer-style versioning policy).
12. **Optional gates** — `ingestion-snapshot`; a stricter notebook-output gate;
    revisit enforcing `leakage`.
13. **Shipped since this section was last written (specs `0019`–`0028`):**
    - `0019` pipeline observability.
    - `0020`/`0021` the monitoring → alerting chain (`agents/monitoring/`,
      `agents/alerts/`, `adapters/alert_delivery/`).
    - `0022` asset-class mechanics agents, feeding `trading_strategies/` and
      `securities_financing/`.
    - `0023` the securities-lending workflow promoted to a tested runtime,
      with a balance-sheet-cap correctness fix found along the way.
    - `0024`/`0025` role-operations Phase 1 + the data-provenance guardrail
      — see item 4, the dedicated tracking entry for this initiative.
    - `0026` the model plugin adapter — register an already-built internal
      optimization model as a reviewed, contract-bound plugin via a
      local-only `model_plugins.yml`.
    - `0027` the data source catalog (`sources/`) — a centralized,
      per-source registry of APIs/DBs/feeds with quality, point-in-time,
      and credential-pointer metadata, wired into `data_contract.md`,
      `credential_access`, and `data_ingestion`; populated with six public
      sources (FRED, BLS, EIA, BEA, Census, SEC EDGAR), with a matching
      `adapters/data_access/external_apis/eia.md` profile added.
    - `0028` financing cost analysis promoted to a tested, dependency-free
      runtime — cost-of-carry decomposition, financing-aware returns,
      understated-backtest flags, rate-shock sensitivity, and
      classification-keyed capacity findings, reconciling with `0023`'s
      rate/classification vocabulary by value (no `numpy` dependency added).
    - `0029`/`0030` role-operations Phases 2 and 3 — see item 4, the
      dedicated tracking entry for this initiative. The fourteen-agent
      roster is now complete.
    - `0031` the last three backing instructions
      (`risk_management`/`data_ingestion`/`reproducibility`) — see item 9,
      the dedicated tracking entry.
    - `0032` the first two executable `adapters/alert_delivery/` providers
      — email and webhook, following the adapter's own pre-existing
      Recommended Starting Set. Deterministic payload construction and
      redaction only; no network/SMTP/HTTP code lives in this SDK — a real
      send requires an adopter-supplied `transport` callable and
      `dry_run=False`, the same credential/execution boundary already drawn
      for `credential_access` and the `0026` model-plugin dispatcher. The
      remaining five providers shipped in `0037` (see below).
    - `0033` the `economists/` agent group — see item 10, the dedicated
      tracking entry.
    - `0034` cardinality-constrained portfolio construction — see item 1,
      the dedicated tracking entry. Closes the SDK's only standing `P0`
      backlog item (an application actually built on the `0013` solver
      toolkit) and corrects the stale collateral/margin-LP mention that
      previously stood in for it.
    - `0035` the funding ladder (`funding_ladder.py`) — see item 1, the
      dedicated tracking entry. The second application built on `0013`'s
      toolkit (`min_cost_flow`), a general treasury/cash-funding tool
      matching cash obligations to funding tenors at minimum cost;
      explicitly not a securities-financing tool.
    - `0036` multi-period rebalancing (`multi_period_rebalancing.py`) —
      see item 1, the dedicated tracking entry. The third and last
      application on the `0013` toolkit (`solve_dp`): a discretized
      single-position DP trading transaction cost against tracking-error
      cost over a horizon. Every `0013` solver now has a shipped
      application.
    - `0037` the remaining five `adapters/alert_delivery/` providers —
      Slack, Teams, ticketing, PagerDuty/Opsgenie, SMS/push — completing
      the adapter's own Recommended Starting Set end to end (all seven
      providers now executable). `pagerduty_opsgenie` and `sms_push`
      structurally enforce their own stated severity-routing rules
      (raise unless `allow_all_severities=True`) rather than leaving them
      as prose; `sms_push` also truncates an oversized message to a
      short-message length cap with a visible marker. Also factored the
      dry-run/transport/`DeliveryResult` wrapper duplicated between
      `email.py`/`webhook.py` into a shared `deliver_via` helper, verified
      behavior-preserving by `0032`'s own test suite passing unchanged.
    - `0038` the factor risk model (`factor_risk_model.py`) — see item 8,
      the dedicated tracking entry. Closes the standing "risk-model spec
      end to end" worked-example gap and operationalizes
      `instructions/risk_management.md` (`0031`) with a tested runtime;
      every decomposition sums exactly to the total it decomposes, by
      construction (Euler identity), not just by convention.
    - `0039` ingestion data contract emission (`ingestion_data_contract.py`)
      — see item 8, the dedicated tracking entry. Closes the standing
      "ingestion example that emits a data contract" worked-example gap;
      `validate_ingestion` checks a caller-supplied row set against a
      declared contract (schema, keys, missingness), and
      `render_data_contract` renders `templates/data/data_contract.md`'s
      section structure populated entirely from those real, computed
      results, phrased as findings "in the validated sample" rather than
      an unqualified guarantee. Item 8's worked-examples backlog is now
      fully closed.
    - `0040` the README index/runtime sync gate
      (`hooks/stages/readme-sync-check.sh`). `agent-catalog`/`spec-index`
      already kept `agents/README.md`/`specs/README.md` from drifting as
      agents/specs were added; this gate closes the third leg — a spec
      whose `specs/README.md` row names a real, tested pytest module (its
      Tests column) but whose ID is missing from root `README.md`'s own
      runtime table. Wired into `run-stage.sh`, `hooks/README.md`, root
      `README.md`'s gate table, and CI's docs-integrity enforcement step
      alongside `docs-link`/`agent-catalog`/`spec-index`. The exact gap
      this file's own Risks section names ("narrative docs ... need
      periodic manual refresh") is now partially self-checking.
    - `0041` ranking-loss forecasting (`ranking_forecast.py`) — closes the
      SDK's sole remaining `P0` backlog line ("additional ML/DL examples"
      beyond `0006`'s point-wise baseline/challenger). `train_ranker`
      trains a linear scorer with a pairwise (RankNet-style) ranking loss
      over same-day pairs only, composing `0006`'s `build_labels`/
      `FeatureStore`/`make_folds`/`evaluate`/`LinearModel` unmodified —
      changes only the training objective, not the leakage-safe
      machinery around it. `run_ranking_forecast` trains the ranker and
      `0006`'s point-wise baseline on identical folds for direct
      comparison; a fixed-seed synthetic fixture demonstrates the ranker
      matching or beating the point-wise baseline's rank IC, disclosed
      explicitly (spec `RISK-003`) as a mechanism demonstration, not a
      backtested market claim.

    - `0042` the pipeline builder (`pipeline_builder.py`) — the
      design-time layer ahead of `0011`'s runtime, and the first of the
      three remaining `P1` `data_engineering` items to get an executable
      runtime. `compile_intent` validates a declared intent's graph **by
      constructing an `0011` `Pipeline`**, so cycles, unknown
      dependencies, and duplicate step names cannot be judged differently
      at design time than at run time; `review_readiness` encodes
      `instructions/pipeline_engineering.md`'s checklist as
      severity-tagged findings, collecting all of them;
      `render_pipeline_manifest` emits a
      `templates/data/pipeline_manifest.md`-shaped document from the real
      DAG and real findings; `to_pipeline` binds implementations back
      into a runnable `0011` `Pipeline`. It reviews *declarations, not
      implementations*, and says so — idempotency and test coverage are
      claims until `0011` exercises them. The generated example at
      `specs/0042-pipeline-builder/pipeline_manifest.md` is the
      repository's first manifest artifact, so the `pipeline-contract`
      gate now validates real content rather than reporting "no manifest
      detected" on every run.

    - `0043` the documented-count drift gate
      (`hooks/stages/doc-counts-check.sh`). `agent-catalog`, `spec-index`,
      and `readme-sync` each check that an *entity* is listed somewhere;
      none can check a number written in prose, which is how the agent,
      gate, and instruction-standard counts in this file, `sdk_plan.md`,
      and root `README.md` all went stale at once. The gate derives each
      count from the filesystem — reusing `agent-catalog-check.sh`'s own
      definition of a public agent, so the two cannot disagree — and
      reports every stated count that differs. It also reports how many
      claims it checked, so a pattern that stops matching is visible
      rather than passing quietly. The Risks entry below about narrative
      docs needing manual refresh is now materially narrower: the
      countable part is mechanical.

    - `0044` the backtest engine (`backtesting.py`) — the artifact this SDK
      existed to govern and had never produced. `instructions/backtesting.md`,
      `agents/backtest_review/`, `templates/docs/backtest_report.md`, and a
      **CI-enforced** `backtest` gate were all in place while the gate
      reported "no backtest report artifact detected" on every run. No
      look-ahead is structural: `weights[i]` meets `returns[i + lag]` with
      `lag >= 1` enforced, an indexing impossibility rather than an
      assertion. Net of costs is the default (turnover-scaled transaction
      cost, financing on short exposure only), and a probabilistic Sharpe
      (Bailey & López de Prado) ships with every Sharpe rather than as an
      optional extra. The generated example on **disclosed synthetic data**
      is the repo's first backtest artifact; it reports a *negative* result
      (Sharpe −0.69, PSR 0.167), which is the correct answer for random data
      after costs and a fair demonstration that the engine is not tuned to
      flatter. Its stated limit: the guarantee covers the simulation loop,
      not the provenance of the weights it is handed.

    - `0045` the FRED point-in-time panel adapter
      (`fred_point_in_time.py`) — the input-side half of the gap `0044`
      left open. `0044` guarantees its simulation loop does not look
      ahead and says it cannot vouch for the weights it is handed; for a
      macro backtest that is precisely where leakage lives, because
      economic series are revised. This adapter reads
      `gold_fred_point_in_time` and selects vintages by window
      containment on `realtime_start`/`realtime_end`, so a revision
      published later can never be returned for an earlier as-of date —
      the property its decisive test pins directly (original value before
      the revision, revised value after). Publication lag falls out of
      the data rather than needing a parameter, and `is_missing` rows are
      absent rather than zero, because a zero is a number a model will
      happily trade on. Read-only, no API key: it consumes a SQLite file
      the operator produced (P9).

    - `0046` the walk-forward backtest harness (`walk_forward.py`) —
      closes the gap `0044`'s own rendered report admitted to ("results
      here are in-sample unless that was applied upstream"), which is the
      first thing `agents/backtest_review/` discounts. The pieces already
      existed and had never been composed: `0006`'s `make_folds` produces
      purged, embargoed splits and `0044`'s `run_backtest` measures a
      path. Fold construction is **delegated**, not reimplemented — a
      second implementation could disagree with `0006` about what is
      purged. `fit_predict` is called once per fold on training periods
      only, and its weights are evaluated on that fold's held-out periods
      with the rebalance lag preserved across the slice. The headline is
      the fold *distribution* (Sharpe dispersion, best/worst, positive
      fraction), not a single pooled number that could hide one lucky
      stretch. The generated example is again honestly negative — 20% of
      folds positive, pooled probabilistic Sharpe 0.041 — which is the
      right answer for a trailing-mean tilt on random data after costs.
      Variant selection on fold results is an explicit Non-Goal: that
      needs a deflated Sharpe, the named follow-up.

    **The real run — done.** `scripts/fred_real_run.py` wires the leak-free
    `fred_point_in_time` panel into the `0046` walk-forward harness against
    an operator-produced `fred_local.db`: 61,833 point-in-time rows across
    8 macro series, 320 monthly as-of dates, 5 purged/embargoed folds, 265
    held-out periods. Pooled out-of-sample Sharpe 0.28, probabilistic Sharpe
    0.907, 80% of folds positive — with one fold sharply negative (Sharpe
    −1.31), the honest walk-forward answer a single pooled number would
    have hidden. Report: `specs/0045-fred-point-in-time/backtest_report.md`.
    The weighting is a demonstration-only cross-sectional z-score of
    trailing momentum (fit per-fold, train-only) — not a claimed signal,
    per `0045`'s Non-Goals; re-run with `scripts/fred_real_run.py
    --db-path <fred_local.db>` whenever the operator refreshes the data.

    **Otherwise:** conic/global/nonlinear optimizer forms once a
    dependency-free method or an optional solver dependency is chosen, a
    listwise ranking loss once `0041`'s pairwise variant is trusted, or
    the two remaining `P1` `data_engineering` runtimes (`data_modeling`,
    `pipeline_deployment` — the latter is the handoff edge `0042`
    deliberately stops at).
    `repo_financing`/`collateral_management`
    stay agent-contract-only by choice — this SDK routes to an adopter's
    own optimization models via
    `agents/optimization/model_plugin_registration/` (spec `0026`) rather
    than owning securities-financing LP/optimization logic itself; an
    executable dispatcher for `0026` is worth building once a concrete
    invocation target exists. Otherwise: continuing to populate `sources/`
    as real sources come into use.

14. **P1 Generalization & Team Onboarding — making QuantSmith self-serve across
    domains.** QuantSmith is now a comprehensive framework (162 agents, 52 specs,
    33 gates, 33 standards); the next phase is reducing discovery friction and
    enabling team-intuitive adoption without deep codebase reading.
    - **P0 Phase 1a: Role profiles** (`roles/{portfolio_manager,risk_manager,quant_researcher,data_engineer,compliance_officer}.md`):
      Define personas with their workflows, agents, specs, and handoff points. A
      new Portfolio Manager reads `roles/portfolio_manager.md` and learns which
      agents apply, which specs they own, which gates matter. Replaces the treasure
      hunt through `agents/README.md`.
    - **P0 Phase 1b: Domain starter kits** (`templates/domains/{equities,fixed_income,multi_asset,derivatives}/`):
      Copy-paste templates with pre-wired agents, specs, and instructions for each
      asset class. New equities team forks `templates/domains/equities/` → 80% of
      their agent catalog and specs are ready. Reduces onboarding from weeks to
      days.
    - **Phase 2: Workflow discovery** (`docs/workflow_discovery.md`):
      A decision tree (3 questions: Goal? Stage? Timeline?) that routes users to the
      right orchestrator without reading 162 agent READMEs. Pairs with workflow
      patterns below.
    - **Phase 3: Cross-domain composition patterns** (`patterns/{portfolio_plus_hedge,macro_asset_allocation,signal_plus_model_plus_portfolio}.md`):
      Document 5–10 common multi-domain workflows (equities + options, multi-asset
      with macro, signal → forecast → portfolio) with agent chaining, handoff
      boundaries, and expected outputs. Teams reuse patterns rather than designing
      from first principles.
    - **Phase 4: Extensibility by recipe** (`docs/extending_quantsmith/{add_asset_class,add_signal_type,add_risk_model,add_gate}.md`):
      Step-by-step walkthroughs showing how to add a new domain/agent/spec/gate
      without breaking existing ones, with concrete examples. Enables downstream
      teams to extend rather than fork-and-modify.
    - **Phase 5: Consumer upgrade path & versioning** (`docs/consumer_adoption.md`):
      Document the full lifecycle for external repos: fork → pin → customize →
      upgrade → contribute back, with schema_version compatibility checking (from
      spec `0047`). Enables multi-team adoption and central maintenance.
    - **Phase 6: Instrumentation & observability** (agent call logging):
      Track which agents, workflows, gates, and domain patterns are used by which
      teams; failure rates, completion times, and handoff quality. Informs next
      iterations and prioritization.
15. **Company knowledge over time — one initiative, phased across specs.**
    *(Related: item 16 ships the repo shapes that adopt it; item 17 exposes it
    to a team over MCP.)*
    The goal: a workflow arrives already knowing a dataset's kinks, a
    researcher does not re-derive what a colleague established last quarter,
    and both can say where the knowledge came from and who vouched for it.
    Phased like the role-operations roster (item 4) — small, shippable
    specs rather than one large one, because the read path is useful before
    a write path exists, and the write path should not be designed until
    retrieval has shown what is worth capturing.

    **Two distinct systems, easily conflated.** `instructions/workflow_memory.md`
    governs `memory/` — structured records about databases, datasets, schemas,
    fields, and their quirks. `instructions/knowledge_base.md` governs
    `agents/knowledge/` reading a company's *unstructured* institutional
    knowledge from external sources declared in `knowledge_sources.yml`. The
    same four `knowledge/` agents serve both. Only the first has a runtime.

    - **Scaffold — done** (spec `0002`): the `memory/` two-axis layout, the
      record vocabulary (`type`/`confidence`/`corroboration`/`pit_scope`/
      `status`), `manifest.yaml`, and the `memory` gate. Records were
      committed but nothing ever read them *as records* — the gate greps for
      the string `first_seen`, which proves a field name appears in a file
      and nothing more.
    - **Runtime, read path — partial** (spec `0048`): `workflow_memory.py`.
      Built: a dependency-free subset YAML parser that raises rather than
      guessing (`T-001`), a **type-aware point-in-time filter** (`T-003`),
      and structural validation replacing the string grep (`T-005`), plus
      list-form `evidence` with a derived corroboration count (`T-013`).
      The PIT rule is the substantive idea: a memory store is *itself*
      look-ahead, so mechanical facts (`schema`/`quirk`/`pitfall`) are
      timeless while claims about what worked (`pattern`/`metric`/
      `performance`) are bounded by `last_confirmed` — corroboration is
      where the future enters a record.
      **Outstanding:** `query` (`T-002`), `render_context` (`T-004` — until
      this lands nothing can feed an agent prompt), decay (`T-006`), author
      handles (`T-007`), `store_version` (`T-008`), the CLI and gate
      rewiring (`T-009`/`T-010`), supersession and contradiction validation
      (`T-014`–`T-016`). 11 of 23 `AC-*` verified.
    - **Read/analytics surface — built** (spec `0057-knowledge-console`):
      `src/quantsmith/knowledge_console/`. The first consumer to read the whole
      `memory/` tree as records rather than as strings — a filesystem
      store-loader over `0048`, a pure, deterministic view-model (counts,
      trends, a records↔scope↔evidence-run knowledge graph, a git changes feed,
      and a needed-review queue that collects the curation signals `0048`
      already computes), a standard-library HTTP API, and a Vite/React front
      end with a self-contained single-file snapshot. It also ships the
      **pluggable natural-language query seam** (`QueryEngine` protocol +
      grounded keyword default via `resolve_engine`) so a real LLM engine can
      answer questions over the store later without a UI or API change. It is
      deliberately read-only: the approval *action* (write-back) is the
      `0049` write path below.
    - **Write path — built** (spec `0049-workflow-memory-write-path`):
      extends `workflow_memory.py`. Capture happens at the **runtime
      boundary, not the gate boundary** — `propose_records()` takes a small,
      generic `CandidateSpec` (any pipeline can build one without importing
      memory-module internals), `stage_candidates()` writes it to a
      **committed** `memory/inbox/<workflow>/<source_run>.yaml`, so a pull
      request touching that path *is* the approval workflow, and `promote()`
      is the one deliberate, human-invoked action that assigns an id,
      stamps `author`/`first_seen`/`last_confirmed`, and appends the record
      to its live catalog — refusing (never silently promoting) on a missing
      field or id collision, and warning (never blocking) on a same-scope/
      same-type contradiction. `discard()` removes a candidate without
      promoting it; the removal commit is the audit trail. Also finishes
      `0048`'s outstanding author resolution (`resolve_author`/
      `derive_handle`: env → local `identity.yml` → git → OS user → `None`,
      never storing a raw email/username). One worked producer integration:
      `ingestion_data_contract.candidates_from_validation()` turns `0039`'s
      real schema violations and failed quality rules into candidates,
      proving the runtime-boundary thesis against an actual runtime rather
      than a synthetic example. A stdlib CLI
      (`workflow_memory_cli.py` / `quantsmith-memory`) exposes propose,
      list-inbox, promote, and discard. `walk_forward` (`0046`,
      `performance`), `fred_point_in_time` (`0045`, vintages), and
      `factor_risk_model` (`0038`, `metric`) are named next producers,
      each a thin translator against the same `CandidateSpec` contract —
      not blocked on anything here. `templates/docs/run_card.md` gained the
      "Memory proposed" field beside its existing "Memory version used".
    - **Per-person viewer access control — built** (spec
      `0058-viewer-access-control`): `access_control.py`. Activates
      `access_level`, the field `0048`'s own spec named and explicitly
      deferred enforcing "until a caller exists that has a level to enforce
      against" — `0057` built two. A committed, opt-in `access/roster.yml`
      maps a resolved pseudonymous handle (reusing `0049`'s `resolve_author`/
      `derive_handle` unchanged, moved rather than duplicated to avoid a
      circular import) to a `public`/`internal`/`restricted` clearance.
      Enforcement is inactive with no roster or an empty one — identical to
      today's unfiltered behavior — and activates for *every* viewer, not
      only listed ones, the moment the roster names its first person; an
      unlisted or unresolvable identity falls back to the roster's declared
      `default_clearance`, never full access by omission. Filtering happens
      once, at the read boundary — `workflow_memory.query(...,
      viewer_clearance=...)` and both `0057` view-model builders
      (`knowledge_console.model`/`knowledge_console.research`, covering the
      `0056` research store too) — as a plain optional parameter on otherwise
      pure functions, so nothing downstream (rendering, the graph, the
      review queue, an exported snapshot) can see what was already filtered
      out, and every pre-existing caller that omits it is unaffected
      (NFR-004, all 290 pre-`0058` tests pass unmodified bar one mechanical
      monkeypatch-target fix). A `whoami` CLI command and a `preview-access`
      command make onboarding and roster-change review a copy-paste, not a
      source-code read; a new `access-check.sh` gate validates the roster
      the same way `memory-check.sh` validates `memory/`. Explicitly not
      authentication — pseudonymous, local-per-person, same trust model
      `0049` already established for write attribution; a shared/
      multi-tenant deployment needs the `0052`–`0054` MCP-server work first.
    - **Retrieval logging — not specced.** Nothing measures whether retrieval
      helps, which leaves this initiative's own premise unevidenced. It also
      gates pruning: without it the store only grows, and eventually costs
      more to search than it saves. Cheapest version is recording which record
      ids were served to a run, in the run-card slot that already exists.
    - **Market-research knowledge base — specced, not yet built** (spec `0056`).
      This is the knowledge-base half for user notes, firm research, generated
      summaries, market color, explicitly tagged email color, fund-manager
      letters, sell-side research, and other approved external materials. It
      deliberately keeps the same
      knowledge-base MCP interface (`knowledge://market_research/...`) while
      allowing separate governed storage, access-tiered indexes, entitlement
      checks, citations, point-in-time retrieval, and audit records underneath.
      The `agents/knowledge/` contracts remain the agent layer; `0056` is the
      deployable market-research knowledge contract they should eventually read.
      Real research content remains outside this repo.
    - **Morning market brief — first real runtime slice of `0056`'s
      generated-summaries flow** (spec `0059`,
      `src/quantsmith/pipelines/market_brief.py`). Pulls free-API market
      commentary from three providers (NewsAPI, Alpha Vantage
      `NEWS_SENTIMENT`, Finnhub), computes what's honestly deterministic
      (recency filtering, cross-provider dedupe, a sentiment rollup where
      Alpha Vantage actually covers a ticker), and hands the rest to a new
      `agents/economists/morning_brief_writer/` agent to write the grounded
      "Views & Analysis" section. Stages a `pending_review` candidate to a
      local-only, gitignored root — never `research/`, per `0056`'s own
      Non-Goals. Credentials follow the existing `sources/*.yml` +
      `credential_access` pattern, so this is configurable per clone with
      no code change: three new `sources/*.yml` entries, one new local
      `morning_brief_config.yml` (watchlist, enabled providers, delivery
      route, schedule). Does not build `0056`'s promotion mechanics, MCP
      exposure, or entitlement enforcement — see `0059`'s Non-Goals.

    **Honest status.** The store holds **5 records, all reference examples** —
    no real institutional knowledge has been captured yet. The read path is
    being built ahead of demand. The fastest test of whether this earns its
    keep is capturing 20–30 real records from actual CRSP/FRED work and seeing
    whether retrieval changes anyone's behaviour, before investing further in
    machinery.

16. **Repository shapes — pre-canned skeletons for multi-repo adoption.**
    *(Related: item 15 is the knowledge these repos accumulate; item 17 is how
    a team reaches it.)*
    `templates/repos/` ships scaffolds a team picks from rather than assembling
    a repo by hand: `quant-research`, `quant-models`, `data-pipelines`. Each
    carries the full root structure (`.agents/`, `.copilot/`, `.githooks/`,
    `.github/`, `config/`, `docs/`, `hooks/stages/`, `instructions/`,
    `memory/`, `scripts/`, `specs/`, `src/`, `tests/`, `templates/`) plus
    `CLAUDE.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `pyproject.toml`, and a
    **pre-filled `quantsmith.conf`** — so the adopter configures nothing.

    `scaffold-repo.sh --shape <name> --into <dir>` copies the shared base,
    overlays the shape, and pulls in the SDK's gate scripts and templates, so
    a scaffolded repo runs its own gates immediately. All three shapes
    currently scaffold to ~90 files and pass their declared blocking gates on
    a fresh tree, verified.

    **The gate selection per shape is the substance, not the directories.**
    `quant-research` keeps `spec` advisory — demanding a spec per experiment
    stops people experimenting, which is the entire value of that shape.
    `quant-models` blocks on `backtest` and `leakage`, because a look-ahead bug
    there is a bad trade rather than a bad report. `data-pipelines` blocks on
    `data-contract`/`pipeline-contract`, since a silent schema change reaching
    a model months later is that shape's characteristic failure. Each shape's
    `README.md` argues its selection rather than listing it.

    This also **reverses the sequencing** previously planned for the
    portability work: shipping the shapes first means the config format is
    *derived* from three real configs rather than guessed at, so the gate
    parameterization has something concrete to be validated against.
    - **Done:** the three shapes, the scaffolder, the shared base, and
      `handoff-sync` reading `QF_DOC_ROADMAP` (a down-payment on the gate
      parameterization — a scaffolded repo names its roadmap
      `docs/roadmap.md`, and the gate now honours that).
    - **Next (`0050`):** parameterize the remaining doc gates against
      `quantsmith.conf`; collapse `agent-catalog`+`spec-index` into one
      `catalog-sync`, since both are "entities under a root must appear in an
      index".
    - **Then (`0051`):** conformance levels. `docs/conformance.md` and
      `QF_CONFORMANCE_LEVEL` ship in the skeletons already, declared but not
      yet verified by any gate — adoption is currently a claim, not a check.
    - **Known gap:** `doc-counts` and `repro` are advisory in the shapes
      because a fresh repo has no counts to drift and no run to reproduce.
      Both should be promoted once a repo has content; the shapes say so
      inline rather than leaving it silent.

17. **MCP servers over the shared knowledge base — exposing it to a team.**
    A centralized knowledge-base repository is only useful if agents across the
    team can reach it. `adapters/` is already the right seam: its own README
    defines an adapter as "the boundary between agent decisions and external
    systems... agents decide, adapters translate an approved payload into a
    provider-specific action." An MCP server is exactly that, so this becomes an
    **eighth adapter group**, `adapters/mcp_servers/`, following `llm_runtime/`'s
    shape (README + `adapter_contract.md` + one file per provider).

    Two existing pieces do most of the work:
    - **`templates/knowledge/knowledge_sources.yml` is already a server
      manifest** — `path`, `access_level`, `include`/`exclude`, `freshness_days`,
      `domains_from_subfolders`. Written for the `knowledge` gate; it happens to
      be exactly what a resources server needs.
    - **`0048`'s runtime is the graph server's backing store** — typed records,
      validation, and the type-aware point-in-time filter.

    Three servers, sequenced by dependency (see the Planned specs table):
    - **`0052` resources primitive** — read-only, serves declared Markdown/text
      under a `knowledge://<source>/<domain>/<path>` scheme. Build first: it
      needs no new storage and it validates the adapter contract.
    - **`0053` memory/knowledge graph** — `memory_query(scope, type, as_of)` over
      `0048`. The `as_of` parameter is the differentiator: a generic memory MCP
      server will serve 2026 knowledge to a 2020 backtest, and this one will not,
      because mechanical facts are timeless while claims about what worked are
      bounded by `last_confirmed`. For a quant team that is the difference
      between a memory server and a leakage vector. Graph edges already exist as
      fields (`superseded_by`, `coexists`).
    - **`0054` vector/RAG** — `search(query, domain, access_level, as_of)`
      returning cited passages, never bare prose, since
      `instructions/knowledge_base.md` already requires grounded, cited answers.

    **The team-scale hazard, recorded because it is easy to miss.** MCP servers
    run with the *server's* credentials, not the caller's — so a shared
    knowledge-base server reachable by the whole team will serve `restricted`
    content to anyone who can open a connection unless designed against. Two
    rules belong in the contract: the caller's clearance is a **parameter**,
    never an assumption about who can reach the endpoint; and for RAG, filter at
    **index** time with one index per access tier, not at query time.
    Post-retrieval filtering still leaks — nearest-neighbour distances reveal
    that a restricted document exists and roughly what it concerns, even when it
    is never returned. For an MNPI-adjacent shop that is the difference between
    a compliance story and a compliance incident.

    Related: item 15 (what the knowledge is), item 16 (how repos adopt it).
    This item is how a team *reaches* it.

    **Market-research namespace now specified.** Spec `0056` adds
    `knowledge://market_research/...` as a governed domain behind the same MCP
    front door. It does not require a separate MCP client path; it requires
    different storage and governance underneath the shared interface. Treat it
    as a consumer of `0052`/`0054`, with stricter entitlement, source-license,
    freshness, and point-in-time rules than ordinary internal documentation.
    Tagged email color is included only through explicit labels, folders, or
    saved searches; broad inbox keyword scanning is deliberately out of scope.

18. **Firmwide readiness — distribution, ownership, and usage signal.**
    Three of the five gaps between "a good SDK" and "infrastructure a firm
    runs on". Built as gates rather than documents, because the failure in
    each case is silence.

    - **Distribution that does not drift** — `upstream-drift` (gate 30) plus
      `scripts/sync-upstream.sh`. Adoption is copy-and-own, so ten repos
      copying one gate and each tuning it a little is not a risk, it is a
      certainty. You cannot prevent that and should not try: adopters SHOULD
      tune gates to their repo. What you can do is make divergence **visible**.
      Each shape now pins `QF_UPSTREAM_REF`; the gate reports every copied file
      that differs from it, and the sync script either refreshes the copies or
      moves the pin. Dry-run by default, since a sync that silently overwrote
      local tuning would destroy the thing the model is built around.
      Offline-tolerant: an unreachable upstream reports and exits clean,
      because a gate that goes red when GitHub is slow is one people learn to
      ignore.

    - **Ownership and a support path** — `ownership` (gate 31), plus
      `docs/ownership.md` and `docs/gate_runbook.md` in this repo and every
      shape. The gate's substance is **placeholder detection**: a scaffold
      ships `@OWNER` and `<@handle>` deliberately, and those are precisely the
      strings that survive to production if nothing looks for them. An unfilled
      template reads as governed while owning nothing. It is blocking in every
      shape — unlike a run manifest, ownership can be filled in on day one, and
      a fresh scaffold goes from blocked to passing in about thirty seconds.
      Found the gap **here** on its first run: this repository had no
      CODEOWNERS, no ownership document, and no runbook. All three now exist.
      `docs/ownership.md` states the single-maintainer risk plainly rather than
      hiding it — every surface has one owner and no backup, which is the first
      thing that breaks at firm scale.

    - **A usage signal** — `QF_USAGE_LOG` in `common.sh` plus
      `scripts/usage-report.sh`. Off unless the path is set; records only
      timestamp, gate, finding count, and enforce flag. No paths, no finding
      text, no identity, and it never leaves the machine — a usage log carrying
      findings would carry company data, and this has to stay safe to enable
      anywhere. It answers what nobody could answer before: which gates ever
      fire, which never do, which deserve promoting to blocking.
      **Its first run was already informative** — `repro`, `doc-counts`, and
      `data-provenance` fire on 100% of runs in this repo, which by the
      report's own guidance means "a known finding people have learned to
      ignore." That is an accurate description of how they have been treated.

    **Two gaps named here — both now closed:**
    - **One real workflow on real data — done.** `scripts/fred_real_run.py`
      wires `0045`'s leak-free FRED panel into `0046`'s walk-forward harness
      against an operator-produced `fred_local.db`; see item 13's "The real
      run" entry above for the numbers. Converts that worked example from
      argument to evidence.
    - **`access_level` enforced rather than declared — done** (spec `0058`).
      `workflow_memory.query()` now accepts an explicit `caller_clearance`
      parameter and filters records by `access_level` when one is supplied,
      defaulting to unrestricted for today's single local trust boundary. The
      narrower gap that remains: no caller yet *resolves* a real person's
      clearance and passes it in — that's still the MCP work (item 17,
      `0052`–`0054`), where a network-reachable server must always supply an
      explicit `caller_clearance` rather than relying on the default meant for
      a local, already-trusted process.

## Open Questions For The Owner

- Copyable scaffold, Python package, or CLI/copier? (Directionally answered in
  `docs/packaging.md`; revisit its criteria if audience or update cadence changes.)
- Which agent runtime is the primary target (local, general LLM, both)?
- Does the knowledge-base half (item 15) get a runtime, or stay a pointer to
  wherever the company's unstructured knowledge already lives (Confluence,
  Notion, a docs repo)? Building a second store is only worth it if grounding,
  access control, and provenance are things the existing system cannot do —
  otherwise `agents/knowledge/` should retrieve from it, not replace it.
- Which gates should graduate from advisory to enforced, and when?
- Should downstream repos pin a version of the SDK, and how are updates delivered?

## Risks

- Breadth: 162 agents is useful only if each stays narrow and inspectable.
- Heuristic gates (`leakage`, `backtest`, `secret-scan` fallback) can false-positive
  or miss; keep them advisory unless a repo's layout makes them reliable.
- Docs can drift from the code; the `docs-link`, `agent-catalog`, and `spec-index` gates help, but
  narrative docs (this file, `sdk_plan.md`, `agentic_dictionary.md`) need periodic
  manual refresh.
- Copied gates assume conventional artifact names; adopters must tune the patterns.

## Definition Of Done For The Next Slice

- `docs/adoption_guide.md` is complete enough that a fresh repo can install the SDK.
- The packaging decision has a chosen path with first steps taken.
- A second end-to-end worked example exists beyond the momentum signal.
- **Generalization phase (item 14) — foundations in place:**
  - `roles/` directory populated with at least three personas (Portfolio Manager, Quant Researcher, Risk Manager).
  - `templates/domains/equities/` starter kit complete and validated by a new team's onboarding.
  - `docs/workflow_discovery.md` decision tree operational and tested on 5+ team requests.
  - At least two composition patterns extracted and documented in `patterns/`.
  - First extensibility recipe written (e.g., `docs/extending_quantsmith/add_asset_class.md`).
  - Logging instrumentation added to `agents/workflow_orchestrator/` to track agent calls and gate results.
