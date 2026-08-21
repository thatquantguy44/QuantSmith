# Plan: Factor Risk Model

- **Spec:** 0038-factor-risk-model (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-08-11

## Approach

Add one new, self-contained, dependency-free module,
`src/quantsmith/pipelines/factor_risk_model.py`, implementing the
standard Barra-style factor risk decomposition as plain Python over
`Sequence[Sequence[float]]` matrices — the same vocabulary
`portfolio_construction.py` (`0007`) already uses, for consistency, though
this module has no solver to compose with (unlike `0034`/`0035`/`0036`,
which each called into `0013`).

## Architecture & Components

```text
factor_risk_model.py
  VarianceDecomposition   -- total_variance, factor_variance, specific_variance
  RiskContributions        -- asset_contributions (sum = total vol),
                               factor_contributions (sum = factor variance)

  decompose_variance(weights, exposures, factor_cov, specific_var)
      f = exposures^T . weights                      (portfolio factor exposure, len k)
      factor_variance   = f^T . factor_cov . f
      specific_variance = sum(w_i^2 * specific_var_i)
      total_variance    = factor_variance + specific_variance

  marginal_contribution_to_risk(weights, exposures, factor_cov, specific_var)
      Sigma . w  =  exposures . (factor_cov . f)  +  specific_var (elementwise) * weights
      asset_contributions_i  = weights_i * (Sigma . w)_i / sqrt(total_variance)
                                                        (Euler: sums to sqrt(total_variance))
      factor_contributions_j = f_j * (factor_cov . f)_j
                                                        (Euler: sums to factor_variance)

  risk_concentration(contributions)
      shares = contributions / sum(contributions)
      effective_number_of_bets = 1 / sum(shares_i^2)

  stress_loss(weights, exposures, factor_shock)
      f = exposures^T . weights
      loss = f . factor_shock                          (linear, first-order estimate)
```

## Interfaces & Data Contracts

`VarianceDecomposition` and `RiskContributions` are the two new (frozen)
dataclasses — minimal, direct result types. Inputs (`weights`,
`exposures`, `factor_cov`, `specific_var`, `factor_shock`) are plain
`Sequence[float]`/`Sequence[Sequence[float]]`, matching
`portfolio_construction.py`'s existing `Vector`/`Matrix` type aliases; no
new schema.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Both decompositions (variance, risk contribution) are built from the same Euler-identity algebra that *guarantees* the parts sum to the total — not a separate check bolted on after an unrelated computation. |
| P10 Honest reporting | yes | `stress_loss` is documented explicitly as a linear, first-order approximation, never presented as a full repricing. |
| P8 No silent trade-offs | yes | RISK-001 through RISK-003 are named in the spec, each with a stated mitigation. |
| P5 Reversibility | yes | New, additive, self-contained module; no existing file is modified. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `decompose_variance` | T-001 |
| REQ-002 | `marginal_contribution_to_risk` | T-001 |
| REQ-003 | `risk_concentration` | T-001 |
| REQ-004 | `stress_loss` | T-001 |
| REQ-005 | Dimension validation in every function | T-001 |
| REQ-006 | `specs/README.md`, `src/quantsmith/pipelines/README.md`, root `README.md` | T-003 |
| NFR-001 | No randomness; pure functions of their inputs | T-001 |
| NFR-002 | Standard-library only | T-001 |
| NFR-003 | Euler-identity decomposition (sums exactly by construction) | T-001 |
| NFR-004 | Validation gates | T-004 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Scope | Cross-sectional decomposition/attribution/stress only | Also cover drawdown/tail/VaR-CVaR time-series risk | Those need a return history, a materially different input shape than a single exposure/covariance snapshot; bundling both into one module would blur two different jobs. Explicit Non-Goal rather than a half-covered theme. |
| Concentration metric | Effective number of bets (`1 / sum(share_i^2)`) | A top-N-contributors share, or a raw Herfindahl index | Effective-number-of-bets is the standard risk-parity-literature metric with an intuitive unit (an equivalent count of equally-sized independent bets), and is a simple, well-known transform of the Herfindahl index rather than a second metric to maintain. |
| Stress model | Linear, first-order factor-shock P&L | A full nonlinear repricing under the shock | A full repricing needs asset-level pricing functions this SDK doesn't have; the linear approximation is the standard first pass in factor risk models and is disclosed honestly as such (RISK-001), not oversold. |
| Estimation scope | Consume an already-estimated exposure/covariance snapshot | Also estimate the factor model (regression/PCA) | Matches `0007`'s own precedent (consumes, doesn't estimate, a covariance matrix); factor-model estimation is a materially different, larger problem better scoped as its own follow-up spec if needed. |

## Validation Strategy

`tests/test_factor_risk_model.py`, one test per acceptance criterion
(AC-001 through AC-007), following `0007`/`0013`/`0034`–`0037`'s own
per-AC test naming convention. Then `hooks/stages/run-stage.sh spec
agent-catalog docs-link spec-index`, the full `pytest tests/ -q`, and
`git diff --check`.

## Rollout, Observability & Rollback

Rollout is a branch commit (and push, if requested). Rollback is
reverting the single commit; no existing module is modified.

## Open Questions

- Should a historical-scenario stress engine (replaying an actual episode
  rather than a supplied factor-shock vector) be a follow-up spec, feeding
  from `economists/macro_scenario_analyst`'s quantified indicator paths?
