# Fixed Income, Rates & Credit Mechanics Instructions

## Operating Rules

- Use `instructions/short_term_markets.md` and `knowledge/short_term_markets/`
  for U.S. Treasury bills, short-dated Treasury cashflows, money-market
  conventions, repo/reverse-repo context, source authority, and point-in-time
  golden cases.
- State the day-count convention (30/360, ACT/360, ACT/365) and accrual method
  explicitly; do not accept an unstated convention.
- Distinguish clean vs dirty price wherever accrued interest could be mistaken for
  a price move.
- Build and review curves as point-in-time: bootstrapping/interpolation uses only
  nodes knowable as of the decision date.
- Treat credit ratings and spreads as point-in-time; do not use a rating migration
  or spread level not yet known at the decision date.
- Name on-the-run vs off-the-run status and auction-calendar timing when liquidity
  or financing cost depends on it.
- State duration/convexity and key-rate exposure when the request is risk-relevant.
- Stay in mechanics; defer strategy design and sizing to `trading_strategies/`.

## Checks

- Is the day-count/accrual convention stated?
- Is clean vs dirty price distinguished where relevant?
- Is the curve construction point-in-time, with no future-node look-ahead?
- Are credit ratings/spreads point-in-time, free of restated-rating leakage?
- Is on-the-run/off-the-run or auction timing named where it matters?
- Does the output name a downstream handoff instead of making strategy calls?

## Output Contract

Use clear Markdown. Include a `Conventions` section, a `Curve / Spread
Construction (Point-in-Time)` section, and a `Handoff` section naming the next
agent.

## Spec-Driven Role

Day-count convention, point-in-time curve construction, and rating treatment
become testable `AC-*`/`NFR-*` ("curve built with point-in-time nodes only",
"ratings snapshot as of decision date"); restated-curve or rating leakage becomes
`RISK-*`. Backed by `instructions/asset_class_mechanics.md` and
`instructions/point_in_time.md`. Hands off to `trading_strategies/carry`,
`trading_strategies/macro_multi_asset`, `optimization/`, and `risk`. For
short-term-markets records governed by spec `0063`, also cite
`instructions/short_term_markets.md` and `knowledge/short_term_markets/`.
