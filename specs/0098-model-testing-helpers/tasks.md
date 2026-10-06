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
| AC-001 | `tests/test_model_testing_helpers.py` `::test_generators_are_deterministic_and_leave_global_state_alone_AC_001`, `::test_spd_matrix_is_symmetric_positive_definite_AC_001`, `::test_input_spec_parsing_and_bad_specs_AC_001`, `::test_constructed_instance_satisfies_its_own_kkt_conditions_AC_001`, `::test_instance_scaling_and_relaxation_helpers_AC_001`, `::test_constructed_lp_optimum_matches_scipy_oracle_AC_001`, `::test_constructed_qp_optimum_matches_scipy_oracle_AC_001`, `::test_generator_defaults_ranges_and_statistics_AC_001`, `::test_regression_dataset_semantics_AC_001`, `::test_convex_instance_shapes_validation_and_construction_properties_AC_001`, `::test_generator_coverage_of_supports_active_sets_and_magnitudes_AC_001` | done |
| AC-002 | `tests/test_model_testing_helpers.py` `::test_scaling_holds_for_homogeneous_and_fails_for_the_rest_AC_002`, `::test_permutation_invariant_and_equivariant_AC_002`, `::test_translation_idempotence_symmetry_AC_002`, `::test_monotone_detects_the_wrong_direction_AC_002`, `::test_relations_report_zero_cases_exceptions_and_hangs_honestly_AC_002`, `::test_relation_check_is_reproducible_from_its_seed_AC_002`, `::test_call_guarded_leaves_no_timer_and_restores_the_handler_AC_002`, `::test_to_jsonable_truncates_converts_and_never_emits_non_finite_AC_002`, `::test_relation_parameters_and_defaults_are_validated_AC_002`, `::test_permutation_edge_cases_AC_002`, `::test_monotone_edge_cases_and_tolerance_AC_002`, `::test_relation_counters_report_what_was_evaluated_AC_002` | done |
| AC-003 | `tests/test_model_testing_helpers.py` `::test_differential_agree_and_disagree_AC_003`, `::test_differential_exception_handling_AC_003`, `::test_differential_zero_cases_timeouts_and_bad_arguments_AC_003`, `::test_differential_accepts_explicit_inputs_and_a_named_reference_AC_003`, `::test_compare_values_covers_text_shape_nan_infinity_and_tolerance_AC_003`, `::test_differential_counts_deviations_and_ranks_the_worst_case_AC_003`, `::test_differential_does_not_agree_when_one_implementation_overflows_AC_003`, `::test_differential_reports_the_size_of_near_misses_that_still_agree_AC_003` | done |
| AC-004 | `tests/test_model_testing_helpers.py` `::test_least_squares_passes_every_regression_check_AC_004`, `::test_a_biased_fit_fails_recovery_and_orthogonality_but_not_scaling_AC_004`, `::test_a_fit_that_drops_the_intercept_is_caught_AC_004`, `::test_a_fit_that_depends_on_row_order_is_caught_AC_004`, `::test_penalised_fits_are_not_failed_for_properties_they_lack_AC_004`, `::test_noisy_recovery_uses_standard_errors_AC_004`, `::test_no_intercept_models_and_option_passthrough_AC_004`, `::test_regression_checks_report_crashes_wrong_shapes_and_zero_cases_AC_004`, `::test_regression_checks_are_reproducible_AC_004`, `::test_regression_checks_pin_counts_caps_and_the_orthogonality_measure_AC_004`, `::test_scaling_check_draws_every_column_including_the_first_AC_004` | done |
| AC-005 | `tests/test_model_testing_helpers.py` `::test_nonneg_least_squares_matches_scipy_AC_005`, `::test_kkt_holds_at_the_constructed_optimum_with_recovered_multipliers_AC_005`, `::test_kkt_names_the_failed_condition_AC_005`, `::test_kkt_with_supplied_multipliers_checks_signs_and_stationarity_AC_005`, `::test_kkt_equality_constraints_and_unconstrained_AC_005`, `::test_kkt_certifies_optimality_only_for_convex_problems_AC_005`, `::test_runner_passes_a_correct_lp_solver_AC_005`, `::test_runner_passes_a_correct_qp_solver_AC_005`, `::test_runner_fails_broken_solvers_on_the_check_each_one_breaks_AC_005`, `::test_runner_reports_crashes_hangs_and_zero_cases_AC_005`, `::test_runner_failures_reproduce_from_the_instance_seed_AC_005`, `::test_nnls_stops_and_reports_when_it_does_not_converge_AC_005`, `::test_kkt_with_inequality_and_equality_together_recovers_both_multipliers_AC_005`, `::test_kkt_stationarity_is_relative_to_the_gradient_scale_AC_005`, `::test_kkt_convexity_uses_a_numerical_tolerance_AC_005`, `::test_runner_caps_failures_and_rejects_malformed_solver_results_AC_005`, `::test_nnls_reports_its_residual_when_it_stops_early_and_empty_problems_are_convex_AC_005`, `::test_relaxation_tolerance_is_relative_to_the_optimum_AC_005` | done |
| AC-006 | `tests/test_model_testing_helpers.py` `::test_signal_beats_its_placebo_and_noise_does_not_AC_006`, `::test_a_model_that_reads_the_held_out_labels_is_flagged_AC_006`, `::test_determinism_passes_seeded_and_fails_unseeded_models_AC_006`, `::test_beats_baseline_regression_and_classification_AC_006`, `::test_noise_features_catch_a_model_that_finds_skill_without_features_AC_006`, `::test_ml_split_defaults_to_chronological_and_never_overlaps_AC_006`, `::test_ml_checks_report_crashes_bad_outputs_and_unreachable_alpha_AC_006`, `::test_ml_checks_are_reproducible_from_the_seed_AC_006`, `::test_determinism_details_AC_006`, `::test_split_validation_and_ragged_predictions_AC_006`, `::test_placebo_p_value_and_the_smallest_reachable_alpha_AC_006`, `::test_noise_feature_statistics_and_both_branches_AC_006`, `::test_determinism_notices_a_run_that_differs_in_the_middle_AC_006`, `::test_noise_features_pass_a_small_excess_inside_k_standard_errors_AC_006` | done |
| AC-007 | `tests/test_model_testing_helpers.py` `::test_cli_metamorphic_exit_codes_AC_007`, `::test_cli_metamorphic_params_and_string_relations_AC_007`, `::test_cli_output_is_standard_json_even_with_non_finite_values_AC_007`, `::test_cli_differential_exit_codes_AC_007`, `::test_cli_bad_input_exits_two_with_bad_input_AC_007` | done |
| AC-008 | `tests/test_model_helpers_on_sdk_solvers.py` `::test_solve_lp_passes_known_optimum_kkt_scaling_and_relaxation_AC_008`, `::test_solve_lp_agrees_with_scipy_on_degenerate_equality_and_max_problems_AC_008`, `::test_solve_portfolio_satisfies_kkt_so_its_answer_is_optimal_AC_008`, `::test_solve_portfolio_with_a_turnover_penalty_satisfies_kkt_AC_008`, `::test_the_kkt_check_can_tell_when_portfolio_solver_stops_early_AC_008`, `::test_solve_portfolio_is_equivariant_to_relabelling_assets_AC_008`, `::test_portfolio_variance_is_non_increasing_in_risk_aversion_AC_008` | done |
| AC-009 | `QF_DIFF_BASE=origin/main QF_STAGE_ENFORCE=1 hooks/stages/run-stage.sh` (all 35 stages, no findings; the whole-branch view CI uses), `ruff check` on every file created or changed, `uv lock --check` (unchanged), shell syntax of every hook, full `pytest tests/`: 1345 passed, 0 failed (the C++ sanitizer failure that predated this work is fixed by `0097` T-011) | done |

## Follow-ups

See "Follow-on scope" in `plan.md`.
