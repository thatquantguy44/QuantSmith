# Plan: Retail Underwriting Fairness Harness

- **Spec:** 0074-retail-underwriting-fairness-harness (`spec.md`)
- **Status:** Approved
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-09-11

## Approach

Same discipline as `0073`: compose `0072`'s existing arithmetic, add exactly
the layer `G-0072-005` named as missing, and resolve the spec's own open
question the same way `0073` resolved its structurally identical one — no
model ships, only the deterministic testing machinery around one.

`credit_risk_knowledge.py` already has `adverse_impact_ratio` (the
per-group selection-rate math) tested against `golden.fairness.adverse_
impact_ratio`. What it does not have — what `G-0072-005` names — is a way to
run that math against a raw scored population, a way to measure whether a
feature is a proxy for protected-class membership, and a way to search for a
less-discriminatory cutoff. `0074` adds those three things and composes them
into `run_fairness_harness`, the real function `decision_paths.json`'s
`hook.disparate_impact.*` identifiers resolve to.

## Architecture & Components

```text
credit_risk_knowledge.py (0072, unchanged)
  adverse_impact_ratio
                    |
                    v
retail_fairness_harness.py (0074, new)
  measure_disparity()                 -- group counts at a cutoff -> AIR
  measure_proxy_association()         -- Pearson correlation, feature vs
                                          protected-class membership
  search_less_discriminatory_alternative() -- caller-supplied candidate
                                              cutoffs -> closest eligible one,
                                              or an honest "none found"
  run_fairness_harness()              -- composes all of the above; this IS
                                          hook.disparate_impact.*
                    |
                    v
agents/credit_risk/fair_lending_review/  (new; justified by reference_runtime)
```

### Component responsibilities

| Component | Responsibility |
| --- | --- |
| `measure_disparity` | Turns a raw applicant population into the group counts `adverse_impact_ratio` needs, and returns a structured result including overall approval rate. |
| `measure_proxy_association` | The proxy-visibility obligation, made real: a dependency-free Pearson correlation between a feature and protected-class membership, refusing to compute a meaningless result on a constant feature or single-group population. |
| `search_less_discriminatory_alternative` | The LDA-search obligation, made real: evaluates caller-supplied candidate cutoffs and recommends the smallest policy change that clears the threshold within tolerance, or honestly reports none exists. |
| `run_fairness_harness` | The composed entry point; runs the search only when the baseline actually breaches the threshold. |
| `agents/credit_risk/fair_lending_review/` | Thin routing contract naming this module and the fairness obligations it tests. |

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Single-group or empty populations raise; a constant feature raises rather than returning a meaningless correlation; a breach with no search inputs raises rather than silently skipping the search; disparity threshold, candidate cutoffs, and tolerance all have no defaults. |
| P5 Reversibility | yes | Purely additive: one new module, one new agent, one spec, and updates to `0072`'s own pack. No existing runtime changes. |
| P6 Observability | yes | Every function returns a structured dataclass naming exactly what was tested and what was found (`threshold_breached`, `alternative_found`, `recommended_cutoff: None`) rather than a bare pass/fail. |
| P9 Security & data | yes | No live data source; every test fixture is a synthetic, seeded random population, not real applicant data. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `measure_disparity` | T-001 |
| REQ-002 | `measure_proxy_association` | T-002 |
| REQ-003 | `search_less_discriminatory_alternative` | T-003 |
| REQ-004 | `run_fairness_harness`'s conditional search | T-004 |
| REQ-005 | `run_fairness_harness`'s `protected_class_basis` validation | T-005 |
| REQ-006 | `0072` pack updates (coverage, gap register, decision paths, 7 records) | T-006 |
| REQ-007 | `agents/credit_risk/fair_lending_review/` | T-007 |
| NFR-001 | No import beyond stdlib + `credit_risk_knowledge` | T-001 |
| NFR-002 | `test_harness_is_deterministic` | T-004 |
| NFR-003 | Every required-argument test across T-001/T-003 | T-001, T-003 |
| NFR-004 | `test_module_has_no_scoring_or_training_function` | T-008 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Scorecard | None; every score is a caller input | Ship a toy reference scorecard alongside the harness | Mirrors `0073`'s resolution of the same question at higher stakes — a shipped scorecard risks being mistaken for a validated, ECOA-compliant model at the point of an actual adverse action. |
| Proxy measure | Pearson correlation, one feature at a time | A multivariate proxy-detection model (e.g., a small classifier predicting protected class from features) | A correlation is transparent, requires no training, and directly answers "is this feature a proxy" without introducing a second unvalidated model into a fairness-testing tool. |
| LDA recommendation rule | Closest-to-baseline eligible cutoff | Best-AIR eligible cutoff | The smallest policy change that fixes the disparity is more defensible and less disruptive than the most aggressive fix; every candidate's full result is still returned, so a caller can apply a different rule. |
| Cutoff sweep | Caller-supplied `candidate_cutoffs`, no generated default | Auto-generate a sweep (e.g., every 10 points below baseline) | An auto-generated sweep is itself a policy choice (step size, range) this module has no standing to make; the same principle as `0073`'s risk weight and `0072`'s disparity threshold. |

## Validation Strategy

Every `AC-*` is proven by `tests/test_retail_fairness_harness.py` against
synthetic, seeded populations. Where `0072`'s golden case supplies known
selection rates, the disparity test reproduces them exactly from raw
applicant records rather than pre-aggregated counts — proving the new
group-counting logic, not just the arithmetic underneath it.

## Rollout, Observability & Rollback

Additive only. Rollback is deleting the new module, test module, agent
directory, and spec directory, and reverting the seven promoted records in
`0072`'s pack. Observability is the test suite: any future change to
`credit_risk_knowledge.adverse_impact_ratio` that breaks an assumption this
module makes fails a named test here. `RISK-001` in `spec.md` names the real
operational gap this spec does not close: nothing here schedules the harness
to run repeatedly in production; that belongs to `0072`'s monitoring-plan
governance artifact.

## Open Questions

None.
