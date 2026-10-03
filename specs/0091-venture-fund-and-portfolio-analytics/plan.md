# Plan: Venture Fund and Portfolio Analytics

- **Spec:** 0091-venture-fund-and-portfolio-analytics (`spec.md`)
- **Status:** Draft (built)
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-10-03

> HOW. Requires the Draft spec; `tasks.md` tracks status.

## Approach

One pure-function module that mirrors the `0083` conventions, three contract agents
that carry the decision boundaries, and tests whose expected values come from hand
arithmetic or exact rational arithmetic (not from the module). Review functions return
flags with numbers; simulations return distributions with assumption ledgers.

## Architecture & Components

```
src/quantsmith/pipelines/venture_fund_analytics.py
  normalize_flows, fund_multiples, deal_moic, xirr, net_cash_flow_profile, j_curve,
  index_level_at, ks_pme, peer_percentile, review_marks,
  simulate_fund, alpha_sensitivity, bootstrap_fund, simulate_reserves, reserve_policy_table
agents/venture_intelligence/{fund_performance_analyst,valuation_marks_reviewer,portfolio_reserve_analyst}
knowledge/venture_intelligence/{conventions,coverage,workflows,models,gaps,glossary}.json
tests/test_venture_fund_analytics.py
```

## Interfaces & Data Contracts

- Flow: `{"date", "type": "contribution" | "distribution" | "nav", "amount" >= 0, "known_at"?}`; contributions are outflows, distributions inflows, the latest NAV a terminal inflow.
- `xirr(...) -> {"irr", "roots", "iterations", "warnings", "day_count"}`.
- `review_marks(holdings, as_of, max_age_days, price_tolerance) -> [{"company_id", "code", "detail", "decision_owner"}]`.
- Simulations return `{"trials", "mean", "mcse", "q05".."q95", "p_below_1x", ..., "assumptions"}`; each trial seeds `random.Random(f"{seed}-{trial}")` so results are independent of global state and common across reserve fractions.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | As-of filtering; refusal on thin peers, bad indices, no paid-in |
| P5 Reversibility | yes | Additive |
| P6 Observability | partial | Warnings and assumption ledgers in every result |
| P9 Security & data | yes | Synthetic only; no network |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `normalize_flows`, `fund_multiples` | T-001 |
| REQ-002 | `xirr` | T-002 |
| REQ-003 | `net_cash_flow_profile`, `j_curve` | T-003 |
| REQ-004 | `index_level_at`, `ks_pme` | T-004 |
| REQ-005 | `peer_percentile` | T-005 |
| REQ-006 | `review_marks` | T-006 |
| REQ-007 | `simulate_fund`, `alpha_sensitivity` | T-007 |
| REQ-008 | `bootstrap_fund` | T-008 |
| REQ-009 | `simulate_reserves`, `reserve_policy_table` | T-009 |
| REQ-010 | conventions, validator inclusion | T-010 |
| REQ-011 | agents, coverage, workflow, indexes, registry | T-011 |
| REQ-012 | roadmap, gap, next number | T-012 |
| NFR-001 | seeded per-trial RNG, stdlib only | T-007, T-013 |
| NFR-002 | assumption ledgers, labels | T-007, T-009 |
| NFR-003 | gates, full suite | T-013 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected | Why |
| --- | --- | --- | --- |
| XIRR roots | Grid scan, report all | Single bisection | Bisection missed the 10%/20% case entirely |
| Randomness | Per-trial `Random(f"{seed}-{t}")` | Global seeding | Independent of global state; common random numbers across policies |
| Reserve model | Explicit hit/false-positive/dilution assumptions | Estimated skill | Skill cannot be estimated from synthetic data; assumptions are visible |
| Mark review | Flags with numbers | A recommended mark | Setting a mark is the valuation committee's decision |
| Predictive models | Split to `0095` | Bundle here | Each needs its own point-in-time validation |

## Validation Strategy

`tests/test_venture_fund_analytics.py` (hand and rational arithmetic, degenerate cases,
determinism, refusal paths); the pack validator for conventions and the flag registry;
gates and the full suite.

## Rollout, Observability & Rollback

Additive. Rollback: delete the module, three agent folders, tests, and revert the listed data and doc edits.

## Open Questions

NAV basis, index choice, and valuation-policy thresholds, all caller-supplied.
