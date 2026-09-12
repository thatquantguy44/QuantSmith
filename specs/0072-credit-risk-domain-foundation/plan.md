# Plan: Credit Risk Domain Foundation

- **Spec:** 0072-credit-risk-domain-foundation (`spec.md`)
- **Status:** Draft
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-09-09

> The HOW for review alongside the Draft spec. The knowledge pack, validator,
> and acceptance tests described below are built; the agent charter and the
> human review are not (see `tasks.md` for per-task status). Nothing in this
> plan changes an existing runtime.

## Approach

Follow `0063`'s proven shape rather than inventing a second pattern: one
canonical, versioned, public domain pack, with human-readable Markdown carrying
expert narrative and citations and machine-readable JSON carrying stable IDs,
conventions, lifecycle graphs, coverage states, and deterministic cases. A small
standard-library validator loads the JSON and checks referential, temporal,
arithmetic, and governance invariants offline.

Where this plan departs from `0063` is the part that makes credit different.
`0063` is a *measurement* contract; credit needs a measurement contract **plus a
decision contract**. A repo rate that is computed with the wrong sign is a wrong
number. A credit score applied to a consumer without derivable reason codes is a
wrong *act*. So the pack carries three layers `0063` did not need:

1. **A decision-path classification.** Every workflow contract declares whether
   it supports a decision about an identifiable consumer. If it does, REQ-014's
   reason-code, policy-version, protected-attribute, and disparate-impact
   obligations are structurally required; if it cannot meet them, the only valid
   state is `decision_support_only`, which the validator enforces and which
   prohibits sole-basis adverse action.
   REQ-020 exists because the first draft of this design stopped at attribute
   absence. That check is trivially satisfiable and certifies nothing: disparate
   impact arises from facially neutral features correlated with protected class,
   so a contract that only inspects a feature list supplies false comfort. The
   substantive half — a testing basis, a disparity metric at the applied cutoff,
   per-feature proxy visibility, and a less-discriminatory-alternative search on
   breach — is now equally structural. An estimate of a protected attribute is
   treated as a protected attribute for feature purposes.

2. **A governance record.** Deployability in the coverage matrix is a computed
   property, not a label: a model is deployable only when a credit model card,
   independent validation evidence, challenger comparison, monitoring thresholds,
   override log, named owner, and kill switch all resolve.
3. **An LLM-evidence admission boundary.** Text-derived values enter through
   `0071` artifacts inside a `0070` envelope, are labeled derived evidence, and
   require named human review before they can be a decision input.

The layering otherwise mirrors `0063`: semantics first (taxonomy, roles,
viewpoints, signs), mechanics second (conventions, lifecycles), evidence and time
around both, and models last (golden cases, coverage and gap registers) so the
foundation defines what later runtimes must reproduce without implementing them.

The agent group is designed here and justified by the coverage matrix, but the
charter deliberately gates creation: a `agents/credit_risk/` agent exists only
when a coverage row shows a distinct workflow no existing agent holds. That is
the direct answer to RISK-007 and to the repository's standing rule against
adding agents to fill a map.

## Architecture & Components

```text
public statutes, supervisory guidance, accounting standards,
capital framework text, supervisory scenarios, public methodology locators
                    |
                    v
            sources/ registry (0027)
                    |
                    v
knowledge/credit_risk/
  README.md                 scope, navigation, review policy, exclusions
  source_policy.md          authority, conflict, freshness, licensing rules
  taxonomy.json             obligors, facilities, measures, roles, aliases
  conventions.json          horizon, conditioning, default defn, discounting
  lifecycles.json           credit state, approval/limit, model lifecycle
  decision_paths.json       consumer-decision contracts + fairness obligations
  governance.json           SR 11-7 artifact requirements + deployability rule
  workflows.json            six end-to-end workflows, agents, runtime boundary
  coverage.json             capability -> artifact -> owner -> status map
  golden_cases.json         deterministic cases and identities
  gap_register.md           evidence, severity, disposition, owning spec
                    |
                    +--> instructions/credit_risk.md
                    |      shared operating standard for all credit agents
                    |
                    +--> agents/credit_risk/ charter (roster, gated creation)
                    |
                    +--> workflows.json / docs   six named end-to-end workflows
                    |
                    +--> credit_risk_knowledge.py + tests
                    |      offline structural/temporal/numeric/governance checks
                    |
                    +--> 0070 envelope + 0071 corpora (LLM evidence boundary)
                    |
                    `--> 0073-0079 bounded consumers
```

### Component responsibilities

| Component | Responsibility |
| --- | --- |
| `knowledge/credit_risk/README.md` | State U.S.-first scope, navigation, review states, how agents cite records, and what the pack explicitly does not claim (notably: it is not model validation). |
| `taxonomy.json` | Stable IDs and deterministic alias resolution for obligors, facilities, exposures, counterparties, measures, roles, rating/score concepts, and default definitions, with the non-interchangeable sets from REQ-002 enforced. |
| `conventions.json` | Units, horizon, conditioning basis, default-definition ID, collateral/guarantee treatment, discounting, currency, seasoning, calibration population, and formula references for every credit measure. |
| `lifecycles.json` | Three transition graphs — credit state, approval/limit, and SR 11-7 model lifecycle — each transition naming its initiating role and produced artifact. |
| `decision_paths.json` | Per-workflow consumer-decision classification, the REQ-014 procedural obligations, and the REQ-020 substantive fairness obligations; the validator refuses a consumer-facing path that cannot derive reason codes or cannot test for disparity. |
| `governance.json` | The credit model card extension and the deployability predicate; a model entry is deployable only when every required governance artifact resolves. |
| `workflows.json` | The six end-to-end workflows: stages, participating agents, required inputs, produced artifacts, gates, human decision points, and each capability's runtime boundary. |
| `coverage.json` | Capability surface mapped to current agents, instructions, runtimes, sources, tests, limitations, and future owning specs, at five coverage levels. |
| `golden_cases.json` | Small deterministic cases pinning EL, EAD/CCF, 12-month vs lifetime ECL with EIR discounting, IRB risk weight, points-to-odds and cutoff, adverse action ranking, migration-matrix row stochasticity, and a rejected outcome-window violation. |
| `gap_register.md` | Observed mismatches with evidence paths, severity, affected consumers, disposition, and owning spec; identification is never recorded as correction. |
| `instructions/credit_risk.md` | Operating standard: resolve measurement basis before computing, never infer a missing convention, treat text-derived values as evidence not inputs, and state uncertainty. |
| `agents/credit_risk/` charter | Roster, per-agent responsibility, inputs/outputs, serving workflow, and the coverage row justifying existence. Creation is gated, not assumed. |
| `credit_risk_knowledge.py` | Standard-library loader/validator for IDs, references, required fields, intervals, lifecycle graphs, decision-path obligations, governance deployability, point-in-time admission, and golden-case arithmetic. Exposes no scoring or provisioning API. |

## Interfaces & Data Contracts

### Common record envelope

Reuses `0063`'s envelope so the two packs stay one system rather than two
dialects. Every record carries `id`, `record_type`, `name`, `jurisdiction`,
`knowledge_as_of`, `effective_from`, `effective_to`, `knowledge_class`,
`source_refs`, `review_status`, `review`, and `supersedes`, with the same
separation of knowledge time from effective time: a historical query passes the
knowledge/as-of check first, then the effective-time check.

`knowledge_class` extends `0063`'s enum with the credit-specific classes
`accounting_standard` and `regulatory_supervisory_rule`, because an accounting
standard and a supervisory rule have different freshness and effective-date
behavior from a market observation and must not share a class.

### Credit measure record

```json
{
  "id": "measure.pd.one_year.pit",
  "record_type": "convention",
  "name": "One-year point-in-time probability of default",
  "units": "probability",
  "horizon": "P1Y",
  "conditioning": "point_in_time",
  "default_definition_id": "defn.default.dpd_90",
  "collateral_treatment": "not_applicable",
  "discounting_basis": null,
  "currency": null,
  "calibration_population": "...",
  "viewpoint": "role.lender",
  "loss_sign": "not_applicable",
  "formula_ref": "formula.el.pd_lgd_ead",
  "jurisdiction": "US",
  "knowledge_class": "stable_mechanic",
  "review_status": "draft"
}
```

The validator rejects a measure that omits an applicable field, and rejects a
formula reference whose operand bases disagree — a lifetime ECL formula cannot
consume a `horizon: P1Y` PD without an explicit, recorded conversion.

### Decision path contract

```json
{
  "id": "workflow.retail_underwriting_decision",
  "consumer_decision": true,
  "reason_codes": {"derivable": true, "policy_ref": "...", "max_reasons": 4},
  "policy_version_field": "decision_policy_version",
  "cutoff_field": "decision_cutoff",
  "override_log_ref": "...",
  "protected_attributes_in_features": [],
  "disparate_impact_hook": "...",
  "sole_basis_adverse_action_permitted": true
}
```

`consumer_decision: true` with any obligation unmet fails validation unless the
record is restated as `decision_support_only` with
`sole_basis_adverse_action_permitted: false`. That is the correct-by-construction
form of REQ-014: the unsafe configuration is unrepresentable rather than merely
discouraged.

### Point-in-time and leakage controls

Credit's leakage modes are not the market's, so the admission check is explicit
about all six from REQ-008: outcome-window alignment (label maturity after the
decision date), attribute as-of versus refresh date, reject inference with a
disclosed assumption, macro scenario vintage and publication lag, restatement and
re-rating backfill, and survivorship in closed and charged-off populations. Each
rejection names the violated rule, so a failure is diagnostic rather than a bare
false.

### LLM evidence admission

A text-derived value is admitted only as `{artifact_ref (0071), source_spans,
envelope_ref (0070), assumption_ledger_entry, replay_ref, evidence_class}` where
`evidence_class` starts at `derived_evidence`. Promotion to `decision_input`
requires a `review` object with a named reviewer, date, and scope. No automated
path performs that promotion.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Unsafe states are unrepresentable rather than warned about: a consumer-decision path without derivable reason codes fails validation; a measure with mismatched bases cannot enter a formula; deployability is computed from resolving governance artifacts, not asserted; point-in-time admission rejects the six credit leakage modes by rule. |
| P5 Reversibility | yes | `0072` is additive knowledge, contracts, and documentation — no existing runtime changes (AC-021), so revert is deletion of new files plus the index/handoff edits. Child specs carry their own rollback; REQ-015 requires a kill switch or fallback policy before any model is marked deployable. |
| P6 Observability | yes | REQ-015 requires monitoring metrics with thresholds, an override and exception log, and a named owner before deployability; NFR-007 requires every described output to be reproducible from a recorded `0070` envelope. |
| P9 Security & data | yes | NFR-006 prohibits consumer PII, loan tapes, bureau values, credit files, internal counterparty terms, MNPI, secrets, licensed vendor documentation, and agency methodology text. All fixtures synthetic and disclosed under `0025`; `secret-scan` and `data-provenance` gates run. |

P7 (small, reviewable changes) is upheld by scope, not by size: the foundation is
one contract-and-knowledge slice, and the seven runtimes it enables are seven
separately activated specs rather than one program-sized change. P8 is upheld by
the gap register and the Trade-offs table below, which record what was chosen
against and why.

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `coverage.json` capability surface across the four pillars | T-001, T-008 |
| REQ-002 | `taxonomy.json` stable IDs, aliases, non-interchangeable sets | T-003 |
| REQ-003 | Viewpoint/sign fields on every measure record | T-003, T-004 |
| REQ-004 | `conventions.json` credit measure convention registry | T-004 |
| REQ-005 | `lifecycles.json` three transition graphs | T-005 |
| REQ-006 | `source_policy.md` + `0027` source registrations | T-006 |
| REQ-007 | `knowledge_class` enum and as-of/effective separation | T-006, T-009 |
| REQ-008 | Credit point-in-time and leakage admission rules | T-009 |
| REQ-009 | `coverage.json` levels + `gap_register.md` | T-008 |
| REQ-010 | `golden_cases.json` and validator arithmetic | T-010 |
| REQ-011 | `agents/credit_risk/` charter with gated creation | T-011 |
| REQ-012 | `workflows.json` — six named end-to-end workflow contracts | T-012 |
| REQ-013 | Runtime boundary classification (in-SDK / `0026` plugin / knowledge-only) | T-012, T-013 |
| REQ-014 | `decision_paths.json` consumer-decision obligations | T-007 |
| REQ-020 | `convention.fairness.disparity_testing` + per-path `fairness_testing` obligations | T-018 |
| REQ-015 | `governance.json` model card extension + deployability predicate | T-013 |
| REQ-016 | LLM evidence admission boundary over `0070`/`0071` | T-014 |
| REQ-017 | `0073`–`0079` reservations in `docs/handoff.md` | T-002 |
| REQ-018 | `instructions/credit_risk.md` + index/catalog/handoff discoverability | T-002, T-015 |
| REQ-019 | Review status and promotion gate across all record types | T-006, T-016 |
| NFR-001 | Standard-library offline validator and tests | T-010, T-017 |
| NFR-002 | Knowledge/effective time separation and vintage fixtures | T-009 |
| NFR-003 | Evidence completeness gate on `reviewed` promotion | T-006, T-016 |
| NFR-004 | Named credit reviewer; automation cannot self-certify | T-016 |
| NFR-005 | `jurisdiction=US` declared; exclusions explicit | T-002, T-003 |
| NFR-006 | Synthetic-only fixtures, `0025` disclosure, secret/provenance gates | T-010, T-017 |
| NFR-007 | `0070` envelope reproducibility for described outputs | T-014 |
| NFR-008 | Mechanically testable fairness and reason-code contracts | T-007 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Program shape | One foundation spec plus seven reserved child specs | Six or more full spec chains written now | `0063` proved the foundation-first shape works here; designing seven runtimes against an unfrozen contract would rewrite all seven when the contract moves (RISK-005, P7). |
| Pack format | JSON contracts plus Markdown narrative, stdlib validator | YAML, or a schema library dependency | Matches `0063` exactly, keeps NFR-001 achievable with no new dependency, and keeps the two domain packs one system rather than two dialects. |
| Fairness handling | Structural: unsafe consumer-decision configuration is unrepresentable | Documented guidance plus reviewer judgement | P4. Guidance is skipped under delivery pressure; a validation failure is not (REQ-014, RISK-003). |
| Fairness depth | Procedural **and** substantive: disparity measured at the applied cutoff, proxy association recorded, LDA search on breach | Attribute absence from the feature set alone | Absence is trivially satisfiable and certifies nothing; shipping it as *the* fairness control would have let `0074` call a feature-list check compliance (REQ-020, RISK-010). |
| Disparity threshold | A required parameter with no default | The four-fifths ratio as a built-in | It is a screening convention, not a legal threshold or safe harbour. A default would let an adopter inherit a number their counsel never chose. |
| Deployability | Computed from resolving governance artifacts | A `deployable: true` field an author sets | A self-asserted flag is exactly how an unvalidated model reaches production; the predicate cannot be satisfied by assertion (REQ-015). |
| Agent creation | Gated on a coverage-matrix row showing a distinct workflow | Ship the full credit agent roster with the foundation | The catalog is at 168 agents; breadth without distinct workflows makes it unnavigable and violates the repository's standing rule (RISK-007). |
| Retail scoring runtime | Deferred to `0074`, open question left open | Ship a reference scorecard in `0072` | A shipped scorecard would be mistaken for a validated model; the contracts and golden cases deliver the value without that risk. |
| Credit data | Synthetic, disclosed fixtures only, permanently | Anonymized real loan or bureau data | NFR-006. Re-identification risk and licensing make this the one place where "carefully handled real data" is not an option worth weighing (RISK-006). |
| Collateral vocabulary | Reuse `0063`'s haircut/margin/eligibility terms | Define credit-side collateral terms independently | A second definition of the same concept is the exact fragmentation `0063` was written to end. |

## Validation Strategy

Every `AC-*` is proven by a deterministic, offline test in
`tests/test_credit_risk_knowledge.py` that names the criterion in its test name,
mirroring `0063`'s convention. Three classes of evidence:

- **Structural** (AC-001 to AC-006, AC-009, AC-011 to AC-014, AC-016 to AC-020) —
  load the JSON pack and assert required fields, unique IDs, alias determinism,
  graph reachability, obligation completeness, and promotion gates. Negative
  cases are mandatory: each must show the invalid configuration *failing*, not
  merely the valid one passing.
- **Numeric** (AC-010, AC-015) — golden cases run twice and compared within
  declared tolerances, plus the migration-matrix row-stochasticity identity and
  deterministic adverse-action reason ordering.
- **Temporal** (AC-007, AC-008) — vintage fixtures proving a later standard
  version or scenario vintage is excluded from an earlier as-of query, and an
  outcome-window fixture proving a label maturing after the decision date is
  rejected with the violated rule named.

AC-021 and AC-022 are release-review evidence: a diff inspection confirming no
existing runtime's numerical output changed and every fixture is synthetic and
disclosed, and a clean-checkout gate run with no credentials or network.

Test authoring routes through `0062`'s `python_test_engineer`; the negative-case
requirement above is the specific instruction to give it.

## Rollout, Observability & Rollback

Blast radius for `0072` itself is documentation-sized: it adds knowledge,
contracts, an offline validator, tests, and index entries, and changes no
runtime. Rollout is a single reviewed change on the feature branch; rollback is
reverting it.

The real rollout question belongs to the children, and this plan sets its terms
now so they are not decided under delivery pressure later: no credit model
reaches a consumer-facing decision path until REQ-014's obligations validate and
REQ-015's governance artifacts resolve. Monitoring for any activated child covers
at minimum score and PD distribution drift, calibration against realized default
outcomes, override rate, decline-reason mix, and segment performance including
fairness-relevant segments — with thresholds and a named owner recorded before
deployment, per `templates/docs/model_monitoring_plan.md`. The kill switch is a
documented fallback policy (prior model version or human underwriting), and it is
a REQ-015 precondition for deployability rather than a launch-day task.

## Open Questions

- Who is the named credit-domain reviewer? Structural review by the repository
  owner is not a substitute, and no record can reach `reviewed` without this.
- Which pillar has the first real consumer, and therefore which child spec
  activates first? Current expectation is `0077` because `0070`/`0071` are built;
  `0073` is the alternative if a portfolio consumer appears first.
- Does `0074` ship any in-SDK reference scoring runtime, or stay
  contract-plus-fairness-harness only?
- Does credit document intelligence need `0054` (MCP RAG server) activated for
  cited retrieval, or do `0071`'s index snapshots serve the first consumer?
- Should the `0079` model-risk runtime be credit-specific, or generalized across
  the SDK's whole model inventory? Credit is the forcing function, but the need
  is not credit-only.
