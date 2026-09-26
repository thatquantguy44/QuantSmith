# Plan: Natural-Language Analytics — Visualization, Interpretation, and Write-Back

- **Spec:** 0080-nl-analytics-insights (`spec.md`)
- **Status:** Draft
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-09-25

> HOW. This plan requires an approved `spec.md`. Every requirement in the spec
> appears in the traceability matrix below.

## Approach

One new standard-library package, `src/quantsmith/nl_analytics/`, runs a fixed
pipeline of pure stages. The only non-deterministic step — turning prose into a
plan — is quarantined behind an interpreter seam whose output is a typed value
that a single validator accepts or rejects. Everything after validation is
deterministic arithmetic over the `0008` semantic layer.

The key design choice is that **the model proposes, the SDK disposes.** An LLM
never sees a database, never emits SQL, and never writes the final numbers: it
fills in a `QueryPlan` whose fields can only hold governed metric names,
declared dimensions, and typed window/comparison values, and — optionally —
phrases a narrative that a grounding validator checks number-by-number against
the computed insight set. Unsafe outputs are unrepresentable (no SQL field) or
rejected (unbacked number) rather than discouraged.

Write-back follows the transport-seam pattern `0032`/`0059` established: the SDK
builds the exact records, validates them against a declared contract, and
hands them to a caller-injected `writer`. Dry run is the default; a commit needs
approval; reversal is by run id.

```
question ──▶ interpret ──▶ validate ──▶ authorize ──▶ execute ──▶ chart
  (NL)      (seam: keyword |  (registry,   (0058)       (0008 over   (form rule)
             LLM → QueryPlan)  defaults)                 injected       │
                                   │                     reader)        ▼
                          clarification_needed                      insights
                                                                        │
                                          ┌──────── narrate + ground ◀──┘
                                          ▼
                                    ChatResponse ──▶ (optional) write-back
                                          │              (contract, dry-run,
                                          ▼               approval, injected writer)
                                   0070 envelope + audit events
```

## Architecture & Components

| Module (`src/quantsmith/nl_analytics/`) | Responsibility |
| --- | --- |
| `plan.py` | `QueryPlan`, `TimeWindow`, `Comparison`, `Filter` frozen dataclasses; `validate_plan(plan, layer, config)`; `describe_plan(plan)` for the plain-language echo. No SQL/code field exists. |
| `interpret.py` | `Interpreter` protocol (`name`, `interpret(question, context) -> QueryPlan \| Clarification`); `KeywordInterpreter` baseline (metric/dimension synonyms, relative-date phrases such as "last week", "yesterday", "MTD"); `register_interpreter` hook. LLM interpreters live outside the package and plug in here. |
| `domain.py` | Selects `0081` packs from the dataset's source domain tags; merges pack vocabulary into the interpreter; applies units, `can_sum`, `suppressed_insights`, caveats, and chart conventions; exposes `Selection.all_reviewed` to write-back. Restrict-only: its outputs are intersected with the generic rules, never unioned. |
| `authorize.py` | Applies `0058` `access_level_allows` to the metric, dimensions, and dataset; masks restricted names out of clarification candidates. |
| `execute.py` | `execute(plan, layer, reader, as_of) -> Result`; the `reader` is a caller-injected callable returning `Fact` rows; filters to `period <= as_of`; computes content hash, row count, latest period. |
| `chart.py` | `choose_chart(result) -> ChartSpec` (declared form rule); `to_vega_lite(spec)`; `to_markdown_table(result)`; `to_panel(spec) -> dashboard_spec.Panel`. |
| `insights.py` | `compute_insights(result, comparison_result, config) -> InsightSet`: level, change, contributors, trend, outliers (trailing-baseline z-score), concentration (HHI / top-N share). |
| `narrate.py` | `template_narrative(insights)`; `ground(narrative, insights, result) -> GroundingReport` (numeric-token extraction with tolerance, causal-phrase list); caveat triggers. |
| `respond.py` | `answer(question, context) -> ChatResponse` — the single entry point composing the stages and emitting the `0070` envelope. |
| `writeback.py` | `WriteBackContract` loader/validator; `build_records(plan, result, insights, ...)` (takes the plan/result/insights directly — `ChatResponse` doesn't carry them; a deviation from this row's original `build_records(response)` sketch); `publish(records, contract, writer, *, dry_run=True, approved=False)`; `reverse(run_id, reversed_at, contract, writer)` (`reversed_at` is caller-supplied, not read from a clock — needed for `prior_insights`' as-of bound on a reversed record; the original sketch omitted it); `prior_insights(reader, key, as_of)`. |
| `writeback_sqlite.py` | The first supported write-back target: `SQLiteWriter` implementing the injected-writer protocol over stdlib `sqlite3` — creates the insight table from the contract schema, `INSERT ... ON CONFLICT(record_key) DO NOTHING` for idempotency, tombstone reversal by `run_id` (`UPDATE ... SET reversed_at`), and a matching reader for `prior_insights`. Parameterized statements only; the path comes from the contract, never from the question. |
| `cli.py` | `quantsmith-nl-analytics ask "<question>" --registry … --data … [--publish --approve]` for local use and the worked example. |

Supporting artifacts:

- `templates/data/writeback_contract.md` — declared targets, schema, key,
  allowed columns, `source_tables` deny-list, `auto_approve`.
- `config/nl_analytics.yml` pattern (documented, not committed with real
  values): default window, minimum sample size, staleness threshold, outlier
  z-threshold, synonyms file path.
- `agents/analytics/data_visualization/` and `agents/analytics/nl_analytics/`
  four-file agent contracts.
- `examples/nl_analytics/` — synthetic desk funding-cost facts, a registry, a
  transcript of three questions over three days, a committed sample response,
  and a stdlib `sqlite3` reference writer against a gitignored local file;
  synthetic-data disclosure at `docs/0080_synthetic_data_disclosure.md`.

## Interfaces & Data Contracts

**`QueryPlan`** — `metric: str`, `dimensions: tuple[str, ...]` (≤ 2),
`filters: tuple[Filter, ...]` (dimension, op ∈ {`eq`,`in`}, values),
`window: TimeWindow` (start/end periods, grain), `comparison: Comparison | None`
(kind ∈ {`prior_period`, `prior_year`, `prior_insight`}, reference),
`rank: int | None`, `defaults_applied: tuple[str, ...]`,
`interpreter: str` (name + version). Frozen; hashable; canonical JSON for
hashing.

**`Clarification`** — `reason`, `candidates: tuple[str, ...]` (post-masking),
`question`.

**`Result`** — `values` (the whole-window aggregate, keyed by dimension
tuple — "the current level") and `series` (the same aggregation done again
per period, ascending, so a chart or an insight never re-reads the data to
learn how the level moved period to period), `row_count`, `latest_period`,
`as_of`, `content_hash` (SHA-256 of canonical plan + `values` + `series`).

**`ChartSpec`** — `chart_type ∈ CHART_TYPES`, `title` (finding-first),
`x`, `y`, `series`, `units`, `sort`, `zero_baseline: bool`, `footnote`
(source, as-of, metric owner), `alt_text`, plus `metric`/`dimensions`/`data`
(the exact rendered rows, self-contained for Vega-Lite and the Markdown
fallback alike). Pie and dual-axis are not representable (not in
`CHART_TYPES`).

**`InsightSet`** — ordered `Insight(kind, statement, values: dict)` (this
spec's field name is `statement_template`; the shipped field is `statement`
— the fully-rendered sentence, not a fill-in-the-blanks template, since 0080
has no second templating layer for insight text; `values` is what a
narrative is grounded against, not the template's slots). Kinds: `level`,
`change`, `contributor`, `trend`, `outlier`, `concentration`.

**`ChatResponse`** — `status ∈ {answered, clarification_needed, masked, empty,
stale, write_rejected}`, `reason`, `headline`, `insights`, `chart`,
`vega_lite`, `markdown_table`, `plan_echo`, `caveats`, `citations`, `run_id`,
`envelope_uri`, `writeback: WriteBackOutcome | None`.

**Insight record (write-back row)** — `record_key` (hash of run id + insight
index), `run_id`, `question_hash`, `plan_hash`, `metric`,
`metric_definition_hash`, `dimensions_json`, `window_start`, `window_end`,
`as_of`, `insight_kind`, `values_json`, `headline`, `interpreter_mode`,
`author_handle` (`0049` pseudonymous handle, never an email), `created_at`,
`reversed_at` (null until reversed — reversal tombstones, it does not delete).

**Time alignment / leakage controls (P4):** `execute` filters rows to
`period <= as_of` before aggregation; comparison and baseline windows are
derived from the plan window and re-filtered by the same bound;
`prior_insights` selects records with `created_at <= as_of` and
`reversed_at is null or reversed_at > as_of`. No stage can read "now".

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Plan type cannot carry SQL; pie/dual-axis unrepresentable; as-of bound applied once at execute and at prior-insight lookup; numbers in prose must ground to computed values. |
| P5 Reversibility | yes | Chat path has no side effects. Write-back: dry-run default, approval gate, append-only, idempotent, reversal by run id via tombstone. Kill switch: remove the target from the contract. |
| P6 Observability | yes | `0070` envelope + audit events per stage; counters by status (clarification rate, grounding-reject rate, write rejections) exposed for `0021`-style monitoring; owner = `nl_analytics` agent owner. |
| P9 Security & data | yes | Stdlib only; injected reader/writer; no credentials; `0058` clearance before execution; existence masking; privacy flags propagated to the LLM adapter; audit stores hashes and redacted text. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `plan.py` `QueryPlan` + `validate_plan` | T-001, T-002 |
| REQ-002 | `Clarification`, declared defaults, `describe_plan` | T-002, T-003 |
| REQ-003 | `interpret.py` protocol, `KeywordInterpreter`, registration hook | T-003, T-004 |
| REQ-004 | `authorize.py` over `0058` | T-005 |
| REQ-005 | `execute.py` with injected reader | T-006 |
| REQ-006 | `chart.py` form rule, Vega-Lite, `to_panel` | T-007 |
| REQ-007 | `insights.py` | T-008 |
| REQ-008 | `narrate.py` grounding + caveats | T-009 |
| REQ-009 | `respond.py` `ChatResponse` | T-010 |
| REQ-010 | `writeback.py` contract, records, `publish` | T-011, T-012 |
| REQ-011 | `writeback.py` approval + `reverse` | T-012 |
| REQ-012 | `writeback.prior_insights` + `prior_insight` comparison | T-013 |
| REQ-013 | `0070` envelope emission in `respond.py` | T-014 |
| REQ-014 | two agent contracts + catalog rows | T-015 |
| REQ-015 | `domain.py`: `0081` selection, vocabulary merge, unit/additivity/caveat/chart application | T-021 |
| REQ-016 | draft-pack caveat + write-back gate on `Selection.all_reviewed` | T-022 |
| REQ-017 | generic fallback + restrict-only merge | T-021 |
| NFR-001 | canonical JSON hashing; no clock reads in stages | T-006, T-014 |
| NFR-002 | as-of bound in execute and prior-insight lookup | T-006, T-013 |
| NFR-003 | stdlib-only package; injected I/O; import scan test | T-016 |
| NFR-004 | redaction in audit events; privacy flag propagation | T-014, T-016 |
| NFR-005 | benchmark test | T-017 |
| NFR-006 | typed `status` on every response path | T-010 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Query language | Typed `QueryPlan` over governed metrics | LLM text-to-SQL | SQL generation bypasses `0008` governance, access control, and PIT guarantees, and cannot be validated structurally. Cost: questions outside the registry need a human or a new metric definition. |
| Baseline interpreter | Deterministic keyword/synonym | LLM-only | Works offline, reproducible, testable in CI, and mirrors `0057`'s seam; an LLM is an upgrade, not a dependency. |
| Ambiguity | Ask (clarification) | Pick most likely | A confident wrong metric is worse than one extra turn (RISK-001). |
| Chart selection | Declared deterministic rule | LLM-chosen chart | Reproducibility (NFR-001) and reviewability; the `data_visualization` agent owns rule changes. |
| Narrative | Template default, LLM optional, both grounded | LLM-only free text | Fabricated numbers are the highest-impact failure (RISK-002). |
| Portable chart format | Vega-Lite JSON + Markdown table | Rendered PNG/SVG in SDK | Keeps the runtime dependency-free; chat surfaces and notebooks render Vega-Lite natively; the table is the accessible fallback. |
| Write semantics | Append-only, tombstone reversal | Upsert / delete | Preserves history for multi-day comparison and audit (REQ-012). |
| DB access | Injected reader/writer | Bundled drivers | Keeps credentials and drivers adopter-owned, as `0032`/`0059` do. |
| Package location | `src/quantsmith/nl_analytics/` package | Extend `pipelines/` single module | Ten cohesive modules; mirrors `knowledge_console/`. |

## Validation Strategy

- Unit tests per module in `tests/test_nl_analytics.py`, each test name or
  docstring naming its `AC-*`.
- Deterministic synthetic fixtures (seeded) for facts spanning the as-of
  boundary; hand-computed expected insights for AC-009.
- A stub LLM interpreter and stub narrator exercise the seams (AC-004, AC-010)
  with no network.
- Replay test through the real `0070` replay engine (AC-017).
- Write-back tests against an in-memory recording writer and the stdlib
  `sqlite3` reference writer (`:memory:`) for idempotency and reversal
  (AC-014/015/016).
- Import/source scan for NFR-003 (AC-019); benchmark for NFR-005 (AC-021).
- Gates: `spec`, `data-provenance` (example disclosure), agent contract/catalog,
  `orchestration`, `docs-link`, `handoff-sync`, `spec-index`, `doc-counts`.

## Rollout, Observability & Rollback

- **Rollout:** ship the chat path first (no side effects); enable write-back
  per target only after its contract is reviewed; LLM interpreter enabled per
  deployment after its clarification and grounding-reject rates are measured
  against the keyword baseline on a fixed question set.
- **Observability:** per-status counters, grounding-reject rate, clarification
  rate, write rejections and reversals, all from audit events. Suggested alert:
  grounding-reject rate > 5 % over a day → review the narrator.
- **Rollback:** chat path — revert the package or unregister the LLM
  interpreter (falls back to keyword). Write-back — `reverse(run_id)` per
  batch; remove the target from the contract to kill all writes.

## Open Questions

- ~~First write-back target~~ — resolved 2026-09-24: SQLite
  (`writeback_sqlite.py`, stdlib `sqlite3`, local gitignored file). A shared
  database adapter is deferred until a team needs one.
- First chat surface; whether the `0057` console hosts it through its existing
  `QueryEngine` seam.
- Whether insight records also become `0048`/`0056` knowledge candidates.
- Multi-metric plans beyond a two-measure scatter — defer until a real
  question set shows demand.
