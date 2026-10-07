# Tasks: Natural-Language Analytics — Visualization, Interpretation, and Write-Back

- **Spec:** 0080-nl-analytics-insights (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-07

> Ordered, testable units of work. Every task cites the requirement(s) it advances
> and carries a Definition of Done. No task without a requirement.

## Definition of Done (applies to every task)

- Code matches the plan; deviations noted in `plan.md`.
- Standard library only; no new runtime dependency.
- No network call, connection string, or credential anywhere in
  `src/quantsmith/nl_analytics/` or its tests — reads, writes, and LLM calls
  are caller-injected.
- Tests exist in `tests/test_nl_analytics.py`, name their `AC-*`, and pass
  deterministically.
- Example data is synthetic and disclosed per `0025`.
- Docs/configs updated alongside the change.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | `plan.py`: `QueryPlan`, `TimeWindow`, `Comparison`, `Filter` frozen dataclasses with canonical JSON; no SQL/code field. | REQ-001, AC-001 | done | |
| T-002 | `validate_plan` against the `0008` registry (metric, declared dimensions, filter values, window, grain) and `describe_plan` echo. | REQ-001, REQ-002, AC-001, AC-003 | done | |
| T-003 | `interpret.py`: `Interpreter` protocol, `Clarification`, `KeywordInterpreter` (synonyms, relative dates, declared defaults). | REQ-002, REQ-003, AC-002, AC-003 | done | |
| T-004 | Interpreter registration hook; stub-LLM test proving one validator for all interpreters. | REQ-003, AC-004 | done | |
| T-005 | `authorize.py`: clearance check via `0058`; existence masking in answers and clarifications. | REQ-004, AC-005 | done | |
| T-006 | `execute.py`: injected reader, as-of filter, row count, latest period, content hash. | REQ-005, NFR-001, NFR-002, AC-006 | done | Two-dimension grouping composes `0008`'s public `compute()` per partition rather than its private `group_by` path, so it works for 0/1/2 declared dimensions. |
| T-007 | `chart.py`: form rule, finding-first titles, units/labels/footnote/alt text, Vega-Lite and Markdown table, `to_panel` rendered via `0015`. | REQ-006, AC-007, AC-008 | done | `execute.py`'s `Result` extended with a per-period `series` (needed for the time-series/outlier shapes; noted below). |
| T-008 | `insights.py`: level, change, contributors, trend, outliers, concentration with the values each rests on. | REQ-007, AC-009 | done | Outlier z-score falls back to a tiny epsilon std when the trailing baseline is perfectly flat, so a real jump off a flat series is still flagged rather than silently skipped (division-by-zero guard would otherwise hide it). |
| T-009 | `narrate.py`: template narrative, grounding validator (numbers, causal phrases), caveat triggers. | REQ-008, AC-010, AC-011 | done | |
| T-010 | `respond.py`: `answer()` entry point and `ChatResponse` with typed status for every path. | REQ-009, NFR-006, AC-012, AC-022 | done | Multi-metric `compare` charts (two-measure scatter) are wired into `chart.py` but `respond.py`'s single-plan `answer()` doesn't orchestrate two plans yet — tracked in Follow-ups, matches the spec's own multi-metric non-goal. |
| T-011 | `templates/data/writeback_contract.md` and contract loader/validator (targets, schema, key, allowed columns, source-table deny-list). | REQ-010, AC-013 | done | `load_contract` parses name, `auto_approve`, and the deny-list from a filled-in copy; schema and idempotency key are the one system-wide insight-record shape (`SCHEMA_COLUMNS`), not per-file, so `columns`/`idempotency_key` aren't parsed. A file still carrying the template's own placeholders is rejected. |
| T-012 | `writeback.py`: `build_records`, `publish` (dry-run default, approval, idempotency), `reverse` by run id (tombstone). | REQ-010, REQ-011, AC-014, AC-015 | done | `WriteBackWriter.reverse` takes a caller-supplied `reversed_at` (not just `run_id`) — needed for `prior_insights`' as-of bound on a reversed record to be exact, per NFR-002; the spec's own interface sketch omitted it, noted here rather than silently deviating. |
| T-013 | `prior_insights` as-of lookup and `prior_insight` comparison kind. | REQ-012, NFR-002, AC-016 | done | Persisted comparison is total-level only (from the `level` insight row); reconstructing a per-dimension breakdown from stored `contributor` rows is a documented follow-up. `respond.py`'s `comparison_key()` joins on metric+dimensions, not the window, so "since yesterday" matches across two different rolling windows; a `reference == "yesterday"` comparison shifts the lookup's as-of back one period so a same-day persisted record can never stand in for yesterday's. |
| T-014 | Emit `0070` envelope and audit events per stage, with replay test. | REQ-013, NFR-001, AC-017 | done | `envelope.py`: opt-in via `AnswerContext.envelope_dir`/`run_id` (no side effect when unset — RISK-004); nine audit events (interpret, validate, execute, chart, insights, narrate-as-gate, deliver, plus start/complete) mapped onto `0070`'s fixed event-type vocabulary; an LLM `interpreter_mode` is marked `model_invocation`/non-deterministic honestly rather than hidden. Redaction and privacy-flag propagation (NFR-004, AC-020) stay T-016's scope — not duplicated here, since this task's own envelope content isn't yet redacted. |
| T-015 | Agents `agents/analytics/data_visualization/` and `agents/analytics/nl_analytics/` (four files each, `Spec-Driven Role`), catalog rows, group README handoffs. | REQ-014, AC-018 | done | Contract-only, per REQ-014: each hands off to `metrics_semantic_layer`, `data_visualization`/`dashboard_design`, and `sql-integration-agent` rather than duplicating them; `data_visualization` documents `chart.py` as its runtime, `nl_analytics` documents the whole `src/quantsmith/nl_analytics/` package. |
| T-016 | Import/source scan test (stdlib only, no credentials or network) and privacy test. | NFR-003, NFR-004, AC-019, AC-020 | done | `dataset_privacy` is caller-declared on `AnswerContext`/`emit_answer_evidence` (never inferred); when any flag is set the question text is redacted out of every rendered artifact and replaced by its hash, and an LLM-backed interpret event carries the flags as the `adapters/llm_runtime/` privacy block that call would use. Redaction scope is the one genuinely free-text field this package carries (the question) — governed plan/result values stay in full since they're vocabulary-controlled, not free text; per-dimension result redaction is a documented follow-up. |
| T-017 | 100k-row benchmark test. | NFR-005, AC-021 | done | 200 desks × 5 currencies × 100 periods = 100,000 rows, answered end to end through `answer()` (keyword interpreter, no data fetch or LLM in the timed section — the row list is built before the clock starts). A cheap fixed-workload calibration runs first so a genuinely under-provisioned CI runner is skipped with a recorded reason rather than failing on wall-clock noise, per the AC's own wording. |
| T-018 | `cli.py` and `examples/nl_analytics/` (synthetic three-day transcript, committed sample response) plus `docs/0080_synthetic_data_disclosure.md`. | REQ-009, REQ-012 | done | `cli.py` (`quantsmith-nl-analytics ask`, registered in `pyproject.toml`) also wires `answer()` to write-back end to end: `AnswerContext.writeback` (a new `WriteBackRequest`) makes `answer()` itself call `build_records`/`publish` and attach the `WriteBackOutcome`, returning the previously-unused `write_rejected` status (typed, NFR-006) instead of raising when a commit is refused — closing the gap `respond.py`'s own Follow-ups section named. `examples/nl_analytics/` walks three real CLI invocations over three synthetic days (level, then grouped, then a genuine "since yesterday" `prior_insight` comparison against day 1's persisted record); `sample_response.json` is the committed, byte-checked output of the third. |
| T-020 | `writeback_sqlite.py`: `SQLiteWriter` + reader over stdlib `sqlite3` (schema from contract, `ON CONFLICT DO NOTHING` idempotency, tombstone reversal, as-of prior-insight read); runs AC-014/015/016 against both the recording writer and SQLite (`:memory:` and a temp file). First supported target, resolved by the owner 2026-09-24. | REQ-010, REQ-011, REQ-012, AC-014, AC-015, AC-016 | done | Table name is fixed at construction from the contract (`nl_analytics_writeback_<name>`), never from a record or a later call; every statement is parameterized. |
| T-019 | Update `specs/README.md`, `src/quantsmith/pipelines/README.md` or package README, `docs/handoff.md`, `docs/handoffs/future_features.md`, and `CHANGELOG.md` on ship. | REQ-014 | todo | |

| T-021 | `domain.py`: apply `0081` packs (vocabulary, units, additivity, insight suppression, caveats, chart conventions), term-conflict clarification, and generic fallback. | REQ-015, REQ-017, AC-023, AC-024, AC-026 | done | Fixes insights summing groups for every metric (yields across tenors, VaR across desks). `execute.Result` now carries the layer's own ungrouped `total`/`period_totals`; `insights.py` reads those, never a sum of groups, under a `domain.MetricPolicy`. Generic additivity comes from the `0008` definition only (`sum`/`count` additive; `mean`/ratio non-additive); packs can only make it stricter and only add suppressed kinds. A grouped question on a non-additive metric reports per-group levels and changes with no total; contributor/concentration also require the groups to reconcile to the total, so a direct `compute_insights` call without a policy cannot decompose a mean either. Non-time-summable metrics (stocks, rates) read the latest period, and the chart follows (`snapshot`). `pct`/`bps` changes are in basis points with no percent change. Grounding now treats digits in dimension labels (`10y`) as backed. CLI gains `--domain`/`--packs-root`. |
| T-022 | Unreviewed-pack caveat and write-back refusal unless every applied pack is reviewed. | REQ-016, AC-025 | done | Gate is `domain.writeback_refusal`, not `Selection.all_reviewed` as `plan.md` sketched: `all_reviewed` is false with zero packs, which would refuse every generic (no-pack) write-back; REQ-016 governs *applied* packs only. |
| T-023 | Pack source in the response and envelope; `answer()` raises on domain tags with no catalog; CLI resolves packs via `0081` `resolve_packs` (local, then bundled) and errors only for an explicit empty `--packs-root` or no packs anywhere. | REQ-018, AC-027 | done | |
| T-024 | `adapters/llm_runtime/openai_compatible.py`: standard-library reference backend (`urllib.request`) for OpenAI-compatible chat completions — endpoint URL, model, key env-var name, timeout, retries on 429/5xx; returns text plus provider/model/usage; never logs the key. Document the callable contract in `adapters/llm_runtime/adapter_contract.md`. | REQ-019, NFR-003, AC-028 | todo | Lives outside `src/quantsmith/nl_analytics/` so AC-019's scan still holds. The Dataset Investigator (`0099`) can reuse it for its model roles outside Claude Code. |
| T-025 | `interpret.py`: `LLMInterpreter` (prompt carries the governed vocabulary and plan schema; strict JSON parse; validator gate; clarification on failure), registered via `register_interpreter`. `narrate.py`: `LLMNarrator` with grounding and template fallback plus caveat. Envelope records the model call. | REQ-020, REQ-003, REQ-008, REQ-013, AC-029 | todo | Tests use a stub callable; no network in tests. |
| T-026 | `0057` Console analytics route (`/api/analytics/ask`) and a page that renders the Vega-Lite spec, insights, plan echo, caveats, and citations; viewer clearance via the console's resolver; localhost bind by default. | REQ-021, REQ-004, AC-030 | todo | Separate from the console's `QueryEngine`, which answers over memory records, not datasets. |
| T-027 | `writeback.py`: `approver_handle` on the request and records; contract fields `approver_roles` and `require_distinct_approver`; optional `roles` on roster entries (`access_control.py` parser, validator, `access/roster.yml` template comment). | REQ-023, REQ-011, AC-032 | todo | Roster stays empty by default; a target declaring roles is refused until it has entries. |
| T-028 | Opt-in knowledge candidate on publish (`propose_knowledge`): `0048` candidate record with citations, review status, dry-run preview, and stated reasons when none is created. | REQ-022, REQ-016, AC-031 | todo | |
| T-029 | CLI flags (`--llm-endpoint`, `--llm-model`, `--llm-key-env`, `--approver`, `--propose-knowledge`), `examples/nl_analytics/` update, and the README section on running without Claude Code. | REQ-019, REQ-020, REQ-022, REQ-023 | todo | |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

Every acceptance criterion must be named by at least one test.

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_ac001_plan_is_governed_and_has_no_sql_field`, `test_ac001_filter_and_window_reject_bad_values` | done |
| AC-002 | `test_ac002_unknown_metric_or_dimension_rejected`, `test_ac002_keyword_interpreter_returns_clarification_for_unknown_question`, `test_ac002_ambiguous_question_lists_candidates` | done |
| AC-003 | `test_ac003_default_window_applied_and_echoed`, `test_ac003_no_default_window_configured_is_a_clarification`, `test_ac003_relative_phrase_needs_no_default` | done |
| AC-004 | `test_ac004_llm_style_interpreter_shares_the_same_validator` | done |
| AC-005 | `test_ac005_restricted_metric_is_masked`, `test_ac005_public_metric_passes_through`, `test_ac005_restricted_dimension_is_dropped_not_named` | done |
| AC-006 | `test_ac006_execute_respects_as_of_and_hashes`, `test_ac006_execute_groups_by_declared_dimensions`, `test_ac006_execute_applies_filters` | done |
| AC-007 | `test_ac007_form_rule_by_result_shape`, `test_ac007_vega_lite_and_markdown_are_minimal_and_reflect_data` | done |
| AC-008 | `test_ac008_chart_promotes_to_panel_and_renders` | done |
| AC-009 | `test_ac009_insights_match_hand_computed`, `test_ac009_trend_and_outlier_match_hand_computed` | done |
| AC-010 | `test_ac010_grounding_rejects_unbacked_numbers_and_flags_causal` | done |
| AC-011 | `test_ac011_caveats_triggered` | done |
| AC-012 | `test_ac012_chat_response_complete` | done |
| AC-013 | `test_ac013_writeback_contract_rejections` | done |
| AC-014 | `test_ac014_dry_run_default_and_idempotent_commit` (parametrized: recording writer + SQLite) | done |
| AC-015 | `test_ac015_approval_required_and_reversal_by_run_id` | done |
| AC-016 | `test_ac016_since_yesterday_uses_prior_insight_as_of`, `test_ac016_respond_yesterday_reference_shifts_as_of_by_one` | done |
| AC-017 | `test_ac017_replay_is_byte_identical` | done |
| AC-018 | agent-contract + `agent-catalog` gates | done |
| AC-019 | `test_ac019_stdlib_only_no_credentials_or_network` | done |
| AC-020 | `test_ac020_audit_redaction_and_privacy_flags` | done |
| AC-021 | `test_ac021_benchmark_100k_rows` | done |
| AC-023 | `test_ac023_pack_units_and_additivity_applied`, `test_non_additive_metric_is_never_summed_across_groups`, `test_semi_additive_level_is_the_latest_period_not_a_window_sum` | done |
| AC-024 | `test_ac024_cross_pack_term_conflict_clarifies` | done |
| AC-025 | `test_ac025_draft_pack_caveat_and_writeback_gate` | done |
| AC-026 | `test_ac026_generic_fallback_and_restrict_only` | done |
| AC-027 | `test_ac027_pack_source_reported_and_missing_catalog_raises` | done |
| AC-028 | `test_ac028_openai_compatible_backend_against_stub_server` | todo |
| AC-029 | `test_ac029_llm_interpreter_and_narrator_gated` | todo |
| AC-030 | `test_ac030_console_analytics_route_masks_and_renders` | todo |
| AC-031 | `test_ac031_opt_in_knowledge_candidate` | todo |
| AC-032 | `test_ac032_named_approver_and_roles` | todo |
| AC-022 | `test_ac022_typed_status_on_every_failure_path` | done |

## Follow-ups

Tracked work intentionally deferred (no silent "temporary" shortcuts — P8).

- Shared-database write-back adapter (Postgres / SQL Server via the existing
  `SQLDataSource` classes, or a warehouse) — deferred; SQLite (T-020) is the
  first target.
- `respond.answer()` orchestrating a two-metric plan pair for the scatter
  chart shape; `chart.choose_chart(..., compare=...)` supports it already,
  `answer()` still resolves one plan per question (matches the spec's own
  "one metric per plan in the first slice" assumption).
- Chat-surface adapter (Claude chat / Slack / `0057` console `QueryEngine`).
- Multi-metric plans beyond a two-measure scatter.
- Non-additive metric contribution (distinct counts, medians) — depends on
  `0008`'s own follow-up.
- Promoting persisted insights into `0048`/`0056` knowledge candidates.
- Per-dimension prior-insight comparisons — `prior_insights` currently
  reconstructs a total level only, from the persisted `level` row; a group
  breakdown would need reassembling stored `contributor` rows, not built here.
- ~~`ChatResponse.writeback` stays `None`~~ — resolved by T-018:
  `AnswerContext.writeback` (`WriteBackRequest`) makes `answer()` call
  `build_records`/`publish` itself using the plan/result/insights it already
  computed, and attaches the `WriteBackOutcome` to `ChatResponse.writeback`
  (or returns `write_rejected` if the commit is refused).
- Per-dimension privacy redaction (T-016) — envelope redaction covers the
  question text, the package's one genuinely free-text field; a computed
  result's per-dimension values (e.g. a client-name dimension) are not
  scanned or redacted, since every dimension value comes from the governed
  semantic layer's declared vocabulary, not free text. If a future dataset's
  declared dimension values are themselves sensitive, redacting them would
  need the caller's own dimension-level classification, not built here.
