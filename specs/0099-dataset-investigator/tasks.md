# Tasks: Dataset Investigator

- **Spec:** 0099-dataset-investigator (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-06

> Ordered, testable units of work. Every task cites the requirement(s) it advances
> and carries a Definition of Done. No task without a requirement.

## Definition of Done (applies to every task)

- Deterministic: same inputs, config, and seed give identical outputs.
- No raw rows in any model context or report; synthetic fixtures only.
- Tests in `tests/test_dataset_investigator.py` name their `AC-*` and pass.
- The spec gate passes (`QF_STAGE_ENFORCE=1 hooks/stages/run-stage.sh spec`).

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | `io.py`: CSV, Parquet, pandas, Polars loading; fingerprints; optional-reader errors; `investigator` extra in `pyproject.toml` and `uv.lock`. | REQ-001, NFR-004, AC-001 | todo | |
| T-002 | `schema.py`: semantic roles with evidence, overrides, PII flags. | REQ-002, AC-002 | todo | |
| T-003 | `planner.py`: rule planner with reasons, size thresholds and seeded sampling, `validate_plan` for model plans. | REQ-003, REQ-017, NFR-003, AC-003 | todo | |
| T-004 | `registry.py`: decorator, registry, parameter validation, content-addressed `ToolExecution`. | REQ-004, REQ-005, NFR-001 | todo | |
| T-005 | Tools: profile, quality, distributions, relationships, segmentation. | REQ-004, REQ-006, AC-004, AC-005, AC-006 | todo | |
| T-006 | Tools: anomalies (robust z, Mahalanobis, optional Isolation Forest/LOF) and temporal (KS, PSI, breakpoint, rolling, target drift). | REQ-006, NFR-004, AC-007, AC-008 | todo | |
| T-007 | `findings.py`: candidate rules, I-score components and weights, BH adjustment, top-N. | REQ-007, AC-009 | todo | |
| T-008 | `hypotheses.py`: templates, decision rules, bounded loop, follow-ups, research questions. | REQ-008, REQ-009, NFR-003, AC-010, AC-011 | todo | |
| T-009 | `validator.py` and `context.py`: REQ-010 checks with `0080` grounding; aggregates-only, PII-masked, cell-size-bounded model context. | REQ-010, REQ-017, NFR-002, AC-012, AC-019 | todo | |
| T-010 | `report.py` and `metadata.py`: fixed-order Markdown, JSON schemas, Vega-Lite figures, `run_metadata.yaml`. | REQ-011, REQ-015, AC-013, AC-017 | todo | |
| T-011 | `export.py`: package with byte-identical modules and hashes, pipeline, manifest, generated tests, lock, README, example, `dataset-investigator` (`analyze`/`reproduce`/`rerun`). | REQ-012, REQ-013, REQ-014, NFR-001, AC-014, AC-015, AC-016 | todo | |
| T-012 | `cli.py`: `quantsmith-dataset-investigator` (`analyze`, `profile`, `plan`, `run-tool`, `validate`, `report`, `export`); console script in `pyproject.toml`. | REQ-014, REQ-016, AC-016, AC-018 | todo | |
| T-013 | `.claude/workflows/dataset-investigator.js`: Profile → Plan → Analyze → Investigate → Validate → Report → Export; reasoning agents with schemas; single-command executor steps. | REQ-016, REQ-017, AC-018 | todo | |
| T-014 | `agents/analytics/dataset_investigator/` contract and role prompts; `Spec-Driven Role` section; catalog row; regenerate `agents/agent_registry.yaml`. | REQ-016, AC-018 | todo | |
| T-015 | Safety and performance: source-unchanged and output-confinement tests, source scan for `eval`/`exec`/training/imputation/write-back, import scan, 1M-row benchmark. | NFR-002, NFR-003, NFR-004, NFR-005, AC-020, AC-021, AC-022 | todo | |
| T-016 | Docs on ship: `specs/README.md` row, package README, `docs/handoff.md`, `CHANGELOG.md`, synthetic-data disclosure for fixtures. | REQ-016 | todo | |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

Every acceptance criterion must be named by at least one test.

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_ac001_loaders_and_fingerprints` | todo |
| AC-002 | `test_ac002_semantic_roles` | todo |
| AC-003 | `test_ac003_planner_rules_and_model_plan_validation` | todo |
| AC-004 | `test_ac004_quality_defects_counted` | todo |
| AC-005 | `test_ac005_distributions_match_reference` | todo |
| AC-006 | `test_ac006_relationships_and_segments` | todo |
| AC-007 | `test_ac007_anomalies` | todo |
| AC-008 | `test_ac008_temporal_shift` | todo |
| AC-009 | `test_ac009_ranking_and_bh` | todo |
| AC-010 | `test_ac010_hypothesis_loop_rejects_denominator_effect` | todo |
| AC-011 | `test_ac011_research_questions` | todo |
| AC-012 | `test_ac012_validator_statuses` | todo |
| AC-013 | `test_ac013_report_structure_and_schemas` | todo |
| AC-014 | `test_ac014_exported_package_is_what_ran` | todo |
| AC-015 | `test_ac015_reproduce_finding_cli` | todo |
| AC-016 | `test_ac016_rerun_without_model_is_identical` | todo |
| AC-017 | `test_ac017_run_metadata_fields` | todo |
| AC-018 | `test_ac018_on_demand_entry_points` | todo |
| AC-019 | `test_ac019_model_context_has_no_rows_or_pii` | todo |
| AC-020 | `test_ac020_read_only_and_confined` | todo |
| AC-021 | `test_ac021_benchmark_1m_rows` | todo |
| AC-022 | `test_ac022_imports` | todo |

## Follow-ups

Tracked work intentionally deferred (no silent "temporary" shortcuts — P8).

- **Version 2 — controlled tool extension:** when no registered tool can test a
  hypothesis, generate a candidate module, statically validate it, generate unit
  tests, run it in a sandbox, verify, and only then register it
  (`@analysis_tool(generated=True)`). Needs its own spec; v1 forbids executing
  generated code.
- Future inputs: SQL, Snowflake, Databricks, Excel, APIs, multi-table discovery.
- `adapters/llm_runtime/` backend so the model roles can run outside Claude Code.
- `0081` domain packs as a source of column semantics.
- Comparing investigations across dataset versions; scheduled monitoring runs.
