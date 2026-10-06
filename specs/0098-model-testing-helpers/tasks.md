# Tasks: Model Testing Helpers (Metamorphic, Differential, and Model Checks)

- **Spec:** 0098-model-testing-helpers (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-06

> Every task cites a requirement and carries a Definition of Done.

## Definition of Done (applies to every task)

- Tests pass deterministically; synthetic data from recorded seeds only.
- Every check is proven able to fail: a test where it must pass and a test where it must fail.
- No test hangs; every evaluated callable has a timeout.
- Gates pass and no existing test regresses; no dependency added.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Guarded call, seeded generators, constructed convex instances | REQ-001, NFR-001, NFR-004 | done | |
| T-002 | Metamorphic relations and `check_relation` | REQ-002, NFR-002, NFR-004 | done | |
| T-003 | Differential runner | REQ-003, NFR-002 | done | |
| T-004 | KKT checker, instance runner, scaling and relaxation relations | REQ-005, NFR-002, NFR-003 | done | Own NNLS tested against SciPy |
| T-005 | Regression checks | REQ-004, NFR-002 | done | |
| T-006 | ML checks (determinism, placebo, noise, baseline) | REQ-006, NFR-002 | done | |
| T-007 | `metamorphic` and `differential` subcommands | REQ-007 | done | |
| T-008 | Apply to `solve_lp` and `solve_portfolio`; record `validation.md` | REQ-008, NFR-003 | done | |
| T-009 | Indexes, agents, standards, README, changelog, handoff | REQ-009 | done | Also `docs/sdk_plan.md`, which had no `0097` entry; README spec badge 83 → 84 |
| T-010 | Gates, ruff, lockfile, full suite | NFR-005 | done | One pre-existing failure at the time; fixed by `0097` T-011 |
| T-011 | Mutation-test the helpers with the `0097` runtime and close the real gaps | REQ-001, REQ-002, REQ-003, REQ-005, NFR-002, NFR-004 | done | Found an infinity comparison bug, a leaked-timer gap, an untested non-convergence branch and a misranked `worst_case`; see `validation.md` |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Acceptance Evidence

| AC | Evidence | Status |
| --- | --- | --- |
| AC-001 | `tests/test_model_testing_helpers.py` `::test_generators_are_deterministic_and_leave_global_state_alone_AC_001`, `::test_spd_matrix_is_symmetric_positive_definite_AC_001`, `::test_input_spec_parsing_and_bad_specs_AC_001`, `::test_constructed_instance_satisfies_its_own_kkt_conditions_AC_001`, `::test_instance_scaling_and_relaxation_helpers_AC_001`, `::test_constructed_lp_optimum_matches_scipy_oracle_AC_001`, `::test_constructed_qp_optimum_matches_scipy_oracle_AC_001` | done |
| AC-002 | `tests/test_model_testing_helpers.py` `::test_scaling_holds_for_homogeneous_and_fails_for_the_rest_AC_002`, `::test_permutation_invariant_and_equivariant_AC_002`, `::test_translation_idempotence_symmetry_AC_002`, `::test_monotone_detects_the_wrong_direction_AC_002`, `::test_relations_report_zero_cases_exceptions_and_hangs_honestly_AC_002`, `::test_relation_check_is_reproducible_from_its_seed_AC_002` | done |
| AC-003 | `tests/test_model_testing_helpers.py` `::test_differential_agree_and_disagree_AC_003`, `::test_differential_exception_handling_AC_003`, `::test_differential_zero_cases_timeouts_and_bad_arguments_AC_003`, `::test_differential_accepts_explicit_inputs_and_a_named_reference_AC_003` | done |
| AC-004 | `tests/test_model_testing_helpers.py` `::test_least_squares_passes_every_regression_check_AC_004`, `::test_a_biased_fit_fails_recovery_and_orthogonality_but_not_scaling_AC_004`, `::test_a_fit_that_drops_the_intercept_is_caught_AC_004`, `::test_a_fit_that_depends_on_row_order_is_caught_AC_004`, `::test_penalised_fits_are_not_failed_for_properties_they_lack_AC_004`, `::test_noisy_recovery_uses_standard_errors_AC_004`, `::test_no_intercept_models_and_option_passthrough_AC_004`, `::test_regression_checks_report_crashes_wrong_shapes_and_zero_cases_AC_004`, `::test_regression_checks_are_reproducible_AC_004` | done |
| AC-005 | `tests/test_model_testing_helpers.py` `::test_nonneg_least_squares_matches_scipy_AC_005`, `::test_kkt_holds_at_the_constructed_optimum_with_recovered_multipliers_AC_005`, `::test_kkt_names_the_failed_condition_AC_005`, `::test_kkt_with_supplied_multipliers_checks_signs_and_stationarity_AC_005`, `::test_kkt_equality_constraints_and_unconstrained_AC_005`, `::test_kkt_certifies_optimality_only_for_convex_problems_AC_005`, `::test_runner_passes_a_correct_lp_solver_AC_005`, `::test_runner_passes_a_correct_qp_solver_AC_005`, `::test_runner_fails_broken_solvers_on_the_check_each_one_breaks_AC_005`, `::test_runner_reports_crashes_hangs_and_zero_cases_AC_005`, `::test_runner_failures_reproduce_from_the_instance_seed_AC_005` | done |
| AC-006 | `tests/test_model_testing_helpers.py` `::test_signal_beats_its_placebo_and_noise_does_not_AC_006`, `::test_a_model_that_reads_the_held_out_labels_is_flagged_AC_006`, `::test_determinism_passes_seeded_and_fails_unseeded_models_AC_006`, `::test_beats_baseline_regression_and_classification_AC_006`, `::test_noise_features_catch_a_model_that_finds_skill_without_features_AC_006`, `::test_ml_split_defaults_to_chronological_and_never_overlaps_AC_006`, `::test_ml_checks_report_crashes_bad_outputs_and_unreachable_alpha_AC_006`, `::test_ml_checks_are_reproducible_from_the_seed_AC_006` | done |
| AC-007 | `tests/test_model_testing_helpers.py` `::test_cli_metamorphic_exit_codes_AC_007`, `::test_cli_metamorphic_params_and_string_relations_AC_007`, `::test_cli_output_is_standard_json_even_with_non_finite_values_AC_007`, `::test_cli_differential_exit_codes_AC_007`, `::test_cli_bad_input_exits_two_with_bad_input_AC_007` | done |
| AC-008 | `tests/test_model_helpers_on_sdk_solvers.py` `::test_solve_lp_passes_known_optimum_kkt_scaling_and_relaxation_AC_008`, `::test_solve_lp_agrees_with_scipy_on_degenerate_equality_and_max_problems_AC_008`, `::test_solve_portfolio_satisfies_kkt_so_its_answer_is_optimal_AC_008`, `::test_solve_portfolio_with_a_turnover_penalty_satisfies_kkt_AC_008`, `::test_the_kkt_check_can_tell_when_portfolio_solver_stops_early_AC_008`, `::test_solve_portfolio_is_equivariant_to_relabelling_assets_AC_008`, `::test_portfolio_variance_is_non_increasing_in_risk_aversion_AC_008` | done |
| AC-009 | `QF_STAGE_ENFORCE=1 hooks/stages/run-stage.sh` (all 35 stages, no findings), `ruff check` on every file created or changed, `uv lock --check` (unchanged), full `pytest tests/`: 1306 passed, 1 failed. The failure, `tests/test_test_engineering.py::test_cpp_probe_finds_real_undefined_behaviour`, predates this work: this environment's `clang++` has no AddressSanitizer runtime (the `0097` runtime reports `built: false`) | done, with that one pre-existing failure noted |

## Follow-ups

See "Follow-on scope" in `plan.md`.
