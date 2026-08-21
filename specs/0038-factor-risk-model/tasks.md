# Tasks: Factor Risk Model

- **Spec:** 0038-factor-risk-model (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-11

## Definition of Done (applies to every task)

- Standard-library only; no dependency added.
- Every decomposition's parts sum exactly (within tolerance) to the total
  they decompose.
- A dimension mismatch raises a clear, named error before any computation
  runs.
- Deterministic: the same inputs always return the same result.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Write `decompose_variance`, `marginal_contribution_to_risk`, `risk_concentration`, `stress_loss`, `VarianceDecomposition`, `RiskContributions`. | REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, NFR-001, NFR-002, NFR-003 | done | Euler-identity decomposition; dimension validation upfront. |
| T-002 | Write `tests/test_factor_risk_model.py`. | REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, NFR-001 | done | One test per acceptance criterion (AC-001 – AC-006). |
| T-003 | Wire catalogs and handoff docs. | REQ-006 | done | `specs/README.md`, `src/quantsmith/pipelines/README.md`, root `README.md`, `docs/handoff.md`, `docs/handoffs/future_features.md`, `docs/sdk_plan.md`. |
| T-004 | Run validation gates. | NFR-004 | done | `spec`, `agent-catalog`, `docs-link`, `spec-index`; `pytest tests/ -q`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_variance_decomposition_sums_exactly_AC_001` | done |
| AC-002 | `test_risk_contributions_sum_exactly_AC_002` | done |
| AC-003 | `test_concentration_reflects_dispersion_AC_003` | done |
| AC-004 | `test_stress_loss_linear_AC_004` | done |
| AC-005 | `test_dimension_mismatch_raises_AC_005` | done |
| AC-006 | `test_deterministic_AC_006` | done |
| AC-007 | Direct inspection of `specs/README.md`, `src/quantsmith/pipelines/README.md`, root `README.md` | done |

## Follow-ups

- A historical-scenario stress engine, feeding from
  `economists/macro_scenario_analyst`'s quantified indicator paths
  (carried as an open question in `spec.md`).
- Drawdown/tail (VaR/CVaR) metrics, once a return-history input shape is
  needed beyond this slice's cross-sectional scope.
