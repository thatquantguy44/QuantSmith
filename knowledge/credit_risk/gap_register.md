# Credit Risk Gap Register (spec `0072`)

Observed gaps between the credit capability surface and what this repository
actually has. Identification is **not** correction: a row leaves this register
only when an artifact and its validation evidence change, and the disposition
says which spec owns that.

Severity: `high` blocks any claim of coverage for the capability and blocks
`reviewed` promotion of records that depend on it. `medium` limits the claim.
`low` is a known rough edge.

| ID | Gap | Evidence | Severity | Affected | Disposition | Owner |
| --- | --- | --- | --- | --- | --- | --- |
| G-0072-001 | No named credit-domain reviewer exists, so no record in this pack can be promoted beyond `draft`. | `knowledge/credit_risk/README.md` review policy; every record carries `review_status: draft` and `review: null`. | high | Every capability; the whole pack. | Open. Resolution is a person, not code: a credit risk officer, model validator, or CECL/IFRS 9 owner must accept the review scope. No automation in this repository can substitute. | `0072` T-016 |
| G-0072-002 | No credit measurement runtime exists. PD, LGD, EAD, and rating conventions are contracts with golden cases, not code. | `coverage.json` capability rows at `contract_only`; no module under `src/quantsmith/pipelines/` computes a credit measure. | high | `capability.wholesale_measurement`, `capability.counterparty_limits` | Assigned. The golden cases fix what the runtime must reproduce; the runtime itself is out of `0072`'s scope by its own non-goals. | `0073` |
| G-0072-003 | The lifetime PD term-structure method is deliberately unset, so lifetime ECL cannot be computed end to end from a one-year PD. | `conventions.json` `param.pd.term_structure_method` has `default: null, required: true`. | medium | `capability.expected_credit_loss` | Accepted by design, not deferred by omission. There is no universal correct method; a default here would silently impose ours on every adopter. The parameter must be supplied. | `0075` |
| G-0072-004 | The IRB risk weight is an input, so no capital number can be produced from this pack alone. | `conventions.json` `param.rwa.risk_weight` has `default: null, required: true`; `golden.rwa.irb_risk_weight` supplies it as an input with declared provenance. | medium | `capability.regulatory_capital` | Accepted by design. National implementation differs from the international framework; a hard-coded weight would make a wrong capital number look authoritative. | `0076` |
| G-0072-005 | No fairness harness exists. The decision contract is enforced structurally, but `hook.disparate_impact.*` is a declared identifier with no implementation behind it. | `decision_paths.json` names the hooks; no module implements one. | high | `capability.retail_underwriting` | Assigned. `0074` must ship the harness before any retail scoring path can move past `contract_only`. Until then the contract can prove a workflow *declares* the hook, not that the hook works. | `0074` |
| G-0072-006 | No governed credit corpus exists, so the LLM evidence boundary is unexercised on real credit documents. | `0071`'s only registered corpus is `text_intelligence_fixture`, whose fictional content is explicitly not evidence. | medium | `capability.document_intelligence` | Assigned. `0077` must choose a licensed, source-registered corpus and freeze its entitlement policy. The admission rules are testable today on synthetic fixtures; their real-world behaviour is not yet demonstrated. | `0077` |
| G-0072-007 | Credit sources are registered as locators only; nothing is ingested, and no vintage control is exercised against a real publication. | `sources/{cfpb,fasb,ifrs_foundation,bis_basel,occ}.yml` all carry `status: evaluating` and `method: manual_download`. | medium | Every capability that cites a source. | Assigned. Live ingestion, vintage capture, and data contracts belong to `0078`, matching how `0063` deferred its own ingestion to `0068`. | `0078` |
| G-0072-008 | Counterparty credit concentration has no runtime, and the nearest existing one measures something else. | `0038`'s `factor_risk_model.py` decomposes market factor risk and concentration, not counterparty credit exposure. | medium | `capability.counterparty_limits` | Assigned. The distinction is recorded here precisely so `0038` is not mistaken for coverage because the word "concentration" appears in both. | `0073` |
| G-0072-009 | No monitoring runtime exists, so the deployability predicate can check that a monitoring plan is *declared*, not that monitoring runs. | `governance.json` `gov.monitoring_plan` requires the artifact; nothing measures drift or calibration. | medium | `capability.model_governance` | Assigned. Whether the runtime should be credit-specific or generalized across the SDK's whole model inventory is an open question in `0072`'s spec. | `0079` |
| G-0072-010 | The pack asserts that IFRS 9 and CECL differ but does not yet enumerate where, beyond staging and lifetime scope. | `conventions.json` holds one lifetime-ECL convention citing both `ifrs_foundation` and `fasb`. | low | `capability.expected_credit_loss` | Open. Splitting the convention is likely correct but should follow a real consumer rather than precede one, so the split is driven by a difference that matters to someone. | `0075` |

## What this register is not

It is not a list of everything credit risk contains. It is a list of gaps
between the **declared capability surface** in `coverage.json` and what this
repository has. Products, jurisdictions, and portfolios outside that surface —
non-U.S. jurisdictions, insurance and sovereign credit, securitization and
structured credit, counterparty valuation adjustments, credit derivative
pricing — are recorded as out of scope in `0072`'s spec, not as gaps here.
