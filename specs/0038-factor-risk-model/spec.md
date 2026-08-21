# Spec: Factor Risk Model

- **ID:** 0038-factor-risk-model
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-08-11

## Problem & Context

`instructions/risk_management.md` (spec `0031`) states the standard
`agents/risk/` reviews against — exposure, concentration, drawdown/tail
behavior, stress response, monitorable limits — but nothing in the SDK
computes any of it. `docs/handoff.md`'s "More worked examples" line item
has stood open since the forecast spec (`0006`) shipped: "a risk-model
spec end to end." A factor risk model is the standard, well-defined quant
deliverable that operationalizes several of `risk_management.md`'s themes
at once: it decomposes portfolio variance into factor and specific risk,
attributes that risk back to individual assets and factors (so
"concentration" is a computed number, not a judgment call), and applies a
factor-shock scenario to estimate stress loss — the exact kind of
quantified scenario `economists/macro_scenario_analyst` (spec `0033`)
already produces and this model can now actually consume.

This closes the loop the same way `0028` (`financing_cost_analysis`)
closed it for `securities_financing/`: an existing backing standard
(`risk_management.md`) with no runtime behind it gets one, dependency-free
and tested, following `portfolio_construction.py`'s (`0007`) own
plain-list-of-lists matrix vocabulary rather than introducing `numpy`.

## Goals

- Add `src/quantsmith/pipelines/factor_risk_model.py`:
  `decompose_variance` (total portfolio variance = factor risk + specific
  risk, exactly), `marginal_contribution_to_risk` (Euler decomposition of
  variance into per-asset and per-factor contributions that sum exactly to
  the total), `risk_concentration` (an effective-number-of-bets measure
  over risk contributions), and `stress_loss` (a linear factor-shock P&L
  estimate).
- Every decomposition sums exactly to the total it decomposes — a
  correct-by-construction property checked in the acceptance criteria, not
  just asserted in prose.
- Validate input dimensions (exposures, factor covariance, specific
  variance, weights) explicitly; a mismatch raises a clear error rather
  than silently producing a wrong number.
- State the stress-loss estimate's actual scope honestly: a linear,
  first-order approximation from the factor model, not a full repricing.

## Non-Goals

- No factor-model *estimation* (regression, PCA, statistical factor
  construction) — this model consumes an already-estimated exposure
  matrix and factor covariance as input, the same way `portfolio_construction.py`
  consumes an already-estimated covariance matrix rather than estimating
  one itself.
- No historical/empirical stress testing (replaying an actual historical
  episode) — `stress_loss` applies a supplied factor-shock vector
  linearly; a fuller historical-scenario engine is a candidate follow-up,
  not this slice.
- No drawdown, tail (VaR/CVaR), or time-series risk metrics — those need
  a return history, not a single-period exposure/covariance snapshot; this
  slice covers the cross-sectional decomposition/attribution/stress
  themes of `risk_management.md`, not all of them.
- No point-in-time data-fetching; exposures/covariances are supplied as of
  a caller-stated snapshot date, matching `0007`'s own scope (the model
  consumes a covariance matrix, it doesn't estimate or fetch one).

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | `decompose_variance` shall compute factor variance and specific variance such that their sum equals total portfolio variance exactly. | must |
| REQ-002 | `marginal_contribution_to_risk` shall compute per-asset risk contributions summing exactly to total portfolio volatility, and per-factor variance contributions summing exactly to factor variance (Euler decomposition). | must |
| REQ-003 | `risk_concentration` shall compute an effective-number-of-bets measure from a set of risk contributions. | must |
| REQ-004 | `stress_loss` shall estimate portfolio P&L under a supplied factor-shock vector via the linear factor model, documented explicitly as a first-order approximation. | must |
| REQ-005 | The system shall validate that `exposures`, `factor_cov`, `specific_var`, and `weights` have consistent dimensions, raising a clear error on mismatch. | must |
| REQ-006 | `specs/README.md`, `src/quantsmith/pipelines/README.md`, and root `README.md` shall list the new module and its spec. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Determinism | The same inputs always return the same decomposition, contributions, concentration, and stress loss. |
| NFR-002 | Dependency isolation | Standard-library only, consistent with `0007`/`0013`. |
| NFR-003 | Correct by construction | Every decomposition's parts sum exactly (within floating-point tolerance) to the total it decomposes — checked, not just documented. |
| NFR-004 | Repository hygiene | `spec`, `agent-catalog`, `docs-link`, `spec-index` gates and the full pytest suite pass. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given weights, exposures, factor covariance, and specific variance, when `decompose_variance` runs, then factor variance plus specific variance equals total variance within tolerance. | REQ-001 |
| AC-002 | Given the same inputs, when `marginal_contribution_to_risk` runs, then the per-asset contributions sum to total portfolio volatility and the per-factor contributions sum to factor variance, both within tolerance. | REQ-002 |
| AC-003 | Given a set of risk contributions, when `risk_concentration` runs, then a more concentrated contribution set (one asset dominates) yields a lower effective-number-of-bets than a more diversified set with the same total. | REQ-003 |
| AC-004 | Given a factor-shock vector, when `stress_loss` runs, then scaling the shock by a constant scales the estimated loss by the same constant (linearity). | REQ-004 |
| AC-005 | Given `exposures`/`factor_cov`/`specific_var`/`weights` with mismatched dimensions, when any function runs, then a `ValueError` is raised naming the mismatch. | REQ-005 |
| AC-006 | Given the same inputs, when any function runs twice, then the results are identical both times. | NFR-001 |
| AC-007 | Given `specs/README.md`, `src/quantsmith/pipelines/README.md`, and root `README.md`, when inspected, then each lists spec `0038` and `factor_risk_model.py`. | REQ-006 |

## Data & Dependencies

No data dependencies. Standard-library only; no import from
`portfolio_construction.py`/`optimization_solvers.py` is required (the
module is self-contained linear algebra on the same plain
`Sequence[Sequence[float]]` vocabulary those modules already use, for
consistency, not composition — there is no shared solver to reuse here).

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | `stress_loss`'s linear approximation is mistaken for a full repricing under the shock. | A stress estimate is trusted beyond what a first-order factor-model approximation actually supports. | Stated explicitly in the module docstring, `README.md` wiring, and this spec's Non-Goals — never described as an exact repricing. |
| RISK-002 | A caller supplies an exposure/covariance snapshot that's actually stale, and the model reports a decomposition as current. | A risk read is acted on after the inputs it was computed from are no longer representative. | Out of scope for this slice to enforce mechanically (no data-fetching, see Non-Goals); the module is a pure function of its inputs — staleness is the caller's responsibility to state, matching `0007`'s own scope boundary. |
| RISK-003 | A dimension mismatch between `exposures`/`factor_cov`/`specific_var` silently produces a numerically valid but wrong decomposition instead of an error. | A risk report based on misaligned inputs looks plausible but is wrong. | REQ-005/AC-005 requires an explicit, named validation error on any dimension mismatch, checked before any computation runs. |

## Assumptions & Open Questions

- Assumption: a single-period, already-estimated exposure/covariance
  snapshot is the right scope for this slice, matching `0007`'s own
  precedent of consuming rather than estimating a covariance matrix.
- Assumption: an effective-number-of-bets measure is a sufficient first
  concentration metric; alternative concentration measures (e.g. a
  top-N-contributors share) are a candidate follow-up if a concrete
  workflow needs one.
- Open question: should a historical-scenario stress engine (replaying an
  actual episode rather than a supplied factor-shock vector) be a
  follow-up spec, feeding from `economists/macro_scenario_analyst`'s
  quantified indicator paths?

## Exceptions

None.
