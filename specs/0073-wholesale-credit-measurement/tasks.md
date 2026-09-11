# Tasks: Wholesale Credit Measurement

- **Spec:** 0073-wholesale-credit-measurement (`spec.md`, `plan.md`)
- **Last updated:** 2026-09-11

## Definition of Done (applies to every task)

- Every arithmetic result matches its corresponding `0072` golden case
  exactly, not approximately-plausibly.
- Every missing-input or unregistered-limit path raises rather than
  defaulting or silently passing through.
- No rating assignment, PD estimation, or LGD estimation anywhere in the
  module — a mechanical test enforces this, not just a docstring.
- No change to `credit_risk_knowledge.py`'s arithmetic primitives.
- Documentation and `0072`'s pack updated in the same change.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | `measure_facility`'s EAD resolution: override, or full `drawn_balance`/`limit`/`ccf`; raise on neither or a partial set. | REQ-001, NFR-001, NFR-004 | done | Matches `golden.ead.ccf_undrawn` exactly. |
| T-002 | `measure_facility`'s expected-loss branch via `basis_compatible`; withhold EL and name violated rules on mismatch, still return EAD. | REQ-002 | done | Matches `golden.el.pd_lgd_ead` and reproduces `golden.el.basis_mismatch_rejected`'s rejection. |
| T-003 | `measure_facility`'s RWA branch: computed only when a risk weight is supplied. | REQ-003 | done | Matches `golden.rwa.irb_risk_weight`. |
| T-004 | `aggregate_counterparty_exposure`: sum EAD/EL per counterparty, name basis-violated facilities separately. | REQ-004 | done | A violated facility contributes EAD but not EL, and is named, not zeroed silently. |
| T-005 | `check_counterparty_limits`: breach detection; raise on an unregistered limit. | REQ-005, NFR-004 | done | |
| T-006 | `compute_concentration`: largest share + Herfindahl index; `concentration_threshold` required, no default. | REQ-006, NFR-003, NFR-004 | done | |
| T-007 | `grade_transition_probabilities`: validated row lookup via `migration_matrix_rows`. | REQ-007 | done | Matches `golden.migration.row_stochastic`'s matrix. |
| T-008 | `run_counterparty_limit_review`: compose T-001–T-006 into one deterministic function. | REQ-008, NFR-002 | done | Two runs on identical inputs are dataclass-equal. |
| T-009 | Update `0072`'s `coverage.json` (both capabilities → `reference_runtime`), `gap_register.md` (`G-0072-002` resolved), and promote the eight previously-blocked records to `reviewed`. | REQ-009 | done | Content of the eight records is unchanged; only `review_status`/`review`/`blocked_by_gap_ids` move. |
| T-010 | Create `agents/credit_risk/counterparty_limits/` (four files); do not create `agents/credit_risk/obligor_rating/`. | REQ-010 | done | `workflow.wholesale_obligor_review` stays `adopter_plugin_via_0026`; no runtime justifies that agent yet. |
| T-011 | Add `test_module_has_no_rating_or_pd_estimation_function`, scanning the module's exported names for rating/PD-estimation-shaped functions. | NFR-003 | done | |
| T-012 | Index `0073` across `specs/README.md`, `docs/handoff.md`, `agents/README.md`, root `README.md`; update agent/spec counts. | REQ-009, REQ-010 | done | `doc-counts`, `spec-index`, `handoff-sync`, `agent-catalog` gates clean. Cites REQ-009/REQ-010 because indexing the pack updates and the new agent is how each becomes discoverable. |
| T-013 | Run the full gate suite and `pytest -q`; record evidence. | NFR-001 | done | Evidence recorded below. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_ead_from_ccf_matches_the_golden_case`, `test_ead_override_bypasses_ccf_computation`, `test_ead_with_no_input_path_raises`, `test_partial_ccf_inputs_do_not_silently_fall_back` | done |
| AC-002 | `test_expected_loss_matches_the_golden_case`, `test_basis_mismatch_withholds_expected_loss_not_a_wrong_number` | done |
| AC-003 | `test_rwa_matches_the_golden_case_and_requires_a_supplied_weight` | done |
| AC-004 | `test_aggregation_sums_ead_and_el_across_facilities_for_one_counterparty`, `test_a_basis_violation_is_named_not_treated_as_zero_loss` | done |
| AC-005 | `test_limit_check_detects_breach_and_within_limit`, `test_exposure_without_a_registered_limit_raises_not_passes_silently` | done |
| AC-006 | `test_concentration_flags_a_dominant_counterparty`, `test_concentration_threshold_is_a_required_argument_not_a_default`, `test_concentration_requires_at_least_one_exposure` | done |
| AC-007 | `test_grade_transition_probabilities_matches_the_golden_matrix`, `test_non_stochastic_matrix_is_refused`, `test_unknown_grade_is_refused` | done |
| AC-008 | `test_run_counterparty_limit_review_end_to_end`, `test_run_counterparty_limit_review_is_deterministic` | done |
| AC-009 | Manual review of `0072`'s `coverage.json`/`gap_register.md` diff against this spec | done |
| AC-010 | `agent-catalog` gate (no findings) + directory listing check | done |
| AC-011 | `test_module_has_no_rating_or_pd_estimation_function` | done |

## Validation Evidence

Captured 2026-09-11 on `claude/credit-risk-agents-spec-zttp6c`.

- `PYTHONPATH=src pytest -q tests/test_wholesale_credit_measurement.py` -> `20 passed`
- `PYTHONPATH=src python3 -m quantsmith.pipelines.credit_risk_knowledge` -> validates clean with both capabilities at `reference_runtime` and `G-0072-002` closed
- `PYTHONPATH=src pytest -q` -> full suite passes with no existing test's behavior changed
- `hooks/stages/run-stage.sh spec spec-index handoff-sync doc-counts docs-link
  source-catalog data-provenance secret-scan agent-catalog readme-sync` ->
  clean except the pre-existing `readme-sync` finding for spec `0066`
- `git diff --check` -> no whitespace errors

## Follow-ups

- A richer concentration framework (sector, geography, correlated-obligor
  clustering) beyond largest-share and Herfindahl — deferred until a real
  consumer needs it.
- `agents/credit_risk/obligor_rating/` stays uncreated. It activates only
  when a real rating/PD runtime exists — either an adopter's own model
  registered via `0026`, or a future approved spec that changes
  `workflow.wholesale_obligor_review`'s runtime boundary.
