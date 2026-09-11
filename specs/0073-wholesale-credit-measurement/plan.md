# Plan: Wholesale Credit Measurement

- **Spec:** 0073-wholesale-credit-measurement (`spec.md`)
- **Status:** Approved
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-09-11

## Approach

Compose, don't reimplement — the same discipline `0077` used for `0070`/`0071`
applied here to `0072`'s own arithmetic. `credit_risk_knowledge.py` already
defines and tests `expected_loss`, `ead_from_ccf`, `rwa_from_risk_weight`,
`basis_compatible`, and `migration_matrix_rows`; `0073` imports them directly
and adds exactly the layer they were missing: facility-level composition,
counterparty aggregation, limit checking, and concentration.

The runtime-boundary split `0072`'s own `workflows.json` already declared is
load-bearing, not incidental: `workflow.wholesale_obligor_review` stays
`adopter_plugin_via_0026` because rating assignment and PD/LGD estimation are
a regulated model an institution must own. `0073` never estimates a PD or
assigns a rating — every measurement function takes PD, LGD, and risk weight
as arguments. `workflow.counterparty_limit_review` has no such boundary, so
`0073` implements it fully as `run_counterparty_limit_review`.

## Architecture & Components

```text
credit_risk_knowledge.py (0072, unchanged)
  expected_loss, ead_from_ccf, rwa_from_risk_weight,
  basis_compatible, migration_matrix_rows
                    |
                    v
wholesale_credit_measurement.py (0073, new)
  measure_facility()              -- one facility: EAD, EL (or withheld +
                                      violated_rules), RWA
  aggregate_counterparty_exposure() -- sum EAD/EL per counterparty, name
                                        basis-violated facilities separately
  check_counterparty_limits()     -- breach detection; raises on an
                                      unregistered limit
  compute_concentration()         -- largest share + Herfindahl index;
                                      concentration_threshold has no default
  grade_transition_probabilities() -- validated migration-matrix row lookup
  run_counterparty_limit_review() -- composes all of the above
                    |
                    v
agents/credit_risk/counterparty_limits/  (new; justified by reference_runtime)
```

### Component responsibilities

| Component | Responsibility |
| --- | --- |
| `measure_facility` | The measurement half of `capability.wholesale_measurement`: EAD, EL, RWA from supplied PD/LGD/risk-weight. Never estimates any of its inputs. |
| `aggregate_counterparty_exposure` | Rolls facility measurements up to counterparty level; a missing EL is named, never zeroed. |
| `check_counterparty_limits` | The breach-detection half of `capability.counterparty_limits`; refuses to pass an unregistered exposure through silently. |
| `compute_concentration` | The concentration half; threshold is always an argument. |
| `grade_transition_probabilities` | Ties `golden.migration.row_stochastic`'s validated arithmetic into a usable lookup. |
| `run_counterparty_limit_review` | `workflow.counterparty_limit_review` as one deterministic function. |
| `agents/credit_risk/counterparty_limits/` | Thin routing contract naming this module and the workflow it implements. |

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Every missing-input path (EAD, limit registration) raises rather than defaulting; a basis mismatch withholds EL rather than computing a wrong number; concentration threshold and risk weight have no defaults to silently fall back to. |
| P5 Reversibility | yes | Purely additive: one new module, one new agent, one spec, and updates to `0072`'s own pack. No existing runtime changes. |
| P6 Observability | yes | Every function returns a structured dataclass naming exactly what could and could not be computed (`violated_rules`, `facilities_with_basis_violation`, `threshold_breached`) rather than a bare number. |
| P9 Security & data | yes | No live data source; test fixtures are synthetic numbers, not real counterparty data. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `measure_facility`'s EAD resolution | T-001 |
| REQ-002 | `measure_facility`'s `basis_compatible` check | T-002 |
| REQ-003 | `measure_facility`'s RWA branch | T-003 |
| REQ-004 | `aggregate_counterparty_exposure` | T-004 |
| REQ-005 | `check_counterparty_limits` | T-005 |
| REQ-006 | `compute_concentration` | T-006 |
| REQ-007 | `grade_transition_probabilities` | T-007 |
| REQ-008 | `run_counterparty_limit_review` | T-008 |
| REQ-009 | `0072` pack updates (coverage, gap register, 8 records) | T-009 |
| REQ-010 | `agents/credit_risk/counterparty_limits/` | T-010 |
| NFR-001 | No import beyond stdlib + `credit_risk_knowledge` | T-001 |
| NFR-002 | `test_run_counterparty_limit_review_is_deterministic` | T-008 |
| NFR-003 | `test_module_has_no_rating_or_pd_estimation_function` | T-011 |
| NFR-004 | Every raise-not-default test across T-001/T-005/T-006 | T-001, T-005, T-006 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Rating/PD scope | Take PD, LGD, risk weight as inputs only | Ship a simple reference PD model (e.g., logistic scorecard) alongside the measurement math | A shipped PD model, however simple, would be mistaken for validated credit risk and would compete with an institution's own regulated model — exactly what `workflow.wholesale_obligor_review`'s `adopter_plugin_via_0026` boundary exists to prevent. |
| Concentration measure | Largest-share + Herfindahl index | A richer multi-dimensional concentration framework (sector, geography, correlation clustering) | Proportionate to what `0072`'s own capability scope claims; a richer framework is real, separate, future-consumer-driven work, not something to build speculatively now. |
| Migration matrix | A thin, validated row lookup | A full transition-probability simulation/Markov-chain engine | `0072`'s golden case only claims row-stochasticity and an absorbing default state; building a simulation engine on top would be scope well beyond what this spec's gap actually required. |

## Validation Strategy

Every `AC-*` is proven by `tests/test_wholesale_credit_measurement.py`, and
where a `0072` golden case supplies a known-correct number (EAD, EL, RWA,
migration row), the test asserts equality against that exact value rather
than an independently-derived one — the point is that this runtime
reproduces the golden cases, not that it computes something plausible.

## Rollout, Observability & Rollback

Additive only. Rollback is deleting the new module, test module, agent
directory, and spec directory, and reverting the eight promoted records in
`0072`'s pack back to their pre-`0073` state (recoverable from git history,
not from re-deriving the block). Observability is the test suite: any future
change to `credit_risk_knowledge.py`'s primitives that breaks an assumption
this module makes fails a named test here.

## Open Questions

None.
