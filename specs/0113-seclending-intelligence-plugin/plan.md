# Plan: SFMeridian — Securities Finance Intelligence Plugin (Foundation)

- **Spec:** 0113-seclending-intelligence-plugin (`spec.md`)
- **Status:** Approved
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-10-22 (governed-first tier on `0080`/`0081`)

> HOW. Every `REQ-*`/`NFR-*` in `spec.md` appears in the traceability matrix
> below. Delivery order and phase exit criteria are in `roadmap.md`. This plan
> designs the whole plugin at contract level; each child spec (`0114`–`0120`)
> refines its slice and may tighten, but not loosen, what is fixed here.

## Approach

Build the securities-lending intelligence capability as **one plugin with one
tool contract**, and make every answer pass through a deterministic pipeline
in which the language model only ever *proposes* — SQL, wording, a choice of
exemplar — and deterministic code *disposes*: it resolves identifiers, verifies
the query, executes it read-only, recomputes numbers, and checks citations.
Hallucination is limited by construction because there is no path from model
output to the user that skips those checks.

Answering is **tiered, governed-first** (REQ-023). Every question goes to
`0080` first: if it maps to a governed `0008` metric (seeded from `0081`'s
`securities_financing_prime` pack), `0080` plans it, the plugin supplies the
rows through `0080`'s injected `Reader` by running reviewed **metric source
queries** through the same verify/execute path (REQ-024), and `0080` computes
insights, picks the chart, and grounds the narrative. Only when `0080` says
the question names no governed metric does the plugin fall through to the
reviewed-query tiers (`reuse` → `adapt` → `generate`). An ambiguity among
governed metrics is returned as `0080`'s clarification, never resolved by
falling through. So there is one answer path per question, and the governed
path is always tried first.

The query repository is the plugin's memory of "how this firm queries its
data". It is declared in configuration, indexed into exemplars and structure
(join graph, metric expressions, filters, parameter templates), reconciled
against a dated catalog snapshot, and grown only through a reviewed promotion
path. Retrieval of a reviewed exemplar is always preferred to generation.

The plugin reuses the SDK rather than duplicating it: `0063` supplies domain
meaning and sign conventions, `0008` supplies governed metric rules, `0023`
supplies the execution seam and synthetic database, `0049` the reviewed write
path, `0052`/`0058` the MCP and access contracts, `0070` the run envelope and
replay, `0071` the LLM evidence boundary, `0110` the plugin packaging, and
`0047` the SemVer contract with downstream apps.

## Architecture & Components

```text
                    ┌──────────────────── surfaces (REQ-002) ───────────────────┐
  app / chatbot ──▶ │ Python API  │  MCP server (0052)  │  Claude Code plugin    │
                    └──────────────────────────┬────────────────────────────────┘
                                               ▼
                               tool contract v1 (REQ-001)
                                               │
  ┌────────────── config (REQ-003/004) ────────┼───────────────────────────────┐
  │ sfmeridian.yml → schema validate → layered resolve → frozen Config │
  └────────────────────────────────────────────┼───────────────────────────────┘
                                               ▼
   ask(question, as_of, caller)  ── orchestrator (sfmeridian_orchestrator) ──┐
     1 classify intent + resolve terms ── glossary / 0063 pack (REQ-012/013) │
     G governed tier ──────────────────── 0080 answer() (REQ-023)            │
         interpret → QueryPlan over 0008 metrics (0081 pack-aware)           │
         Reader = metric source queries → steps 5–6 → Facts (REQ-024)        │
         0080 insights + chart + grounded narrative → step 9 → step 10       │
         clarification among governed metrics → return it (no fall-through)  │
         "no governed metric" → continue at step 2                           │
     2 retrieve exemplars ─────────────── query index (REQ-006, 0114)        │
     3 map concepts → columns ─────────── semantic mapping (REQ-008, 0115)   │
     4 compose SQL (reuse|adapt|generate) sql_composer (REQ-009, 0116)       │
     5 verify (deterministic) ─────────── sql_verifier tool (REQ-010, 0116)  │──▶ reject → retry ≤ N or abstain
     6 execute read-only ──────────────── execution seam (REQ-011, 0116)     │
     7 compute derived numbers in tools ─ 0008 / 0023 / 0028 runtimes        │
     8 draft answer (LLM)                                                    │
     9 grounding check (deterministic) ── answer_grounding (REQ-012, 0117)   │──▶ strip / abstain
    10 redact by clearance ────────────── access layer (REQ-017)             │
    11 emit answer + citations + 0070 run envelope ─────────────────────────┘
                                               │
   feedback.propose ──▶ staging inbox (0049 pattern) ──▶ human promote ──▶ index (REQ-014)

   learning path (offline, incremental, REQ-006/007):
   query repos (git|local|object_store) → fetch at pinned ref → parse front-matter
     → SQL structure extraction → exemplar store + join graph + metric candidates
     → reconcile with catalog snapshot (drift → exclude) → lexical (+ optional
       embedding) index
```

### Package layout (delivered by `0114`–`0118`)

```text
plugins/sfmeridian/
  pyproject.toml                    # distributable: sfmeridian (SemVer, NFR-007)
  src/sfmeridian/
    contract/                       # tool schemas (JSON Schema), error codes, version
    config/                         # schema, loader, layered resolution, validate-only
    repos/                          # git/local/object_store fetchers, pinned refs
    indexing/                       # front-matter, SQL structure extraction, join graph, index
    catalog/                        # introspection, catalog files, snapshots, drift reconcile
    semantic/                       # concept → column mapping on 0008 rules, seeded from 0081; 0063 glossary bridge
    governed/                       # the only 0080/0081 adapter: tier routing, Reader, pack resolution, amendments
    compose/                        # retrieval-first composer (LLM via adapters/llm_runtime)
    verify/                         # deterministic static verifier + EXPLAIN cost guard
    execute/                        # read-only seam over 0023 SQLDataSource / adopter drivers
    grounding/                      # claim extraction, citation check, recompute, abstain
    access/                         # clearance, redaction classes, allowlists
    feedback/                       # propose/stage/promote (0049 pattern)
    eval/                           # golden-question harness and metrics
    surfaces/
      api.py                        # Python API
      mcp_server.py                 # MCP server on the 0052 adapter contract
  claude_plugin/                    # .claude-plugin/plugin.json, skills/, .mcp.json (0110 packaging)
  fixtures/                         # synthetic DB seed, synthetic query repo, golden set (0025-flagged)
  tests/
```

Database-driver extras for the first targets are `[postgres]`, `[oracle]`, and
`[databricks]` (catalog rows pending admission review). Optional extras are drawn only from the governed tooling catalog
(`tooling_catalog.md`, REQ-027): `[data]`, `[conventions]`, `[calendars]`,
`[timeseries]`, `[validation]`, `[optimization]`, `[sources]`, `[excel]`, plus
the database-driver and `[sqlparse]` extras below.

The core depends on the standard library plus a SemVer-pinned `quantsmith`
dependency used only by `governed/` (the stdlib-only `nl_analytics`,
`metrics_semantic_layer`, and `analytics_packs` modules, NFR-003); no other
plugin module imports `quantsmith`, so a `0080` interface change is absorbed
in one place (RISK-013). Optional extras:
`[postgres]`, `[oracle]`, `[databricks]` (drivers; SQL Server and Snowflake later), `[sqlparse]` (a stricter SQL
parser, e.g. `sqlglot`), `[embeddings]` (via the `0071` seam). Without
`[sqlparse]` the verifier uses a conservative stdlib tokenizer that *rejects*
any construct it cannot resolve — it never fails open.

## Interfaces & Data Contracts

### Tool contract v1 (REQ-001, REQ-002)

| Tool | Purpose | Key inputs | Key outputs |
| --- | --- | --- | --- |
| `config.validate` | Validate and resolve configuration | path or inline config | resolved config hash, errors |
| `repos.index` | (Re)index query repositories, incrementally | repo IDs (optional), force | indexed/rejected/unreviewed counts, snapshot refs |
| `repos.status` | Index health | — | per-repo ref, freshness, drift findings |
| `catalog.snapshot` | Introspect or load a catalog | profile ID | snapshot ID, dated object counts |
| `catalog.describe` | Describe tables/columns for grounding | profile, objects | columns, types, keys, comments, concept mappings |
| `metrics.list` | Governed metrics available to the caller | profile | metric names, units, additivity, pack ID and review status, bound source query, availability |
| `queries.search` | Retrieve exemplars | intent text, filters (tags, profile, review status) | ranked exemplars with citations and scores |
| `glossary.lookup` | Resolve a domain term | term | `0063` record or plugin glossary entry, viewpoint |
| `sql.compose` | Compose SQL retrieval-first | question, as_of, profile | SQL, bound params, path (`reuse`/`adapt`/`generate`), sources |
| `sql.verify` | Deterministic static verification | SQL, params, profile, question type | pass/fail with codes, normalized SQL hash |
| `sql.execute` | Read-only execution of a *verified* query | verification token, params | rows (redacted), provenance record |
| `answer.ground` | Check a draft answer against results | draft, run IDs | per-claim verdicts, cleaned answer or abstention |
| `queries.get`, `index.rejections`, `index.findings`, `index.metrics`, `index.joins` | Index inspection (built in `0114`) | exemplar ID or filters | exemplars, rejections, findings, metric candidates, join edges |
| `feedback.list`; `feedback.promote`, `feedback.discard` (`human_only`) | Inbox triage and human decisions (built in `0114`) | candidate ID, note/reason | candidate records |
| `governance.validate` | Roster, handoff, tooling, manifest, and import checks (built in `0114`) | strict | report |
| `ask` | End-to-end orchestrated answer | question, as_of, caller | answer, tier (`governed`/`reuse`/`adapt`/`generate`), citations, chart spec (governed tier), caveats, run envelope — or clarification or abstention |
| `feedback.propose` | Stage a candidate exemplar or correction | run ID, correction, proposer | inbox candidate ID |
| `eval.run` | Run the golden-question evaluation | golden set version, thresholds | metrics, pass/fail per threshold |

`sql.execute` accepts only a short-lived verification token issued by
`sql.verify` for that exact normalized SQL hash and parameter set; there is no
execute-raw-SQL tool. This makes "verify before execute" a property of the
interface, not of agent discipline.

**Error codes** (stable, part of the contract): `E_CONFIG_INVALID`,
`E_CONFIG_OVERRIDE_DENIED`, `E_REPO_FETCH`, `E_FRONTMATTER_INVALID`,
`E_VERIFY_NOT_READ_ONLY`, `E_VERIFY_MULTI_STATEMENT`,
`E_VERIFY_UNKNOWN_IDENTIFIER`, `E_VERIFY_JOIN_KEY`, `E_VERIFY_UNBOUND_PARAM`,
`E_VERIFY_MISSING_PIT`, `E_VERIFY_NO_LIMIT`, `E_VERIFY_COST`,
`E_VERIFY_TABLE_NOT_ALLOWED`, `E_EXEC_TOKEN`, `E_EXEC_TIMEOUT`,
`E_ACCESS_DENIED`, `E_GROUND_UNCITED`, `E_GROUND_MISMATCH`,
`E_GROUND_UNDEFINED_TERM`, `E_GROUND_VIEWPOINT`, `E_ABSTAIN_INSUFFICIENT_EVIDENCE`,
`E_GOVERNED_CLARIFICATION`, `E_METRIC_SOURCE_UNAVAILABLE`, `E_WRITEBACK_DISABLED`.

### Configuration (REQ-003, REQ-004, REQ-017, REQ-020)

Template: `templates/sfmeridian/sfmeridian.yml` (placeholders
only). Real file: repo-root `sfmeridian.yml` (gitignored) or the path in
`SFMERIDIAN_CONFIG`. Top-level sections:

| Section | Holds |
| --- | --- |
| `schema_version` | Config schema version (NFR-007). |
| `query_repositories[]` | `id`, `kind` (`git`/`local`/`object_store`), `uri`, `ref`, `paths.include`/`exclude`, `dialect`, `metadata_convention` (`front_matter`/`sidecar`), `trust_tier`, `review_policy` (`reviewed_only`/`allow_unreviewed_as_hints`), `refresh` (`on_demand`/cron). |
| `databases[]` | `id` (profile), `dialect`, `connection.secret_ref` (pointer, never a value), `read_only: true` (required), `schemas_allowlist`, `tables_allowlist`, `row_limit`, `timeout_s`, `explain_cost_limit`, `max_concurrency`. |
| `catalog` | Per profile: `source` (`introspect`/`file`), `file`, `refresh`, `drift_policy` (`exclude`/`warn`). |
| `semantic_mapping` | Per profile: concept (an `0081` pack metric/dimension name or a `0063` ID) → physical expression, grain, PIT column, viewpoint. |
| `governed_tier` | `enabled`, `interpreter` (`keyword`/`llm`), `packs_root` (for `resolve_packs`; local overlay first), `domain_tags` (e.g. `securities_lending`), `metric_sources` (metric → reviewed exemplar ID and column map to `Fact` period/dims/measures), `writeback.enabled: false` (REQ-026). |
| `grounding` | `retrieval_min_score`, `max_compose_retries`, `require_citation_per_number: true`, `abstain_message`, numeric tolerance. |
| `access` | Redaction classes (`counterparty_identity`, `account`, `client_position`), column → class map, caller clearance source (`0058` roster). |
| `llm` | Runtime profile name resolved through `adapters/llm_runtime/`; temperature and token budgets; no keys. |
| `retrieval` | `lexical` (default) or `lexical+embeddings`; embedding profile via `0071`. |
| `feedback` | Inbox location, promoters (handles), auto-propose on accepted answers (bool). |
| `eval` | Golden set path(s) (repo synthetic + optional adopter-private), thresholds (NFR-002). |
| `per_call_overrides_allowlist` | Fields a caller may override per call (e.g. `as_of`, `row_limit` lower only). |

Resolution order: built-in defaults → file → `SFMERIDIAN__*` environment
variables → per-call overrides (allowlisted, and only in the restrictive
direction for safety fields). The resolved config is frozen and hashed; the
hash is in every run envelope.

### Query metadata convention (REQ-005)

Front-matter in the leading comment block of each `.sql` file (sidecar
`<name>.yml` alternative). Template:
`templates/sfmeridian/query_front_matter.sql`. Required for `reviewed`:
`id`, `title`, `intent`, `owner`, `dialect`, `profile`, `params[]` (name, type,
required), `tables[]`, `pit_columns[]`, `grain`, `review_status`, `reviewed_by`,
`reviewed_on`. Optional: `tags[]`, `concepts[]` (`0063` IDs), `viewpoint`,
`supersedes`, `notes`. Front-matter is parsed as data only (RISK-005).

### Derived learning artifacts (REQ-006, REQ-007)

| Artifact | Shape | Citation |
| --- | --- | --- |
| Exemplar | `{exemplar_id, repo_id, ref, path, line_span, sql_hash, intent, params, tables, concepts, review_status}` | repo, ref, path, span |
| Join edge | `{left.table.col, right.table.col, join_type, support_count, exemplar_ids}` | supporting exemplars |
| Metric candidate | `{name, expression, grain, tables, exemplar_ids}`; promoted to the semantic mapping only by review | supporting exemplars |
| Filter pattern | `{column, operator, typical_values_redacted, exemplar_ids}` | supporting exemplars |
| Drift finding | `{snapshot_id, object, change, affected_exemplars}` | catalog snapshot |

The index stores SQL text, identifiers, and metadata — **never result rows**
(RISK-006). Artifacts are content-addressed and written as JSONL so re-index is
incremental and diffable (NFR-001, NFR-005).

### Point-in-time and viewpoint controls (REQ-010, REQ-013)

- A question classified as `as_of` requires a predicate on each fact table's
  declared PIT column (from front-matter or semantic mapping) bound to the
  `as_of` parameter; `latest` questions are labelled as such in the answer.
- Every concept mapping declares a viewpoint (`borrower`, `lender`, `agent`,
  `beneficial_owner`) and unit; the grounding check rejects combining
  viewpoints or units without a `0063` conversion record.
- Fee/rebate accrual uses ACT/360 per `0066` unless the mapping declares
  another basis explicitly.

## Agent Loop Runtime (REQ-028, REQ-029)

SFMeridian agents are not prompt files with a checklist; each is a bounded
tool loop the plugin runs, built in `0114` and used by every later child:

```text
manifest (goal, tools, verifiers, budgets, human checkpoints, never)
   │
   ▼
policy.decide(state) ──▶ ToolCall ──▶ tool registry (schema check, effect) ──▶ observation ─┐
   ▲                    Finish   ──▶ deterministic verifiers ── fail ──▶ observation ───────┤
   │                    Escalate ──▶ stop: a human checkpoint                               │
   └────────────────────────────────────────────────────────────────────────────────────────┘
trace ──▶ run record (run ID, config hash, audit events) ──▶ 0070 envelope
```

- **Tool registry** (`sfmeridian.tools`): the contract table above *is* the
  registry. Effects: `read`, `index`, `propose`, `human_only`, and
  `execute_read` from `0116` (verified read-only SQL). Apps and agents call
  the same tools.
- **Manifests** (`sfmeridian/data/agents/<name>.json`): mirror the agent's
  `coverage.json` loop row; the governance check fails when they disagree or
  when a manifest grants a `human_only` tool.
- **Harness** (`sfmeridian.agent.run_agent`): least privilege, budgets,
  verified finish with bounded repair, escalation as a first-class outcome,
  deterministic trace.
- **Policies**: a deterministic policy per agent (offline, testable) and
  `ModelPolicy`, which prompts an injected completion function with the goal,
  granted tool schemas, and observations, and parses one JSON action; output
  passes the same harness checks. Two malformed actions escalate.
- **Verifiers**: deterministic functions over the run's observations and the
  proposed finish — the agent-level form of REQ-012 grounding (for example,
  "every finding cites evidence observed in this run").
- **Evaluation**: each agent's golden runs join the `0117` evaluation gate
  (completion rate, verifier-repair rate, escalation precision, denied-call
  rate).

Each coverage row below carries its loop in `coverage.json`: granted tools,
verifiers, human checkpoints, and stop condition.

## Agent Roster & Coverage Matrix (REQ-015)

**Reused agents (no change to their charters in this spec):**

| Existing agent | Role in the plugin |
| --- | --- |
| `securities_financing/securities_lending` | Domain lead: interprets borrow/lend mechanics, GC vs specials, recalls; consumes plugin answers. |
| `securities_financing/financing_cost_analysis` | Turns plugin-sourced, point-in-time borrow costs into all-in carry and financing-aware backtests. |
| `securities_financing/collateral_management` | Collateral, haircut, margin, and concentration questions; counterparty/collateral exposure workflow. |
| `securities_financing/repo_financing` | Cash-collateral reinvestment and funding context where lending meets repo. |
| `sql-integration-agent` | Generic SQL safety review; reference for the execution seam rules. |
| `data_ingestion/database_connectivity` | Connection profiles, drivers, read-only service accounts. |
| `knowledge/knowledge_retrieval` | Retrieval over the `0063` pack and glossary. |
| `analytics/nl_analytics` (`0080`) | **The governed tier**: question → `QueryPlan` → insights → grounded narrative over the plugin's `Reader`. |
| `analytics/metrics_semantic_layer` (`0008`) | Owns governed metric definitions; reviews metric candidates the plugin learns from the query repository before they become governed. |
| `analytics/data_visualization` | Chart choice for governed-tier answers (`0080` `ChartSpec`, Vega-Lite). |
| `data_quality`, `quality-guard-agent` | Data checks on result sets; release gate over the eval report. |
| `provenance/lineage_capture` | Lineage from answer → run → query → repo commit → catalog snapshot. |
| `data_engineering/schema_evolution` | Classifies catalog drift found by reconciliation. |
| `risk`, `backtest_review` | Downstream consumers of borrow cost and recall risk. |
| `workflow_orchestrator` | Drives the SDD flow for each child spec. |

### Specialist Handoff Map (REQ-021, REQ-022)

The plugin supplies *grounded evidence* (cited runs, point-in-time panels,
`0063` terms); these existing agents supply *specialist judgement* on it. Each
handoff passes run IDs and citations, never raw credentials or unredacted
restricted columns, and each agent keeps its own never-boundary. The plugin
proposes no agent for any workflow below.

**Optimization** (`agents/optimization/`, routed by `optimization_orchestrator`)

| Agent | Trigger | Plugin evidence in | Output | Never | Workflow |
| --- | --- | --- | --- | --- | --- |
| `problem_formulation` | Any allocation, pricing, or capacity question that needs an optimizer | inventory, demand, constraints panels | formal objective, variables, constraints, data map | never solves with undeclared constraints | W7, W8, W9 |
| `linear_programming` | Inventory-to-demand allocation (extends `0023`'s LP) | lendable inventory, borrow demand, fees, caps | proposed allocation | never ignores the balance-sheet cap (`0023` AC) | W7 |
| `mixed_integer_optimization` | Allocation with minimum lot sizes, counterparty count limits, or all-or-nothing loans | same as LP plus lot/limit data | proposed allocation | never reports a MIP gap as optimal | W7 |
| `collateral_margin_optimization` | Cheapest-to-deliver collateral, substitutions, margin under schedules (`0067` contract) | collateral holdings, eligibility, haircuts, margin calls | proposed collateral allocation | never breaches eligibility or concentration schedules | W8 |
| `pricing_revenue_optimization` | Fee-setting for warm/special names, tiered counterparty pricing | PIT fee history, utilization, demand elasticity estimates | proposed fee grid with expected revenue range | never reprices; proposals only | W9 |
| `resource_capacity_optimization` | Balance-sheet, RWA, or lending-capacity budgeting across programs | capacity limits, balances, returns on capacity | proposed capacity split | never exceeds declared limits | W7, W9 |
| `robust_optimization` | Allocations that must survive recall or demand uncertainty | demand/recall forecast intervals (W10) | robust allocation and cost of robustness | never hides the uncertainty set | W7 |
| `solver_diagnostics_sensitivity` | **Every** solve above | solver output | status, binding constraints, duals, sensitivities | never certifies a solve it cannot reproduce | W7, W8, W9 |
| `model_plugin_registration` | Adopter's in-house allocation or collateral engine | `0026` manifest | understanding brief and routing | never inspects proprietary logic | W7, W8 |

**Risk** (`agents/risk/`, `agents/enterprise_risk/`)

| Agent | Trigger | Plugin evidence in | Output | Never | Workflow |
| --- | --- | --- | --- | --- | --- |
| `risk` | Short-side or lending-program risk profile | borrow cost, recall, concentration panels | risk profile, stress cases | never states return without the risk story | W3, W11 |
| `counterparty_credit_risk` | Exposure to borrowers net of collateral and indemnification | loans, collateral marks, netting sets, limits | netted, collateralized exposure, PFE with horizon | never lets gross exposure stand for net | W11 |
| `liquidity_treasury_risk` | Cash-collateral reinvestment, recall-driven liquidity needs | cash collateral balances, reinvestment holdings, recall forecasts | liquidity gap and stress with stated basis | never reports a liquidity number without its basis | W11 |
| `operational_risk` | Fails, buy-ins, late returns, booking breaks | fails and buy-in records, recall timelines | classified events vs near-misses | never classifies a developing event as a loss | W3 |
| `model_risk_management` | The plugin's own models and the grounding pipeline once used for decisions | eval reports (REQ-016), model cards | inventory entry, validation cadence, findings | never approves its own validation | W12 |

**Portfolio management** (`agents/portfolio_management/`, routed by `pm_orchestrator`)

| Agent | Trigger | Plugin evidence in | Output | Never | Workflow |
| --- | --- | --- | --- | --- | --- |
| `universe_selection` | Shortable universe for a strategy | PIT availability, HTB status, fees | eligible, PIT short universe | never uses today's borrow status historically | W5, W10 |
| `compliance_constraints` | Locate, Reg SHO, restricted-list, and lending-guideline checks | locates, restricted lists, client lending guidelines | pre/post-trade constraint checks, exceptions | never waives a constraint | W10 |
| `liquidity_cash_management` | Short-side implementability under borrow and funding | availability, recall risk, funding | implementability verdict and constraints | never assumes free borrow | W10 |
| `risk_budgeting` | Borrow-cost and recall risk inside the portfolio risk budget | borrow-cost panel, recall indicators | budget usage and breaches | never reallocates budget itself | W10 |
| `rebalance_trade_implementation` | Rebalances that open or cover shorts | locate status, availability, fees | implementation plan with borrow checks | never sends orders | W10 |
| `performance_attribution` | Borrow cost and lending income in portfolio results; reviews C-08's revenue attribution | revenue and borrow-cost runs | attribution incl. financing effect | never omits costs | W4, W10 |
| `data_signal_intake` | Borrow-derived signals (utilization, fee moves, short interest) entering PM decisions | plugin panels with run citations | readiness verdict | never admits a signal without PIT proof | W5, W10 |

**Knowledge** (`agents/knowledge/`)

| Agent | Trigger | Plugin evidence in | Output | Never | Workflow |
| --- | --- | --- | --- | --- | --- |
| `knowledge_retrieval` | Domain term or desk-procedure lookup | — | cited `0063`/glossary records | never answers without a source | W1 |
| `knowledge_ingestion` | Onboarding desk runbooks, data dictionaries, and schema docs that explain the query repository | documents (adopter-local) | provenance-tagged, access-aware chunks; PII/secret flags | never ingests restricted material into a lower tier | W6 |
| `knowledge_curation` | Dedup, conflict, and staleness across exemplars, metric definitions, and glossary terms | index, drift findings, candidate inbox | canonical choices, conflict and gap list | never resolves a conflict without a canonical source | W6, W12 |
| `institutional_memory` | Accepted answers, corrections, and recurring desk questions | promoted feedback, decisions | durable records feeding the index (`0049`) | never persists unreviewed claims | W12 |

**Machine learning** (`agents/machine_learning/`, routed by `ml_orchestrator`)

| Agent | Trigger | Plugin evidence in | Output | Never | Workflow |
| --- | --- | --- | --- | --- | --- |
| `problem_framing_labeling` | Defining targets: "goes special within h days", "recalled within h days", demand level | PIT event history | label spec with horizon and leakage review | never labels with information after the decision time | W10 |
| `feature_store_engineering` | Reusable PIT borrow features (utilization, fee momentum, days-to-cover, recall rate) | plugin panels with as-of | feature definitions with as-of joins | never serves a feature without its as-of | W10 |
| `time_series_forecasting` | Borrow demand, utilization, fee forecasts | PIT panels | forecasts with baseline and intervals | never reports a forecast without a naive baseline | W2, W10 |
| `supervised_learning` | Specials and recall classifiers | features and labels above | calibrated scores | never reports uncalibrated probabilities | W3, W10 |
| `unsupervised_anomaly` | Unusual fee, utilization, or recall patterns; unusual query-rejection patterns | PIT panels, verifier logs | ranked anomalies with explanations | never treats an anomaly as a confirmed event | W2, W12 |
| `model_selection_validation` | Every model above | candidate models | purged/walk-forward validation (`0006`/`0046`) | never selects on in-sample results | W10 |
| `causal_uplift` | Effect of a fee or recall-policy change on demand or revenue | pre/post panels, experiment design | effect estimate with identification assumptions | never presents correlation as effect | W9 |
| `ranking_recommendation` | Exemplar ranking for `queries.search` if lexical retrieval underperforms on the golden set | golden-set retrieval logs | ranker with offline metrics | never ranks unreviewed exemplars above reviewed | W1 |
| `mlops_monitoring` | Drift and decay of deployed borrow models | live predictions vs outcomes | drift and decay alerts | never retrains silently | W12 |

**Proposed new agents** (group folder `agents/securities_financing/sfmeridian/`; each created only by its child spec):

| Row | Agent | Distinct workflow | Never does | Child |
| --- | --- | --- | --- | --- |
| C-01 | `query_librarian` | Onboard and index query repositories; front-matter hygiene; dedup; drift triage; review queue for candidates. | Never promotes a candidate or edits query SQL without a named human reviewer. | `0114` |
| C-02 | `semantic_mapping_steward` | Bind `0081` pack metrics and `0063` concepts to physical columns and metric source queries per profile; declare grain, PIT column, viewpoint, unit; draft `0081` pack amendments for missing concepts. | Never invents a mapping without a catalog object and an exemplar or owner confirmation; never edits a pack's `review` block or defines a concept privately. | `0115` |
| C-03 | `sql_composer` | Retrieval-first SQL composition (reuse → adapt → generate) under the catalog and mapping, **only for questions `0080` reports as outside the governed metrics** — the workflow `nl_analytics` deliberately does not hold. | Never executes SQL and never bypasses `sql.verify`. | `0116` |
| C-04 | `sfmeridian_orchestrator` | Route desk questions through the governed tier, then the 11-step pipeline; pick analytics agents; manage retries and abstention. | Never answers from model memory; never returns a number without a run citation. | `0116`/`0117` |
| C-05 | `answer_grounding_reviewer` | Claim-level citation, recompute, term, and viewpoint checks on draft answers. | Never adds new facts; can only cite, correct to the cited value, remove, or abstain. | `0117` |
| C-06 | `utilization_specials_analyst` | Desk-facing interpretation of utilization, demand/supply, fee trends, GC→warm→special migration, days-to-cover; consumes `time_series_forecasting` and `unsupervised_anomaly` outputs rather than building models. | Never builds or trains a model itself; never uses non-PIT rates for history. | `0119` |
| C-07 | `recall_buyin_risk_analyst` | Recall pressure (dividends, votes, sales), buy-in and fail exposure on open loans/borrows; consumes `supervised_learning` recall scores and hands events to `operational_risk`. | Never sends or recommends sending a recall; outputs risk indicators only. | `0119` |
| C-08 | `lending_revenue_analyst` | Program revenue attribution: by security, counterparty tier, GC vs specials, agent/beneficial-owner split, intrinsic vs reinvestment; method reviewed by `performance_attribution`. | Never restates booked revenue; reconciles to the book and reports differences. | `0119` |
| C-10 | `lending_data_researcher` | Adaptive research of one lending dataset (coverage ledger, pushed-down aggregates, securities-finance rule pack, evidence-driven follow-ups, recommendations, reproducible bundle). | Never runs model or repository SQL, writes, repairs, or invents context; never states an extract result as a population fact. | `0121` (built) |
| C-09 | `lending_reporting_check` | Field completeness and consistency checks for SFTR / Rule 10c-1a style datasets. | Never submits, certifies, or interprets regulation. | `0120` |

`sql.verify` and grounding checks are **tools, not agents**: they are
deterministic and model-independent by design, so they get no prompt. The
counterparty/collateral exposure workflow is held by `collateral_management`,
`counterparty_credit_risk`, and `risk` (W11) and gets no new agent (RISK-009);
likewise every optimization, portfolio-management, knowledge, and ML workflow
in the handoff map above.

## Canonical Workflows (REQ-019)

| Workflow | Agents | Tools | Inputs → outputs | Review gate | Must cite |
| --- | --- | --- | --- | --- | --- |
| W1 Desk question → cited answer | C-04, `nl_analytics` (governed tier), C-03, C-05, `securities_lending` | `ask` (all steps) | question, as_of → answer + tier + citations, clarification, or abstention | grounding check | run IDs, query IDs, pack ID and review status, `0063` terms |
| W2 Daily utilization & specials monitor | C-06, `time_series_forecasting`, `unsupervised_anomaly`, `alert_policy`, `alert_router` | `queries.search`, `sql.*`, `answer.ground` | as_of → movers, migrations, alerts | `data_quality` on inputs | runs per metric, PIT predicate |
| W3 Recall & buy-in risk review | C-07, `supervised_learning`, `operational_risk`, `collateral_management`, `risk` | `sql.*`, `answer.ground` | book as_of, corporate-action calendar → risk list | named human review | runs, corporate-action source |
| W4 Lending revenue attribution | C-08, `performance_attribution`, `financing_cost_analysis` | `sql.*`, `0008` metrics | period → attribution reconciled to book | reconciliation to book total | runs, reconciliation diff |
| W5 Borrow cost → backtests | `financing_cost_analysis`, `universe_selection`, `data_signal_intake`, `backtest_review` | `sql.*` (PIT) | universe, dates → PIT borrow-cost panel | `leakage` + `backtest` gates | runs with `as_of` per date |
| W6 Query-repository onboarding | C-01, C-02, `schema_evolution`, `knowledge_ingestion`, `knowledge_curation` | `repos.index`, `catalog.snapshot`, `feedback.propose` | config, desk docs → index, drift report, review queue | human promotion | repo refs, snapshot IDs |
| W7 Inventory allocation | `problem_formulation` → `linear_programming` / `mixed_integer_optimization` / `robust_optimization` (or a `0026` plugin) → `solver_diagnostics_sensitivity`; `resource_capacity_optimization` | `sql.*` (inventory, demand, caps) | as_of → proposed allocation, binding constraints, sensitivities | named human review | runs per input panel, solver status |
| W8 Collateral optimization | `collateral_management`, `collateral_margin_optimization` (`0067`) → `solver_diagnostics_sensitivity` | `sql.*` (holdings, eligibility, haircuts) | as_of → proposed collateral allocation and substitutions | named human review | runs, eligibility schedule version |
| W9 Fee and capacity pricing | `pricing_revenue_optimization`, `causal_uplift`, `resource_capacity_optimization` → `solver_diagnostics_sensitivity` | `sql.*` (PIT fees, utilization) | period → proposed fee grid, expected revenue range | named human review | runs, elasticity assumptions |
| W10 Borrow-aware portfolio decisions | `universe_selection`, `compliance_constraints`, `liquidity_cash_management`, `risk_budgeting`, `rebalance_trade_implementation`, `data_signal_intake`; models from `problem_framing_labeling` → `feature_store_engineering` → `time_series_forecasting` / `supervised_learning` → `model_selection_validation` | `sql.*` (PIT) | strategy, dates → shortable universe, constraints, borrow-aware plan | `leakage` + `backtest` gates; PM review | runs with `as_of` per date, validation report |
| W11 Counterparty and liquidity review | `counterparty_credit_risk`, `liquidity_treasury_risk`, `collateral_management`, `risk` | `sql.*` (loans, collateral, cash reinvestment) | as_of → netted exposure, liquidity gap, stress | named human review | runs, netting-set and basis statements |
| W13 Dataset research | `lending_data_researcher` → `dataset_investigator` (deep file EDA), `data_quality` (contract acceptance), `schema_evolution` (reference changes) | `research.*` | dataset, context → coverage, findings, recommendations, bundle | human decision on every recommendation | evidence IDs, query hashes, scope |
| W12 Plugin governance and learning | `model_risk_management`, `mlops_monitoring`, `unsupervised_anomaly`, `knowledge_curation`, `institutional_memory`, `quality-guard-agent` | `eval.run`, `repos.status`, `feedback.*` | eval reports, drift, feedback → findings, promotions, inventory entry | human promotion; MRM review | eval report version, promoted record IDs |

## Hallucination Evaluation Protocol (REQ-016, NFR-002)

- **Fixture:** a synthetic SQLite database extending `0023`'s
  `seed_demo_data` (`borrow_rates`, `positions`, `sec_lending_book`, `recalls`)
  with `lendable_inventory`, `collateral`, `counterparties`, `corporate_actions`,
  and `program_revenue`; a synthetic `securities_lending`-tagged `0027`
  source entry so `0080` selects the `0081` pack; a synthetic query repository (~40 annotated queries,
  some deliberately stale, unreviewed, or malformed); all flagged per `0025`.
- **Golden set:** versioned JSONL; each question has a category, `as_of`,
  expected SQL result (not expected SQL text), expected citations, and
  expected abstention flag. Categories: lookup, aggregation, as-of (PIT),
  viewpoint/sign, multi-join, metric (utilization, revenue), unanswerable
  (missing column/table), ambiguous (must clarify), adversarial (injection in
  comments or results), drifted (exemplar references a dropped column), and
  governed (maps to an `0081` pack metric; must be answered at tier
  `governed`, and again through `reuse` for the agreement check).
- **Metrics:** identifier-fabrication rate (unresolved identifiers in executed
  SQL), execution accuracy (executes without error when answerable),
  result-match accuracy (result set equals expected), unsupported-claim rate
  (claims without a valid citation in final answers), viewpoint-error rate,
  abstention precision and recall, exemplar-reuse rate, governed-tier share,
  **tier-agreement rate** (governed vs reuse answers to the same question must
  match: target 100%, RISK-012), wrong-tier rate (a governed question answered
  by SQL composition, or an ambiguity resolved by fall-through: target 0), and
  p95 latency.
- **Gate:** `eval.run` compares to thresholds in config; `quality-guard-agent`
  treats a miss as release-blocking. LLM-dependent metrics are reported with
  the model profile and run three seeds; deterministic metrics must be exact.
  Coordinates with `0103` (evaluation agents) without depending on it.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Verify-token interface makes unverified execution impossible; PIT predicates required for as-of; numbers recomputed by tools; viewpoint conversions explicit. |
| P5 Reversibility | yes | Plugin is an additive package; config, index, and inbox are files; removal touches no existing agent or runtime (NFR-008). |
| P6 Observability | yes | Every answer carries a `0070` run envelope, config hash, catalog snapshot, repo ref; eval report per release; drift findings surfaced. |
| P9 Security & data | yes | Read-only profiles, secret pointers only, allowlists, redaction classes, clearance, index holds no result rows, no real data in repo. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | Tool contract v1, error codes, single distributable | T-001, T-020 |
| REQ-002 | Three surfaces over one contract | T-021, T-022, T-023 |
| REQ-003 | Config schema, layered resolution, validate-only, template | T-002, T-005 |
| REQ-004 | `query_repositories[]` and fetchers | T-002, T-006 |
| REQ-005 | Front-matter convention and parser | T-003, T-007 |
| REQ-006 | Exemplar store, join graph, metric/filter extraction | T-008 |
| REQ-007 | Catalog snapshots and drift reconciliation | T-010, T-011 |
| REQ-008 | Semantic mapping on `0008` rules | T-012 |
| REQ-009 | Retrieval-first composer | T-014 |
| REQ-010 | Deterministic verifier and cost guard | T-015 |
| REQ-011 | Read-only execution seam and provenance | T-016 |
| REQ-012 | Grounding check and abstention | T-018 |
| REQ-013 | Viewpoint/unit enforcement on `0063` | T-012, T-018 |
| REQ-014 | Feedback inbox, promotion | T-009 |
| REQ-015 | Roster and coverage matrix | T-004, T-017, T-026 |
| REQ-016 | Golden set, metrics, gate | T-019 |
| REQ-017 | Access, redaction, secret pointers | T-013 |
| REQ-018 | Child-spec roadmap | T-024 |
| REQ-019 | Canonical workflows W1–W6 | T-004, T-026 |
| REQ-020 | Multi-dialect profiles | T-016, T-025 |
| REQ-021 | Specialist handoff map; workflows W7–W12 | T-028, T-029 |
| REQ-022 | Decision-support output envelope for optimizer and model results | T-029, T-030 |
| REQ-027 | Tooling catalog, admission review, catalog-only recommendations | T-036, T-037 |
| REQ-028 | Loop harness, manifests, policies, verifiers, traces | T-038, T-040 |
| REQ-029 | Shared tool registry with effects; `human_only` decisions | T-039 |
| REQ-023 | Governed-first tier routing through `0080` (`governed/`) | T-031, T-035 |
| REQ-024 | `Reader` over verified metric source queries | T-032 |
| REQ-025 | Concept vocabulary seeded from `0081`; pack amendments; unreviewed-pack caveat | T-033 |
| REQ-026 | Write-back disabled by default; target validation | T-034 |
| NFR-001 | Offline deterministic fixtures and harness | T-008, T-019 |
| NFR-002 | Release thresholds | T-019 |
| NFR-003 | Stdlib core, optional extras | T-020 |
| NFR-004 | Read-only, limits, credential hygiene | T-013, T-015, T-016 |
| NFR-005 | Latency/cost budgets, incremental re-index | T-008, T-015 |
| NFR-006 | Synthetic fixtures disclosed | T-019, T-027 |
| NFR-007 | SemVer and schema versions | T-001, T-023 |
| NFR-008 | Additive, removable package | T-027 |
| NFR-009 | Catalog gates pass | T-005, T-027 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Question → SQL path | Governed-first through `0080`, query repository for the tail | A second, independent NL→SQL path | `0080` already plans over governed metrics with clarification, clearance, and grounding; two paths would answer the same question two ways (RISK-012). |
| `0080` dependency | Pinned `quantsmith` import isolated in `governed/` | Vendor a copy of `0080` | A vendored copy forks the governed path and its fixes; pinning plus one adapter keeps a single source of truth. |
| Missing pack concepts | Propose `0081` amendments | Plugin-private concept list | Private definitions would fork the domain vocabulary `0080` and reviewers rely on. |
| Third-party libraries | Governed catalog screened from community lists; optional extras only | Adopt a curated list wholesale | Most entries are trading, crypto, or pricing tools outside scope or against the read-only boundary; unvetted packages are a supply-chain risk (RISK-014). |
| Packaging | Separate distributable under `plugins/sfmeridian/` | Module inside `src/quantsmith/` | Apps must install it without the SDK (NFR-003); `0110` already packages Claude plugins. |
| "Learning" | Indexed retrieval + structure extraction + reviewed promotion | Fine-tuning on the query repo | Auditable, reversible, no training data leaves the adopter; fine-tune deferred until eval shows a gap (roadmap Phase 6). |
| Verification | Deterministic verifier with fail-closed tokenizer; optional strict parser | LLM self-check of SQL | A model cannot reliably check its own invented identifiers; determinism makes the fabrication-rate threshold of 0 achievable. |
| Execute interface | Verification token required | Execute raw SQL with a guard flag | Makes verify-before-execute an interface property, not discipline. |
| Ground truth for eval | Expected result sets | Expected SQL text | Many correct SQL strings exist; results are what users consume. |
| Retrieval | Lexical BM25 default, embeddings optional | Embeddings required | Air-gapped and restricted adopters; determinism of tests. |
| Verifier/grounding as agents | Tools | Dedicated agents | No judgement to delegate; prompts add an attack surface. |
| Optimization, risk, PM, knowledge, ML work | Handoff to existing agents with contracts | Plugin-owned optimizer/model/risk agents | Those agents already hold the workflows and review standards (RISK-009); the plugin's job is grounded evidence, not specialist judgement. |
| Query repo location | Configuration only | Convention path in this repo | Firms keep queries in their own Git/hosts; the public repo must hold none. |

## Validation Strategy

- Unit tests per component, each naming its `AC-*` (`0114`–`0118`).
- Contract tests: identical results across the three surfaces (AC-002) and
  schema-compatibility checks between versions (AC-023).
- Adversarial verifier suite (AC-010) and grounding suite (AC-012, AC-013).
- The golden-question harness (AC-016) on the synthetic database, deterministic
  metrics exact, LLM-dependent metrics over three seeds with the model profile
  recorded.
- Replay of `ask` runs through the `0070` replay command (AC-011).
- Tier-routing and `Reader` tests against `0080`'s own fixtures plus the
  synthetic database, pinned to the `quantsmith` version under test
  (AC-027, AC-028); pack-seeding validation through `0081`'s validator (AC-029).
- Repo gates: `spec`, `spec-index`, `handoff-sync`, `agent-catalog`,
  `skills-export`, `secret-scan`, `data-provenance` (AC-022, AC-024).

## Rollout, Observability & Rollback

- **Rollout:** Phases in `roadmap.md`. Shadow mode first (answers produced and
  evaluated but shown only to the plugin owner), then a named pilot desk, then
  app integrations. Each phase exits only on its criteria.
- **Observability:** per-answer run envelope; daily metrics — abstention rate,
  verifier rejection codes, fabrication attempts caught, drift findings, p95
  latency, warehouse cost by profile — fed to `monitoring/model_signal_monitoring`
  and `alerts/alert_policy`.
- **Kill switch:** `grounding.mode: retrieval_only` in config disables the
  `generate` path (reviewed exemplars only); `enabled: false` disables `ask`.
- **Rollback:** pin the previous plugin version (SemVer); index and inbox are
  versioned files and can be restored to a prior snapshot.

## Open Questions

- Which viewpoint and dialect the first adopter needs (see `spec.md`).
- Who reviews the `0081` `securities_financing_prime` pack and its amendments.
- Whether the MCP server should also expose the query index as `0052`
  resources (`knowledge://sfmeridian/...`) or tools only.
- Whether `0120` (regulatory completeness) should be scheduled ahead of
  `0119` for an adopter under a near-term reporting obligation.
