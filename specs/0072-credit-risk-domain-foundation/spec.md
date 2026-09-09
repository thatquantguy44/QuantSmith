# Spec: Credit Risk Domain Foundation

- **ID:** 0072-credit-risk-domain-foundation
- **Status:** Draft
- **Author:** Joshua Lutkemuller, CFA
- **Approver:**
- **Last updated:** 2026-09-09

## Problem & Context

QuantSmith's coverage is deep on the investment side — signals, portfolio
construction, execution, backtesting, securities financing, and the shared
short-term-markets foundation (`0063`) — and thin on the **credit** side of a
financial institution. Credit risk is where most bank model inventory, most
regulatory scrutiny, and most current AI-deployment demand actually sit, and the
SDK currently has no canonical contract for any of it.

The gap is not a missing model. It is a missing shared vocabulary and a missing
governance boundary. Credit work spans four constituencies that use overlapping
words for different quantities:

- **Wholesale / counterparty credit** — obligor and facility ratings, PD, LGD,
  EAD, drawn and undrawn exposure, limits, concentration, counterparty credit
  risk, credit spreads.
- **Retail / consumer lending** — application and behavioral scorecards,
  cutoffs, adverse action reasons, reject inference, fair-lending testing.
- **Accounting and regulatory capital** — IFRS 9 and CECL expected credit loss,
  staging, lifetime versus 12-month horizons, Basel IRB risk weights, stress
  testing and capital planning submissions.
- **Credit document intelligence** — credit memos, covenant extraction,
  financial spreading, early-warning signals from filings, news, and internal
  documents.

The same five letters mean different things across those four: a "PD" may be
through-the-cycle or point-in-time, one-year or lifetime, IRB-calibrated or
IFRS 9-conditioned, and the four are not interchangeable in any formula. "LGD"
may be downturn or expected. "Default" may mean 90 days past due, unlikeliness
to pay, an IRB reference definition, an IFRS 9 stage 3 trigger, or an internal
watch-list action. "Exposure" may be notional, drawn balance, EAD after a credit
conversion factor, or exposure net of collateral. An agent that silently picks
one of those meanings produces a number that looks right and is wrong, and in
this domain a wrong number can become a declined loan, an understated
provision, or a misstated capital ratio.

Two further problems are specific to deploying **AI** here rather than
statistics:

1. **A credit decision that touches a consumer is a regulated act.** In the U.S.,
   ECOA and Regulation B require specific principal reasons for adverse action;
   SR 11-7 requires model risk management with independent validation, ongoing
   monitoring, and documented limitations. A model output that cannot produce
   reason codes, cannot be validated, or cannot be reproduced is not deployable,
   however accurate it is.
2. **LLM-derived evidence is not yet admissible credit evidence.** Extracting a
   covenant from a credit agreement or a risk factor from a filing is genuinely
   useful, and genuinely unsafe as an unattributed input to a decision. The SDK
   already has the machinery to make it safe — `0070`'s typed run envelope,
   assumption ledger, audit events, and replay, and `0071`'s governed corpora,
   source spans, access tiers, and leakage-aware evaluation — but nothing yet
   requires credit work to use them.

This spec establishes the shared **U.S.-first credit risk domain foundation**
that later scoring, provisioning, capital, and document specs must consume. It
follows `0063`'s pattern deliberately: a knowledge and validation contract plus
an agent-group charter, not a mega-spec that implements every credit model.

## Goals

- Create a canonical, versioned credit risk domain pack covering the four
  pillars above, their measures, conventions, lifecycles, and regulatory
  context.
- Make measurement basis explicit wherever ambiguity changes an answer:
  horizon, conditioning (TTC/PIT), default definition, collateral treatment,
  discounting, currency, seasoning, and economic viewpoint.
- Separate stable mechanics, accounting and regulatory rules, market and
  portfolio observations, and empirical or model claims so point-in-time use is
  correct by construction — including the outcome-window and reject-inference
  leakage modes unique to credit.
- Define an agent-group charter for `agents/credit_risk/` in which every agent
  is justified by a distinct workflow in the coverage matrix, not by the
  existence of a topic.
- Define the end-to-end credit **workflows** those agents compose, and the
  **runtime boundary** that says which reference runtimes ship in the SDK and
  which are adopter-owned models registered through `0026`.
- Make fair lending, adverse action, and SR 11-7 model governance structural
  requirements of any credit decision path, not documentation added afterwards.
- Require LLM-derived credit evidence to arrive through `0070` envelopes and
  `0071` corpora with resolvable citations, never as an unattributed input.
- Inventory current agents, instructions, runtimes, sources, and tests against
  the capability matrix; record gaps rather than hide them, and assign each to a
  bounded follow-on spec.
- Provide deterministic golden cases that future credit runtimes must reproduce
  before claiming compatibility with the foundation.

## Non-Goals

- No scoring, provisioning, capital, stress, or document-extraction runtime is
  implemented by this spec. Those are separate specs `0073`–`0079`.
- No live bureau, vendor, rating-agency, loan-tape, or internal-warehouse
  connection is implemented. Source ingestion belongs to `0078`.
- No consumer data, loan-level tape, bureau attribute, internal counterparty
  term, rating-agency methodology text, or licensed vendor documentation is
  committed. Fixtures are synthetic and disclosed under `0025`.
- No legal, accounting, tax, or regulatory-capital advice. The pack identifies
  authoritative materials, concepts, applicability, and review dates; qualified
  owners decide how a rule applies to a particular institution or exposure.
- No jurisdiction beyond U.S.-first in the initial pack. Extensions must declare
  jurisdiction and conventions explicitly rather than inherit U.S. defaults.
- No new agent is added merely because a topic appears in the taxonomy. The
  coverage matrix must demonstrate a distinct workflow first.
- No existing runtime is silently changed. `0072` is contract and knowledge work;
  every behavioral change gets acceptance criteria in its owning child spec.
- No claim that any artifact here constitutes model validation. Structure can be
  automated; validation under SR 11-7 requires named, independent human review.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The foundation shall define a capability map covering, at minimum: wholesale obligor/facility rating and PD/LGD/EAD measurement; counterparty credit exposure and limits/concentration; retail application and behavioral scoring and underwriting decisions; IFRS 9 and CECL expected credit loss including staging and lifetime measurement; Basel IRB risk weights and regulatory-capital inputs; supervisory stress testing and capital planning; credit document intelligence; and credit model governance and monitoring. Every capability shall carry a scope, coverage level, current artifact(s), limitation, and owning existing or future spec. | must |
| REQ-002 | The foundation shall define a canonical taxonomy with stable IDs, preferred names, aliases, definitions, classifications, parent and related concepts, and collision rules. The following shall not be treated as interchangeable: obligor / facility / exposure / counterparty; PD / expected default frequency / observed default rate; through-the-cycle PD / point-in-time PD; one-year PD / lifetime PD; LGD / loss rate / recovery rate; EAD / notional / drawn balance / credit conversion factor; expected credit loss / impairment / provision / charge-off / write-off; rating grade / score / score band; and each admitted default definition (days-past-due threshold, unlikeliness to pay, IRB reference, IFRS 9 stage 3 trigger, CECL nonaccrual, internal watch-list action). | must |
| REQ-003 | Every measure, formula, and example shall declare its economic viewpoint using canonical roles — at minimum lender/creditor, borrower/obligor, guarantor, protection buyer, protection seller, servicer, and investor — and shall make explicit whether an amount is drawn or undrawn, on- or off-balance-sheet, gross or net of collateral and guarantees, and whether a loss quantity is signed positive or negative. | must |
| REQ-004 | The foundation shall define a machine-readable convention registry for credit measures. Each convention shall carry units (probability, rate, percent, basis points, currency amount), horizon, conditioning basis (TTC/PIT/scenario-conditioned), default definition ID, collateral and guarantee treatment, discounting basis (including effective interest rate for IFRS 9 measurement), currency, seasoning/vintage basis, calibration population, day count where accrual applies, jurisdiction, effective interval, formula reference, and source references. | must |
| REQ-005 | The foundation shall define lifecycle contracts for: obligor/facility credit state (origination, performing, watch, forbearance/modification, stage transition, default, workout, cure, charge-off, recovery, closure); credit approval and limit management (request, analysis, approval authority, limit set, utilization, breach, exception, review); and credit model lifecycle under SR 11-7 (development, independent validation, approval, deployment, monitoring, remediation, retirement). Each contract shall enumerate valid states, events, preconditions, the role that initiates or receives each event, and the artifacts each transition produces. | must |
| REQ-006 | The foundation shall define an evidence hierarchy and source-reference contract. Every reviewed knowledge record shall identify a registered source, authority type, document or dataset locator, publication/retrieval date, jurisdiction, effective interval, access/license class, and the claim or field the source supports. Conflicting sources shall be resolved explicitly or retained as a visible conflict. | must |
| REQ-007 | Every knowledge record shall be classified as one of: stable mechanic, accounting standard, regulatory/supervisory rule, contractual convention, portfolio/market observation, empirical finding, or model assumption. The class shall determine required `as_of`, `effective_from`, `effective_to`, validation, and freshness behavior; no later observation, standard version, or supervisory scenario vintage may leak into an earlier as-of query. | must |
| REQ-008 | The foundation shall define credit-specific point-in-time and leakage rules covering, at minimum: performance/outcome-window alignment (no label observed after the decision date is usable as a feature); bureau and internal attribute as-of versus refresh date; reject inference and its explicit assumption disclosure; macroeconomic scenario vintage and publication lag; restatement and re-rating backfill; and survivorship in closed-account and charged-off populations. | must |
| REQ-009 | The foundation shall contain a coverage matrix and gap register mapping current agents, instructions, runtimes, source entries, and tests to the canonical capabilities. Coverage levels shall distinguish absent, prose-only, contract-only, reference-runtime, and validated-runtime states; limitations and the responsible child spec shall be explicit. | must |
| REQ-010 | The foundation shall provide deterministic golden cases for each pillar. Cases shall include typed inputs, units, viewpoint, convention IDs, source or assumption references, expected outputs, tolerances, and identities where relevant. At minimum the set shall exercise: expected loss from PD/LGD/EAD; EAD from drawn balance and a credit conversion factor; twelve-month versus lifetime ECL with staging and effective-interest discounting; a Basel IRB risk-weight computation; scorecard points-to-odds and cutoff application; adverse action reason ranking from a scored decision; a rating migration matrix and its row-stochastic identity; and a point-in-time admission case that rejects an outcome-window violation. | must |
| REQ-011 | The foundation shall define an agent-group charter for `agents/credit_risk/`, naming each proposed agent, its narrow responsibility, its inputs and outputs, the workflow it serves, and the coverage-matrix row justifying it. An agent shall not be created without such a row, and each created agent shall carry `README.md`, `instructions.md`, `prompt.md`, and `tasks.md` plus a `Spec-Driven Role` section and a row in `agents/README.md`. | must |
| REQ-012 | The foundation shall define named end-to-end credit workflows composing the agent group with existing SDK surfaces, covering at minimum: wholesale obligor review and rating; counterparty limit and concentration review; retail underwriting decision with adverse action output; ECL measurement and staging; supervisory stress and capital planning; and credit document intelligence feeding a credit review. Each workflow shall name its stages, participating agents, required inputs, produced artifacts, gates, and human decision points. | must |
| REQ-013 | The foundation shall define the runtime boundary: which credit runtimes ship in-SDK as dependency-light deterministic references under `src/quantsmith/pipelines/`, and which are adopter-owned models that register through `0026`'s model-plugin contract. Any measure whose correct value is institution-, portfolio-, or policy-specific shall be an input or a plugin, never a hard-coded SDK constant. | must |
| REQ-014 | Any credit workflow that produces or supports a decision about an identifiable consumer applicant or borrower shall be required by contract to: emit principal-reason codes traceable to the model inputs that drove the outcome; record the decision policy version, cutoff, and overrides applied; keep protected-class attributes out of model features while permitting their use in segregated fairness testing; and expose a disparate-impact test hook. A workflow that cannot meet these shall be declared decision-support-only and prohibited from being the sole basis of an adverse action. | must |
| REQ-015 | The foundation shall define credit model governance artifacts consistent with SR 11-7: a model card extending `templates/docs/model_card.md` with credit-specific fields (default definition, calibration population and window, segment performance, downturn treatment, known limitations), required independent validation evidence, a challenger/benchmark comparison, ongoing monitoring metrics and thresholds, an override and exception log, a named owner, and a documented kill switch or fallback policy. A model without these shall not be marked deployable in the coverage matrix. | must |
| REQ-016 | Any LLM- or NLP-derived input to a credit workflow shall arrive as a `0071` text artifact carried inside a `0070` run envelope, with resolvable source spans, a recorded model/prompt/context manifest, an assumption-ledger entry for every inferred value, and replay capability. Such an input shall be labeled derived evidence and shall not be promoted to a decision input without named human review recorded against the record. | must |
| REQ-017 | The foundation shall reserve but not prematurely design seven bounded child specs: `0073` wholesale credit measurement runtime; `0074` retail underwriting and fair-lending runtime; `0075` IFRS 9 / CECL expected credit loss engine; `0076` regulatory capital and supervisory stress testing; `0077` credit document intelligence; `0078` credit data sources and ingestion contracts; and `0079` credit model risk management and monitoring runtime. Each reservation shall name its dependencies and activation boundary. | must |
| REQ-018 | The credit pack shall be discoverable from `specs/README.md`, `docs/handoff.md`, `agents/README.md`, and a shared `instructions/credit_risk.md` operating standard. Existing agents that touch credit concepts shall link to the canonical pack instead of independently redefining shared terms. | should |
| REQ-019 | Every knowledge record, golden case, and agent contract shall carry a review status (`draft`, `reviewed`, `superseded`, `retired`). Promotion to `reviewed` shall require a named credit-domain reviewer, review date, review scope, supporting evidence, and no unresolved severity-high gap affecting that record. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Deterministic, offline validation | All committed schemas, references, effective intervals, lifecycle graphs, and golden cases validate without network access, using the Python standard library plus existing project dependencies only. |
| NFR-002 | Temporal correctness | Every time-varying item carries both knowledge/as-of and effective-time semantics; fixtures prove that a later standard version, scenario vintage, or outcome observation is rejected for an earlier as-of use. |
| NFR-003 | Evidence completeness | 100% of records marked `reviewed` have resolvable source references with field- or claim-level support; unsupported items remain `draft`. |
| NFR-004 | Expert reviewability | Promotion evidence records a non-email reviewer handle, review date, and review scope; automation may validate structure but cannot self-certify credit correctness or constitute model validation. |
| NFR-005 | Bounded scope | The initial pack declares `jurisdiction=US`; every excluded product, portfolio, or jurisdiction is marked out of scope or future rather than implied by a generic term. |
| NFR-006 | Privacy, security, and licensing | No consumer PII, loan-level tape, bureau attribute value, credit file, internal counterparty term, MNPI, secret, licensed vendor documentation, or rating-agency methodology text is committed. All committed examples are synthetic and disclosed per `0025`. |
| NFR-007 | Auditability and reproducibility | Any credit output the pack's contracts describe is reproducible from a recorded `0070` envelope: inputs, convention IDs, policy version, model version, and assumptions, with no hidden state. |
| NFR-008 | Fairness testability | Fairness and adverse action contracts are expressed so they can be tested mechanically on synthetic fixtures: reason codes are derivable, protected attributes are absent from feature sets, and disparate-impact hooks are callable. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given the capability map, when each domain named in REQ-001 is queried, then at least one capability row exists carrying scope, coverage level, current artifact(s), limitation, and owning existing or future spec. | REQ-001, REQ-009 |
| AC-002 | Given the taxonomy, when stable IDs and aliases are validated, then IDs and preferred names are unique, aliases resolve deterministically, and every non-interchangeable pair or set named in REQ-002 remains distinct with no shared alias. | REQ-002 |
| AC-003 | Given any credit measure record, when validated, then its viewpoint, drawn/undrawn and gross/net collateral treatment, and loss-sign convention are present; a measure that omits any of them fails validation. | REQ-003 |
| AC-004 | Given any convention record, when validated, then units, horizon, conditioning basis, default-definition ID, collateral treatment, discounting basis, currency, calibration population, jurisdiction, effective interval, formula reference, and source or assumption references are present as applicable; incompatible or omitted fields fail validation. | REQ-004, NFR-001 |
| AC-005 | Given the three lifecycle contracts, when their transition graphs are validated, then all states are reachable from an initial state, terminal states are explicit, each transition names its initiating role and produced artifact, and an undeclared transition is rejected. | REQ-005 |
| AC-006 | Given a record marked `reviewed`, when evidence validation runs, then every source reference resolves and carries authority, locator, jurisdiction, date, effective interval, access, license, and supported-claim metadata; otherwise the record cannot be promoted. | REQ-006, REQ-019, NFR-003 |
| AC-007 | Given two versions of an accounting standard, supervisory scenario, or portfolio observation, when an as-of date precedes the later version's knowledge date, then the later version is excluded even if its effective interval overlaps. | REQ-007, NFR-002 |
| AC-008 | Given a feature/label fixture whose label outcome window closes after the stated decision date, when point-in-time admission runs, then the case is rejected and the violated rule from REQ-008 is named in the failure. | REQ-008, NFR-002 |
| AC-009 | Given the current repository, when the gap register is inspected, then every capability row at coverage level below `reference-runtime` has an evidence path, severity, disposition, and an owning spec; no row is represented as covered without a named artifact and test. | REQ-009 |
| AC-010 | Given the golden-case set, when it is run twice offline, then every case named in REQ-010 produces identical results within declared tolerances, and the migration-matrix case's rows each sum to one within tolerance. | REQ-010, NFR-001 |
| AC-011 | Given the agent-group charter, when each proposed `agents/credit_risk/` agent is inspected, then it names a coverage-matrix row, a workflow, narrow inputs and outputs, and a distinct responsibility not already held by an existing agent; a proposed agent without such a row is rejected. | REQ-011 |
| AC-012 | Given the workflow contracts, when each workflow named in REQ-012 is inspected, then its stages, participating agents, required inputs, produced artifacts, gates, and human decision points are enumerated, and every referenced agent exists in the charter or is marked as future work with its owning spec. | REQ-012 |
| AC-013 | Given the runtime boundary, when each capability is inspected, then it is classified as in-SDK reference runtime, adopter plugin via `0026`, or knowledge-only, and no institution-, portfolio-, or policy-specific value appears as a hard-coded SDK constant rather than a declared input or parameterized assumption. | REQ-013, NFR-001 |
| AC-014 | Given a workflow contract declared to support a consumer credit decision, when it is validated, then it declares reason-code derivation, decision policy version, cutoff, override recording, an empty protected-attribute feature set, and a callable disparate-impact hook; a contract missing any of these validates only when it is marked decision-support-only and prohibited from sole-basis adverse action. | REQ-014, NFR-008 |
| AC-015 | Given a synthetic scored decision fixture and its declared reason-code policy, when adverse action reasons are derived twice, then the same ordered principal reasons are produced, each traceable to a named model input, and no protected attribute appears among them. | REQ-014, NFR-008, NFR-007 |
| AC-016 | Given a model entry in the coverage matrix marked deployable, when governance validation runs, then a credit model card, independent validation evidence, challenger comparison, monitoring metrics with thresholds, an override log location, a named owner, and a kill-switch or fallback policy are all present; otherwise the entry cannot be marked deployable. | REQ-015, NFR-004 |
| AC-017 | Given an LLM-derived value proposed as a credit workflow input, when admission validation runs, then it carries a `0071` artifact reference with resolvable source spans, a `0070` envelope with prompt/context manifest and assumption-ledger entry, and a replay reference; without named human review it is admitted only as labeled derived evidence, never as a decision input. | REQ-016, NFR-007 |
| AC-018 | Given `docs/handoff.md` and `specs/README.md`, when the planned-spec tables are inspected, then `0073`–`0079` appear with the scopes, dependencies, and activation rule required by REQ-017, `0072` is identified as the active Draft, and the next unreserved number is `0080`. | REQ-017, REQ-018 |
| AC-019 | Given the repository's existing agents and instructions, when a credit term or convention is needed, then `instructions/credit_risk.md` exists and the touching agents point to the canonical pack; any retained local summary is consistent with it and declares its scope. | REQ-018 |
| AC-020 | Given a knowledge record, golden case, or agent contract proposed as `reviewed`, when reviewer metadata is absent or a severity-high gap remains open against it, then promotion is rejected. | REQ-019, NFR-004 |
| AC-021 | Given the `0072` implementation diff, when reviewed, then no existing runtime's numerical output changed, and every committed example is synthetic and carries a `0025` disclosure. | REQ-013, NFR-005, NFR-006 |
| AC-022 | Given a clean checkout, when the credit validation module and the existing repository gates run, then they pass without credentials, network access, consumer data, or private data. | NFR-001, NFR-006 |

## Data & Dependencies

### Existing repository dependencies

- `0063-short-term-markets-domain-foundation` — the pattern this spec follows and
  the source of collateral, haircut, and margin vocabulary that counterparty
  credit reuses rather than redefines.
- `0070-prompt-context-harness-foundation` — the typed run envelope, prompt and
  context manifests, assumption ledger, audit events, and replay engine that
  make a credit output auditable (REQ-016, NFR-007).
- `0071-nlp-llm-quant-text-intelligence-foundation` — governed corpora, source
  spans, access tiers, structured text tasks, and leakage-aware evaluation that
  credit document intelligence consumes (REQ-016).
- `0026-model-plugin-adapter` — the registration and invocation boundary for
  adopter-owned scoring, ECL, and capital models (REQ-013).
- `0027-source-catalog` and `templates/data/source_catalog_entry.yml` — the
  canonical source registry; this spec registers metadata, not a second registry.
- `0025-data-provenance-guardrail` — real-data-first policy and the synthetic
  data disclosure every committed credit fixture requires (NFR-006).
- `0038-factor-risk-model`, `0044-backtesting`, `0046-walk-forward` — existing
  risk, evaluation, and validation surfaces credit models should reuse.
- `templates/docs/model_card.md`, `model_monitoring_plan.md`,
  `production_readiness_checklist.md`, `decision_log.md` — the governance
  templates REQ-015 extends rather than replaces.
- `instructions/point_in_time.md`, `instructions/data_provenance.md`,
  `instructions/model_validation.md`, `instructions/risk_management.md` —
  temporal, evidence, validation, and risk constraints already in force.

### External source classes to register during implementation

The foundation records locators and claim-level support; it does not copy source
content. Priority order:

1. statutes, regulations, and supervisory guidance (for example ECOA and
   Regulation B for adverse action, and supervisory model risk management
   guidance);
2. accounting standard-setter material for impairment and expected credit loss;
3. international and national capital-framework text and national implementing
   rules;
4. supervisory stress-testing scenarios, instructions, and reporting forms;
5. official statistical and macroeconomic publishers already registered under
   `0027` (used as scenario drivers, with vintage controls);
6. rating agency and vendor methodology documents, by public locator only,
   subject to access terms and never reproduced;
7. reviewed internal credit policy; and
8. analyst interpretation, always labeled and never promoted above its evidence.

Inclusion in this list is not evidence by itself; each record must cite the
specific document or dataset version it uses.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A polished credit taxonomy is mistaken for validated credit expertise. | Agents answer confidently from structure without substance; a wrong provision or decline looks authoritative. | `draft` versus `reviewed` separation, claim-level evidence, named credit-domain reviewer, coverage levels and gaps exposed (REQ-019, NFR-004). |
| RISK-002 | Measurement bases are silently mixed — TTC PD in an IFRS 9 formula, expected LGD where downturn LGD is required, notional where EAD is required. | Provisions, capital, and pricing are wrong in ways that reconcile internally and fail externally. | Mandatory convention fields, non-interchangeable term sets, and golden cases that fail on basis mismatch (REQ-002, REQ-004, REQ-010). |
| RISK-003 | A consumer-facing decision path ships without deployable reason codes or fairness testing. | Regulatory exposure, consumer harm, and an undeployable model at the last gate. | REQ-014 makes reason codes, policy versioning, protected-attribute segregation, and a disparate-impact hook structural; a contract that cannot meet them is decision-support-only. |
| RISK-004 | LLM-extracted document evidence becomes an unattributed decision input. | An unverifiable, unreproducible fact underpins a credit decision. | REQ-016 requires `0071` source spans inside a `0070` envelope, an assumption-ledger entry, replay, and named human review before promotion. |
| RISK-005 | The foundation becomes an encyclopedia and no runtime follows. | Review stalls; the SDK gains breadth on paper and nothing usable. | U.S.-first boundary, fixed artifact contracts, explicit non-goals, and seven separately activated child specs (REQ-017, RISK mitigation mirrors `0063`). |
| RISK-006 | Committed fixtures leak consumer or counterparty data. | Privacy and contractual breach; the most serious failure available here. | NFR-006 prohibits real credit data outright; all fixtures synthetic and disclosed under `0025`; `secret-scan` and `data-provenance` gates run. |
| RISK-007 | Agent sprawl: a credit agent per topic rather than per workflow. | 168 agents becomes 190 and the catalog stops being navigable. | REQ-011 requires a coverage-matrix row and a distinct workflow before an agent exists; the charter is reviewed as a whole. |
| RISK-008 | Existing runtimes appear credit-compatible because names match while assumptions do not. | Silent model error survives the documentation layer. | Coverage levels, gap register, golden cases, and explicit child-spec ownership; no compatibility claim without validation (REQ-009). |
| RISK-009 | Regulatory and accounting rules change, or supervisory scenarios are revised. | Stale rules served as current, or a later scenario vintage leaking into a historical analysis. | Effective intervals, knowledge/as-of separation, source versions, supersession, and freshness review owned by `0078`/`0079` (REQ-007, NFR-002). |

## Assumptions & Open Questions

- Assumption: U.S.-first, mirroring `0063`, because the registered source
  catalog and likely first consumers are most developed there. Other
  jurisdictions extend the schemas; they do not silently reuse U.S. defaults.
- Assumption: canonical machine-readable artifacts use JSON so offline
  validation needs no new parser dependency; Markdown carries narrative and
  citations. This matches `0063` and keeps NFR-001 achievable.
- Assumption: no real credit data will ever be committed to this repository, so
  every golden case is a synthetic, disclosed fixture whose purpose is to pin a
  convention or an identity, not to evidence portfolio behavior.
- Assumption: adopter-owned scoring, ECL, and capital models are the norm;
  in-SDK runtimes exist to make conventions executable and testable, not to
  compete with a bank's validated model inventory.
- Open question: which named credit practitioner — a credit risk officer, model
  validator, or CECL/IFRS 9 owner — approves records as `reviewed`? Structural
  review by the repository owner is not the same signature.
- Open question: which pillar has the first real consumer? The coverage matrix
  must answer before any of `0073`–`0077` is activated. Current expectation is
  `0077` (document intelligence) because `0070`/`0071` are already built, with
  `0073` (wholesale measurement) as the alternative if a portfolio consumer
  appears first.
- Open question: should retail underwriting (`0074`) ship any in-SDK reference
  scoring runtime at all, or remain contract-plus-fairness-harness only, given
  that any shipped scorecard risks being mistaken for a validated model? `0072`
  supplies the contracts and golden cases either way and does not prejudge it.
- Open question: does credit document intelligence need `0054` (MCP RAG server)
  activated for cited retrieval, or can `0071`'s index snapshots serve the first
  consumer without it?

## Exceptions

None.
