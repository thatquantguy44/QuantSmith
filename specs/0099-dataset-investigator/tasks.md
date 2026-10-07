# Tasks: Dataset Investigator

- **Spec:** 0099-dataset-investigator (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-07

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
| T-001 | `io.py`: CSV, Parquet, pandas, Polars loading; fingerprints; optional-reader errors; `investigator` extra in `pyproject.toml` and `uv.lock`. | REQ-001, NFR-004, AC-001 | done | `analysis/loading.py`. CSV/TSV/Parquet/pandas/Polars (via `to_pandas`); file SHA-256 plus a content hash over a normalized frame (ISO date strings → datetimes, strings → object) so CSV and Parquet copies hash alike. `investigator` extra added and locked. |
| T-002 | `schema.py`: semantic roles with evidence, overrides, PII flags. | REQ-002, AC-002 | done | `analysis/roles.py`. Text heuristics (length, words, spaces) read a seeded 20,000-row sample; cardinality uses every row. |
| T-003 | `planner.py`: rule planner with reasons, size thresholds and seeded sampling, `validate_plan` for model plans. | REQ-003, REQ-017, NFR-003, AC-003 | done | `analysis/planner.py`. 14 named analyses; every planned call and skip carries its reason; above `sample_threshold` the reason states the sample size and seed. |
| T-004 | `registry.py`: decorator, registry, parameter validation, content-addressed `ToolExecution`. | REQ-004, REQ-005, NFR-001 | done | `analysis/registry.py`. Pydantic parameter models (`extra=forbid`), column-role eligibility per parameter, PII refusal for value-revealing tools, content-addressed execution ids. |
| T-005 | Tools: profile, quality, distributions, relationships, segmentation. | REQ-004, REQ-006, AC-004, AC-005, AC-006 | done | 21 registered tools in all (T-005 + T-006). Group labels vectorized for speed; groups below `min_cell` pooled. |
| T-006 | Tools: anomalies (robust z, Mahalanobis, optional Isolation Forest/LOF) and temporal (KS, PSI, breakpoint, rolling, target drift). | REQ-006, NFR-004, AC-007, AC-008 | done | Multivariate methods robustly standardize (log first for positive, skew > 2 columns); MCD fitted on a seeded ≤5,000-row subsample and scored on all rows; Isolation Forest and LOF flag an explicit, recorded `contamination` share (default 1%) instead of the libraries' `auto` offsets, which flagged ~20% of ordinary data; LOF uses 35 neighbours so a group of similar outliers cannot mask itself. Drift breakpoints are scanned on a seeded 100,000-row sample, then every statistic is computed on all rows; the scanned p-value is Bonferroni-corrected for the candidates scanned. |
| T-007 | `findings.py`: candidate rules, I-score components and weights, BH adjustment, top-N. | REQ-007, AC-009 | done | `analysis/findings.py`. 15 rule functions; claims written from evidence with labels in backticks; BH over every tool test plus rule-derived tests. |
| T-008 | `hypotheses.py`: templates, decision rules, bounded loop, follow-ups, research questions. | REQ-008, REQ-009, NFR-003, AC-010, AC-011 | done | `analysis/hypotheses.py`. Declarative decision rules; templates for gap, missingness, time window, shift, correlation; the denominator-effect follow-up on a rejected window-volume hypothesis; model proposals validated and grounded. |
| T-009 | `validator.py` and `context.py`: REQ-010 checks with `0080` grounding; aggregates-only, PII-masked, cell-size-bounded model context. | REQ-010, REQ-017, NFR-002, AC-012, AC-019 | done | `analysis/validator.py` (grounding reimplemented from `0080` so the package stays standalone; decimals-aware tolerance; backticked labels must be known) and `context.py`. Model review can only downgrade. |
| T-010 | `report.py` and `metadata.py`: fixed-order Markdown, JSON schemas, Matplotlib figures from recorded aggregates, `run_metadata.yaml`. | REQ-011, REQ-015, AC-013, AC-017 | done | `analysis/report.py`, `analysis/metadata.py`. Figures use the reference palette (blue/orange pair validated: CVD ΔE 24.7), one axis each. |
| T-011 | `export.py`: package with byte-identical modules and hashes, pipeline, manifest, generated tests, lock, README, example, `dataset-investigator` (`analyze`/`reproduce`/`rerun`). | REQ-012, REQ-013, REQ-014, NFR-001, AC-014, AC-015, AC-016 | done | `export.py` (runtime) builds the package around a byte-for-byte copy of `analysis/`; `analysis/pipeline.py` holds `manifest`, `reproduce`, `rerun` so the package carries them. |
| T-012 | `cli.py`: `quantsmith-dataset-investigator` (`analyze`, `profile`, `plan`, `run-tool`, `validate`, `report`, `export`); console script in `pyproject.toml`. | REQ-014, REQ-016, AC-016, AC-018 | done | `cli.py`. Step commands take `--context ROLE` so one call is one workflow step; `report --export`; exit 5 for a rejected narrative. |
| T-013 | `.claude/workflows/dataset-investigator.js`: Profile → Plan → Analyze → Investigate → Validate → Report → Export; reasoning agents with schemas; single-command executor steps. | REQ-016, REQ-017, AC-018 | done | Dry-run with real commands and stubbed reasoning agents: a model hypothesis was tested, an unbacked narrative rejected and its rewrite accepted. Default command `uv run --frozen --extra investigator quantsmith-dataset-investigator` (override `args.command`). |
| T-014 | `agents/analytics/dataset_investigator/` contract and role prompts; `Spec-Driven Role` section; catalog row; regenerate `agents/agent_registry.yaml`. | REQ-016, AC-018 | done | Registry regenerated (207 agents); catalog rows in `agents/README.md` and `agents/analytics/README.md`. |
| T-015 | Safety and performance: source-unchanged and output-confinement tests, source scan for `eval`/`exec`/training/imputation/write-back, import scan, 1M-row benchmark. | NFR-002, NFR-003, NFR-004, NFR-005, AC-020, AC-021, AC-022 | done | Benchmark: 1M × 20 in about 60 s on the development container (budget 120 s). |
| T-016 | Docs on ship: `specs/README.md` row, package README, `docs/handoff.md`, `CHANGELOG.md`, synthetic-data disclosure for fixtures. | REQ-016 | done | Synthetic data only, generated in code by `synthetic.py` (no data files committed). |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

Every acceptance criterion must be named by at least one test.

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_ac001_loaders_and_fingerprints` | done |
| AC-002 | `test_ac002_semantic_roles` | done |
| AC-003 | `test_ac003_planner_rules_and_model_plan_validation` | done |
| AC-004 | `test_ac004_quality_defects_counted` | done |
| AC-005 | `test_ac005_distributions_match_reference` | done |
| AC-006 | `test_ac006_relationships_and_segments` | done |
| AC-007 | `test_ac007_anomalies` | done |
| AC-008 | `test_ac008_temporal_shift` | done |
| AC-009 | `test_ac009_ranking_and_bh` | done |
| AC-010 | `test_ac010_hypothesis_loop_rejects_denominator_effect` | done |
| AC-011 | `test_ac011_research_questions` | done |
| AC-012 | `test_ac012_validator_statuses` | done |
| AC-013 | `test_ac013_report_structure_and_schemas` | done |
| AC-014 | `test_ac014_exported_package_is_what_ran` | done |
| AC-015 | `test_ac015_reproduce_finding_cli` | done |
| AC-016 | `test_ac016_rerun_without_model_is_identical` | done |
| AC-017 | `test_ac017_run_metadata_fields` | done |
| AC-018 | `test_ac018_on_demand_entry_points` | done |
| AC-019 | `test_ac019_model_context_has_no_rows_or_pii` | done |
| AC-020 | `test_ac020_read_only_and_confined` | done |
| AC-021 | `test_ac021_benchmark_1m_rows` | done |
| AC-022 | `test_ac022_imports` | done |

Real-data regressions (IBM Telco churn, UCI Occupancy), each a synthetic fixture
reproducing the defect: `test_ac002_numbers_stored_as_text_are_numeric`,
`test_ac003_planner_names_candidate_targets`,
`test_ac007_regimes_are_not_called_outliers`,
`test_ac010_protective_gap_tested_in_its_own_direction`,
`test_ac012_same_rows_through_another_column_are_merged`,
`test_ac013_small_values_keep_their_digits`.

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
