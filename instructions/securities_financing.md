# Securities Financing Instructions

## Purpose

Use this instruction set when a strategy borrows, lends, or funds securities or cash
— shorting, leverage, repo funding, or collateralized trading. It is the shared
standard behind the `agents/securities_financing/` group. The goal is that financing
cost and risk are accounted for as first-class parts of a strategy's economics, not
omitted as back-office detail.

For U.S. short-term-markets terms, roles, signs, day counts, settlement, source
authority, and golden cases, retrieve `knowledge/short_term_markets/` through
`instructions/short_term_markets.md`. Local summaries below are routing guidance,
not replacements for the canonical 0063 foundation.

## Required Inputs

- The positions (long, short, financed) and the financing they require.
- Borrow/rebate, repo/funding, and margin data, point-in-time.
- Collateral eligibility, haircuts, and margin terms.
- Counterparty and regulatory constraints.

## Expected Output

- A financing plan (borrow, repo/funding, collateral).
- Returns net of all financing legs.
- Counterparty, rehypothecation, and funding-roll risk.
- Point-in-time treatment of financing inputs.
- Regulatory flags where relevant (Reg SHO, SFTR, LCR/NSFR).

## Standards

- **Financing is a cost, not a footnote.** Net borrow fee, short rebate, funding,
  and margin from returns; state the edge after them.
- **Point-in-time financing data.** Borrow rates, hard-to-borrow status, and repo
  rates change and are a leakage surface; use what was knowable at the trade date.
  See `instructions/point_in_time.md`.
- **General collateral vs specials.** Distinguish repo specialness from
  stock-loan specialness by viewpoint. Repo specialness is positive when `GC repo
  rate - specific collateral repo rate` is positive; stock-loan specialness uses
  borrow-fee/rebate economics under the borrower/lender viewpoint.
- **Counterparty and rehypothecation risk are named.** Financing creates exposure
  to a counterparty and to reuse of posted collateral; make both explicit.
- **Capacity reflects availability.** Hard-to-borrow names and scarce funding cap
  size and carry recall/roll risk.
- **Respect regulation.** Reg SHO locate/close-out, SFTR reporting, and Basel/LCR/
  NSFR impacts are flagged where they apply.

## Checks

- Are borrow, rebate, funding, and margin all netted from returns?
- Are financing inputs point-in-time, not hindsight?
- Are general collateral and specials distinguished by product and viewpoint,
  using `knowledge/short_term_markets/`?
- Are counterparty and rehypothecation exposures named?
- Is capacity limited by borrow availability and funding, with recall/roll risk?
- Are the relevant regulatory requirements flagged?

## Common Failure Modes

- Backtesting shorts as if borrow were free, or leverage as if funding were free.
- Using today's borrow/funding rates for a historical decision (look-ahead).
- Ignoring specials, so a cheap-borrow assumption overstates the edge.
- Overstating short capacity in hard-to-borrow names.
- Missing recall/buy-in risk on shorts or roll risk on overnight funding.
- Ignoring rehypothecation and counterparty exposure in the financing chain.

## Spec-Driven Alignment

This standard backs the `agents/securities_financing/` group across Testing and
Deployment. Financing-cost accounting becomes testable `AC-*`/`NFR-*` ("returns net
of borrow/rebate/funding/margin", "point-in-time financing inputs"); counterparty,
rehypothecation, recall, and roll become `RISK-*`. Point-in-time financing data is
enforced by `instructions/point_in_time.md`; short/long-short cost realism by the
`backtest` gate's financing theme (constitution P3, P4). The group feeds
`backtest_review`, `risk`, and the `trading_strategies/` agents whose edges depend on
financing.
