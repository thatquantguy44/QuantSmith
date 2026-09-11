# Credit Risk Worked Example: Cascadia Fabricators, Inc.

A single reporting cycle threading three Approved, tested credit-risk
runtimes (`0077`, `0073`, `0074`) under the same `0072` governance program.
Every number below is computed by this module's real functions, not
hand-typed — see `report.json` for the full machine-readable output.

## 1. Document intelligence (spec `0077`)

Cascadia's credit memo was admitted through `0072`'s LLM evidence-admission boundary as `decision_input` (admitted: True).

## 2. Wholesale measurement (spec `0073`)

Cascadia's revolving facility: EAD = 4,000,000.00, expected loss = 24,000.00, RWA = 3,000,000.00. Counterparty limit status: within_limit (utilization 80.0%). Portfolio concentration: largest counterparty share 50.0% (Herfindahl index 0.3828), threshold breached: True. Breached counterparties: ['counterparty.northfield-mills'].

## 3. Retail fairness testing (spec `0074`)

A separate retail underwriting book (not Cascadia — see this module's docstring for why the two stay distinct) was tested at cutoff 650: adverse impact ratio 0.569, threshold breached: True. Where breached, a less-discriminatory-alternative search recommended cutoff 610.

## What this does not claim

No rating, PD/LGD estimate, or credit score is produced anywhere in this
module. Cascadia's PD/LGD/risk-weight are illustrative credit-committee
inputs, not a model output; the retail population's scores are synthetic
stand-ins for whatever an adopter's own underwriting model produces. See
`docs/credit_risk_worked_example_synthetic_data_disclosure.md`.
