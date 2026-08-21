# Securities Financing Agents

This folder groups agents for securities financing — the borrowing, lending, and
funding of securities and cash that determine whether a strategy's edge survives.
For a quant, financing is a first-class correctness concern: ignoring borrow costs,
short rebate, and funding overstates short and long-short alpha the same way leakage
does.

## Agents

| Agent | Handles |
| --- | --- |
| `securities_lending/` | Stock loan/borrow: locates and availability, GC vs hard-to-borrow (specials) rates, short rebate, recalls, buy-ins, corporate actions and manufactured dividends. |
| `repo_financing/` | Repo and reverse repo: funding positions, repo rates, term vs overnight, tri-party vs bilateral, haircuts, roll and counterparty risk. |
| `collateral_management/` | Eligibility, haircuts, margin, collateral optimization and substitution, concentration, rehypothecation, and regulatory (LCR/NSFR) impact. |
| `financing_cost_analysis/` | All-in cost of carry, borrow cost and short rebate, financing spread — and financing-aware backtesting. Tested runtime (spec `0028`). |

## Group Workflow

```
securities_lending | repo_financing | collateral_management
  → financing_cost_analysis → backtest_review + risk
```

`securities_lending/` (spec `0023`) and `financing_cost_analysis/` (spec
`0028`) have tested runtimes; `repo_financing/` and `collateral_management/`
remain agent-contract-only — `financing_cost_analysis`'s runtime accepts
their financing legs (funding rate, margin/haircut) as structured input, so
it does not require either to have a runtime first.

Model the relevant borrow, funding, and collateral terms first; consolidate them
into an all-in financing cost; then apply that cost to strategy validation and risk
review. The flow can use one or all three domain agents depending on the position.

## Shared Principles

Every securities-financing agent upholds the constitution and the quant standards:

- **Financing is a cost, not a footnote.** Borrow fees, short rebate, funding, and
  haircuts are netted from returns; a strategy's edge is stated after them.
- **Point-in-time borrow data.** Borrow rates and hard-to-borrow status change and
  are a leakage surface: a short backtest must use the borrow cost knowable at the
  time, not today's. See `instructions/point_in_time.md`.
- **Counterparty and rehypothecation risk are named.** Financing creates exposure
  to a counterparty and to reuse of posted collateral; both are made explicit.
- **Regulation is respected.** Reg SHO locate/close-out, SFTR reporting, and
  Basel/LCR/NSFR impacts are flagged where relevant.
- **Capacity reflects availability.** Hard-to-borrow names cap short capacity;
  availability and recall risk are part of the result.

## Where They Fit

Securities-financing agents feed Testing and Deployment: they make backtests
financing-aware (via `backtest_review` and the `backtest` gate's financing theme),
inform `risk` (counterparty, rehypothecation, funding), and support the
`trading_strategies/` agents whose edges depend on borrow and funding — especially
`carry/`, `event_driven_arbitrage/`, and `market_making_microstructure/`.

## Related

- `instructions/securities_financing.md` — the shared standard behind this group.
- `agents/trading_strategies/` — strategies whose net edge depends on financing.
- `agents/risk/` — counterparty, funding, and rehypothecation exposure.
