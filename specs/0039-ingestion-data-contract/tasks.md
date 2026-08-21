# Tasks: Ingestion Data Contract Emission

- **Spec:** 0039-ingestion-data-contract (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-11

## Definition of Done (applies to every task)

- Standard-library only; no dependency added.
- Every rendered claim traces to a field on `IngestionValidationResult`;
  nothing is stated that wasn't actually checked.
- Deterministic: the same rows, schema, and rules always return the same
  result and rendered text.
- Rendered output satisfies `hooks/stages/data-contract-check.sh`'s own
  keyword checks.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Write `validate_ingestion`, `render_data_contract`, `ColumnSpec`, `QualityRule`, `PointInTimeSpec`, `SchemaViolation`, `QualityRuleResult`, `IngestionValidationResult`. | REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, NFR-001, NFR-002 | done | Type-check table keyed by declared type name; exact-match duplicate-key detection; Grain & Keys / Missingness wording states actual findings. |
| T-002 | Write `tests/test_ingestion_data_contract.py`. | REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, NFR-001, NFR-003 | done | One test per acceptance criterion (AC-001 – AC-008); AC-006's test checks the rendered text against `data-contract-check.sh`'s own keyword regexes. |
| T-003 | Wire catalogs and handoff docs. | REQ-006 | done | `specs/README.md`, `src/quantsmith/pipelines/README.md`, root `README.md`, `docs/handoff.md`, `docs/handoffs/future_features.md`, `docs/sdk_plan.md`. |
| T-004 | Run validation gates. | NFR-004 | done | `spec`, `agent-catalog`, `docs-link`, `spec-index`; `pytest tests/ -q`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_type_violation_reported_AC_001` | done |
| AC-002 | `test_null_in_non_nullable_column_reported_AC_002` | done |
| AC-003 | `test_duplicate_key_count_AC_003` | done |
| AC-004 | `test_missingness_rule_observed_matches_actual_AC_004` | done |
| AC-005 | `test_clean_rows_no_violations_AC_005` | done |
| AC-006 | `test_rendered_contract_satisfies_gate_keywords_AC_006` | done |
| AC-007 | `test_duplicate_keys_stated_not_default_AC_007` | done |
| AC-008 | `test_deterministic_AC_008` | done |
| AC-009 | Direct inspection of `specs/README.md`, `src/quantsmith/pipelines/README.md`, root `README.md` | done |

## Follow-ups

- Take a `sources/<id>.yml` entry directly (schema/quality fields) rather
  than a separately caller-supplied schema, once a concrete workflow
  wires the two together (carried as an open question in `spec.md`).
- A live-fetch adapter (with its own `transport`-style injection seam),
  should a concrete data source need this module wired end-to-end rather
  than fed pre-pulled rows.
