# Enterprise Risk Standard

The standard behind `agents/enterprise_risk/`: six disciplines a bank or
diversified financial-services firm runs that are not the same job as
`agents/risk/` (which reviews the risk *of a signal, model, portfolio, or
strategy* — see `instructions/risk_management.md`). Operational risk, model
risk management, counterparty credit risk, AML/financial crime, liquidity and
treasury risk, and climate/ESG risk each have their own inventory, their own
regulatory expectations, and their own named owner — folding them into a
single "risk" review erases exactly the distinctions that matter when a
regulator, an auditor, or a board committee asks who owns what.

## Why This Standard

`agents/risk/` was written for one job — interrogating a strategy's risk
before or after it trades — and it does that job well. It was never written
for a loss event in operations, a model past its validation date, a
derivative counterparty's netted exposure, a suspicious-activity alert, a
bank's interest-rate-risk-in-the-banking-book position, or a financed-emissions
number. Asking it to cover all of those anyway produces reviews that are
technically present but structurally wrong — the same failure mode credit
risk had before `0072` gave it its own domain foundation. This standard gives
the other six disciplines the same treatment: named scope, named non-scope,
and a shared rule about what none of them may do.

## Shared Rule: Measure and Surface, Never Decide

Every agent under this standard reviews, aggregates, or measures what it is
given; none of them scores, prices, approves, files, or decides on behalf of
a human accountable for that decision. This is the same boundary
`agents/credit_risk/` draws around rating and PD/LGD estimation, applied
across six more disciplines:

| Agent | Never does this | Because |
| --- | --- | --- |
| `operational_risk` | Approve a control's design or close a finding | Control ownership and audit sign-off belong to the control owner and auditor. |
| `model_risk_management` | Approve or reject a model for production | Model approval is a named validator's or committee's decision under the firm's SR 11-7-style policy. |
| `counterparty_credit_risk` | Price a derivative or set a CSA term | Pricing and legal terms are a trading desk's and legal's decisions; this agent consumes marks and agreement terms as given. |
| `aml_financial_crime` | Decide an alert is suspicious or file a SAR | Suspicious-activity determination and filing are a named compliance officer's regulated decision. |
| `liquidity_treasury_risk` | Set a funding or hedging strategy | Treasury strategy is ALCO's decision; this agent measures the position it acts on. |
| `climate_esg_risk` | Assert a scenario's probability or a firm's target adequacy | Scenario selection and target-setting are strategic and disclosure decisions for the accountable committee. |

## Coverage — what each agent must establish

| Agent | Must establish |
| --- | --- |
| `operational_risk` | Loss events by type and business line, control gaps, KRI breaches, and whether losses are within or above declared thresholds. |
| `model_risk_management` | Model inventory completeness, validation currency (on-time vs. overdue), open finding severity and age, and override rate versus policy. |
| `counterparty_credit_risk` | Netted exposure per counterparty (current and potential future), collateral/CSA terms applied, and limit utilization — never gross, unnetted marks. |
| `aml_financial_crime` | Alert-to-case and case-to-SAR funnel health, false-positive rate, KYC refresh currency, and confidentiality of any SAR-related content. |
| `liquidity_treasury_risk` | LCR/NSFR (or equivalent) versus regulatory minimum and internal buffer, NII/EVE sensitivity by scenario, and the behavioral assumptions those numbers depend on. |
| `climate_esg_risk` | Financed-emissions data quality and attribution method, exposure to transition-risk sectors, and physical-hazard exposure by geography. |

## Rules

1. **Name the discipline, not just "risk."** A finding belongs to exactly one
   of these six areas (or to `agents/risk/`'s investment-risk lane); a report
   that says "risk" without naming which kind is incomplete.
2. **State the basis before the number.** A netted exposure states its
   netting set; an LCR states its calculation date and whether it is a
   period-end or period-average; a financed-emissions figure states its
   attribution method and data-quality tier. A number without its basis is
   not yet a finding.
3. **A confidentiality boundary is a hard boundary, not a formatting choice.**
   `aml_financial_crime` never surfaces individual-alert or SAR content in an
   aggregated report — see its own instructions.
4. **Assumption-driven outputs say so.** `liquidity_treasury_risk` sensitivities
   and `climate_esg_risk` scenario exposures are model results built on stated
   assumptions, not observed facts; report the assumption alongside the number.
5. **Every named risk gets an owner and a threshold**, the same rule
   `instructions/risk_management.md` states for investment risk — an
   operational-loss trend, a model past its validation date, or an LCR
   approaching its floor is a finding only once it has a stated threshold and
   an accountable owner, not a narrative.
6. **Hand off, don't absorb.** These agents feed `agents/role_operations/governance_readiness_checklist`,
   `agents/deployment_release/`, and each other (e.g. `counterparty_credit_risk`
   feeds `agents/credit_risk/counterparty_limits` for the wholesale-credit view
   of the same counterparty) rather than duplicating what those agents already do.

## Checklist

- [ ] The finding names its discipline (one of the six, or investment risk).
- [ ] Every number states its basis (netting set, calculation date,
      attribution method, or equivalent).
- [ ] No individual AML alert or SAR content appears outside
      `aml_financial_crime`'s own confidentiality boundary.
- [ ] Every assumption-driven number (liquidity sensitivity, climate scenario
      exposure) states the assumption it depends on.
- [ ] Every named risk has a metric, a threshold, and an owner.
- [ ] No agent under this standard has scored, priced, approved, or filed
      anything on a human's behalf.

## Runtime & Spec

- Agents: `agents/enterprise_risk/` (spec `0082-enterprise-risk-agents`) —
  contract-only; no SDK runtime models or decides anything in these six
  disciplines. An executable runtime, if one is built later, composes
  caller-supplied inputs the same way `0073`'s wholesale-credit measurement
  composes caller-supplied PD/LGD/EAD.
- Distinct from: `instructions/risk_management.md` (`agents/risk/` —
  investment/portfolio risk) and `instructions/credit_risk.md`
  (`agents/credit_risk/` — wholesale/retail credit measurement and fairness).
- Feeds: `agents/role_operations/governance_readiness_checklist`,
  `agents/deployment_release/`, and `agents/credit_risk/counterparty_limits`
  (from `counterparty_credit_risk`, the derivatives/XVA view feeding the
  wholesale-credit view of the same counterparty).
