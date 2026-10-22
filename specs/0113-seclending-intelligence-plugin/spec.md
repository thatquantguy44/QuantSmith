# Spec: SFMeridian — Securities Finance Intelligence Plugin (Foundation)

- **ID:** 0113-seclending-intelligence-plugin
- **Status:** Approved
- **Author:** Joshua Lutkemuller, CFA
- **Approver:** Joshua Lutkemuller, CFA (2026-10-22)
- **Last updated:** 2026-10-22 (REQ-021/REQ-022 handoffs; REQ-023–REQ-026 governed-first tier on `0080`/`0081`; REQ-027 tooling catalog; named SFMeridian)
- **Product name:** SFMeridian (distributable `sfmeridian`). Only the plugin
  carries this name; QuantSmith is unchanged. The spec directory keeps its
  original slug so existing links stay stable.

> WHAT and WHY only. Implementation lives in `plan.md`; the phased delivery
> order lives in `roadmap.md`. This is an **umbrella foundation spec** in the
> shape of `0063`, `0072`, and `0083`: it defines the plugin boundary, the
> configuration contract, the grounding (anti-hallucination) contract, the
> agent roster and coverage matrix, the evaluation protocol, and the
> child-spec roadmap (`0114`–`0120`). Each runtime and each new agent is
> created by a bounded child spec, never by this one.

## Problem & Context

Securities-finance desks (agency lenders, beneficial owners, prime brokers,
and short-side quant teams) answer the same questions every day — *what is
on loan, at what fee, against what collateral, to whom; what is utilization
doing; which names are going special; what is at risk of recall; what did the
program earn* — and the answers live in SQL databases whose schemas are
idiosyncratic, poorly documented, and spread across a loan book, an
availability/inventory feed, a rates feed, a collateral system, counterparty
reference data, and third-party securities-finance market data.

The institutional knowledge of how to query those databases correctly already
exists — in a **repository of hand-written, reviewed SQL queries** that analysts
have accumulated. What does not exist is an agent that (a) learns from that
repository instead of inventing SQL, (b) refuses to state a number it did not
compute from a cited query, and (c) can be lifted out of QuantSmith and
embedded in other applications.

The SDK already has the pieces, unconnected:

- Domain agents: `securities_financing/securities_lending`,
  `financing_cost_analysis`, `collateral_management`, `repo_financing`.
- Domain knowledge: the `0063` short-term-markets pack (taxonomy, viewpoints,
  fee/rebate sign conventions, lifecycles, golden cases) and the `0066`
  corrections (ACT/360 accrual, configurable GC/WARM/HTB thresholds).
- A runtime: `0023`'s `sec_lending_workflow.py` and `sql_data.py`
  (`SQLDataSource`, `SQLiteDataSource.seed_demo_data`, query templates).
- Data access: `sql-integration-agent`, `data_ingestion/database_connectivity`,
  `adapters/data_access/sql.md`.
- Governed natural-language analytics: `0080` (`analytics/nl_analytics`)
  already turns a question into a typed `QueryPlan` over `0008` governed
  metrics — never free-form SQL — asks for clarification instead of guessing,
  checks `0058` clearance with existence masking, executes through a
  caller-injected read-only `Reader` (`QueryPlan → Facts`), computes insights
  deterministically, and grounds its narrative. `0081` ships a draft
  `securities_financing_prime` domain pack (`on_loan_value`, `borrow_fee`,
  `utilization`, `lending_revenue`, `client_debit_balance`, with units,
  additivity, fee/rebate and specials conventions, insight-suppression rules,
  and golden cases) that `0080` applies by domain tag.
- Retrieval and governance: `knowledge/knowledge_retrieval`, `0052`–`0054` MCP
  adapter contract and access tiers, `0071` LLM evidence boundary, `0070` run
  envelope and replay, `0008` metrics semantic layer, `0049` reviewed write
  path, `0102` lineage.
- Packaging: `0110`'s skills export and local plugin marketplace; `0047`'s
  downstream SemVer contract.

Why it needs its own foundation rather than a prompt on top of
`sql-integration-agent`:

- **Text-to-SQL hallucinates in specific, preventable ways**: invented tables
  and columns, wrong join keys, a fee read as a rebate, a quantity summed with a
  market value, a latest-snapshot query run against an as-of question. Each is
  preventable structurally (catalog resolution, reviewed exemplars, viewpoint
  conventions, point-in-time predicates), not by asking the model to be careful.
- **The query repository is the ground truth for "how we do it here"** and
  must be configurable per adopter — its location, layout, dialect, and review
  workflow differ between firms and cannot be hard-coded.
- **Governed metrics cover the head, not the tail.** `0080` answers questions
  that map to a governed metric and deliberately never writes SQL; most desk
  questions (a specific counterparty's open loans against a recall list, a
  join the metrics layer does not model) live in the query repository's long
  tail. The plugin therefore **extends `0080` rather than competing with it**:
  governed metrics first, reviewed queries second, constrained generation last
  (REQ-023).
- **Apps down the road** (a desk chatbot, a Slack assistant, a BI copilot, a
  batch report) need one stable interface, not a QuantSmith checkout.

## Goals

- Define a **self-contained, versioned plugin** (`sfmeridian`)
  with one tool contract exposed through three surfaces: a Python API, an MCP
  server, and a Claude Code plugin — usable by an app without the rest of the
  SDK.
- Answer **governed-first** through `0080` over `0008` metrics seeded from
  the `0081` securities-financing pack, and use the query repository for the
  questions governed metrics cannot answer — one path per question, never two
  competing ones.
- Make the **query repository a configuration value**, not a code constant:
  one or more Git, local, or object-store locations, each with its own layout,
  dialect, trust tier, and review policy.
- **Learn from the query repository** by retrieval and structure extraction
  (exemplars, join paths, metric definitions, filters, point-in-time columns),
  with a human-reviewed feedback loop — never by silently promoting
  model-written SQL.
- Make **hallucination structurally limited**: no number without a cited,
  executed, read-only query; no identifier that does not resolve in a catalog
  snapshot; no domain term without a `0063` record; explicit abstention when
  evidence is insufficient.
- **Measure** hallucination with a golden-question evaluation protocol and
  release thresholds, rather than asserting it.
- Expand the existing securities-financing agent group with only the agents a
  coverage row justifies, and route to existing agents everywhere else —
  including the optimization, risk, portfolio-management, knowledge, and
  machine-learning groups (REQ-021).

## Non-Goals

- **No runtimes, tools, or new agents in this spec.** They are created by
  `0114`–`0120` (`roadmap.md`). This spec ships documents and a placeholder
  configuration template only.
- **No real data, firm schemas, real query text, counterparty names, or
  positions in this repository.** The repo is a public scaffold. Real query
  repositories, connection profiles, and semantic mappings live in a
  gitignored adopter-local `sfmeridian.yml` and adopter-controlled
  storage (same rule as `role_context.yml` and `model_plugins.yml`).
- **No writes to any lending, trading, or books-and-records system.** The
  plugin is read-only analytics and decision support; it does not book loans,
  send recalls, reprice, allocate inventory, or submit regulatory reports.
- **No model fine-tuning in the first release.** "Learning" means indexed
  retrieval, structure extraction, and reviewed promotion of new exemplars;
  fine-tuning is a deferred option (`roadmap.md`, Phase 6) gated on evaluation
  evidence.
- **Not legal or regulatory advice.** Reg SHO, SFTR, and SEC Rule 10c-1a are
  named as context; interpretation and dates belong to adopter counsel.
- **No vendor selection.** Third-party securities-finance data vendors are
  named as source *types*; choosing and licensing one is an adopter decision.
- **No replacement of existing agents or runtimes.** `0023`/`0028`/`0063`/
  `0066` stay authoritative for their mechanics, and `0080`/`0081` stay
  authoritative for governed-metric answering and domain-pack semantics; the
  plugin calls them and proposes pack amendments through `0081`'s review flow.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The SDK shall define the plugin boundary: a single distributable (`sfmeridian`) with a versioned tool contract (named tools, JSON-schema inputs/outputs, error codes) that is the only interface apps depend on. | must |
| REQ-002 | The tool contract shall be exposed through three surfaces with identical semantics: an importable Python API, an MCP server conforming to the `0052` adapter contract, and a Claude Code plugin (skills plus MCP configuration) packaged with `0110`'s plugin tooling. | must |
| REQ-003 | The plugin shall be configured by one declarative file (`sfmeridian.yml`) with a published schema, layered resolution (defaults → file → environment overrides → per-call overrides limited to an allowlist), and a validate-only mode; a tracked template contains placeholders only and the real file is gitignored. | must |
| REQ-004 | The configuration shall declare one or more **query repositories**, each with: kind (`git`, `local`, `object_store`), location, ref/branch or snapshot, include/exclude paths, SQL dialect, metadata convention, trust tier, and review policy. No repository location is hard-coded anywhere in the plugin. | must |
| REQ-005 | The SDK shall define a **query metadata convention** (front-matter in a leading SQL comment block, or a sidecar file) carrying at least: stable ID, title, intent description, owner, dialect, target database profile, parameters with types, referenced tables, point-in-time columns, grain, review status, and tags; files without metadata are indexable but marked `unreviewed`. | must |
| REQ-006 | The plugin shall **learn from the query repository** by indexing it into: retrievable exemplars (intent ↔ SQL), an observed join graph (table pairs and join keys), metric definitions (named expressions), common filters, and parameter templates; every derived artifact cites the source file, commit/snapshot, and line span. | must |
| REQ-007 | The plugin shall maintain a **schema catalog snapshot** per database profile (tables, columns, types, keys, row-count estimates, comments) obtained by read-only introspection or a declared catalog file, versioned and dated, and shall reconcile it against identifiers referenced by the query repository. | must |
| REQ-008 | The plugin shall provide a **semantic mapping**, seeded from the `0081` `securities_financing_prime` pack (REQ-025), from canonical securities-lending concepts (from `0063`: e.g. on-loan quantity, lendable quantity, utilization, fee rate, rebate rate, loan balance, collateral value, margin, recall quantity) to physical columns and expressions per database profile, reusing the `0008` metrics semantic layer rules (defined once, period-consistent, ratio metrics over the same rows). | must |
| REQ-009 | For questions the governed tier (REQ-023) cannot answer, the plugin shall compose SQL **retrieval-first**: prefer a reviewed exemplar (parameterized), then adapt a reviewed exemplar, and only then generate new SQL constrained to the catalog snapshot and semantic mapping; every composed query records which path produced it and which exemplars it drew on. | must |
| REQ-010 | The plugin shall **statically verify** every query before execution: single read-only statement, every table/column resolves in the catalog snapshot, joins use declared or observed keys, parameters are bound (no string interpolation), required point-in-time predicates are present for as-of questions, a row limit and timeout apply, and an optional `EXPLAIN` cost check passes. A query that fails verification is never executed. | must |
| REQ-011 | The plugin shall execute only through a read-only execution seam (wrapping `0023`'s `SQLDataSource` or an adopter driver) and return results with provenance: query ID or hash, composition path, database profile, catalog snapshot version, as-of, parameters, row count, and run ID in the `0070` envelope. | must |
| REQ-012 | The plugin shall enforce a **grounding contract** on every answer: each quantitative claim cites a result (run ID, column, row selector); each domain term resolves to a `0063` record or the plugin glossary; derived numbers are recomputed deterministically in tools, not by the language model; unsupported claims are removed or the answer abstains with the reason and the missing evidence. The check shall reuse and extend `0080`'s narrative grounding validator, not re-implement it. | must |
| REQ-013 | The plugin shall apply `0063` viewpoint and sign conventions (borrower vs lender, fee vs rebate, stock-loan specialness vs repo specialness, ACT/360 accrual per `0066`) and shall reject an answer that mixes viewpoints without an explicit conversion. | must |
| REQ-014 | The plugin shall support a **reviewed feedback loop**: accepted answers, user corrections, and newly composed queries can be proposed as candidate exemplars to a staging inbox (the `0049` propose/stage/promote pattern); only a human promotion changes the review status used for retrieval. | must |
| REQ-015 | The SDK shall publish an agent roster and coverage matrix that reuses existing agents (`securities_lending`, `financing_cost_analysis`, `collateral_management`, `repo_financing`, `sql-integration-agent`, `data_ingestion/database_connectivity`, `knowledge/knowledge_retrieval`, `data_quality`, `quality-guard-agent`, `provenance/lineage_capture`, `risk`, `workflow_orchestrator`) and proposes new agents only where a coverage row shows a workflow no existing agent holds; each proposed agent has a never-boundary and a creating child spec. | must |
| REQ-016 | The SDK shall define a **hallucination evaluation protocol**: a versioned golden-question set over a synthetic securities-lending database, metrics (identifier-fabrication rate, execution accuracy, result-match accuracy, unsupported-claim rate, viewpoint-error rate, abstention precision/recall, exemplar-reuse rate), and release thresholds that gate every plugin release. | must |
| REQ-017 | The plugin shall enforce access and data-handling controls: database credentials only via `secrets_management` pointers, per-profile allowlists of schemas/tables, column-level redaction classes (counterparty identity, account, client positions), and `0052`/`0058` caller clearance on retrieval and results. | must |
| REQ-018 | The SDK shall publish an ordered child-spec roadmap (`0114`–`0120`) with scope, dependencies, the coverage rows each closes, and phase exit criteria (`roadmap.md`). | must |
| REQ-019 | The SDK shall define canonical workflows at charter level: ad-hoc desk question → cited answer; daily utilization and specials monitor; recall and buy-in risk review; lending revenue attribution; short-side borrow-cost feed into `financing_cost_analysis`/backtests; and query-repository onboarding. | should |
| REQ-020 | The plugin shall support **multiple database profiles and dialects** (SQLite for offline tests; PostgreSQL, Oracle, and Databricks SQL as the first adopter targets; SQL Server and Snowflake later) behind one interface, with dialect differences resolved in configuration and the execution seam, not in agents. | should |
| REQ-021 | The plugin shall **hand off, not re-implement**, specialist work to existing agents in five groups — optimization (`optimization/`), risk (`risk`, `enterprise_risk/`), portfolio management (`portfolio_management/`), knowledge (`knowledge/`), and machine learning (`machine_learning/`) — through declared handoff contracts naming the trigger, the plugin evidence passed (run IDs, point-in-time panels, citations), the expected output, and the agent's never-boundary; no new plugin agent may hold a workflow one of these agents already holds. | must |
| REQ-023 | The plugin shall answer **governed-first**: it shall pass each question to `0080` (`answer()` with the configured interpreter, `0081` pack selection, and caller clearance) before any SQL composition. It shall fall through to the reviewed-query tiers only when `0080` reports that the question references no governed metric or dimension; when `0080` returns a clarification among governed candidates, the plugin shall return that clarification and shall not fall through. Every answer records its tier: `governed`, `reuse`, `adapt`, or `generate`. | must |
| REQ-024 | The plugin shall supply `0080`'s read-only `Reader`: each governed metric's base measures are bound in configuration to a reviewed **metric source query** from the query repository, run through `sql.verify`/`sql.execute` with the plan's as-of and filters bound as parameters, and returned as `0008` `Fact` rows with provenance; a metric whose source query is missing, unreviewed, or drifted is unavailable to the governed tier, never silently served. | must |
| REQ-025 | The concept vocabulary shall be **seeded from `0081`'s `securities_financing_prime` pack** (metrics, dimensions, units, additivity, conventions, insight-suppression rules), resolved through `0081`'s `resolve_packs` so adopter-local pack overlays apply. Concepts the pack lacks (for example rebate rate, lendable value, on-loan quantity, recall quantity, collateral value, days-to-cover) shall be proposed as pack amendments through `0081`'s review flow, never defined privately in the plugin; answers that use an unreviewed pack carry `0080`'s unreviewed-pack caveat. | must |
| REQ-026 | `0080` insight write-back shall be **disabled by default** in the plugin; enabling it requires explicit configuration, `0080`'s write-back contract and approval rules, and reviewed packs (`0080` REQ-016), and its target may never be a lending, trading, or books-and-records system. | must |
| REQ-027 | SFMeridian shall keep a governed **third-party tooling catalog** (`tooling_catalog.md`, machine-readable form in `0114`) listing every library a component may depend on or an agent may recommend, each with ring (`adopt`/`trial`/`assess`/`hold`/`exclude`), SFMeridian use, owning component or agent, extra, license, maintenance and supply-chain review, and reviewer. Community curated lists are discovery inputs only; no library is depended on or recommended without an admission review, and an agent never recommends a package absent from the catalog. | must |
| REQ-028 | Every SFMeridian agent shall be a **loop agent**, not only contract files: a versioned manifest (goal, least-privilege tool grant, verifiers, step and tool-call budgets, repair limit, human checkpoints, never-boundary) run by a shared loop harness that plans, calls tools, observes, verifies, and repeats; refuses tools outside the manifest and every `human_only` tool; ends as `completed` only after its verifiers pass (feeding failures back for repair), otherwise `escalated`, `budget_exhausted`, `denied`, or `failed`; and records a deterministic trace the `0070` run envelope can carry. Policies are pluggable: a deterministic policy runs offline; a model policy wraps a caller-injected completion function (the `adapters/llm_runtime/` contract). | must |
| REQ-029 | Agents and apps shall share **one tool registry**: every capability is a named tool with a JSON-Schema input and a declared effect (`read`, `index`, `propose`, `human_only`, and in later children `execute_read`); there is no agent-only back door, and decisions reserved for people (promotion, discard, approval) are `human_only` tools no manifest can grant. | must |
| REQ-022 | Every optimization or ML output that reaches a plugin answer shall stay **decision support**: optimizers return proposed allocations with solver diagnostics and sensitivities (via `solver_diagnostics_sensitivity`), and models return forecasts or scores with a baseline, an interval or calibration, and a point-in-time feature attestation; neither books, recalls, reprices, or trades. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Offline determinism | Indexing, verification, and the evaluation harness run offline against the synthetic SQLite database and produce identical output on repeat runs given the same config, query snapshot, and catalog snapshot. |
| NFR-002 | Hallucination thresholds | Release gate on the golden set: identifier-fabrication rate in executed SQL = 0; unsupported-claim rate ≤ 1%; viewpoint-error rate = 0; execution accuracy ≥ 90%; abstention recall on unanswerable questions ≥ 95%. Thresholds are configuration, versioned with the golden set. |
| NFR-003 | Portability | The plugin's core imports only the standard library, declared optional extras (database drivers, SQL parser, embeddings), and a SemVer-pinned `quantsmith` dependency limited to its stdlib-only governed-analytics modules (`nl_analytics`, `pipelines.metrics_semantic_layer`, `pipelines.analytics_packs`, and what they import); everything else in the SDK is reached only through documented adapters. |
| NFR-004 | Safety | Zero write, DDL, or multi-statement queries reach a database; every query has a row limit and timeout; credentials never appear in logs, results, traces, or the index. |
| NFR-005 | Latency and cost | Interactive answer p95 ≤ 15 s excluding database execution time; query-repository re-index is incremental (changed files only); warehouse cost guard via configurable `EXPLAIN` limits. |
| NFR-006 | Data provenance | Every repo-tracked example, fixture, and golden question is synthetic and disclosed per `0025`; no real entity, counterparty, CUSIP/ISIN tied to a real position, or firm query appears in the repository. |
| NFR-007 | Compatibility | The tool contract follows SemVer per `0047`; breaking changes bump the major version and ship a migration note; the config schema carries `schema_version`. |
| NFR-008 | Reversibility | Removing the plugin is deleting its package, its config, and its doc sections; it modifies no existing agent's behaviour or runtime. |
| NFR-009 | Catalog consistency | `hooks/stages/run-stage.sh spec`, spec-index, handoff-sync, agent-catalog, and skills-export gates pass. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given the plan, when read, then it names one distributable, lists every tool with input/output schema and error codes, and states that apps depend only on that contract. | REQ-001, NFR-003 |
| AC-002 | Given the same tool call, when issued through the Python API, the MCP server, and the Claude Code plugin against the synthetic database, then the results and provenance records are identical. | REQ-002 |
| AC-003 | Given a config that omits a required field, sets an unknown key, or overrides a non-allowlisted field per call, when validated, then validation fails with a named error; and a valid config resolves deterministically through the layer order. | REQ-003 |
| AC-004 | Given two query repositories (one `local`, one `git` at a pinned ref) declared only in configuration, when the plugin indexes, then both are indexed, each exemplar records its repository, ref, and path, and a code search finds no hard-coded repository location. | REQ-004 |
| AC-005 | Given a SQL file with valid front-matter, one with malformed front-matter, and one with none, when indexed, then the first is indexed with all fields, the second is rejected with a reason, and the third is indexed as `unreviewed`. | REQ-005 |
| AC-006 | Given the synthetic query repository, when indexed, then the join graph, metric definitions, and parameter templates match the expected golden extraction, and every derived artifact cites file, snapshot, and line span. | REQ-006 |
| AC-007 | Given a catalog snapshot and a query repository that references a dropped column, when reconciled, then the drift is reported with the affected exemplars and those exemplars are excluded from retrieval until re-reviewed. | REQ-007 |
| AC-008 | Given the semantic mapping, when utilization is requested by day and by counterparty, then it is computed as one governed ratio over the same rows and the by-counterparty slices reconcile with the total under the `0008` rules. | REQ-008 |
| AC-009 | Given a question matching a reviewed exemplar, when composed, then the exemplar is used with bound parameters and the record shows path `reuse`; given a novel question, then the record shows path `generate` and lists the catalog objects and exemplars it drew on. | REQ-009 |
| AC-010 | Given composed queries containing an invented column, a `DELETE`, two statements, an interpolated literal from user input, and an as-of question without a point-in-time predicate, when verified, then each is rejected with a specific code and none is executed. | REQ-010, NFR-004 |
| AC-011 | Given an executed query, when its result is returned, then it carries query ID/hash, path, profile, catalog version, as-of, parameters, row count, and a `0070` run ID, and replaying the run reproduces the result on the synthetic database. | REQ-011, NFR-001 |
| AC-012 | Given a draft answer containing one uncited number, one number that disagrees with its cited cell, and one undefined term, when grounding-checked, then all three are flagged and the final answer either removes them or abstains with the missing evidence named. | REQ-012 |
| AC-013 | Given a golden case where a lender-view fee is presented as a borrower-view rebate, when checked, then the answer is rejected as a viewpoint error citing the `0063` convention. | REQ-013 |
| AC-014 | Given a user correction, when proposed, then a candidate exemplar appears in the staging inbox with provenance, is not used for retrieval, and becomes retrievable only after a recorded human promotion. | REQ-014 |
| AC-015 | Given the coverage matrix, when validated, then every proposed agent has a distinct workflow, a never-boundary, and a creating child spec; no proposed agent duplicates a workflow an existing agent holds; and every reused agent is named with its role. | REQ-015 |
| AC-016 | Given the golden-question set and thresholds, when the evaluation harness runs on the synthetic database, then every metric in REQ-016 is reported and a release is blocked when any NFR-002 threshold is missed. | REQ-016, NFR-002 |
| AC-017 | Given a caller without clearance for counterparty identity, when an answer depends on a counterparty-level result, then counterparty identifiers are redacted or the answer is withheld, and no credential appears in any log, trace, or index artifact. | REQ-017, NFR-004 |
| AC-018 | Given `roadmap.md` and `specs/README.md`, when read, then `0114`–`0120` are reserved with scope, dependency, closed coverage rows, and phase exit criteria. | REQ-018 |
| AC-019 | Given the workflow charters, when read, then each of the six REQ-019 workflows names its agents, tools, inputs, outputs, review gate, and the evidence it must cite. | REQ-019 |
| AC-020 | Given the same golden questions against SQLite and the PostgreSQL, Oracle, and Databricks SQL dialect fixtures, when run, then dialect differences are handled by configuration and the execution seam, and no agent prompt or tool contract changes. | REQ-020 |
| AC-021 | Given the plan, when read, then latency/cost budgets, incremental re-indexing, and the `EXPLAIN` cost guard are specified with configurable limits. | NFR-005 |
| AC-022 | Given a repo-wide scan, when examples, fixtures, and golden questions are searched, then every record is flagged synthetic per `0025` and none references a real counterparty, position, or firm query. | NFR-006 |
| AC-023 | Given the tool contract and config schema, when inspected, then both carry versions, and the plan states the SemVer and migration-note rules. | NFR-007 |
| AC-025 | Given the handoff map in `plan.md`, when validated, then every listed optimization, risk, portfolio-management, knowledge, and ML agent exists in `agents/`, has a trigger, inputs, outputs, and never-boundary, and appears in at least one canonical workflow; and no proposed plugin agent's workflow duplicates one of them. | REQ-021 |
| AC-026 | Given an optimizer result and a model forecast returned through a plugin answer, when inspected, then the optimizer result carries solver status, diagnostics, and sensitivities, the forecast carries a baseline comparison, an interval or calibration, and a PIT feature attestation, and neither output is phrased as an executed action. | REQ-022 |
| AC-027 | Given three golden questions — one that maps to a governed metric, one that names no governed metric, and one ambiguous between two governed metrics — when asked, then the first is answered at tier `governed` with no SQL composed, the second falls through to `reuse`/`adapt`/`generate`, and the third returns `0080`'s clarification with no fall-through. | REQ-023 |
| AC-028 | Given governed metrics bound to reviewed metric source queries, when `0080` executes a plan through the plugin's `Reader`, then the `Fact` rows reproduce the source queries' totals for the plan's as-of and filters, every row batch carries run provenance, and a metric bound to an unreviewed or drifted source query is reported unavailable. | REQ-024 |
| AC-029 | Given the resolved pack catalog, when the semantic mapping is validated, then all five `securities_financing_prime` metrics are present with the pack's units and additivity, each concept the pack lacks appears only as a proposed pack amendment (not a plugin-private definition), and an answer built on the draft pack carries the unreviewed-pack caveat. | REQ-025, REQ-008 |
| AC-030 | Given the default configuration, when a request asks to publish insights, then write-back is refused with a stated reason; and a configuration naming a lending or books-and-records target is rejected by validation. | REQ-026 |
| AC-031 | Given the tooling catalog, when validated, then every `adopt`/`trial` entry names an SFMeridian component or agent, an optional extra, and a completed admission review (license, maintenance, pinned hash, advisory scan); no core module imports a non-stdlib library; and an agent answer recommending a package not in the catalog is rejected by the grounding check. | REQ-027, NFR-003 |
| AC-032 | Given a loop agent and its manifest, when its policy calls a tool outside the grant or a `human_only` tool, exceeds a budget, or finishes with a failing verifier, then the run is `denied`, `budget_exhausted`, or repaired and re-verified (and `failed` after the repair limit), never `completed`; and a passing run's trace and run ID are identical on replay. | REQ-028 |
| AC-033 | Given the tool registry, when listed through the Python API and called by an agent, then both see the same tools, schemas, and effects; an input violating a schema is refused before the handler runs; and no manifest validates while granting a `human_only` tool. | REQ-029 |
| AC-024 | Given the full repository after this spec lands, when `run-stage.sh spec`, spec-index, handoff-sync, agent-catalog, and skills-export run, then they pass with no new findings, and the diff modifies no existing agent's behaviour or runtime. | NFR-008, NFR-009 |

## Data & Dependencies

- **Reuses (not redefines):** `0063` taxonomy, viewpoints, conventions,
  lifecycles, golden cases; `0066` accrual and classification corrections;
  `0023` runtime and `sql_data.py` execution seam and synthetic database;
  `0028` financing cost analysis; `0008` metrics semantic layer; `0049`
  propose/stage/promote write path; `0052`–`0054` MCP adapter contract and
  access tiers; `0058` viewer access control; `0070` run envelope, assumption
  ledger, replay; `0071` LLM evidence boundary and embeddings seam; `0102`
  lineage; `0110` plugin packaging; `0067` collateral/margin optimizer
  contract and `0026` model plugins (adopter-owned optimizers); `0013`
  optimization solvers; `0082` enterprise-risk agents; `0006`/`0046`
  forecasting folds and walk-forward harness (borrow-demand models); `0047` downstream SemVer contract; `0025`
  synthetic-data disclosure; `0027` source catalog; `0080` natural-language
  analytics (`answer()`, interpreter seam, `Reader`, grounding validator) and
  `0081` domain packs (`securities_financing_prime`, `resolve_packs`, review flow); `adapters/data_access/sql.md`
  and `adapters/llm_runtime/`.
- **Data domains the semantic mapping must cover** (physical tables are
  adopter-specific): loan book / open loans and returns; lendable inventory
  and availability; fee, rebate, and indicative rates; collateral (cash and
  non-cash), marks, and margin; counterparties, limits, and credit; recalls,
  buy-ins, and fails; corporate actions and manufactured payments; program
  revenue and agent/beneficial-owner splits; third-party securities-finance
  market data (utilization, days-to-cover, indicative fee, demand/supply).
- **Regulatory context named for adopter counsel:** Reg SHO locate and
  close-out; EU/UK SFTR transaction reporting; SEC Rule 10c-1a securities
  lending reporting to FINRA (compliance dates `unverified` here — confirm
  with counsel). The plugin may support completeness checks later (`0120`);
  it never submits reports.
- **Access:** repository content is public. Query text, schemas, and results
  are adopter data and live only in the gitignored config's referenced
  locations and adopter-controlled storage.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | Model invents tables, columns, or join keys. | Wrong numbers presented confidently. | REQ-010 catalog resolution and join-key verification; fabrication rate gated at 0 (NFR-002). |
| RISK-002 | Fee/rebate or borrower/lender viewpoint confusion. | Revenue or cost misstated in sign or magnitude. | REQ-013 `0063` viewpoint enforcement; golden viewpoint cases; viewpoint-error rate gated at 0. |
| RISK-003 | As-of question answered from a latest snapshot (look-ahead), or a backtest consumes today's borrow cost. | Leakage into signals and backtests. | REQ-010 required point-in-time predicates; `instructions/point_in_time.md`; `leakage` gate on downstream consumers. |
| RISK-004 | Query repository contains stale, wrong, or unreviewed SQL that the plugin then "learns". | Errors laundered as institutional knowledge. | REQ-005 review status; REQ-007 drift exclusion; default retrieval uses `reviewed` only; REQ-014 human promotion. |
| RISK-005 | Prompt injection through query comments, column comments, or result text. | Tool misuse or data exfiltration. | Comments and results treated as data; verifier is deterministic and model-independent; red-team cases in the golden set (coordinates with `0103`). |
| RISK-006 | Sensitive counterparty, client, or position data leaks through answers, logs, or the index. | Confidentiality and regulatory breach. | REQ-017 redaction classes, clearance, allowlists; index stores identifiers and SQL, not result rows; secret-scan gate. |
| RISK-007 | Expensive or runaway warehouse queries. | Cost incidents, contention with production. | Row limits, timeouts, `EXPLAIN` cost guard, `0101`-style concurrency limits per profile. |
| RISK-008 | Plugin API churn breaks downstream apps. | Integration breakage. | NFR-007 SemVer, contract tests in `0118`, deprecation window. |
| RISK-009 | Agent roster grows to fill the map. | Overlapping charters and review noise. | REQ-015 coverage gating; roster capped at the rows in `plan.md`. |
| RISK-011 | Demand, specials, or recall models leak future borrow data or overfit short histories, or an optimizer's proposed allocation is read as an instruction. | False signals; unreviewed inventory or pricing actions. | REQ-022; `problem_framing_labeling` and `model_selection_validation` own labels and purged validation; `feature_store_engineering` enforces PIT features; `solver_diagnostics_sensitivity` reviews every solve; outputs labelled decision support. |
| RISK-012 | The governed tier and a reviewed query disagree on the same number (e.g. utilization computed two ways). | Contradictory answers erode trust. | Tier-agreement check in the golden set: governed questions are also answered through the reuse tier and must match; a disagreement flags the exemplar or the binding for review. |
| RISK-013 | `0080` and `0081` are still Draft; their interfaces may change, and every pack is unreviewed. | Plugin breakage; caveated answers indefinitely. | Pin the `quantsmith` version (`0047`); isolate the dependency in one `governed/` adapter with contract tests; make naming the pack reviewer a Phase 0 exit criterion. |
| RISK-014 | A third-party library is abandoned, relicensed, typosquatted, or compromised, or an agent recommends a package that does not exist. | Supply-chain compromise; license exposure; broken installs. | REQ-027 admission rules; pinned hashes; optional extras only; catalog-only recommendations checked by grounding; periodic re-review. |
| RISK-010 | Evaluation set is too easy or drifts from real usage. | False confidence in hallucination metrics. | Versioned golden set with unanswerable and adversarial questions; adopter-local private golden set overlay; periodic refresh from promoted feedback. |

## Assumptions & Open Questions

- Assumption: the adopter has (or will assemble) a query repository in Git or
  a shared directory, and analysts are willing to add front-matter to their most
  used queries; un-annotated files still index as `unreviewed`.
- Assumption: databases are reachable read-only from where the plugin runs,
  through a service account managed by the adopter's secret store.
- Assumption: an LLM runtime is available through `adapters/llm_runtime/`;
  the verifier, executor, and grounding checks do not depend on which model.
**Resolved 2026-10-22 (owner decisions, recorded at approval):**

- Viewpoint: the first deployment serves the **agency lender / beneficial
  owner**. Default concept viewpoints are `lender`/`beneficial_owner`; fees are
  income; `lending_revenue_analyst` (C-08) is the first `0119` agent, then
  `utilization_specials_analyst` (C-06), then `recall_buyin_risk_analyst` (C-07).
- Dialects: the first adopter targets are **PostgreSQL, Oracle, and Databricks
  SQL** (REQ-020). SQLite stays the offline test fixture; SQL Server and
  Snowflake move to later.
- Retrieval: **lexical (BM25) only** for now; embeddings remain an optional
  extra, enabled only if the golden set shows a retrieval gap.
- Order: `0119` analytics before `0120` reporting checks (as `roadmap.md`
  assumes), unless an adopter reporting deadline reorders them.
- Pack reviewer: Joshua Lutkemuller, CFA reviews the `0081`
  `securities_financing_prime` pack and its proposed amendments; the review
  itself is pending (the pack stays `draft`).
- Build order: `0115` then `0116` (`0114`, `0115`, and `0121` are built; current
  state and the pickup point are in `handoff.md`).

**Still open:**

- Who is the named domain owner who will review the `0081`
  `securities_financing_prime` pack (and its proposed amendments)? Until
  then every governed answer carries the unreviewed-pack caveat and
  write-back stays refused. Needed before `0115` is approved, not before
  `0114`.

## Exceptions

None.
