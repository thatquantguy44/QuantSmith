# Tasks: Data Provenance & Synthetic-Data Disclosure Guardrail

- **Spec:** 0025-data-provenance-guardrail (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-09

## Definition of Done (applies to every task)

- The priority stack (actual data first, synthetic disclosed as a last
  resort) is documented and referenced by every group this slice touches.
- The gate degrades gracefully when nothing is configured, and its heuristic
  scan is documented as a heuristic, not a guarantee.
- No fabricated capability claims (this does not classify data as real vs.
  synthetic automatically).

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Add the backing standard. | REQ-001 | done | `instructions/data_provenance.md`. |
| T-002 | Add the disclosure template. | REQ-002 | done | `templates/docs/synthetic_data_disclosure.md`. |
| T-003 | Add the `data-provenance` gate. | REQ-003, NFR-001, NFR-003 | done | `hooks/stages/data-provenance-check.sh`; tested clean, flagged (docs/*.md mentioning synthetic data, no disclosure), and resolved (disclosure added). |
| T-004 | Wire `role_operations` and cross-reference existing visual/narrative standards. | REQ-004 | done | `agents/role_operations/README.md`, `rapid_scaffolder/{README,instructions}.md`; one-line cross-reference in `instructions/data_storytelling.md` and `agents/analytics/dashboard_design/instructions.md`. |
| T-005 | Wire catalogs and run validation gates. | NFR-002 | done | `specs/README.md`, root `README.md`, `hooks/README.md`, `run-stage.sh`, CI workflow; `spec agent-catalog docs-link spec-index secret-scan role-context data-provenance`; full `pytest tests/ -q`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `hooks/stages/data-provenance-check.sh` run against a fully-filled disclosure template copy | done |
| AC-002 | `hooks/stages/data-provenance-check.sh` run against a `docs/*.md` mentioning synthetic data with no disclosure present | done |
| AC-003 | Same file, re-run after adding a matching disclosure artifact | done |
| AC-004 | `hooks/stages/data-provenance-check.sh` run with neither artifact present | done |
| AC-005 | Direct inspection of `agents/role_operations/rapid_scaffolder/instructions.md` | done |

## Follow-ups

- Decide whether runtime demo/test fixtures using synthetic data by design
  (e.g. `sec_lending.py`'s `_build_synthetic()`) need a disclosure artifact
  too, or whether their existing docstring/README labeling is sufficient.
- Consider extending `dashboard_design`/`data_storytelling` beyond the
  one-line cross-reference if a concrete workflow surfaces a gap the
  existing "numbers from a governed source" rule doesn't cover.
- Consider whether the Disclosure Table should eventually be machine-checked
  row-by-row once dashboard/report artifacts share a common, parseable
  format.
