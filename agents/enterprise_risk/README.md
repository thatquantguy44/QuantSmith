# Enterprise Risk Agents

Six agents, one per discipline `agents/risk/` was never built to cover:
operational risk, model risk management, counterparty credit risk (XVA),
AML/financial crime, liquidity and treasury risk (IRRBB), and climate/ESG
risk. Grouped under spec `0082-enterprise-risk-agents`, sharing
`instructions/enterprise_risk.md`.

## Why this group exists

Spec `0081`'s 40 analytics domain packs named a reviewer agent for each of
seven business-and-risk families. Twenty-seven of them fell back to
`agents/risk` — whose own charter (`instructions/risk_management.md`) is the
risk of a signal, model, portfolio, or strategy, not operational loss events,
model-inventory governance, derivative counterparty exposure, AML program
health, bank-level liquidity, or financed emissions. Each of those six is a
real discipline with its own inventory, its own regulatory expectations, and
its own accountable owner; folding them into one generic agent hid that.
This group gives each its own narrow, correctly-scoped agent, the same
treatment credit risk got in spec `0072` when a generic review stopped being
enough for it.

`agents/risk/` itself is unchanged and correct for what it already does —
investment and portfolio risk. Most business-line packs that name it
alongside a domain-specific agent (as a general "does this look risky"
second reviewer) are also unchanged; that use is within its charter.

## Agents

| Agent | Handles | Never | Feeds mainly |
| --- | --- | --- | --- |
| `operational_risk/` | Loss events by Basel type and business line, KRI breaches, near-miss/loss separation | Approving or closing a control finding | `alerts/incident_notification`, `role_operations/governance_readiness_checklist` |
| `model_risk_management/` | Model-inventory validation currency, finding severity/age, override rate | Approving or rejecting a model | `role_operations/governance_readiness_checklist`, `machine_learning/mlops_monitoring` |
| `counterparty_credit_risk/` | Netted derivative/securities-financing exposure, PFE vs. limit, wrong-way risk | Pricing a derivative or setting a CSA term | `credit_risk/counterparty_limits` (wholesale-credit view), `risk` |
| `aml_financial_crime/` | Alert/case/SAR funnel health, false-positive rate, KYC currency — aggregate only | Determining suspicion, filing a SAR, or naming an individual | `alerts/alert_policy`, a named compliance officer |
| `liquidity_treasury_risk/` | LCR/NSFR vs. minimum and buffer, NII/EVE sensitivity, entity/currency traps | Setting a funding or hedging strategy | ALCO's own process, `risk` |
| `climate_esg_risk/` | Financed-emissions data quality, transition-sector exposure, physical-hazard mapping | Asserting scenario probability or target adequacy | `research_analyst`, the disclosure committee |

Every agent is contract-only today (no SDK runtime); each takes its data —
loss events, inventory records, netted exposures, aggregate monitoring
metrics, liquidity ratios, emissions data — as caller-supplied input, the
same posture `agents/credit_risk/counterparty_limits` takes toward PD/LGD/EAD
before its runtime existed.

## `0081` packs re-pointed by this group

`aml_financial_crime`, `climate_esg_risk`, `counterparty_risk_xva`,
`liquidity_risk`, `model_risk`, `operational_risk`, and `treasury_alm_irrbb`
in `knowledge/analytics_packs/` now name the matching agent above instead of
the generic `agents/risk`.
