# Tasks: Test Engineering Runtime (Python and C++)

- **Spec:** 0097-test-engineering-runtime (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-03

> Every task cites a requirement and carries a Definition of Done.

## Definition of Done (applies to every task)

- Tests pass deterministically; synthetic projects only; real tools used where installed and stand-ins labelled where not.
- No test hangs; every subprocess has a timeout.
- Gates pass and no existing test regresses.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Stack detector | REQ-001 | done | |
| T-002 | Runners, result model, JUnit parsing | REQ-002, REQ-003, NFR-001 | done | CTest and GoogleTest via fixtures and a stand-in |
| T-003 | Sanitizer output parser | REQ-004 | done | |
| T-004 | Python edge-case probe and characterization tests | REQ-005, REQ-006, NFR-002 | done | |
| T-005 | C++ boundary harness with sanitizers | REQ-007, NFR-002 | done | |
| T-006 | Mutation testing with coverage | REQ-008, NFR-001, NFR-003 | done | |
| T-007 | Flakiness and order checks | REQ-009, NFR-002 | done | |
| T-008 | Command line | REQ-010 | done | |
| T-009 | Dependency, agents, indexes, docs | REQ-011 | done | |
| T-010 | Gates and full suite | NFR-004 | done | |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Acceptance Evidence

| AC | Evidence | Status |
| --- | --- | --- |
| AC-001 | `tests/test_test_engineering.py::test_detect_python_and_cpp`, `::test_detect_marks_javascript_unsupported` | done |
| AC-002 | `::test_run_command_rejects_string_argv`, `::test_run_command_times_out_and_caps_output`, `::test_cli_missing_tool_exits_two` | done |
| AC-003 | `::test_zero_tests_is_never_a_pass`, `::test_run_pytest_reports_pass_fail_and_no_tests`, `::test_parse_junit_pytest_and_gtest_forms`, `::test_parse_junit_rejects_oversize`, `::test_gtest_stand_in_binary_parses_xml` (stand-in) | done |
| AC-004 | `::test_sanitizer_parsing_kinds` | done |
| AC-005 | `::test_probe_finds_divide_by_zero_and_empty_index`, `::test_probe_respects_documented_exceptions`, `::test_probe_flags_input_mutation`, `::test_generated_characterization_tests_are_valid_python`, `::test_untyped_function_reports_nothing_probed_not_clean`, `::test_probe_isolates_relative_file_side_effects` | done |
| AC-006 | `::test_cpp_probe_finds_real_undefined_behaviour`, `::test_cpp_probe_reports_compile_failure_not_success` (real `clang++`; skipped without a compiler) | done |
| AC-007 | `::test_mutation_kills_with_good_tests_and_reports_survivor_and_uncovered`, `::test_mutation_refuses_a_failing_baseline`, `::test_mutants_are_deterministic_and_change_source` | done |
| AC-008 | `::test_flaky_detects_order_and_hash_dependence`, `::test_flaky_reports_no_tests_instead_of_stable`, `::test_to_node_id_converts_dotted_names`, `::test_order_dependence_reports_every_failing_seed` | done |
| AC-009 | `::test_cli_detect_and_exit_codes`, `::test_cli_run_returns_one_on_failure`, `::test_cli_passes_extra_args_after_double_dash`, `::test_run_passes_env_so_environment_dependent_bugs_reproduce`, `::test_run_uses_the_projects_interpreter_flag`, `::test_cli_edges_exit_two_when_nothing_probed` | done |
| AC-010 | gates (`QF_STAGE_ENFORCE=1 hooks/stages/run-stage.sh`), `uv lock --check`, full `pytest` | done |
