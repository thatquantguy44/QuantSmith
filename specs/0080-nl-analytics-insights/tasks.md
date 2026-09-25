# Tasks: Natural-Language Analytics — Visualization, Interpretation, and Write-Back

- **Spec:** 0080-nl-analytics-insights (`spec.md`, `plan.md`)
- **Last updated:** 2026-09-24

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
| T-011 | `templates/data/writeback_contract.md` and contract loader/validator (targets, schema, key, allowed columns, source-table deny-list). | REQ-010, AC-013 | todo | |
| T-012 | `writeback.py`: `build_records`, `publish` (dry-run default, approval, idempotency), `reverse` by run id (tombstone). | REQ-010, REQ-011, AC-014, AC-015 | todo | |
| T-013 | `prior_insights` as-of lookup and `prior_insight` comparison kind. | REQ-012, NFR-002, AC-016 | todo | |
| T-014 | Emit `0070` envelope and audit events per stage, with redaction and privacy-flag propagation; replay test. | REQ-013, NFR-001, NFR-004, AC-017, AC-020 | todo | |
| T-015 | Agents `agents/analytics/data_visualization/` and `agents/analytics/nl_analytics/` (four files each, `Spec-Driven Role`), catalog rows, group README handoffs. | REQ-014, AC-018 | todo | |
| T-016 | Import/source scan test (stdlib only, no credentials or network) and privacy test. | NFR-003, NFR-004, AC-019, AC-020 | todo | |
| T-017 | 100k-row benchmark test. | NFR-005, AC-021 | todo | |
| T-018 | `cli.py` and `examples/nl_analytics/` (synthetic three-day transcript, committed sample response) plus `docs/0080_synthetic_data_disclosure.md`. | REQ-009, REQ-012 | todo | |
| T-020 | `writeback_sqlite.py`: `SQLiteWriter` + reader over stdlib `sqlite3` (schema from contract, `ON CONFLICT DO NOTHING` idempotency, tombstone reversal, as-of prior-insight read); runs AC-014/015/016 against both the recording writer and SQLite (`:memory:` and a temp file). First supported target, resolved by the owner 2026-09-24. | REQ-010, REQ-011, REQ-012, AC-014, AC-015, AC-016 | todo | |
| T-019 | Update `specs/README.md`, `src/quantsmith/pipelines/README.md` or package README, `docs/handoff.md`, `docs/handoffs/future_features.md`, and `CHANGELOG.md` on ship. | REQ-014 | todo | |

| T-021 | `domain.py`: apply `0081` packs (vocabulary, units, additivity, insight suppression, caveats, chart conventions), term-conflict clarification, and generic fallback. | REQ-015, REQ-017, AC-023, AC-024, AC-026 | todo | Packs and validator shipped by `0081`. |
| T-022 | Unreviewed-pack caveat and write-back refusal unless every applied pack is reviewed. | REQ-016, AC-025 | todo | |

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
| AC-013 | `test_ac013_writeback_contract_rejections` | todo |
| AC-014 | `test_ac014_dry_run_default_and_idempotent_commit` | todo |
| AC-015 | `test_ac015_approval_required_and_reversal_by_run_id` | todo |
| AC-016 | `test_ac016_since_yesterday_uses_prior_insight_as_of` | todo |
| AC-017 | `test_ac017_replay_is_byte_identical` | todo |
| AC-018 | agent-contract + `agent-catalog` gates | todo |
| AC-019 | `test_ac019_stdlib_only_no_credentials_or_network` | todo |
| AC-020 | `test_ac020_audit_redaction_and_privacy_flags` | todo |
| AC-021 | `test_ac021_benchmark_100k_rows` | todo |
| AC-023 | `test_ac023_pack_units_and_additivity_applied` | todo |
| AC-024 | `test_ac024_cross_pack_term_conflict_clarifies` | todo |
| AC-025 | `test_ac025_draft_pack_caveat_and_writeback_gate` | todo |
| AC-026 | `test_ac026_generic_fallback_and_restrict_only` | todo |
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
