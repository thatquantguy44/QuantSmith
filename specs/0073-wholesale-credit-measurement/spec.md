# Spec: Wholesale Credit Measurement

- **ID:** 0073-wholesale-credit-measurement
- **Status:** Approved
- **Author:** Joshua Lutkemuller, CFA
- **Approver:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-09-11

## Problem & Context

`0072`'s gap register named `G-0072-002` as a high-severity gap blocking two
capabilities: PD/LGD/EAD measurement and counterparty exposure/limit/
concentration review existed only as taxonomy, conventions, and golden cases
— contracts describing correct arithmetic, never a runnable pipeline. Eight
records (two capabilities, two workflows, and four golden cases) stayed
`draft` because promoting them to `reviewed` while the runtime they describe
did not exist would have been exactly the failure mode `0072`'s own `RISK-001`
warns against: a validated-looking record for content that was not yet
operationally provable.

`0072`'s workflow contracts had already drawn the boundary this spec must
respect: `workflow.wholesale_obligor_review`'s runtime classification is
`adopter_plugin_via_0026` (rating assignment and PD/LGD estimation are an
institution's own regulated model, never an SDK-shipped one), while
`workflow.counterparty_limit_review`'s is `in_sdk_reference_runtime`
(aggregation, limit checking, and concentration need no institution-specific
model). `0073` builds exactly what each boundary allows: the **measurement**
step for the first — computing expected loss, exposure at default, and
risk-weighted assets from an already-known PD, LGD, and risk weight — and the
**full workflow** for the second.

## Goals

- Implement `measure_facility`: expected loss, EAD (from a credit conversion
  factor or a supplied override), and RWA for one facility, reusing `0072`'s
  own arithmetic primitives (`expected_loss`, `ead_from_ccf`,
  `rwa_from_risk_weight`, `basis_compatible`) rather than reimplementing them.
- Implement counterparty exposure aggregation, limit checking, and
  concentration measurement as a genuine in-SDK reference runtime — no
  rating or PD model required.
- Implement `grade_transition_probabilities`, a validated lookup into a
  migration matrix, reusing `migration_matrix_rows`.
- Close `G-0072-002`: once this runtime exists and is tested, the eight
  records it was blocking are promoted to `reviewed` — content unchanged,
  only the gap that blocked them closes.
- Create `agents/credit_risk/counterparty_limits/`, justified now that
  `capability.counterparty_limits` reaches `reference_runtime` — not
  `agents/credit_risk/obligor_rating/`, since rating/PD modeling remains
  unbuilt and plugin-only.

## Non-Goals

- No rating assignment, PD estimation, or LGD estimation model. PD, LGD, and
  risk weight are always inputs to this module, never outputs of it. A test
  (`test_module_has_no_rating_or_pd_estimation_function`) makes this a
  mechanically checked claim, not a prose promise.
- No change to `credit_risk_knowledge.py`'s arithmetic — this module composes
  it, and does not duplicate or diverge from it.
- No live data feed, database connection, or vendor rating-agency
  integration. All example data in tests is synthetic.
- No `agents/credit_risk/obligor_rating/` agent. `workflow.wholesale_obligor_
  review`'s runtime boundary stays `adopter_plugin_via_0026`; creating that
  agent ahead of a real rating/PD runtime would repeat exactly the mistake
  `0072`'s own charter is gated to prevent.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | `measure_facility` shall compute EAD from either a supplied override or `drawn_balance`/`limit`/`ccf`; supplying neither, or a partial set of the latter three, shall raise rather than default. | must |
| REQ-002 | `measure_facility` shall compute expected loss only when the supplied PD and LGD pass `basis_compatible`; on a basis mismatch it shall return `expected_loss: None` and the violated rule IDs, still returning the computed EAD. | must |
| REQ-003 | `measure_facility` shall compute RWA when a risk weight is supplied and return `None` otherwise; it shall never supply a default risk weight. | must |
| REQ-004 | `aggregate_counterparty_exposure` shall sum EAD and available expected loss per counterparty and separately name any facility whose expected loss could not be computed, rather than treating it as zero. | must |
| REQ-005 | `check_counterparty_limits` shall raise when a counterparty has exposure but no registered limit, rather than passing it through unchecked. | must |
| REQ-006 | `compute_concentration` shall report the largest counterparty's share and a Herfindahl-style index across all counterparties, and shall require `concentration_threshold` as an argument with no default. | must |
| REQ-007 | `grade_transition_probabilities` shall validate row-stochasticity via `migration_matrix_rows` before returning a row, and shall raise on a non-stochastic matrix or an unknown starting grade. | must |
| REQ-008 | `run_counterparty_limit_review` shall compose REQ-001–REQ-006 into one deterministic function reproducing the same report for the same inputs. | must |
| REQ-009 | `0072`'s `coverage.json`, `gap_register.md`, and the eight previously-blocked records shall be updated to reflect this runtime's existence; `G-0072-002` shall be marked resolved and the eight records promoted to `reviewed`. | must |
| REQ-010 | `agents/credit_risk/counterparty_limits/` shall be created with the standard four files; `agents/credit_risk/obligor_rating/` shall not be created by this spec. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | No live dependency | The module imports no network client, database driver, or model-provider SDK; `pytest -q tests/test_wholesale_credit_measurement.py` passes offline. |
| NFR-002 | Determinism | `run_counterparty_limit_review` given identical inputs returns an identical report (dataclass equality). |
| NFR-003 | No hard-coded institution-specific values | Risk weight and concentration threshold are always caller-supplied; a search of the module for a bare numeric default on either finds none. |
| NFR-004 | Correct by construction | Every "missing input" and "unregistered limit" case raises rather than silently defaulting or passing through. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a facility with `drawn_balance`, `limit`, and `ccf`, when measured, then EAD matches `golden.ead.ccf_undrawn`'s value exactly; given `ead_override` instead, EAD equals it directly; given neither, or only a partial set of the three, measurement raises. | REQ-001 |
| AC-002 | Given PD and LGD on the same basis, when measured, then expected loss matches `golden.el.pd_lgd_ead`'s value; given operands matching `golden.el.basis_mismatch_rejected`'s mismatch, expected loss is `None` and `violated_rules` names `rule.basis.el_operands`, while EAD is still returned. | REQ-002 |
| AC-003 | Given a supplied risk weight, when measured, RWA matches `golden.rwa.irb_risk_weight`'s value; given none, RWA is `None`. | REQ-003 |
| AC-004 | Given two facilities under one counterparty and one with a basis violation, when aggregated, then total EAD sums both, total expected loss excludes the violated facility's contribution, and the violated facility is named in `facilities_with_basis_violation`. | REQ-004 |
| AC-005 | Given aggregated exposure above and below a supplied limit, when checked, then the above-limit counterparty is `breached` with the correct `breach_amount` and the below-limit one is `within_limit`; given exposure with no registered limit, checking raises. | REQ-005 |
| AC-006 | Given exposures of 0.1 and 0.9 share, when concentration is computed with `threshold=0.5`, then the largest share and HHI (0.82) are correct and `threshold_breached` is `True`; `concentration_threshold` has no default in the function signature. | REQ-006 |
| AC-007 | Given the same four-grade matrix as `golden.migration.row_stochastic`, when a row is requested, then it matches the source row and sums to 1; a non-stochastic matrix or an unknown grade raises. | REQ-007 |
| AC-008 | Given three facilities across two counterparties with a supplied limit registry and threshold, when the end-to-end workflow runs, then the report's breaches and concentration match the composed results of the individual functions, and two runs on the same inputs are equal. | REQ-008, NFR-002 |
| AC-009 | Given this spec merged, when `0072`'s pack is inspected, then `capability.wholesale_measurement` and `capability.counterparty_limits` are `reference_runtime`, `G-0072-002` is resolved, and the eight previously-blocked records are `reviewed`. | REQ-009 |
| AC-010 | Given `agents/credit_risk/`, when inspected after this spec, then `counterparty_limits/` exists with the standard four files and `obligor_rating/` does not. | REQ-010 |
| AC-011 | Given the module's exported names, when scanned for rating- or PD-estimation-shaped functions, then none are found. | NFR-003 (runtime-boundary honesty) |

## Data & Dependencies

- `0072-credit-risk-domain-foundation` — `credit_risk_knowledge.py`'s arithmetic primitives, consumed unchanged; `knowledge/credit_risk/`'s taxonomy, conventions, and golden cases as the acceptance target this module must reproduce.
- `0026-model-plugin-adapter` — the boundary an institution's own rating/PD model registers through; `0073` does not implement or compete with it.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | This runtime is mistaken for a rating or PD model because it sits next to one in the same capability. | An adopter treats SDK output as a substitute for their own regulated model. | REQ-010's agent-naming discipline, NFR-003's mechanical scan, and the module's own docstring state the boundary in the first paragraph, not a footnote. |
| RISK-002 | Promoting the eight previously-blocked records is treated as re-certifying their content, when only the blocking condition changed. | Overstated claim about what "reviewed" means for these records. | `gap_register.md`'s `G-0072-002` disposition and each record's `review.scope` state plainly that the definitions were already reviewed in substance; what changed is that a runtime now exists to operationalize them. |

## Assumptions & Open Questions

- Assumption: a Herfindahl-style index plus largest-single-counterparty share
  is sufficient concentration measurement for this spec's scope. A richer
  concentration framework (sector, geography, correlated-obligor clustering)
  is future work with its own consumer.

## Exceptions

None.
