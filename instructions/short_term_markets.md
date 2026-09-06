# Short-Term Markets Instructions

## Purpose

Use this instruction set when a workflow touches U.S. repo/reverse repo,
securities lending, short-borrow financing, Treasury bills, short-dated Treasury
cashflows, collateral, haircuts, margin, settlement, clearing, reporting, or
short-term funding/cash-product conventions.

The canonical domain pack is `knowledge/short_term_markets/` (spec `0063`).
This standard tells agents how to use it without re-defining its terms.

## Required Inputs

- Product or process ID from `knowledge/short_term_markets/taxonomy.json`.
- Economic viewpoint/role ID before interpreting a cashflow, rate, rebate,
  haircut, margin amount, or specialness claim.
- Convention IDs for quote style, unit, day count, settlement, business-day
  adjustment, rounding, and signs.
- `as_of` date and effective date for facts, rules, rates, and observations.
- Source refs from `sources/` and review status for any knowledge record used.
- Current gaps from `knowledge/short_term_markets/coverage.json` and
  `knowledge/short_term_markets/gap_register.md`.

## Standards

- **Resolve viewpoint first.** Do not say a cashflow is income or cost until the
  role is declared: cash provider/taker, securities provider/receiver, repo
  seller/buyer, securities lender/borrower, beneficial owner, agent lender, or
  short seller.
- **Do not collapse similar terms.** `repo` and `reverse repo`, `GC` and
  `special`, `borrow fee` and `rebate`, `haircut` and `margin`, and `price`,
  `rate`, and `yield` are distinct records. Use the stable IDs.
- **Treat repo and stock-loan specialness separately.** Repo specialness is
  positive when `GC repo rate - specific collateral repo rate` is positive.
  Stock-loan specialness follows borrow-fee or rebate economics and needs its
  own viewpoint conversion.
- **No naked numbers.** Rates, yields, prices, days, haircuts, margin amounts,
  and thresholds need units, quote style, day count, calendar, settlement timing,
  and rounding.
- **No universal thresholds.** GC/special or easy/warm/hard-to-borrow cutoffs
  must be sourced rules or parameterized model assumptions. The current
  securities-lending demo thresholds are draft model assumptions, not market
  truth.
- **Separate knowledge time from effective time.** A record must be knowable as
  of the query date and effective for the economic date. A later-known
  observation cannot leak backward just because it covers the same effective
  period.
- **Respect review status.** `draft` is usable as scaffolded structure, not as
  expert-reviewed content. `reviewed` requires a named non-email reviewer,
  scope, date, evidence refs, and no blocking severity-high discrepancy.
- **Keep behavior ownership scoped.** This standard does not change existing
  runtimes. Runtime corrections belong to `0064` through `0067`; source
  ingestion belongs to `0068`; regulatory/legal knowledge belongs to `0069`.

## Checks

- Is the product/process ID stated and within the U.S.-first scope?
- Is the economic viewpoint explicit before signs are interpreted?
- Are convention IDs named for rates, prices, yields, day count, settlement,
  haircut, margin, and thresholds?
- Are `as_of` and effective dates both present where a record can vary over
  time?
- Do all source refs resolve to `sources/`, and is the record's review status
  disclosed?
- Has the answer checked `gap_register.md` before claiming compatibility with
  current runtimes?
- Is any child-spec work (`0064`-`0069`) kept inactive unless separately
  approved?

## Common Failure Modes

- Calling something "special" without saying repo versus stock loan and whose
  economics are being described.
- Treating a lower special repo rate as if it had the same sign as a higher
  stock-borrow fee.
- Applying an ACT/252 demo fee assumption to ACT/360 money-market accrual, or
  the reverse, without declaring the convention.
- Using a rate learned after a trade starts as though it applied to the whole
  historical holding period.
- Treating a haircut percentage as the margin amount.
- Promoting sourced-looking but unreviewed prose to expert guidance.

## Spec-Driven Alignment

This standard backs spec `0063-short-term-markets-domain-foundation` and is the
shared input contract for future specs `0064` through `0069`. It feeds
`agents/securities_financing/`, `agents/asset_classes/fixed_income_rates/`,
`backtest_review`, `risk`, and any later source-ingestion or collateral/runtime
work. The validator is
`src/quantsmith/pipelines/short_term_markets_knowledge.py`; tests live in
`tests/test_short_term_markets_knowledge.py`.
