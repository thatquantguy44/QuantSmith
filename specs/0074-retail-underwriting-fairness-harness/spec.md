# Spec: Retail Underwriting Fairness Harness

- **ID:** 0074-retail-underwriting-fairness-harness
- **Status:** Approved
- **Author:** Joshua Lutkemuller, CFA
- **Approver:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-09-11

## Problem & Context

`0072`'s gap register named `G-0072-005` as the last remaining high-severity
gap: `decision_paths.json` declared `hook.disparate_impact.*` as a callable
fairness test on every consumer-facing decision path, and 0072's decision contract required
substantive fairness testing (a disparity metric, per-feature proxy
association, and a less-discriminatory-alternative search), but nothing
implemented any of it. Seven records — one capability, one workflow, two
decision paths, and three golden cases — stayed `draft` because promoting
them while the harness they describe did not exist would have been the exact
`RISK-001` failure this pack's design prevents.

`0072`'s spec left one open question standing in the way of closing this
gap: should `0074` ship an in-SDK reference scoring runtime, or stay
contract-plus-fairness-harness only? This spec resolves it: **no scorecard**.
The reasoning mirrors `0073`'s resolution of the structurally identical
question for wholesale rating and PD, at higher stakes — a shipped
scorecard, however clearly labeled "reference," risks being mistaken for a
validated, ECOA-compliant model at the point where a wrong answer is an
actual adverse action against a consumer, not an internal risk number.
Everything `G-0072-005` actually requires — disparity measurement, proxy
association, the less-discriminatory-alternative search — operates on an
already-scored population regardless of where the score came from. `0074`
builds exactly that, and nothing that scores an applicant.

## Goals

- Implement `measure_disparity`: adverse impact ratio at a supplied cutoff,
  computed from a raw applicant population and reusing `0072`'s own
  `adverse_impact_ratio` for the arithmetic.
- Implement `measure_proxy_association`: a dependency-free correlation
  between a named feature and protected-class membership, making proxy
  visibility (one of 0072's own substantive fairness obligations) a real, callable measurement rather than a
  declared-but-unmeasured obligation.
- Implement `search_less_discriminatory_alternative` and compose it into
  `run_fairness_harness`, the real implementation `hook.disparate_impact.*`
  resolves to — searching caller-supplied candidate cutoffs for one that
  clears the disparity threshold within a bounded change in overall approval
  rate, and honestly reporting when none exists.
- Close `G-0072-005`: promote the seven blocked records to `reviewed` once
  this runtime exists — content unchanged, only the blocking condition
  closed.
- Create `agents/credit_risk/fair_lending_review/`, justified now that
  `capability.retail_underwriting` reaches `reference_runtime` for its
  fairness-testing surface — not `agents/credit_risk/retail_underwriting/`,
  since no scoring or decisioning runtime exists or is being built.

## Non-Goals

- No scorecard, scoring model, or any function that produces a score from
  applicant features. Every applicant's score is always an input. A test
  (`test_module_has_no_scoring_or_training_function`) makes this a
  mechanically checked claim.
- No protected-class estimation (e.g., BISG). `0072`'s own conventions
  already scope this as a named, caller-declared method with recorded
  limitations; every applicant's `protected_class_member` value is always
  an input, observed or estimated by the caller's own declared method.
- No reason-code derivation or points-to-odds conversion runtime — those
  already exist, tested, in `credit_risk_knowledge.py`; this spec does not
  duplicate them.
- No default candidate-cutoff sweep or default approval-rate tolerance.
  Both are always caller-supplied arguments.
- No live data feed or real applicant data. All test fixtures are
  synthetic, generated with a fixed random seed for determinism.
- No `agents/credit_risk/retail_underwriting/` agent, since this spec ships
  no underwriting decision runtime, only the fairness-testing harness
  around one.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | `measure_disparity` shall compute the adverse impact ratio at a supplied cutoff from a raw applicant population, using `credit_risk_knowledge.adverse_impact_ratio` for the arithmetic; it shall raise when the population lacks either a protected-class or reference group, or is empty. | must |
| REQ-002 | `measure_proxy_association` shall compute a Pearson correlation coefficient between a named feature and protected-class membership; it shall raise when the feature or the protected-class indicator has zero variance in the population, rather than returning an undefined or meaningless value. | must |
| REQ-003 | `search_less_discriminatory_alternative` shall require `candidate_cutoffs` and `max_approval_rate_delta` as arguments with no default; among candidates that clear the disparity threshold within the allowed approval-rate change, it shall recommend the one closest to the baseline cutoff; when none clears the threshold within tolerance, it shall report `alternative_found: False` rather than recommending an ineligible cutoff. | must |
| REQ-004 | `run_fairness_harness` shall run the less-discriminatory-alternative search only when the baseline breaches the disparity threshold, and shall raise if it breaches without `candidate_cutoffs` supplied, rather than silently skipping a search 0072's decision contract requires. | must |
| REQ-005 | `run_fairness_harness` shall accept and record `protected_class_basis` (`observed` or `estimated`) on its report, and reject any other value. | must |
| REQ-006 | `0072`'s `coverage.json`, `gap_register.md`, `decision_paths.json`'s `disparate_impact_hook` fields, and the seven previously-blocked records shall be updated to reflect this runtime's existence; `G-0072-005` shall be marked resolved. | must |
| REQ-007 | `agents/credit_risk/fair_lending_review/` shall be created with the standard four files; `agents/credit_risk/retail_underwriting/` shall not be created by this spec. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | No live dependency | The module imports no model-provider SDK, network client, or database driver; `pytest -q tests/test_retail_fairness_harness.py` passes offline. |
| NFR-002 | Determinism | `run_fairness_harness` given identical inputs returns an identical report (dataclass equality). |
| NFR-003 | No hard-coded institution-specific values | Disparity threshold, candidate cutoffs, and approval-rate tolerance are always caller-supplied; a scan of the module finds no bare numeric default on any of them. |
| NFR-004 | Runtime-boundary honesty | No function in this module scores an applicant, trains a model, or estimates protected-class membership — checked mechanically, not only documented. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a population matching `golden.fairness.adverse_impact_ratio`'s selection rates, when measured, then `measure_disparity` reproduces its 0.36/0.60/0.6 values exactly; given a single-group population, measurement raises. | REQ-001 |
| AC-002 | Given a feature that differs systematically by protected-class membership, when proxy association is measured, then the correlation reflects that difference in sign and magnitude; given a constant feature or a single-group population, measurement raises. | REQ-002 |
| AC-003 | Given a population and a disparity threshold, when searched over supplied candidate cutoffs with a supplied tolerance, then the recommended cutoff is the closest-to-baseline candidate that both clears the threshold and stays within the tolerance; given no candidate clears it within tolerance, `alternative_found` is `False` and `recommended_cutoff` is `None`. | REQ-003 |
| AC-004 | Given a population whose baseline does not breach the threshold, when the harness runs, then no alternative search occurs; given a breach with no candidate cutoffs supplied, the harness raises naming the obligation it would otherwise skip. | REQ-004 |
| AC-005 | Given an unknown `protected_class_basis` value, when the harness runs, then it raises; given `observed` or `estimated`, the value is recorded on the report unchanged. | REQ-005 |
| AC-006 | Given this spec merged, when `0072`'s pack is inspected, then `capability.retail_underwriting` is `reference_runtime`, `G-0072-005` is resolved, and the seven previously-blocked records are `reviewed`. | REQ-006 |
| AC-007 | Given `agents/credit_risk/`, when inspected after this spec, then `fair_lending_review/` exists with the standard four files and `retail_underwriting/` does not. | REQ-007 |
| AC-008 | Given the module's exported names, when scanned for scoring- or training-shaped functions, then none are found. | NFR-004 |

## Data & Dependencies

- `0072-credit-risk-domain-foundation` — `credit_risk_knowledge.py`'s `adverse_impact_ratio`, consumed unchanged; `knowledge/credit_risk/`'s `decision_paths.json` fairness obligations and golden cases as the acceptance target.
- `0073-wholesale-credit-measurement` — the precedent this spec's scorecard resolution follows: keep the regulated model out, ship the deterministic math and safety checks around it.
- `0026-model-plugin-adapter` — the boundary an institution's own scoring model registers through; `0074` does not implement or compete with it.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | The harness is run once at model launch and never again, missing drift in disparity as the scored population changes over time. | A model that was compliant at launch silently becomes non-compliant. | Out of this spec's scope to enforce operationally, but stated plainly here: `run_fairness_harness` is designed to be called repeatedly (e.g., on every monitoring cycle), and `0072`'s `governance.json` monitoring-plan artifact is the right place to require that cadence. |
| RISK-002 | A caller treats `alternative_found: False` as permission to do nothing, rather than as the trigger for 0072's required business-need-rationale documentation. | An undocumented decision to retain a disparate model. | The harness's job ends at reporting the honest result; `0072`'s `decision_paths.json` `less_discriminatory_alternative.outcome_required` field is the structural requirement that a human record one of the two outcomes. |
| RISK-003 | The Pearson-correlation proxy measure misses a non-linear or categorical proxy relationship. | A real proxy goes undetected because it isn't linear. | Stated as a known limitation in the module docstring; a richer association measure (e.g., mutual information for categorical features) is real, separate, future work once a real consumer needs it. |

## Assumptions & Open Questions

- Assumption: a single Pearson correlation coefficient per feature is a
  sufficient first-pass proxy measure for this spec's scope. Non-linear or
  categorical proxy detection is real, separate future work.
- Assumption: the closest-to-baseline eligible cutoff is the right
  recommendation policy for the LDA search — the smallest policy change
  that fixes the disparity, not the most aggressive one. A future consumer
  may want a different selection rule (e.g., best overall AIR); this spec's
  functions return every candidate's full result, so a caller can apply a
  different rule without re-running the search.

## Exceptions

None.
