# Plan: Funding Ladder Min-Cost Flow

- **Spec:** 0035-funding-ladder (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-08-10

## Approach

Add one new, dependency-free module,
`src/quantsmith/pipelines/funding_ladder.py`, that builds a bipartite
`SOURCE → tenor → obligation → SINK` network and calls `0013`'s
`min_cost_flow` directly — the same composition-not-reimplementation
pattern `0034` established for `solve_milp`. `optimization_solvers.py` is
not modified.

## Architecture & Components

```text
funding_ladder.py
  FundingTenor        -- name, tenor_days, capacity, rate
  FundingObligation    -- name, horizon_days, notional
  FundingLadderResult   -- status, total_cost, allocations, tenor_utilization

  solve_funding_ladder(tenors, obligations) -> FundingLadderResult
    node 0                      = SOURCE
    nodes 1..len(tenors)         = one per tenor
    nodes len(tenors)+1..+len(obligations)  = one per obligation
    last node                    = SINK

    edges:
      SOURCE -> tenor_i            capacity=tenor.capacity,          cost=0
      tenor_i -> obligation_j      capacity=obligation.notional,     cost=tenor.rate * obligation.horizon_days
        (edge exists only when tenor.tenor_days >= obligation.horizon_days)
      obligation_j -> SINK         capacity=obligation.notional,     cost=0

    required_flow = sum(obligation.notional for obligation in obligations)
    -> min_cost_flow(n_nodes, edges, source=0, sink=last, required_flow)   [0013, unmodified]
    -> decode edge_flows into (tenor, obligation) allocations + per-tenor utilization
```

The `obligation_j -> SINK` edge's capacity, exactly equal to that
obligation's notional, is what forces *every* obligation to be fully
funded rather than the flow concentrating on the cheapest few — combined
with `required_flow` equal to the sum of all obligations, the solver must
saturate every one of those edges or report infeasible (REQ-002, REQ-005).

## Interfaces & Data Contracts

`FundingTenor`, `FundingObligation`, and `FundingLadderResult` are the
three new (frozen) dataclasses — a minimal, direct input/output shape, no
external schema. `solve_funding_ladder` is the only public entry point.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Eligibility (tenor length vs. obligation horizon) is enforced by edge existence, not a post-hoc filter — an ineligible allocation is structurally impossible, not just checked for after the fact. |
| P10 Honest reporting | yes | A partially-fundable ladder is never presented as solved; `required_flow` plus per-obligation sink-capacity forces full funding or an explicit `"infeasible"` status. |
| P8 No silent trade-offs | yes | RISK-001 through RISK-003 are named in the spec, each with a stated mitigation; the general-treasury-not-securities-financing boundary is stated repeatedly, not left implicit. |
| P5 Reversibility | yes | New, additive module; `optimization_solvers.py` is unmodified. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | Network construction (eligibility via edge existence) | T-001 |
| REQ-002 | `obligation_j -> SINK` capacity == notional, `required_flow` == total obligations | T-001 |
| REQ-003 | `min_cost_flow`'s own cost-minimization (unmodified) | T-001 |
| REQ-004 | `FundingLadderResult.allocations` / `.tenor_utilization` decoding | T-001 |
| REQ-005 | Status propagation from `min_cost_flow` | T-001 |
| REQ-006 | `specs/README.md`, `src/quantsmith/pipelines/README.md`, root `README.md` | T-003 |
| NFR-001 | No randomness; deterministic network construction and solver call | T-001 |
| NFR-002 | Composition only — direct import of `min_cost_flow`, no reimplementation | T-001 |
| NFR-003 | Standard-library only | T-001 |
| NFR-004 | Validation gates | T-004 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Network shape | Bipartite `SOURCE → tenor → obligation → SINK`, single source/sink | A per-date, multi-period ladder with rolling repayment edges (borrow-then-repay flows back through time) | `min_cost_flow`'s API is single-commodity, single-source/sink. A true rolling ladder (funding drawn at one date, repaid and re-drawn at another) needs a materially more complex time-indexed network; the bipartite match is a clean, honestly-scoped first application — matching `0034`'s own precedent of picking the tractable, composable formulation over the maximally general one. |
| Eligibility rule | Edge existence (`tenor_days >= horizon_days`) | A post-solve filter that discards ineligible allocations | Making an ineligible allocation structurally impossible (P4, correct by construction) is stronger than solving without the constraint and checking after — the same reasoning `0007`'s projection-based feasibility already uses. |
| Full-funding guarantee | `obligation -> SINK` capacity == notional, plus `required_flow` == total obligations | Only set `required_flow` and let the solver distribute flow however is cheapest | Without the per-obligation sink cap, the cheapest solution could over-fund one obligation and under-fund another while still hitting the aggregate `required_flow` target — the per-edge cap is what makes "every obligation individually fully funded" (REQ-002) actually true, not just "the right total volume was funded somewhere." |
| Scope | Static single-snapshot ladder | A rolling, time-stepped simulation re-solving as time passes | Matches `0034`'s own single-decision scope; a rolling simulation is a materially different (and larger) problem, explicitly deferred as a Non-Goal rather than half-built. |

## Validation Strategy

`tests/test_funding_ladder.py`, one test per acceptance criterion
(AC-001 through AC-008), following `0007`/`0013`/`0034`'s own per-AC test
naming convention. Then `hooks/stages/run-stage.sh spec agent-catalog
docs-link spec-index`, the full `pytest tests/ -q`, and `git diff --check`.

## Rollout, Observability & Rollback

Rollout is a branch commit (and push, if requested). Rollback is
reverting the single commit; `optimization_solvers.py` is unmodified, so
nothing downstream is affected by a rollback.

## Open Questions

- Would per-obligation infeasibility diagnostics be worth adding once a
  concrete workflow needs finer-grained feedback than an aggregate
  `"infeasible"` status?
