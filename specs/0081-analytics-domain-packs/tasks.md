# Tasks: Analytics Domain Packs for Financial Services

- **Spec:** 0081-analytics-domain-packs (`spec.md`, `plan.md`)
- **Last updated:** 2026-09-24

> Ordered, testable units of work. Every task cites the requirement(s) it advances
> and carries a Definition of Done. No task without a requirement.

## Definition of Done (applies to every task)

- Standard library only; no new dependency.
- No company data, credentials, or personal data in any pack.
- Tests in `tests/test_analytics_packs.py` name their `AC-*` and pass deterministically.
- The validator CLI exits zero on the committed catalog.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Define the pack contract (`schema_version` `0081.1`), unit and additivity vocabularies, and the README field table. | REQ-001, REQ-003, REQ-011 | done | `knowledge/analytics_packs/README.md` |
| T-002 | Draft 40 packs across seven families from general public conventions, each with reviewer agents, `builds_on`, and golden cases. | REQ-002, REQ-007 | done | All `draft`; review is a follow-up. |
| T-003 | `analytics_packs.py` validator: structure, rate-like additivity rule, insight/caveat targets, golden cases, review completeness, agent and path existence, schema version. | REQ-003, REQ-005, REQ-006, REQ-007, REQ-008, REQ-009, REQ-011, NFR-001, NFR-003 | done | |
| T-004 | `select_packs` with deterministic order, unmatched tags, term conflicts, and write-back eligibility. | REQ-004, REQ-005 | done | |
| T-005 | Catalog checks (family coverage, README sync), coverage report, and CLI. | REQ-009, REQ-010 | done | |
| T-006 | Acceptance tests AC-001–AC-014, including mutation tests that prove each rejection fires. | REQ-001, NFR-001, NFR-002 | done | |
| T-007 | Named review of each pack by a domain owner (status → `reviewed`). | REQ-005 | todo | Owner decision: reviewer per family. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_ac001_catalog_validates_clean` | done |
| AC-002 | `test_ac002_coverage_table_and_family_coverage` | done |
| AC-003 | `test_ac003_rate_like_unit_needs_rationale_to_be_additive` | done |
| AC-004 | `test_ac004_can_sum_and_contributor_suppression` | done |
| AC-005 | `test_ac005_selection_by_source_domain` | done |
| AC-006 | `test_ac006_term_conflicts_reported` | done |
| AC-007 | `test_ac007_review_gate` | done |
| AC-008 | `test_ac008_reviewer_and_builds_on_must_exist` | done |
| AC-009 | `test_ac009_deep_packs_referenced` | done |
| AC-010 | `test_ac010_golden_cases_are_checked` | done |
| AC-011 | `test_ac011_cli_and_readme_sync` | done |
| AC-012 | `test_ac012_uncovered_tags_are_info_only` | done |
| AC-013 | `test_ac013_packs_only_restrict` | done |
| AC-014 | `test_ac014_stdlib_only_and_no_sensitive_content` | done |

## Follow-ups

Tracked work intentionally deferred (no silent "temporary" shortcuts — P8).

- T-007 named review, one pack at a time.
- Adopter override mechanism (spec open question).
- Jurisdiction variants (e.g., EU/UK capital and conduct terminology) once a
  non-U.S. adopter needs them.
