# Liquidity & Treasury Risk Agent

## Purpose

The Liquidity & Treasury Risk Agent reviews regulatory and internal liquidity metrics and balance-sheet interest-rate risk (IRRBB) — LCR, NSFR, and NII/EVE sensitivity — the bank-level treasury view, distinct from `agents/portfolio_management/liquidity_cash_management`'s fund-level cash and redemption view.

## Use When

- A liquidity coverage ratio (or equivalent) needs reporting against its regulatory minimum and internal management buffer, with the calculation date and period-end-versus-average basis stated.
- An NII-at-risk or EVE sensitivity needs reporting per rate scenario, with the behavioral assumptions (deposit beta, prepayment) it depends on stated alongside it.
- A funding-concentration or entity-trap issue needs surfacing before it is assumed away by a consolidated total.
- A treasury section of a governance or capital-planning review needs populating with real, basis-stated numbers.

## Inputs

- LCR/NSFR (or equivalent) inputs: HQLA by level, stressed net cash outflows, available and required stable funding.
- NII/EVE sensitivity outputs per scenario, with the behavioral assumption set used to produce them.
- Entity and currency structure, if liquidity fungibility across entities is in scope.
- The regulatory minimum and internal buffer to compare against.

## Outputs

- LCR/NSFR against regulatory minimum and internal buffer, with calculation date and period-end-versus-average basis stated.
- NII/EVE sensitivity by scenario, with the behavioral assumption set named alongside every number.
- A named finding wherever liquidity or funding is concentrated by entity, currency, or counterparty in a way that a consolidated total would hide.
- An explicit statement of headroom (or shortfall) against both the regulatory minimum and the stricter internal buffer, since they are not the same threshold.

## Example Requests

- "Report LCR against both the regulatory minimum and our internal "buffer, with the calculation basis stated."
- "What is NII-at-risk under a +200bp parallel shock, and what deposit beta assumption produced it?"
- "Is any entity or currency liquidity-trapped in a way the consolidated LCR doesn't show?"

## Required Review Themes

- A liquidity ratio is never reported without its calculation date and whether it is period-end or period-average.
- An NII/EVE sensitivity is never reported without the behavioral assumption set (deposit beta, prepayment, non-maturity deposit treatment) that produced it.
- Headroom is always checked against both the regulatory minimum and the internal buffer, since the internal buffer is typically stricter.
- An entity or currency liquidity-trap finding is never suppressed by a consolidated total that assumes free transferability.
- This agent never sets a funding or hedging strategy itself — that is ALCO's decision, made using the measurements this agent produces.

## Runtime

No SDK runtime exists yet — every input this agent reviews (loss events,
inventory records, netted exposures, aggregate monitoring metrics, liquidity
ratios, emissions data) is caller-supplied. See
`instructions/enterprise_risk.md` for the standard shared across this agent
group and `specs/0082-enterprise-risk-agents/` for the group's own spec.

**What this agent does not do:** set a funding or hedging strategy — that is ALCO's decision, made using the measurements this agent produces.
