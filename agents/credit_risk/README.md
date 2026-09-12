# Credit Risk Agents

This folder groups agents for credit risk — document evidence, wholesale
measurement, and retail fairness testing — under spec
`0072-credit-risk-domain-foundation`. Agent creation is gated: an agent
exists here only when `knowledge/credit_risk/coverage.json` shows a coverage
row with a distinct workflow no existing agent already holds (`0072`
REQ-011). See `agents/README.md`'s own Credit Risk Agents section for the
full agent table and what each agent explicitly does not claim.

## Agents

| Agent | Handles |
| --- | --- |
| `credit_document_analyst/` | Cited extraction from credit documents into `0072`'s LLM evidence-admission boundary. Tested runtime (spec `0077`). |
| `counterparty_limits/` | Counterparty exposure aggregation, limit-breach detection, and concentration from supplied PD/LGD/EAD. Tested runtime (spec `0073`). |
| `fair_lending_review/` | Disparate-impact testing, proxy-feature association, and less-discriminatory-alternative search on an already-scored population. Tested runtime (spec `0074`). |

Notably absent: `obligor_rating` and `retail_underwriting` — rating,
PD/LGD estimation, and consumer credit scoring all stay an adopter's own
model registered via `0026`, so no SDK runtime justifies either agent.

## Group Workflow

```
credit_document_analyst → counterparty_limits → wholesale credit committee
                        ↘
                          fair_lending_review → retail underwriting decision
```

`credit_document_analyst/` (spec `0077`), `counterparty_limits/` (spec
`0073`), and `fair_lending_review/` (spec `0074`) all have tested runtimes.
Document evidence admitted by `credit_document_analyst` feeds a human
credit reviewer's wholesale decision (`0072`'s `path.wholesale_obligor_review`);
it is never itself the sole basis of that decision — see `0072` REQ-016.
`counterparty_limits` and `fair_lending_review` sit on opposite sides of
`0072`'s own consumer-decision line: wholesale/counterparty review is not a
consumer decision (no ECOA fairness obligation attaches), while any retail
underwriting or account-management decision (`path.retail_underwriting_decision`,
`path.retail_account_management`) must run `fair_lending_review`'s
disparate-impact hook before it can be the sole basis of an adverse action.

**Worked example:** `examples/credit_risk_worked_example/` (built by
`src/quantsmith/pipelines/credit_risk_worked_example.py`, tested by
`tests/test_credit_risk_worked_example.py`) threads all three runtimes
against one reporting cycle — a synthetic wholesale obligor's credit memo
admitted as evidence, its facility measured and limit-checked, and a
separate retail book fairness-tested at its applied cutoff — deliberately
keeping the wholesale obligor and the retail population two distinct
entities, matching `0072`'s own consumer-decision boundary rather than
fictionalizing them as the same borrower.

## Shared Principles

- **No model ships as an SDK default.** Rating, PD/LGD estimation, and
  consumer scoring stay adopter-plugin-only via `0026`; these agents measure,
  aggregate, and test — they never assign a rating or a score.
- **Evidence, not decisions.** A document-derived value is `derived_evidence`
  until a named human reviewer promotes it to `decision_input` (`0072`
  REQ-016); no automation performs that promotion itself.
- **Fairness testing is structural, not optional.** Any consumer-facing
  decision path in `0072`'s knowledge pack requires a disparity metric at
  the applied cutoff, recorded proxy-feature association, and a
  less-discriminatory-alternative search on breach — the unsafe
  configuration is unrepresentable, not merely discouraged.
- **No institution-specific value defaults.** Risk weights, disparity and
  concentration thresholds, and candidate cutoffs are always caller-supplied
  arguments; nothing here bakes in a policy-specific number.

## Related

- `specs/0072-credit-risk-domain-foundation/` — the taxonomy, conventions,
  lifecycles, decision contract, and gap register this whole group serves.
- `instructions/point_in_time.md` — the leakage discipline that also governs
  any point-in-time-sensitive credit data.
- `agents/securities_financing/` — a comparable domain-first agent group with
  its own canonical knowledge pack (`0063`) and worked example.
