# Plan: Securities Lending Intelligence Plugin (Foundation)

- **Spec:** 0113-seclending-intelligence-plugin (`spec.md`)
- **Status:** Draft
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-10-22

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
  │ seclending_plugin.yml → schema validate → layered resolve → frozen Config │
  └────────────────────────────────────────────┼───────────────────────────────┘
                                               ▼
   ask(question, as_of, caller)  ── orchestrator (seclending_orchestrator) ──┐
     1 classify intent + resolve terms ── glossary / 0063 pack (REQ-012/013) │
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
plugins/seclending/
  pyproject.toml                    # distributable: quantsmith-seclending (SemVer, NFR-007)
  src/quantsmith_seclending/
    contract/                       # tool schemas (JSON Schema), error codes, version
    config/                         # schema, loader, layered resolution, validate-only
    repos/                          # git/local/object_store fetchers, pinned refs
    indexing/                       # front-matter, SQL structure extraction, join graph, index
    catalog/                        # introspection, catalog files, snapshots, drift reconcile
    semantic/                       # concept → column mapping on 0008 rules; 0063 glossary bridge
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

The core depends on the standard library only. Optional extras:
`[postgres]`, `[mssql]`, `[snowflake]` (drivers), `[sqlparse]` (a stricter SQL
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
| `queries.search` | Retrieve exemplars | intent text, filters (tags, profile, review status) | ranked exemplars with citations and scores |
| `glossary.lookup` | Resolve a domain term | term | `0063` record or plugin glossary entry, viewpoint |
| `sql.compose` | Compose SQL retrieval-first | question, as_of, profile | SQL, bound params, path (`reuse`/`adapt`/`generate`), sources |
| `sql.verify` | Deterministic static verification | SQL, params, profile, question type | pass/fail with codes, normalized SQL hash |
| `sql.execute` | Read-only execution of a *verified* query | verification token, params | rows (redacted), provenance record |
| `answer.ground` | Check a draft answer against results | draft, run IDs | per-claim verdicts, cleaned answer or abstention |
| `ask` | End-to-end orchestrated answer | question, as_of, caller | answer, citations, run envelope, or abstention |
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
`E_GROUND_UNDEFINED_TERM`, `E_GROUND_VIEWPOINT`, `E_ABSTAIN_INSUFFICIENT_EVIDENCE`.

### Configuration (REQ-003, REQ-004, REQ-017, REQ-020)

Template: `templates/seclending_plugin/seclending_plugin.yml` (placeholders
only). Real file: repo-root `seclending_plugin.yml` (gitignored) or the path in
`QS_SECLENDING_CONFIG`. Top-level sections:

| Section | Holds |
| --- | --- |
| `schema_version` | Config schema version (NFR-007). |
| `query_repositories[]` | `id`, `kind` (`git`/`local`/`object_store`), `uri`, `ref`, `paths.include`/`exclude`, `dialect`, `metadata_convention` (`front_matter`/`sidecar`), `trust_tier`, `review_policy` (`reviewed_only`/`allow_unreviewed_as_hints`), `refresh` (`on_demand`/cron). |
| `databases[]` | `id` (profile), `dialect`, `connection.secret_ref` (pointer, never a value), `read_only: true` (required), `schemas_allowlist`, `tables_allowlist`, `row_limit`, `timeout_s`, `explain_cost_limit`, `max_concurrency`. |
| `catalog` | Per profile: `source` (`introspect`/`file`), `file`, `refresh`, `drift_policy` (`exclude`/`warn`). |
| `semantic_mapping` | Per profile: canonical concept ID (`0063`) → physical expression, grain, PIT column, viewpoint. |
| `grounding` | `retrieval_min_score`, `max_compose_retries`, `require_citation_per_number: true`, `abstain_message`, numeric tolerance. |
| `access` | Redaction classes (`counterparty_identity`, `account`, `client_position`), column → class map, caller clearance source (`0058` roster). |
| `llm` | Runtime profile name resolved through `adapters/llm_runtime/`; temperature and token budgets; no keys. |
| `retrieval` | `lexical` (default) or `lexical+embeddings`; embedding profile via `0071`. |
| `feedback` | Inbox location, promoters (handles), auto-propose on accepted answers (bool). |
| `eval` | Golden set path(s) (repo synthetic + optional adopter-private), thresholds (NFR-002). |
| `per_call_overrides_allowlist` | Fields a caller may override per call (e.g. `as_of`, `row_limit` lower only). |

Resolution order: built-in defaults → file → `QS_SECLENDING__*` environment
variables → per-call overrides (allowlisted, and only in the restrictive
direction for safety fields). The resolved config is frozen and hashed; the
hash is in every run envelope.

### Query metadata convention (REQ-005)

Front-matter in the leading comment block of each `.sql` file (sidecar
`<name>.yml` alternative). Template:
`templates/seclending_plugin/query_front_matter.sql`. Required for `reviewed`:
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
| `data_quality`, `quality-guard-agent` | Data checks on result sets; release gate over the eval report. |
| `provenance/lineage_capture` | Lineage from answer → run → query → repo commit → catalog snapshot. |
| `data_engineering/schema_evolution` | Classifies catalog drift found by reconciliation. |
| `risk`, `backtest_review` | Downstream consumers of borrow cost and recall risk. |
| `workflow_orchestrator` | Drives the SDD flow for each child spec. |

**Proposed new agents** (group folder `agents/securities_financing/seclending_intelligence/`; each created only by its child spec):

| Row | Agent | Distinct workflow | Never does | Child |
| --- | --- | --- | --- | --- |
| C-01 | `query_librarian` | Onboard and index query repositories; front-matter hygiene; dedup; drift triage; review queue for candidates. | Never promotes a candidate or edits query SQL without a named human reviewer. | `0114` |
| C-02 | `semantic_mapping_steward` | Map `0063` concepts to physical columns per profile; declare grain, PIT column, viewpoint, unit. | Never invents a mapping without a catalog object and an exemplar or owner confirmation. | `0115` |
| C-03 | `sql_composer` | Retrieval-first SQL composition (reuse → adapt → generate) under the catalog and mapping. | Never executes SQL and never bypasses `sql.verify`. | `0116` |
| C-04 | `seclending_orchestrator` | Route desk questions through the 11-step pipeline; pick analytics agents; manage retries and abstention. | Never answers from model memory; never returns a number without a run citation. | `0116`/`0117` |
| C-05 | `answer_grounding_reviewer` | Claim-level citation, recompute, term, and viewpoint checks on draft answers. | Never adds new facts; can only cite, correct to the cited value, remove, or abstain. | `0117` |
| C-06 | `utilization_specials_analyst` | Utilization, demand/supply, fee trends, GC→warm→special migration, days-to-cover. | Never forecasts without a stated baseline and interval; never uses non-PIT rates for history. | `0119` |
| C-07 | `recall_buyin_risk_analyst` | Recall pressure (dividends, votes, sales), buy-in and fail exposure on open loans/borrows. | Never sends or recommends sending a recall; outputs risk indicators only. | `0119` |
| C-08 | `lending_revenue_analyst` | Program revenue attribution: by security, counterparty tier, GC vs specials, agent/beneficial-owner split, intrinsic vs reinvestment. | Never restates booked revenue; reconciles to the book and reports differences. | `0119` |
| C-09 | `lending_reporting_check` | Field completeness and consistency checks for SFTR / Rule 10c-1a style datasets. | Never submits, certifies, or interprets regulation. | `0120` |

`sql.verify` and grounding checks are **tools, not agents**: they are
deterministic and model-independent by design, so they get no prompt. The
counterparty/collateral exposure workflow is held by `collateral_management` +
`risk` and gets no new agent (RISK-009).

## Canonical Workflows (REQ-019)

| Workflow | Agents | Tools | Inputs → outputs | Review gate | Must cite |
| --- | --- | --- | --- | --- | --- |
| W1 Desk question → cited answer | C-04, C-03, C-05, `securities_lending` | `ask` (all steps) | question, as_of → answer + citations or abstention | grounding check | run IDs, query IDs, `0063` terms |
| W2 Daily utilization & specials monitor | C-06, `alert_policy`, `alert_router` | `queries.search`, `sql.*`, `answer.ground` | as_of → movers, migrations, alerts | `data_quality` on inputs | runs per metric, PIT predicate |
| W3 Recall & buy-in risk review | C-07, `collateral_management`, `risk` | `sql.*`, `answer.ground` | book as_of, corporate-action calendar → risk list | named human review | runs, corporate-action source |
| W4 Lending revenue attribution | C-08, `financing_cost_analysis` | `sql.*`, `0008` metrics | period → attribution reconciled to book | reconciliation to book total | runs, reconciliation diff |
| W5 Borrow cost → backtests | `financing_cost_analysis`, `backtest_review` | `sql.*` (PIT) | universe, dates → PIT borrow-cost panel | `leakage` + `backtest` gates | runs with `as_of` per date |
| W6 Query-repository onboarding | C-01, C-02, `schema_evolution` | `repos.index`, `catalog.snapshot`, `feedback.propose` | config → index, drift report, review queue | human promotion | repo refs, snapshot IDs |

## Hallucination Evaluation Protocol (REQ-016, NFR-002)

- **Fixture:** a synthetic SQLite database extending `0023`'s
  `seed_demo_data` (`borrow_rates`, `positions`, `sec_lending_book`, `recalls`)
  with `lendable_inventory`, `collateral`, `counterparties`, `corporate_actions`,
  and `program_revenue`; a synthetic query repository (~40 annotated queries,
  some deliberately stale, unreviewed, or malformed); all flagged per `0025`.
- **Golden set:** versioned JSONL; each question has a category, `as_of`,
  expected SQL result (not expected SQL text), expected citations, and
  expected abstention flag. Categories: lookup, aggregation, as-of (PIT),
  viewpoint/sign, multi-join, metric (utilization, revenue), unanswerable
  (missing column/table), ambiguous (must clarify), adversarial (injection in
  comments or results), and drifted (exemplar references a dropped column).
- **Metrics:** identifier-fabrication rate (unresolved identifiers in executed
  SQL), execution accuracy (executes without error when answerable),
  result-match accuracy (result set equals expected), unsupported-claim rate
  (claims without a valid citation in final answers), viewpoint-error rate,
  abstention precision and recall, exemplar-reuse rate, and p95 latency.
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
| Packaging | Separate distributable under `plugins/seclending/` | Module inside `src/quantsmith/` | Apps must install it without the SDK (NFR-003); `0110` already packages Claude plugins. |
| "Learning" | Indexed retrieval + structure extraction + reviewed promotion | Fine-tuning on the query repo | Auditable, reversible, no training data leaves the adopter; fine-tune deferred until eval shows a gap (roadmap Phase 6). |
| Verification | Deterministic verifier with fail-closed tokenizer; optional strict parser | LLM self-check of SQL | A model cannot reliably check its own invented identifiers; determinism makes the fabrication-rate threshold of 0 achievable. |
| Execute interface | Verification token required | Execute raw SQL with a guard flag | Makes verify-before-execute an interface property, not discipline. |
| Ground truth for eval | Expected result sets | Expected SQL text | Many correct SQL strings exist; results are what users consume. |
| Retrieval | Lexical BM25 default, embeddings optional | Embeddings required | Air-gapped and restricted adopters; determinism of tests. |
| Verifier/grounding as agents | Tools | Dedicated agents | No judgement to delegate; prompts add an attack surface. |
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
- Whether the MCP server should also expose the query index as `0052`
  resources (`knowledge://seclending/...`) or tools only.
- Whether `0120` (regulatory completeness) should be scheduled ahead of
  `0119` for an adopter under a near-term reporting obligation.
