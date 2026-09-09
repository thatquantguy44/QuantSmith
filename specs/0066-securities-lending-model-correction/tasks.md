# Tasks: Securities-Lending Model Correction & Expansion

- **Spec:** 0066-securities-lending-model-correction (`spec.md`, `plan.md`)
- **Last updated:** 2026-09-09

## Definition of Done (applies to every task)

- Every corrected value traces to a specific `0063` `golden.*` record.
- Every existing test continues to pass unless it hardcoded the
  pre-correction behavior being deliberately fixed (day-count, PIT
  boundary), in which case it is updated to match the correction.
- No code or doc claims an unenforced constraint.
- `gap_register.md`'s disposition is updated for every corrected row.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Make GC/WARM classification thresholds configurable. | REQ-001 | done | `SecLendingUniverseAgent.__init__` gains `gc_threshold_bps`/`warm_threshold_bps`; `_classify` takes them as params. |
| T-002 | Correct fee/rebate day-count basis to ACT/360. | REQ-002 | done | Two `/252` sites → `_DAY_COUNT_BASIS = 360.0`; annualization `*252` → `*_DAY_COUNT_BASIS`. |
| T-003 | Correct `InventoryOptimizationAgent`'s counterparty claim. | REQ-003, NFR-004 | done | Docstring rewritten; `OptimizedAllocation.counterparty` → `Optional[str] = None`; `"BEST_AVAILABLE"` placeholder removed. |
| T-004 | Tighten `check_point_in_time`'s PIT boundary. | REQ-004 | done | `rate_asof > period_end` → `rate_asof > period_start`; message reworded. |
| T-005 | Make `FinancingLeg.day_count_basis` explicit. | REQ-005 | done | New field, default 360.0; `_leg_cost` uses `leg.day_count_basis`. |
| T-006 | Update `securities_lending/instructions.md`. | REQ-006 | done | Cites `concept.repo_special`/`concept.stock_loan_special`. |
| T-007 | Update `gap_register.md` dispositions. | REQ-007 | done | D-0063-002 through 006 reference the corrected file/test. |
| T-008 | Add/update tests. | NFR-001, NFR-002 | done | See Test Coverage Map. |
| T-009 | Run validation gates and full suite. | NFR-003 | done | `spec`, `docs-link`, `spec-index`, `doc-counts`, `handoff-sync`, `agent-catalog`, `source-catalog`, `secret-scan`; full `pytest -q`; `git diff --check`. |
| T-010 | Update catalogs/roadmap. | REQ-007 (catalog visibility) | done | `specs/README.md`, `docs/handoff.md`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_classification_thresholds_are_configurable_D_0063_002` | done |
| AC-002 | `test_daily_fee_uses_act360_matches_seclend_golden_case_D_0063_003` | done |
| AC-003 | `test_optimizer_allocations_have_no_counterparty_assignment_D_0063_004` | done |
| AC-004 | `test_check_point_in_time_flags_midperiod_lookahead_D_0063_005` | done |
| AC-005 | `test_leg_day_count_basis_is_explicit_and_overridable_D_0063_006` | done |
| AC-006 | Direct inspection of `securities_lending/instructions.md` | done |
| AC-007 | Direct inspection of `gap_register.md` | done |
| AC-008 | `hooks/stages/run-stage.sh spec docs-link spec-index doc-counts handoff-sync agent-catalog source-catalog secret-scan`; full `pytest -q` | done |

## Follow-ups

- If a future spec adds real per-security×counterparty demand ingestion to
  the SQL data model, revisit D-0063-004's "honest fix" decision — a
  genuine LP reformulation becomes possible at that point (see `spec.md`'s
  Assumptions).
- `0064` (repo economics/lifecycle runtime) and `0065` (cash products)
  remain separately reserved; neither is a dependency of this slice.
