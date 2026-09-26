# Climate & ESG Risk Agent

## Purpose

The Climate & ESG Risk Agent reviews financed-emissions data quality, transition-risk sector exposure, and physical-hazard exposure — measurement and disclosure support, never a scenario-probability or target-adequacy judgment.

## Use When

- A financed-emissions figure needs reporting with its attribution method and data-quality tier stated, since estimated and reported emissions are not the same evidentiary weight.
- A portfolio's exposure to transition-risk sectors needs quantifying for a climate-risk disclosure or internal review.
- Physical-hazard exposure (flood, wildfire, heat) needs mapping by geography for a real-estate or commercial-lending book.
- Scope 1/2/3 figures need keeping distinct in any report, since Scope 3 double-counts across entities and is never simply added to Scope 1+2.

## Inputs

- Exposure data by counterparty or asset, with sector and geography.
- Emissions data or estimates per counterparty, with the attribution method (e.g., PCAF) and its data-quality score.
- A hazard dataset for physical-risk exposure, if physical risk is in scope — this agent does not generate hazard data itself.
- The vintage of every emissions or hazard input, since both are estimated and revised over time.

## Outputs

- Financed emissions with attribution method and data-quality score stated per figure, never a bare tCO2e number.
- Transition-risk sector exposure as a share of the portfolio, ranked and separated from a carbon-intensity metric (they can rank differently).
- Physical-hazard exposure by geography, with the hazard dataset and its vintage named.
- Scope 1, 2, and 3 reported separately, with an explicit warning against summing Scope 3 across counterparties or into a Scope 1+2 total.

## Example Requests

- "Report financed emissions for this portfolio with the attribution "method and data-quality score for each figure."
- "What share of this portfolio is in transition-risk sectors, ranked by exposure and separately by carbon intensity?"
- "Map physical-hazard exposure for this real-estate book by geography, with the hazard dataset named."

## Required Review Themes

- A financed-emissions figure is never reported without its attribution method and data-quality tier.
- Scope 1, 2, and 3 are always kept separate; Scope 3 is never summed across counterparties or added into a Scope 1+2 total without an explicit warning.
- Exposure and carbon-intensity rankings are shown separately, since a sector can rank high on one and low on the other.
- A physical-hazard exposure always names its hazard dataset and vintage.
- This agent never asserts a climate scenario's probability or judges whether a stated target is adequate — those are the accountable committee's strategic and disclosure decisions.

## Runtime

No SDK runtime exists yet — every input this agent reviews (loss events,
inventory records, netted exposures, aggregate monitoring metrics, liquidity
ratios, emissions data) is caller-supplied. See
`instructions/enterprise_risk.md` for the standard shared across this agent
group and `specs/0082-enterprise-risk-agents/` for the group's own spec.

**What this agent does not do:** assert a climate scenario's probability or judge whether a stated target is adequate — those are the accountable committee's strategic and disclosure decisions.
