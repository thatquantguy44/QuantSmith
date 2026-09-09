# Securities Lending Instructions

## Operating Rules

- Use `instructions/short_term_markets.md` and `knowledge/short_term_markets/`
  for U.S. securities-lending roles, borrow-fee/rebate signs, GC/special
  distinctions, point-in-time source rules, lifecycles, and current gap records.
- Net the borrow fee and short rebate from short returns; never assume a free short.
- Distinguish general collateral from stock-loan specials by borrower/lender
  viewpoint; do not import the repo-special sign convention without an explicit
  conversion. `concept.stock_loan_special` (higher-borrow-cost viewpoint) and
  `concept.repo_special` (GC-minus-specific-rate viewpoint) are distinct
  records in `knowledge/short_term_markets/taxonomy.json` for exactly this
  reason — see `golden.repo.specialness_sign`'s invariant that "stock-loan
  specialness signs must not be reused without viewpoint conversion."
- Use point-in-time borrow rates and hard-to-borrow status, not today's values.
- Treat recall risk as a constraint: a recalled borrow can force a buy-in.
- Handle corporate actions on loaned stock: manufactured dividends and lost votes.
- Respect locate/close-out rules (e.g. Reg SHO) where they apply.
- Reflect availability in capacity; hard-to-borrow names cap short size.

## Checks

- Is the borrow fee/rebate netted from short returns?
- Are GC and specials distinguished, with specials costed correctly?
- Are borrow rates and HTB status point-in-time, not hindsight?
- Are recall and buy-in risks characterized?
- Are corporate actions on loaned stock handled?
- Is short capacity limited by borrow availability?

## Output Contract

Use clear Markdown. Include a `Borrow Cost & Availability` section and a `Recall &
Buy-In Risk` section. State the point-in-time treatment of borrow data.

## Spec-Driven Role

Borrow assumptions become spec criteria: "borrow cost netted", "point-in-time borrow
rates", and "capacity reflects availability" become `AC-*`/`NFR-*`; recall, buy-in,
and specials risk become `RISK-*`. Point-in-time borrow data is enforced by
`instructions/point_in_time.md`; short-cost realism by the `backtest` gate's
financing theme. See `instructions/securities_financing.md`. The classification,
inventory-optimization, and concentration-risk mechanics have a tested runtime in
`specs/0023-securities-lending-workflow/`. For the canonical 0063 foundation, see
`instructions/short_term_markets.md` and `knowledge/short_term_markets/`. Hands
off to `financing_cost_analysis`, `backtest_review`, and `risk`.
