# Spec: Securities Lending Intelligence Plugin (Foundation)

- **ID:** 0113-seclending-intelligence-plugin
- **Status:** Draft
- **Author:** Joshua Lutkemuller, CFA
- **Approver:**
- **Last updated:** 2026-10-22

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
- **Apps down the road** (a desk chatbot, a Slack assistant, a BI copilot, a
  batch report) need one stable interface, not a QuantSmith checkout.

## Goals

- Define a **self-contained, versioned plugin** (`quantsmith-seclending`)
  with one tool contract exposed through three surfaces: a Python API, an MCP
  server, and a Claude Code plugin — usable by an app without the rest of the
  SDK.
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
  coverage row justifies, and route to existing agents everywhere else.

## Non-Goals

- **No runtimes, tools, or new agents in this spec.** They are created by
  `0114`–`0120` (`roadmap.md`). This spec ships documents and a placeholder
  configuration template only.
- **No real data, firm schemas, real query text, counterparty names, or
  positions in this repository.** The repo is a public scaffold. Real query
  repositories, connection profiles, and semantic mappings live in a
  gitignored adopter-local `seclending_plugin.yml` and adopter-controlled
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
  `0066` stay authoritative for their mechanics; the plugin calls them.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The SDK shall define the plugin boundary: a single distributable (`quantsmith-seclending`) with a versioned tool contract (named tools, JSON-schema inputs/outputs, error codes) that is the only interface apps depend on. | must |
| REQ-002 | The tool contract shall be exposed through three surfaces with identical semantics: an importable Python API, an MCP server conforming to the `0052` adapter contract, and a Claude Code plugin (skills plus MCP configuration) packaged with `0110`'s plugin tooling. | must |
| REQ-003 | The plugin shall be configured by one declarative file (`seclending_plugin.yml`) with a published schema, layered resolution (defaults → file → environment overrides → per-call overrides limited to an allowlist), and a validate-only mode; a tracked template contains placeholders only and the real file is gitignored. | must |
| REQ-004 | The configuration shall declare one or more **query repositories**, each with: kind (`git`, `local`, `object_store`), location, ref/branch or snapshot, include/exclude paths, SQL dialect, metadata convention, trust tier, and review policy. No repository location is hard-coded anywhere in the plugin. | must |
| REQ-005 | The SDK shall define a **query metadata convention** (front-matter in a leading SQL comment block, or a sidecar file) carrying at least: stable ID, title, intent description, owner, dialect, target database profile, parameters with types, referenced tables, point-in-time columns, grain, review status, and tags; files without metadata are indexable but marked `unreviewed`. | must |
| REQ-006 | The plugin shall **learn from the query repository** by indexing it into: retrievable exemplars (intent ↔ SQL), an observed join graph (table pairs and join keys), metric definitions (named expressions), common filters, and parameter templates; every derived artifact cites the source file, commit/snapshot, and line span. | must |
| REQ-007 | The plugin shall maintain a **schema catalog snapshot** per database profile (tables, columns, types, keys, row-count estimates, comments) obtained by read-only introspection or a declared catalog file, versioned and dated, and shall reconcile it against identifiers referenced by the query repository. | must |
| REQ-008 | The plugin shall provide a **semantic mapping** from canonical securities-lending concepts (from `0063`: e.g. on-loan quantity, lendable quantity, utilization, fee rate, rebate rate, loan balance, collateral value, margin, recall quantity) to physical columns and expressions per database profile, reusing the `0008` metrics semantic layer rules (defined once, period-consistent, ratio metrics over the same rows). | must |
| REQ-009 | The plugin shall compose SQL **retrieval-first**: prefer a reviewed exemplar (parameterized), then adapt a reviewed exemplar, and only then generate new SQL constrained to the catalog snapshot and semantic mapping; every composed query records which path produced it and which exemplars it drew on. | must |
| REQ-010 | The plugin shall **statically verify** every query before execution: single read-only statement, every table/column resolves in the catalog snapshot, joins use declared or observed keys, parameters are bound (no string interpolation), required point-in-time predicates are present for as-of questions, a row limit and timeout apply, and an optional `EXPLAIN` cost check passes. A query that fails verification is never executed. | must |
| REQ-011 | The plugin shall execute only through a read-only execution seam (wrapping `0023`'s `SQLDataSource` or an adopter driver) and return results with provenance: query ID or hash, composition path, database profile, catalog snapshot version, as-of, parameters, row count, and run ID in the `0070` envelope. | must |
| REQ-012 | The plugin shall enforce a **grounding contract** on every answer: each quantitative claim cites a result (run ID, column, row selector); each domain term resolves to a `0063` record or the plugin glossary; derived numbers are recomputed deterministically in tools, not by the language model; unsupported claims are removed or the answer abstains with the reason and the missing evidence. | must |
| REQ-013 | The plugin shall apply `0063` viewpoint and sign conventions (borrower vs lender, fee vs rebate, stock-loan specialness vs repo specialness, ACT/360 accrual per `0066`) and shall reject an answer that mixes viewpoints without an explicit conversion. | must |
| REQ-014 | The plugin shall support a **reviewed feedback loop**: accepted answers, user corrections, and newly composed queries can be proposed as candidate exemplars to a staging inbox (the `0049` propose/stage/promote pattern); only a human promotion changes the review status used for retrieval. | must |
| REQ-015 | The SDK shall publish an agent roster and coverage matrix that reuses existing agents (`securities_lending`, `financing_cost_analysis`, `collateral_management`, `repo_financing`, `sql-integration-agent`, `data_ingestion/database_connectivity`, `knowledge/knowledge_retrieval`, `data_quality`, `quality-guard-agent`, `provenance/lineage_capture`, `risk`, `workflow_orchestrator`) and proposes new agents only where a coverage row shows a workflow no existing agent holds; each proposed agent has a never-boundary and a creating child spec. | must |
| REQ-016 | The SDK shall define a **hallucination evaluation protocol**: a versioned golden-question set over a synthetic securities-lending database, metrics (identifier-fabrication rate, execution accuracy, result-match accuracy, unsupported-claim rate, viewpoint-error rate, abstention precision/recall, exemplar-reuse rate), and release thresholds that gate every plugin release. | must |
| REQ-017 | The plugin shall enforce access and data-handling controls: database credentials only via `secrets_management` pointers, per-profile allowlists of schemas/tables, column-level redaction classes (counterparty identity, account, client positions), and `0052`/`0058` caller clearance on retrieval and results. | must |
| REQ-018 | The SDK shall publish an ordered child-spec roadmap (`0114`–`0120`) with scope, dependencies, the coverage rows each closes, and phase exit criteria (`roadmap.md`). | must |
| REQ-019 | The SDK shall define canonical workflows at charter level: ad-hoc desk question → cited answer; daily utilization and specials monitor; recall and buy-in risk review; lending revenue attribution; short-side borrow-cost feed into `financing_cost_analysis`/backtests; and query-repository onboarding. | should |
| REQ-020 | The plugin shall support **multiple database profiles and dialects** (at least SQLite for tests, PostgreSQL, SQL Server, Snowflake) behind one interface, with dialect differences resolved in configuration and the execution seam, not in agents. | should |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Offline determinism | Indexing, verification, and the evaluation harness run offline against the synthetic SQLite database and produce identical output on repeat runs given the same config, query snapshot, and catalog snapshot. |
| NFR-002 | Hallucination thresholds | Release gate on the golden set: identifier-fabrication rate in executed SQL = 0; unsupported-claim rate ≤ 1%; viewpoint-error rate = 0; execution accuracy ≥ 90%; abstention recall on unanswerable questions ≥ 95%. Thresholds are configuration, versioned with the golden set. |
| NFR-003 | Portability | The plugin's core imports only the standard library plus declared optional extras (database drivers, SQL parser, embeddings); it does not import QuantSmith modules outside its own package at runtime, except through the documented adapters it bundles. |
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
| AC-020 | Given the same golden questions against SQLite and one other configured dialect fixture, when run, then dialect differences are handled by configuration and the execution seam, and no agent prompt or tool contract changes. | REQ-020 |
| AC-021 | Given the plan, when read, then latency/cost budgets, incremental re-indexing, and the `EXPLAIN` cost guard are specified with configurable limits. | NFR-005 |
| AC-022 | Given a repo-wide scan, when examples, fixtures, and golden questions are searched, then every record is flagged synthetic per `0025` and none references a real counterparty, position, or firm query. | NFR-006 |
| AC-023 | Given the tool contract and config schema, when inspected, then both carry versions, and the plan states the SemVer and migration-note rules. | NFR-007 |
| AC-024 | Given the full repository after this spec lands, when `run-stage.sh spec`, spec-index, handoff-sync, agent-catalog, and skills-export run, then they pass with no new findings, and the diff modifies no existing agent's behaviour or runtime. | NFR-008, NFR-009 |

## Data & Dependencies

- **Reuses (not redefines):** `0063` taxonomy, viewpoints, conventions,
  lifecycles, golden cases; `0066` accrual and classification corrections;
  `0023` runtime and `sql_data.py` execution seam and synthetic database;
  `0028` financing cost analysis; `0008` metrics semantic layer; `0049`
  propose/stage/promote write path; `0052`–`0054` MCP adapter contract and
  access tiers; `0058` viewer access control; `0070` run envelope, assumption
  ledger, replay; `0071` LLM evidence boundary and embeddings seam; `0102`
  lineage; `0110` plugin packaging; `0047` downstream SemVer contract; `0025`
  synthetic-data disclosure; `0027` source catalog; `adapters/data_access/sql.md`
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
| RISK-010 | Evaluation set is too easy or drifts from real usage. | False confidence in hallucination metrics. | Versioned golden set with unanswerable and adversarial questions; adopter-local private golden set overlay; periodic refresh from promoted feedback. |

## Assumptions & Open Questions

- Assumption: the adopter has (or will assemble) a query repository in Git or
  a shared directory, and analysts are willing to add front-matter to their most
  used queries; un-annotated files still index as `unreviewed`.
- Assumption: databases are reachable read-only from where the plugin runs,
  through a service account managed by the adopter's secret store.
- Assumption: an LLM runtime is available through `adapters/llm_runtime/`;
  the verifier, executor, and grounding checks do not depend on which model.
- Open question: primary viewpoint for the first deployment — agency lender /
  beneficial owner, prime broker, or short-side borrower? Affects default
  semantic mappings and which analytics agent (`0119`) is built first.
- Open question: which non-SQLite dialect is the first adopter target
  (PostgreSQL, SQL Server, or Snowflake)?
- Open question: is an embedding model permitted in the adopter environment,
  or must retrieval stay lexical (BM25) only? The design supports both.
- Open question: is `0119`'s analytics work wanted before the regulatory
  completeness checks (`0120`), as `roadmap.md` assumes?

## Exceptions

None.
