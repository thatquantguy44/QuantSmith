# Collateral Management Instructions

## Operating Rules

- Use `instructions/short_term_markets.md` and `knowledge/short_term_markets/`
  for U.S. collateral, haircut, margin amount, substitution, lifecycle, source,
  and review-status records before making allocation claims.
- Apply eligibility and haircuts exactly as the collateral schedule specifies.
- Optimize allocation to post the cheapest eligible collateral within limits.
- Respect concentration limits; do not over-post a single issuer or asset.
- Avoid wrong-way risk: collateral correlated with the counterparty's default.
- Distinguish initial from variation margin; model call behavior under stress.
- Make rehypothecation explicit; reused collateral is an exposure.
- Surface the LCR/NSFR and capital impact of collateral decisions.

## Checks

- Are eligibility and haircuts applied per the schedule?
- Does allocation post the cheapest eligible collateral within concentration limits?
- Is wrong-way risk avoided?
- Are initial vs variation margin and call behavior under stress modeled?
- Is rehypothecation made explicit?
- Are the regulatory (LCR/NSFR, capital) consequences stated?

## Output Contract

Use clear Markdown. Include an `Eligibility & Haircuts` section, an `Allocation`
section, and a `Margin & Rehypothecation` section. Note regulatory impact.

## Spec-Driven Role

Collateral rules become spec criteria: "cheapest-to-deliver within limits" and
correct haircuts/margin become `AC-*`/`NFR-*`; concentration, wrong-way, and
rehypothecation become `RISK-*`. See `instructions/securities_financing.md`,
`instructions/short_term_markets.md`, and `knowledge/short_term_markets/`. Hands
off to `repo_financing`, `risk` (counterparty/wrong-way), and the deployment gate
for margin-call operational readiness.
