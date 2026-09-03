# Tasks: Quant Model Factory

- **Spec:** 0061-quant-model-factory (`spec.md`, `plan.md`)
- **Last updated:** 2026-09-03

## Definition of Done (applies to every task)

- Standard library only; no new dependency.
- No network call anywhere in `src/quantsmith/pipelines/quant_factory.py`
  or its tests; no imports from other `src/quantsmith/` modules.
- Deterministic: the same `FactorySpec` and ordered `LaneResult` list
  always produce the same `FactoryDecision` and ledger entry.
- Every AC has a passing test in `tests/test_quant_factory.py`.
- Spec gate passes: `hooks/stages/run-stage.sh spec`.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Write `FactorySpec`, `LaneSpec`, `LaneResult`, `ConvergenceGate`, `FactoryDecision`, `FactoryError`, `score_lane`, `FactoryRunner` (including `_converge_best_of_n`, `_converge_all_required`, `_converge_first_to_pass`, `_append_ledger`). | REQ-001 through REQ-011, NFR-001 through NFR-004 | done | `src/quantsmith/pipelines/quant_factory.py`. No imports from `src/quantsmith/`; stdlib only. |
| T-002 | Write `tests/test_quant_factory.py` — one test per AC-001 through AC-013. | REQ-001 through REQ-011, NFR-001 through NFR-004 | done | In-memory `LaneResult` fixtures; ledger tests use `tempfile.TemporaryDirectory`; no mocking. |
| T-003 | Write the `agents/quant_factory/` four-file contract and `templates/prompts/factory_run_card.md`. | REQ-012, REQ-013 | done | `README.md`, `instructions.md`, `prompt.md`, `tasks.md` in `agents/quant_factory/`; template in `templates/prompts/`. |
| T-004 | Wire catalogs and cross-references. | REQ-014 | done | `specs/README.md`, root `README.md`, `agents/README.md`. |
| T-005 | Run validation gates. | NFR-001 through NFR-004 | done | `hooks/stages/run-stage.sh spec`; `pytest tests/test_quant_factory.py -q`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_score_lane_valid_metrics_in_unit_range_AC_001` | done |
| AC-002 | `test_score_lane_leakage_flag_scores_zero_AC_002` | done |
| AC-003 | `test_score_lane_error_set_scores_zero_AC_003` | done |
| AC-004 | `test_best_of_n_approves_higher_scorer_AC_004` | done |
| AC-005 | `test_best_of_n_all_below_threshold_fails_AC_005` | done |
| AC-006 | `test_all_required_both_pass_approved_AC_006` | done |
| AC-007 | `test_all_required_leakage_flag_fails_run_AC_007` | done |
| AC-008 | `test_first_to_pass_second_lane_wins_third_skipped_AC_008` | done |
| AC-009 | `test_first_to_pass_none_pass_fails_AC_009` | done |
| AC-010 | `test_ledger_entry_written_with_required_fields_AC_010` | done |
| AC-011 | `test_duplicate_lane_id_raises_factory_error_AC_011` | done |
| AC-012 | `test_unknown_lane_id_in_result_raises_factory_error_AC_012` | done |
| AC-013 | `test_deterministic_same_inputs_same_decision_AC_013` | done |
| AC-014 | `hooks/stages/agent-catalog-check.sh` against `agents/quant_factory/` | done |
| AC-015 | Direct inspection of `specs/README.md`, `README.md`, `agents/README.md` | done |

## Follow-ups

- A `weights` vector on `ConvergenceGate` so callers can tune Sharpe vs.
  drawdown vs. return importance (deferred from spec open questions).
- A per-lane streaming callback for real-time status during long runs
  (deferred from spec open questions).
- A `pareto_front` convergence mode for multi-objective selection (noted
  in spec Assumptions as a natural fourth mode).
- Scheduling integration: a worked `ScheduleJob` example that launches a
  factory run via `0055`'s `agentic_workflow` target (similar to
  `0059`'s `schedule_registry.md`).
