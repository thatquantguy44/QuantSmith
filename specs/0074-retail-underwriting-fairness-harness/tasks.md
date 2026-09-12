# Tasks: Retail Underwriting Fairness Harness

- **Spec:** 0074-retail-underwriting-fairness-harness (`spec.md`, `plan.md`)
- **Last updated:** 2026-09-11

## Definition of Done (applies to every task)

- Every disparity computation reproduces the corresponding `0072` golden
  case exactly, not approximately.
- No function in this module scores an applicant, trains a model, or
  estimates protected-class membership — a mechanical test enforces this.
- Disparity threshold, candidate cutoffs, and approval-rate tolerance are
  always caller-supplied, never defaulted.
- Documentation and `0072`'s pack updated in the same change.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | `measure_disparity`: group counts at a cutoff from a raw applicant population, reusing `adverse_impact_ratio`; raise on a single-group or empty population. | REQ-001, NFR-001, NFR-003 | done | Reproduces `golden.fairness.adverse_impact_ratio`'s 0.36/0.60/0.6 exactly. |
| T-002 | `measure_proxy_association`: Pearson correlation between a feature and protected-class membership; raise on a constant feature or single-group population. | REQ-002 | done | |
| T-003 | `search_less_discriminatory_alternative`: require `candidate_cutoffs`/`max_approval_rate_delta`; recommend the closest-to-baseline eligible candidate; honestly report none found when none clears the threshold within tolerance. | REQ-003, NFR-003 | done | Both branches (found / not found) verified against real synthetic populations before any test was written to assert them. |
| T-004 | `run_fairness_harness`: run the search only on a breach; raise if breached with no search inputs. | REQ-004, NFR-002 | done | Two runs on identical inputs are dataclass-equal. |
| T-005 | `run_fairness_harness`'s `protected_class_basis` validation. | REQ-005 | done | |
| T-006 | Update `0072`'s `coverage.json` (`capability.retail_underwriting` → `reference_runtime`), `gap_register.md` (`G-0072-005` resolved), `decision_paths.json`'s `disparate_impact_hook` fields, and promote the seven previously-blocked records to `reviewed`. | REQ-006 | done | Content of the seven records is unchanged; only `review_status`/`review`/`blocked_by_gap_ids` move. |
| T-007 | Create `agents/credit_risk/fair_lending_review/` (four files); do not create `agents/credit_risk/retail_underwriting/`. | REQ-007 | done | No scoring or decisioning runtime exists to justify that agent. |
| T-008 | Add `test_module_has_no_scoring_or_training_function`, scanning the module's exported names for scoring/training-shaped functions. | NFR-004 | done | |
| T-009 | Index `0074` across `specs/README.md`, `docs/handoff.md`, `agents/README.md`, root `README.md`; update agent/spec counts. | REQ-006, REQ-007 | done | `doc-counts`, `spec-index`, `handoff-sync`, `agent-catalog` gates clean. |
| T-010 | Run the full gate suite and `pytest -q`; record evidence. | NFR-001 | done | Evidence recorded below. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_disparity_matches_the_golden_case_shape`, `test_disparity_requires_both_groups`, `test_disparity_requires_at_least_one_applicant` | done |
| AC-002 | `test_proxy_association_detects_a_real_correlation`, `test_proxy_association_rejects_a_constant_feature`, `test_proxy_association_rejects_a_single_group_population` | done |
| AC-003 | `test_lda_search_requires_supplied_candidates_and_tolerance`, `test_lda_search_finds_an_alternative_within_tolerance`, `test_lda_search_honestly_reports_no_alternative_within_tolerance` | done |
| AC-004 | `test_harness_skips_lda_search_when_not_breached`, `test_harness_requires_lda_inputs_when_breached` | done |
| AC-005 | `test_harness_rejects_unknown_protected_class_basis` | done |
| AC-006 | Manual review of `0072`'s `coverage.json`/`gap_register.md`/`decision_paths.json` diff against this spec | done |
| AC-007 | `agent-catalog` gate (no findings) + directory listing check | done |
| AC-008 | `test_module_has_no_scoring_or_training_function` | done |

## Validation Evidence

Captured 2026-09-11 on `claude/credit-risk-agents-spec-zttp6c`.

- `PYTHONPATH=src pytest -q tests/test_retail_fairness_harness.py` -> `15 passed`
- `PYTHONPATH=src python3 -m quantsmith.pipelines.credit_risk_knowledge` -> validates clean with `capability.retail_underwriting` at `reference_runtime` and `G-0072-005` closed
- `PYTHONPATH=src pytest -q` -> full suite passes with no existing test's behavior changed
- `hooks/stages/run-stage.sh spec spec-index handoff-sync doc-counts docs-link
  source-catalog data-provenance secret-scan agent-catalog readme-sync` ->
  clean except the pre-existing `readme-sync` finding for spec `0066`
- `git diff --check` -> no whitespace errors

## Follow-ups

- A richer proxy-association measure (mutual information, categorical
  features) beyond Pearson correlation — deferred until a real consumer
  needs it.
- Scheduling `run_fairness_harness` to run repeatedly against a live scored
  population (not just once at model launch) is real, separate work for
  `0072`'s model-monitoring governance artifact, not this spec.
- `agents/credit_risk/retail_underwriting/` stays uncreated. It activates
  only when a real scoring/decisioning runtime exists — an adopter's own
  model registered via `0026`, or a future approved spec that changes the
  scorecard resolution this spec made.
