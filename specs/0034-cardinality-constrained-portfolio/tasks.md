# Tasks: Cardinality-Constrained Portfolio Construction

- **Spec:** 0034-cardinality-constrained-portfolio (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-10

## Definition of Done (applies to every task)

- Standard-library only; no dependency added.
- No modification to `portfolio_construction.py` (`0007`) or
  `optimization_solvers.py` (`0013`) — composition only.
- Deterministic: the same inputs always return the same result.
- Infeasibility is a stated status, never an unclear exception or a wrong
  number.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Write `select_cardinality_support` and `CardinalitySelection`. | REQ-001, REQ-003, REQ-004, REQ-005, NFR-001, NFR-002, NFR-003 | done | MILP over `[w, z]`; `min_weight_selected` and `z_i <= 1` as explicit constraint rows. |
| T-002 | Write `cardinality_constrained_portfolio` and `CardinalityPortfolioResult`. | REQ-002, REQ-003, REQ-004, REQ-005, NFR-001, NFR-002 | done | Reduced-dimension call into `solve_portfolio`; scatter back to full length. |
| T-003 | Write `tests/test_cardinality_portfolio.py`. | REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, NFR-001 | done | One test per acceptance criterion (AC-001 – AC-007). |
| T-004 | Wire catalogs and handoff docs. | REQ-006 | done | `specs/README.md`, `src/quantsmith/pipelines/README.md`, root `README.md`, `docs/handoff.md` (close items 1/5), `docs/handoffs/future_features.md`, `docs/sdk_plan.md`. |
| T-005 | Run validation gates. | NFR-004 | done | `spec`, `agent-catalog`, `docs-link`, `spec-index`; `pytest tests/ -q`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_selection_respects_max_names_AC_001` | done |
| AC-002 | `test_unselected_weights_are_zero_AC_002` | done |
| AC-003 | `test_min_weight_selected_enforced_AC_003` | done |
| AC-004 | `test_infeasible_reported_explicitly_AC_004` | done |
| AC-005 | `test_negative_lower_raises_AC_005` | done |
| AC-006 | `test_deterministic_AC_006` | done |
| AC-007 | `test_turnover_penalty_composition_AC_007` | done |
| AC-008 | Direct inspection of `specs/README.md`, `src/quantsmith/pipelines/README.md`, root `README.md` | done |

## Follow-ups

- A joint-MIQP provider behind an optional external solver dependency,
  once a concrete workflow needs one beyond this heuristic (carried as an
  open question in `spec.md`).
