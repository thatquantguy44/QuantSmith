# Plan: Financing Cost Analysis

- **Spec:** 0028-financing-cost-analysis (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-08-10

## Approach

Add `src/quantsmith/pipelines/financing_cost_analysis.py` following the
established `pipelines/` house style (frozen dataclasses, stdlib-only,
module docstring mapping guarantees to `REQ-*`/`AC-*`, e.g.
`execution_optimization.py`). Reconcile with `0023`'s securities-lending
runtime by accepting plain values (`rate_bps`, `classification`) rather
than importing its `BorrowSecurity` dataclass, which would pull `numpy`
into an otherwise dependency-free module.

## Architecture & Components

```text
FinancingLeg (kind, rate_bps, rate_asof)
FinancedPosition (position_id, side, notional, period, legs[], classification)
  -> decompose()                    -> CostDecomposition (per leg + net)
  -> financing_aware_returns()      -> FinancingAwareReturns (gross/net/drag)
  -> flag_understated_backtest()    -> [str] findings
  -> spread_sensitivity()           -> {shock_bps: net_cost}
  -> capacity_limit()               -> [CapacityFinding] (by GC/WARM/HTB)
  -> check_point_in_time()          -> [str] look-ahead findings

position_from_borrow_rate(rate_bps, classification, ...) -> FinancedPosition
  # reconciles with 0023's BorrowSecurity.rate_bps/.classification by value,
  # not by importing the numpy-dependent sec_lending module
```

## Interfaces & Data Contracts

All types are frozen dataclasses exported from
`quantsmith.pipelines.financing_cost_analysis` and re-exported from
`quantsmith.pipelines`. No external schema; see the module's docstrings for
field-level detail.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P3 Point-in-time | yes | `check_point_in_time` makes a look-ahead leg a first-class, testable finding rather than an assumed-away concern. |
| P4 Correct by construction | yes | Validation in `__post_init__` rejects invalid side/notional/leg-kind at construction time, not silently downstream. |
| NFR — dependency-free | yes | Only `dataclasses`, `datetime`, `typing` imported; reconciliation with `0023` is by value, keeping `pipelines/` numpy-free. |
| P5 Reversibility | yes | New module + tests + spec, isolated on a branch; no existing runtime touched. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `decompose`, `CostDecomposition` | T-001, T-002 |
| REQ-002 | `financing_aware_returns`, `FinancingAwareReturns` | T-001, T-002 |
| REQ-003 | `flag_understated_backtest` | T-001, T-002 |
| REQ-004 | `spread_sensitivity` | T-001, T-002 |
| REQ-005 | `capacity_limit`, `CapacityFinding` | T-001, T-002 |
| REQ-006 | Agent contract, `agents/README.md`, `specs/README.md`, `src/quantsmith/pipelines/README.md` | T-004 |
| NFR-001 | `check_point_in_time` | T-001, T-002 |
| NFR-002 | stdlib-only imports; `position_from_borrow_rate`'s by-value reconciliation | T-001 |
| NFR-003 | Pure functions over frozen dataclasses (no hidden state) | T-001, T-002 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Day-count convention | ACT/360, fixed | Parameterized day-count basis (ACT/365, ACT/ACT, 30/360) | ACT/360 is the standard money-market convention for repo/short-term borrow; a parameterized basis is a real but premature generalization without a concrete non-ACT/360 workflow to validate it against — noted as a Risk/follow-up instead. |
| Reconciliation with `0023` | Accept plain values (`rate_bps`, `classification`) via `position_from_borrow_rate` | Import `sec_lending.BorrowSecurity` directly | Importing it would make this module transitively depend on `numpy`, breaking the `pipelines/` family's dependency-free invariant for every consumer, not just this one. |
| Scope vs. `repo_financing`/`collateral_management` | Accept financing legs as structured input, not gated on those agents having runtimes | Block this spec until `repo_financing`/`collateral_management` are promoted too | The agent's own Inputs already describe "borrow/rebate, repo/funding, and margin data" as data it receives, not data it derives from another agent's runtime; gating on two unrelated promotions would delay a deliverable that doesn't actually need them. |

## Validation Strategy

Run `python -m pytest tests/test_financing_cost_analysis.py -v` to confirm
all six ACs, then the full `pytest tests/ -q`, then `hooks/stages/run-stage.sh
spec agent-catalog docs-link spec-index`, then `git diff --check`.

## Rollout, Observability & Rollback

Rollout is a branch commit (and push, if requested). Rollback is reverting
the single commit; no existing runtime or gate changes behavior.

## Open Questions

- Does a specials-aware (non-uniform) rate-shock model become worth
  building once real HTB financing data exists to validate one against?
- Should `repo_financing`/`collateral_management` be promoted next, now
  that `financing_cost_analysis` — the piece that actually consumes their
  outputs — has a tested runtime to hand off to?
