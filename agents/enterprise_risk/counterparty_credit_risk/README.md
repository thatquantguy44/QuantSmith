# Counterparty Credit Risk Agent

## Purpose

The Counterparty Credit Risk Agent measures derivative and securities-financing counterparty exposure — current and potential future exposure after netting and collateral — distinct from the wholesale-credit facility view `agents/credit_risk/counterparty_limits` already covers.

## Use When

- A counterparty's exposure across a derivatives book needs netting before it is compared to anything — gross mark-to-market overstates exposure whenever a netting agreement exists.
- Potential future exposure (PFE) or expected exposure needs reporting against a limit, at the stated confidence and horizon.
- Wrong-way risk — exposure that rises as the counterparty's own credit worsens — needs flagging as a distinct concern from the exposure level itself.
- A CSA's collateral terms need stating alongside any exposure number they reduce.

## Inputs

- Trade-level mark-to-market and the netting set each trade belongs to.
- CSA terms: threshold, minimum transfer amount, and posted collateral, per netting set.
- A PFE or expected-exposure profile, if quantile-based exposure is in scope — this agent does not compute it from scratch.
- The counterparty limit to compare against.

## Outputs

- Current exposure per netting set: positive MTM after netting and collateral, never a sum of gross trade-level marks.
- PFE or expected exposure against the stated limit, with confidence and horizon named.
- Limit utilization per counterparty, and a named breach where it occurs.
- A wrong-way-risk flag where exposure and counterparty credit quality appear correlated, kept separate from the exposure measurement itself.

## Example Requests

- "Net this counterparty's derivative trades by netting set and report "current exposure after collateral."
- "Is this counterparty's PFE within its limit, and at what confidence and horizon was that PFE computed?"
- "Does this counterparty show wrong-way risk — does exposure rise with its own credit deterioration?"

## Required Review Themes

- Exposure is always netted within its legally enforceable netting set first — gross trade-level marks are never summed across a netting set.
- A PFE or expected-exposure figure always states its confidence level and horizon; those are never assumed.
- CSA terms (threshold, MTA, posted collateral) are stated alongside any exposure they reduce.
- Wrong-way risk is a named, separate flag — never folded silently into the exposure number.
- This agent never prices a derivative or sets a CSA term itself — both are trading and legal decisions it consumes, not makes.

## Runtime

No SDK runtime exists yet — every input this agent reviews (loss events,
inventory records, netted exposures, aggregate monitoring metrics, liquidity
ratios, emissions data) is caller-supplied. See
`instructions/enterprise_risk.md` for the standard shared across this agent
group and `specs/0082-enterprise-risk-agents/` for the group's own spec.

**What this agent does not do:** price a derivative, set a CSA term, or compute a PFE model from scratch — pricing and legal terms are trading and legal decisions, and a supplied exposure profile is consumed, not derived, here.
