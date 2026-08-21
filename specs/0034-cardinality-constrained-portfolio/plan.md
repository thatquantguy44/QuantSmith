# Plan: Cardinality-Constrained Portfolio Construction

- **Spec:** 0034-cardinality-constrained-portfolio (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-08-10

## Approach

Add one new, dependency-free module,
`src/quantsmith/pipelines/cardinality_portfolio.py`, that composes two
already-shipped solvers rather than inventing a third: `0013`'s
`solve_milp` picks the support (which names, at most `max_names`), and
`0007`'s `solve_portfolio` sizes it (mean-variance weights on the reduced
dimension). Neither existing module is modified — this is purely an
additive caller on top of both.

## Architecture & Components

```text
cardinality_portfolio.py
  CardinalitySelection            -- status, selected indices, selection objective
  select_cardinality_support()    -- MILP: variables [w_0..w_{n-1}, z_0..z_{n-1}]
                                      maximize alpha.w  s.t.
                                        sum(w) = budget
                                        w_i <= upper * z_i           (i=0..n-1)
                                        min_weight_selected * z_i <= w_i   (if > 0)
                                        z_i <= 1, z_i integer
                                        sum(z) <= max_names
                                      -> solve_milp(...)

  CardinalityPortfolioResult      -- status, weights (full length), selected indices
  cardinality_constrained_portfolio()
                                   -- 1. select_cardinality_support(...)
                                      2. build alpha_S, cov_S, w_prev_S for selected indices
                                      3. solve_portfolio(alpha_S, cov_S,
                                           ConstraintSet(n=len(S), lower=min_weight_selected, ...),
                                           gamma, w_prev_S, lambda_to)   [0007, unmodified]
                                      4. scatter w_S back into a full-length vector,
                                         zero elsewhere
```

## Interfaces & Data Contracts

No new external schema. `CardinalitySelection` and
`CardinalityPortfolioResult` are the two new (frozen) dataclasses, both
direct, minimal result types — status plus the relevant payload, mirroring
`LPResult`'s (`0013`) and the existing pipeline modules' own result-type
shape. Inputs (`alpha`, `cov`, `budget`, `lower`, `upper`, `gamma`,
`w_prev`, `lambda_to`) reuse `0007`'s existing vocabulary unchanged.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Selected-support weights are always sized by `0007`'s already-feasible-by-construction projection; the reconstruction step (scatter into a zero vector) can't introduce a nonzero weight at an unselected index. |
| P10 Honest reporting | yes | The two-stage decomposition is stated explicitly as a heuristic, not a joint MIQP optimum, in the module docstring and every doc surface this spec touches. |
| P8 No silent trade-offs | yes | RISK-001 through RISK-003 are named in the spec, each with a stated, testable mitigation (AC-003, AC-004, AC-005). |
| P5 Reversibility | yes | New, additive module; `portfolio_construction.py` and `optimization_solvers.py` are unmodified. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `select_cardinality_support` | T-001 |
| REQ-002 | `cardinality_constrained_portfolio` | T-002 |
| REQ-003 | `min_weight_selected` enforced in both the MILP constraint set and the reduced `ConstraintSet.lower` | T-001, T-002 |
| REQ-004 | Status propagation (`"infeasible"` from either stage) | T-001, T-002 |
| REQ-005 | Explicit `lower >= 0` validation | T-001, T-002 |
| REQ-006 | `specs/README.md`, `src/quantsmith/pipelines/README.md`, root `README.md` | T-004 |
| NFR-001 | No randomness; deterministic constraint construction and solver calls | T-001, T-002 |
| NFR-002 | Composition only — direct imports of `solve_milp`/`solve_portfolio`, no reimplementation | T-001, T-002 |
| NFR-003 | Standard-library only | T-001, T-002 |
| NFR-004 | Validation gates | T-005 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Cardinality approach | Two-stage heuristic (MILP select, QP size), reusing existing solvers | A from-scratch MIQP solver (branch-and-bound on the QP relaxation) | A dependency-free MIQP solver is substantially more complex (branching on integers while re-solving a QP subproblem at every node) and is a materially larger, riskier undertaking than composing two already-tested, already-shipped solvers; the two-stage approach is a well-understood practitioner technique, honestly disclosed as a heuristic (RISK-001) rather than oversold as exact. |
| Where selection support is reduced | A genuinely reduced-dimension sub-problem (extract `alpha_S`/`cov_S`, call `solve_portfolio` with `n=len(S)`) | Mask unselected names to zero via a modified `ConstraintSet` (e.g. per-name bounds) | `ConstraintSet` only supports uniform scalar bounds across all `n` names; adding per-name bounds would mean modifying `0007`'s already-shipped, tested module for a need specific to this new spec. Reducing dimensionality instead needs no change to `0007` at all (NFR-002, P5). |
| `min_weight_selected` scope | Enforced in both stages (selection MILP *and* the reduced `ConstraintSet.lower`) | Enforce only in the MILP selection stage | Enforcing it only at selection leaves the sizing stage free to size a selected name down to near-zero (RISK-003) — the whole point of the floor is a real minimum in the *final* weights, not just in an intermediate selection variable. |
| Long-only scope | Explicit, validated long-only (`lower >= 0` required) | Silently clamp a negative `lower` to 0, or attempt a long/short reformulation | `solve_lp`/`solve_milp`'s `x >= 0` assumption makes long/short a materially different problem (needs a `w = w+ - w-` split at minimum); silently clamping would misrepresent the caller's actual request. An explicit, named error (AC-005) is honest about the limitation instead of guessing at intent. |

## Validation Strategy

`tests/test_cardinality_portfolio.py`, one test per acceptance criterion
(AC-001 through AC-007), following `0007`/`0013`'s own per-AC test naming
convention. Then `hooks/stages/run-stage.sh spec agent-catalog docs-link
spec-index`, the full `pytest tests/ -q`, and `git diff --check`.

## Rollout, Observability & Rollback

Rollout is a branch commit (and push, if requested). Rollback is
reverting the single commit; `portfolio_construction.py` and
`optimization_solvers.py` are unmodified, so nothing downstream is
affected by a rollback.

## Open Questions

- Once a real usage pattern exists, is a joint-MIQP provider (behind an
  optional external solver dependency) worth adding alongside this
  heuristic, following the `adapters/dashboard_render/`-style lazy-import
  pattern, rather than replacing it?
