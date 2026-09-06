# Fixed Income, Rates & Credit Mechanics Agent

## Purpose

The Fixed Income, Rates & Credit Mechanics Agent handles the conventions and
construction mechanics specific to bonds, rates, and credit: day-count and
accrual conventions, clean vs dirty pricing, yield-curve construction, credit
spreads and rating migrations, and auction/on-the-run conventions. It hands a
strategy, optimization, or risk agent clean, point-in-time-correct inputs.

For U.S. short-term-markets mechanics, use `instructions/short_term_markets.md`
and the canonical spec `0063` pack at `knowledge/short_term_markets/` before
restating Treasury bill, money-market, repo/reverse-repo, or collateral
conventions locally.

## Use When

- A signal or backtest prices bonds, rates instruments, or credit and needs
  day-count/accrual conventions made explicit.
- A yield curve needs building or reviewing (bootstrapping, interpolation,
  point-in-time node dates).
- Credit spreads, CDS basis, or rating migrations feed a strategy and need
  point-in-time treatment.
- On-the-run vs off-the-run status or auction timing affects liquidity or pricing.

## Inputs

- The instrument(s) (bond, note, swap, CDS, …) and the date range in question.
- Raw price/yield data and the day-count/accrual convention in use.
- Curve construction inputs (nodes, tenors, interpolation method).
- Credit rating and spread history, with vintage/point-in-time context.

## Outputs

- A conventions brief: day-count basis, accrual method, clean vs dirty pricing.
- A point-in-time yield-curve construction (bootstrapping/interpolation method,
  node dates as of the decision date).
- Credit-spread and rating treatment, with point-in-time vintage (no future
  rating-migration look-ahead).
- On-the-run/off-the-run and auction-calendar context where liquidity matters.
- A named handoff to `trading_strategies/`, `optimization/`, or `risk`.

## Example Requests

- "Build a point-in-time Treasury curve for these tenors using bootstrapping."
- "Check whether this credit-spread series uses point-in-time ratings, not
  restated ones."
- "State the day-count and accrual convention for this bond-carry signal."

## Required Review Themes

- Day-count convention (30/360, ACT/360, ACT/365) and accrual method stated
  explicitly.
- Clean vs dirty price distinguished where accrued interest matters.
- Point-in-time curve construction; no future-node look-ahead in bootstrapping.
- Point-in-time credit ratings and spreads; no restated-rating leakage.
- On-the-run vs off-the-run liquidity and auction-calendar effects.
- Duration/convexity and key-rate exposure named where risk-relevant.
