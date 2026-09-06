# Financing Cost Analysis Instructions

## Operating Rules

- Use `instructions/short_term_markets.md` and `knowledge/short_term_markets/`
  before interpreting U.S. repo, securities-lending, cash-product, haircut,
  margin, day-count, or specialness conventions.
- Net every financing leg: borrow fee, short rebate, repo/funding, and margin cost.
- Never let a short or leveraged backtest report returns gross of financing.
- Use point-in-time financing inputs (borrow, funding, margin), not today's.
- Decompose the all-in cost of carry so each leg is visible.
- Quantify the financing spread and its sensitivity to rates and specials.
- Reflect financing in capacity: expensive or scarce funding caps size.
- Reconcile financing assumptions with the securities-lending and repo agents.

## Checks

- Are borrow, rebate, funding, and margin all netted from returns?
- Do short and long-short backtests pay to borrow and fund?
- Are financing inputs point-in-time?
- Is the cost of carry decomposed by leg?
- Is the financing spread's sensitivity quantified?
- Is capacity adjusted for financing cost and availability?

## Output Contract

Use clear Markdown. Include a `Cost Decomposition` section, a `Financing-Aware
Returns` section, and a `Capacity` section. Flag any backtest that understates
financing.

## Spec-Driven Role

Financing-cost accounting is a testable acceptance criterion: "returns net of borrow,
rebate, funding, and margin" and "point-in-time financing inputs" become `AC-*`/
`NFR-*`; financing-spread and capacity risks become `RISK-*`. This agent backs the
`backtest` gate's financing theme (shorts must account for borrow/rebate). The
decomposition, sensitivity, and capacity mechanics have a tested runtime in
`specs/0028-financing-cost-analysis/`. See `instructions/securities_financing.md`,
`instructions/short_term_markets.md`, and `knowledge/short_term_markets/`. Hands
off to `backtest_review` and `risk`. The 0063 gap register keeps this runtime's
fixed-notional, ACT/360, and point-in-time-window limitations visible for later
owner specs; this link does not promote it to broader pricing behavior.
