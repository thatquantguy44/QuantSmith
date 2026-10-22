# Spec: SFMeridian — Adaptive Securities-Finance Dataset Research

- **ID:** 0121-sfmeridian-adaptive-dataset-research
- **Status:** Approved
- **Author:** Joshua Lutkemuller, CFA
- **Approver:** Joshua Lutkemuller, CFA (2026-10-22 — owner direction to incorporate the Dataset Intake Investigator proof of concept and its adaptive EDA spec into SFMeridian for securities finance)
- **Last updated:** 2026-10-22

> WHAT and WHY. A child of `0113` (SFMeridian). References to other specs'
> IDs are written `0113` R-nnn / A-nnn and `poc` A-nn so the spec gate never
> reads them as this spec's own IDs. Source: the owner-supplied *Dataset
> Intake Investigator* prototype and `specs/adaptive_eda_agent_spec.md`
> (status "proposed extension; not implemented", 2026-10-21), referred to here
> as **the POC** and **the POC spec**.

## Problem & Context

Before a securities-lending dataset can feed answers, monitors, analytics, or
backtests, someone has to establish what it is, what can be trusted, and what
to check next: is the loan book unique at security × counterparty × date; is
the fee missing for one region on one day; does on-loan quantity ever exceed
lendable quantity; do borrow categories agree with the fee thresholds; were
borrow rates available on the as-of date or published later; does collateral
cover the loans at the agreed margin. Today that is ad hoc SQL and notebooks,
unreproducible, and language models asked to help state numbers they did not
compute.

The POC already proves the deterministic core for generic files and bounded
SQL Server/Databricks extracts (contracts, grain, ranges, dates, snapshots,
loaders), and the POC spec designs the next step: a bounded research agent
with a coverage ledger, pushed-down database summaries, a deterministic tool
catalog, budgets, evidence-backed recommendations, and a reproducible run
bundle, with 18 acceptance criteria. SFMeridian (`0113`/`0114`) already has
what that design needs underneath — the loop harness, the shared tool
registry, read-only database profiles for PostgreSQL, Oracle, and Databricks
SQL, the strict configuration reader, and the reviewed query repository — but
no agent that researches the lending datasets themselves.

QuantSmith's `0099` Dataset Investigator does file-based EDA with hypotheses
on pandas; it is not database-pushdown, not stdlib, and has no
securities-finance knowledge. This spec does not replace it; it hands
bounded extracts to it when a deep file investigation is wanted.

## Goals

- Apply the POC spec to securities finance inside SFMeridian: a loop agent,
  `lending_data_researcher` (coverage row C-10), that researches lending
  tables in the adopter's databases with accounted-for coverage, pushed-down
  exact aggregates, a securities-finance rule pack, explicit budgets, and
  ranked, evidence-linked recommendations.
- Keep the POC's file intake behavior available as the baseline.
- Never execute model-produced SQL; only plugin-owned templates that pass the
  static checks `0116` will enforce.
- Produce one reproducible run bundle per run.

## Non-Goals

- Automatic repair, imputation, deduplication, clipping, feature removal, or
  any write to a source system (`poc` §3, §8).
- Model training or deployment; causal or significance claims by default.
- Executing repository queries or generated SQL (that is `0116`).
- New scheduling infrastructure; the POC's folder watcher is not carried over
  (runs are on demand or triggered by an external job).
- Live connector certification: `AC-016` stays open until nonproduction
  PostgreSQL, Oracle, and Databricks environments exist.
- SQL Server: the POC supports it; SFMeridian's owner decision (`0113`,
  2026-10-22) defers it. Its templates are kept, gated off until enabled.

## Requirements

| ID | Requirement | Traces to | Priority |
| --- | --- | --- | --- |
| REQ-001 | The plugin shall keep the POC's file intake checks available — CSV, TSV, flat JSON; contract columns and inferred types, business key, ranges, ISO date columns; malformed rows, duplicates, IQR flags, future dates; status `blocked`/`review`/`passed_configured_checks` — as the `intake` family of a research run. | `poc` A-01 | must |
| REQ-002 | A research run shall take a validated **research context** (objective, `dataset_kind`, business grain, time column, expected frequency and calendar, timezone, segments, optional target and feature availability, excluded/allowed/sensitive columns, as-of, materiality thresholds, optional reference profile, budgets), reject contradictions (key or allowed columns that are excluded or sensitive, unknown columns), and never invent missing context: dependent checks are `blocked` or `skipped` with the reason. | `poc` §4, A-04 | must |
| REQ-003 | Datasets shall be declared in configuration (`datasets[]`: id, source `database` or `file`, database profile, object, explicit columns, ordering, parameter-bound filters, optional Delta version, `dataset_kind`); no dataset location, object, or column is taken from free text. | `0113` R-003, R-004 | must |
| REQ-004 | Database work shall use only plugin-owned, versioned, dialect-specific SELECT templates (SQLite, PostgreSQL, Oracle, Databricks; SQL Server gated off) with validated, quoted identifiers drawn from the dataset's allowed columns, bound values, and a row limit; every rendered query shall pass a static check (one read-only statement, identifiers within the allowlist, no inline literals from input) before it runs; and connections shall be read-only and supplied by an injected factory, never by credentials in configuration. | `poc` A-07, §7; `0113` R-010, R-011 | must |
| REQ-005 | Every database result shall carry provenance — object, source version if pinned, filters, template ID and version, query hash, bound parameters with sensitive values redacted, rows returned, truncation, scope label (`full_filtered_population`, `ordered_extract`, `random_sample`, `approximate_aggregate`), exact or approximate, bytes scanned or `unknown` — and no extract-scoped result may become a population claim. | `poc` A-06, §7 | must |
| REQ-006 | The plugin shall provide the deterministic research tool catalog — `inspect_schema`, `summarize_columns`, `check_grain`, `inspect_missingness`, `inspect_numeric`, `inspect_categories`, `inspect_relationships`, `inspect_time`, `compare_segments`, `inspect_target`, `inspect_availability`, `compare_reference`, `check_domain_rules`, `render_charts`, `recommend_actions` — as `research.*` tools in the shared registry, each returning structured results, scope, method, warnings, and evidence IDs. | `poc` §6; `0113` R-029 | must |
| REQ-007 | Summaries, grain checks, missingness by segment and date, time coverage, and domain-rule violation counts shall be pushed down as exact aggregates over the declared filtered population; bounded extracts are used only for distributions, relationships, and examples, and are labelled `ordered_extract`. | `poc` §7, A-15 | must |
| REQ-008 | The plugin shall ship a **securities-finance rule pack** keyed by `dataset_kind` (`loan_book`, `lendable_inventory`, `borrow_rates`, `collateral`, `recalls`, `program_revenue`), each rule declarative (range, comparison between columns, ratio bounds, enumeration, threshold classification consistency, ACT/360 accrual reconciliation), citing its `0063`/`0066` convention or marked adopter-configurable, with thresholds (fee bands, GC/WARM/HTB cut-offs, required collateral margin, materiality) taken from the context — never assumed. | `0113` R-008, R-013 | must |
| REQ-009 | The agent shall keep an **evidence registry** (deterministic evidence IDs), a **coverage ledger** (every applicable family `completed`, `blocked`, `skipped`, or `budget_exhausted`, with a reason), and findings that resolve to evidence; a budget stop is never reported as completed coverage. | `poc` A-02, A-05 | must |
| REQ-010 | The agent shall run as a loop agent on the `0114` harness with a deterministic adaptive policy — intake, schema, summaries, grain, missingness, then follow-ups triggered by evidence (concentrated missingness → segment and date diagnostics; domain violations → segment breakdown; repeated keys → wider-grain probe), then recommendations — and an optional model policy; budgets on steps, queries, local rows and bytes, columns, pairs, wall time, and model tokens; identical repeated actions rejected; at most one retry for a transient read failure; explicit stop reasons. | `poc` §5, A-03, A-08 | must |
| REQ-011 | Recommendations shall follow the POC contract: ID, priority by explicit rubric (blockers and contract or rule violations, then material concentrated issues, then exploratory), category, action, evidence IDs, scope, counts and denominators, chart IDs, observation separated from hypothesis, confidence rationale, limitations, business consequence or `unknown`, a runnable next diagnostic (a rendered read-only template) or a precise question for the data owner, dependencies, effort class, and a verification criterion. Recommendations never trigger repair, deployment, or writes. | `poc` §9, A-18 | must |
| REQ-012 | Each run shall write one bundle — `report.md`, `report.json`, `coverage.json`, `recommendations.json`, `charts/` (Vega-Lite specs with units, denominators, and scope), `analysis/` (the research modules and every rendered SQL template used), `run_manifest.json` (config hash, context, code versions, tool calls, stop reason, artifact hashes, timings), `dataset_contract_proposal.json` (proposed rules, distinct from accepted ones) — with one documented rerun command; frozen inputs reproduce the evidence and artifact hashes. | `poc` §10, A-11, A-13, A-14 | must |
| REQ-013 | Model-facing payloads and shared reports shall contain aggregates and metadata only by default: no credentials, no values of excluded or sensitive columns, no raw rows; text from files, headers, and databases is treated as untrusted data; and tool requests outside the manifest are refused. | `poc` A-09, A-10, §11 | must |
| REQ-014 | Point-in-time checks shall honour the supplied timezone and availability rules: event time before availability, availability no later than the decision time (as-of end of day in the context timezone), naive timestamps without declared timezone semantics `blocked`; an extraction timestamp is never treated as an availability guarantee. | `poc` A-17, §7 | must |
| REQ-015 | When several queries run against an unpinned view or table, the run shall probe consistency (row count and a declared change column, when given, at start and end) and report a limitation when the source changed or a consistent snapshot cannot be established. | `poc` A-12 | must |
| REQ-016 | A live-connector smoke test for PostgreSQL, Oracle, and Databricks shall exist, run only when nonproduction connection pointers are injected, and otherwise report itself skipped, never passed. | `poc` A-16 | should |
| REQ-017 | The SDK shall add the `lending_data_researcher` agent (coverage row C-10, workflow W13 "dataset research") with the four contract files, a loop manifest, catalog rows, and regenerated registry and skills export, and handoffs to `analytics/dataset_investigator`, `data_quality`, and `data_engineering/schema_evolution`. | `0113` R-015, R-028 | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Portability | Standard library only, Python 3.11+; drivers are injected, never imported by the package. |
| NFR-002 | Determinism | Frozen inputs reproduce numeric evidence, evidence IDs, and artifact hashes (timings excluded). |
| NFR-003 | Safety | No write, DDL, or multi-statement SQL can be rendered; no source is modified. |
| NFR-004 | Honest reporting | Denominators, exclusions, methods, scope, and approximation are stated on every number. |
| NFR-005 | Catalog consistency | All `run-stage.sh` gates pass under enforcement. |

## Acceptance Criteria

`AC-001`–`AC-018` are the POC spec's A-01–A-18 applied to SFMeridian and
securities finance; the test names are the POC's.

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given the POC's synthetic positions file and contract, when the intake family runs, then status and findings match the POC's (blocked; malformed row, duplicate row, repeated key, negative balance, invalid and future dates). `test_intake_regression` | REQ-001 |
| AC-002 | Given a loan-book dataset, when a run completes, then every applicable family has a ledger entry with status and reason. `test_coverage_accounting` | REQ-009 |
| AC-003 | Given fees missing for one region on one business date, when the run reaches missingness, then it issues a segment and a date diagnostic and the finding cites both. `test_adaptive_missingness_followup` | REQ-010 |
| AC-004 | Given no grain, calendar, or target, when the run completes, then grain, gap, and target checks are `blocked`/`skipped` with reasons, unique columns are reported only as candidates, and no context is invented. `test_missing_context_no_invention` | REQ-002 |
| AC-005 | Given a finished run, when findings and recommendations are resolved, then every one cites registered evidence with matching numbers. `test_evidence_integrity` | REQ-009, REQ-011 |
| AC-006 | Given a truncated ordered extract, when its evidence is used, then findings say "in the returned extract" and none claims the population. `test_scope_propagation` | REQ-005 |
| AC-007 | Given an injection-shaped filter value, an unknown or excluded column, and an expression as a column name, when queries are built, then values are bound, identifiers rejected, and nothing runs. `test_database_query_boundary` | REQ-004 |
| AC-008 | Given tight budgets, when the run exceeds queries, steps, local rows, or time, or repeats an action, then it stops with `budget_exhausted` or rejects the duplicate, never reports completed coverage, and retries a transient failure at most once. `test_budget_and_stop_conditions` | REQ-010 |
| AC-009 | Given a database text value instructing the agent to promote candidates or run SQL, when the run (deterministic or model policy) proceeds, then no non-granted tool runs, no source changes, and only SELECT templates execute. `test_read_only_and_prompt_injection` | REQ-013, NFR-003 |
| AC-010 | Given sensitive and excluded columns and a secret pointer, when model prompts and the bundle are scanned, then none of their values and no credential appear. `test_sensitive_data_boundary` | REQ-013 |
| AC-011 | Given frozen inputs, when the run repeats, then numeric evidence, evidence IDs, and artifact hashes are identical. `test_reproducible_analysis` | REQ-012, NFR-002 |
| AC-012 | Given an unpinned view whose base table changes between queries, when the run completes, then the report names the inconsistency as a limitation. `test_mutable_view_provenance` | REQ-015 |
| AC-013 | Given a bundle, when its documented rerun command runs, then it reproduces the evidence using only bundled modules and templates plus the source. `test_bundle_rerun` | REQ-012 |
| AC-014 | Given the bundle's charts, when validated, then each has title, units, denominator, scope, and data, and parses as a Vega-Lite spec. `test_chart_artifact_validation` | REQ-012 |
| AC-015 | Given a seeded SQLite loan book, when pushed-down summaries, grain, missingness, and rule counts are computed, then they equal Python computations over all rows. `test_pushdown_aggregate_correctness` | REQ-007 |
| AC-016 | Given injected nonproduction pointers, when the smoke test runs, then each connector executes one summary template; otherwise the test is skipped. `test_live_connector_smoke` | REQ-016 |
| AC-017 | Given availability timestamps with offsets, a naive timestamp, and an as-of in a declared timezone, when availability is checked, then late-published rates are flagged, the naive column is blocked, and timezone conversion is exact. `test_point_in_time_checks` | REQ-014 |
| AC-018 | Given recommendations, when produced, then none executes, no write-effect tool exists, and the source file is unchanged. `test_recommendation_only_boundary` | REQ-011 |
| AC-019 | Given the seeded loan book, inventory, rates, and collateral fixtures, when domain rules run, then utilization above 1, on-loan above lendable, category–fee disagreements, a negative lender fee, collateral below the supplied margin, and an ACT/360 accrual mismatch are each counted exactly, a legitimate 3,000 bps special is not flagged as an error, and each rule cites its convention or says adopter-configurable. | REQ-008 |
| AC-020 | Given the tool catalog, when listed, then every POC tool exists as a `research.*` tool with a schema, and every result carries scope, method, and evidence IDs. | REQ-006 |
| AC-021 | Given a config `datasets[]` entry with an unknown profile, a free-text object, or SQL Server, when validated, then it fails with a named code. | REQ-003 |
| AC-022 | Given the agent catalog and governance check, when run, then `lending_data_researcher` is a built loop agent with manifest, coverage row C-10, workflow W13, and its handoffs, and all gates pass. | REQ-017, NFR-005 |
| AC-023 | Given any reported number, when inspected, then its denominator, exclusions, method, and scope are present. | NFR-004 |
| AC-024 | Given the package, when imports are scanned, then only the standard library is used. | NFR-001 |

## Data & Dependencies

- `0113`/`0114`: harness, registry, config, database profiles, CLI.
- `0063`/`0066`: fee/rebate viewpoints, GC/WARM/HTB thresholds, ACT/360.
- POC: intake rules, identifier rules, extract provenance, the POC spec.
- `0099`: receives extracts for deep file investigation (handoff, no import).
- Synthetic fixtures only (`0025` disclosure).

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | Ordered extracts read as representative. | Overclaimed quality. | REQ-005 scope labels; AC-006. |
| RISK-002 | Pushdown scans large tables despite row limits. | Warehouse cost. | Filters required for large objects; query budget; bytes `unknown` stated; warehouse limits are the adopter's control. |
| RISK-003 | Domain thresholds assumed rather than supplied. | False violations. | REQ-008 context-only thresholds; rules without thresholds are `skipped`. |
| RISK-004 | Legitimate repeated positions or extreme specials flagged as errors. | Noise and distrust. | Flags not errors; benign-extreme fixtures (AC-019); candidate-key language. |
| RISK-005 | Source text steers a model policy. | Tool misuse. | REQ-013; manifest grants; AC-009. |

## Assumptions & Open Questions

- Assumption: adopters can declare datasets' columns and grain; `0115`'s
  catalog will later supply column lists automatically.
- Open: enable SQL Server now (the POC supports it) or keep the `0113`
  deferral? Templates exist; the config gate stays closed until decided.
- Open: required collateral margin and materiality thresholds for the first
  desk (supplied per run until then).

## Exceptions

None.
