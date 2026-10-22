# Tasks: SFMeridian — Adaptive Securities-Finance Dataset Research

- **Spec:** 0121-sfmeridian-adaptive-dataset-research (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-22

## Definition of Done (applies to every task)

- Matches `plan.md`; tests name their AC; offline and deterministic on Python 3.11+.
- Standard library only; no credentials or real data; fixtures disclosed.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Port the POC intake checks and loader as the `intake` family. | REQ-001, AC-001 | done | `research/intake.py`; as-of now required. |
| T-002 | Research context validation; contradictions; no invented context. | REQ-002, AC-004 | done | `research/context.py`. |
| T-003 | `datasets[]` and `research.output_dir` in the config schema. | REQ-003, AC-021 | done | `config.py`. |
| T-004 | Reviewed templates, dialect rendering (SQLite, PostgreSQL, Oracle, Databricks; SQL Server gated), static check, read-only executor, injected connections. | REQ-004, NFR-003, AC-007 | done | `templates.py`, `sources.py`. |
| T-005 | Provenance on every query; scope labels; extra-row truncation detection. | REQ-005, AC-006 | done | |
| T-006 | The research tool catalog as `research.*` tools with pushdown. | REQ-006, REQ-007, AC-015, AC-020 | done | `analysis.py`, `tools.py`. |
| T-007 | Securities-finance rule pack with cited conventions. | REQ-008, AC-019 | done | `rules.py`. |
| T-008 | Evidence registry, coverage ledger, findings. | REQ-009, NFR-004, AC-002, AC-005, AC-023 | done | `evidence.py`. |
| T-009 | Adaptive deterministic policy; harness duplicate rejection, one transient retry, budget stop status; model token budget. | REQ-010, AC-003, AC-008 | done | `policy.py`, `agent.py`. |
| T-010 | Recommendation contract and rubric. | REQ-011, AC-018 | done | `recommend.py`. |
| T-011 | Run bundle, Vega-Lite charts, manifest, rerun command. | REQ-012, NFR-002, AC-011, AC-013, AC-014 | done | `bundle.py`, `charts.py`, `cli.py`. |
| T-012 | Sensitive, excluded, and untrusted-text handling; model payload boundary. | REQ-013, AC-009, AC-010 | done | |
| T-013 | Point-in-time availability checks with timezones. | REQ-014, AC-017 | done | |
| T-014 | Consistency probes and unpinned-view limitation. | REQ-015, AC-012 | done | |
| T-015 | Live connector smoke test, skipped unless pointers are injected. | REQ-016, AC-016 | blocked | Needs nonproduction PostgreSQL, Oracle, Databricks. |
| T-016 | `lending_data_researcher` agent, manifest, C-10, W13, handoffs, catalog rows, registry, skills export. | REQ-017, AC-022 | done | |
| T-017 | Stdlib-only import scan covers `research/`. | NFR-001, AC-024 | done | |
| T-018 | Gates green; spec index, handoff, README, counts. | NFR-005 | done | |

## Test Coverage Map

All in `tests/test_sfmeridian_research.py`.

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_intake_regression` | done |
| AC-002 | `test_coverage_accounting` | done |
| AC-003 | `test_adaptive_missingness_followup` | done |
| AC-004 | `test_missing_context_no_invention` | done |
| AC-005 | `test_evidence_integrity` | done |
| AC-006 | `test_scope_propagation` | done |
| AC-007 | `test_database_query_boundary` | done |
| AC-008 | `test_budget_and_stop_conditions` | done |
| AC-009 | `test_read_only_and_prompt_injection` | done |
| AC-010 | `test_sensitive_data_boundary` | done |
| AC-011 | `test_reproducible_analysis` | done |
| AC-012 | `test_mutable_view_provenance` | done |
| AC-013 | `test_bundle_rerun` | done |
| AC-014 | `test_chart_artifact_validation` | done |
| AC-015 | `test_pushdown_aggregate_correctness` | done |
| AC-016 | `test_live_connector_smoke` (skipped until live pointers exist) | open |
| AC-017 | `test_point_in_time_checks` | done |
| AC-018 | `test_recommendation_only_boundary` | done |
| AC-019 | `test_ac019_securities_finance_rule_pack_counts` | done |
| AC-020 | `test_ac020_tool_catalog` | done |
| AC-021 | `test_ac021_dataset_config_validation` | done |
| AC-022 | `test_ac022_agent_catalog_and_governance` | done |
| AC-023 | `test_ac023_numbers_carry_denominator_method_scope` | done |
| AC-024 | `test_ac024_stdlib_only` | done |

## Follow-ups

- AC-016 live connector smoke when nonproduction environments exist.
- Owner decision on SQL Server (POC dialect).
- `0115` catalog snapshots replace hand-declared dataset columns.
- `0116` reuses these templates' static check in its verifier.
