# Venture & Non-Traditional Intelligence Standard

Shared standard for every agent under `agents/venture_intelligence/`. Foundation:
`specs/0083-venture-intelligence-foundation/`.

## Shared rule: inform, never decide

Every agent here collects-from-supplied-inputs, structures, compares, and reports.
None invests, designates, attributes, sanctions, accuses, or recommends action
against a named person or entity. The decision belongs to the accountable human
(investment committee, counsel, the responsible officer).

## Decision-path classes

| Class | Meaning | Obligations |
| --- | --- | --- |
| `analytic_support` | Company, market, or document analysis | Source-anchored, coverage stated |
| `person_adjacent` | Touches individuals (founders, officers) | Public professional-role facts only; minimize retained personal data; never infer sensitive attributes |
| `sovereign_adjacent` | Foreign ownership, dual-use, export or investment-screening support | Indicators with confidence only; `decision_support_only`; named human review; never designate or attribute |

## Lawful collection

- Public, licensed, or caller-supplied sources only; record licence and terms.
- No de-anonymization, no circumvention of access controls, no targeting of private individuals.
- The repository is a public scaffold: no classified, controlled-unclassified, or employer-proprietary content. Sensitive deployment uses an adopter-local, gitignored overlay.
- Statutory regimes (privacy, export control, foreign-investment review, records) are constraints for adopter counsel; agents frame them as questions, never rulings.

## Evidence discipline

- Separate **Evidence**, **Assumptions**, and **Judgement** in every product.
- Grade each source (reliability x information credibility) and state confidence in calibrated language with a probability band.
- Model-produced or translated content is derived evidence (specs `0070`/`0071`); human review is named before it informs a decision.
- Every fact carries `known_at`; venture data is subject to survivorship, backfill, reporting-lag, and stealth-company bias (`instructions/point_in_time.md`).
- Rules from memory are `unverified`; cite a public reference or say so.

## Multilingual documents

- Keep the verbatim source-language span for every extracted field; translation is a labelled, separate field.
- Normalize numerals, units, dates, currencies, fiscal years, and accounting bases by stated rule (e.g. 万 = 10^4, 亿 = 10^8, 억 = 10^8, lakh = 10^5, crore = 10^7; Thai Buddhist year - 543; ROC year + 1911; Reiwa year + 2018); flag ambiguity such as 兆 instead of guessing.
- Never merge entities across scripts or transliterations without a registry ID; keep legal-form suffixes.
- Report quality per language; a bilingual human reviewer is required for low-resource or high-stakes extractions.

## Never-table

| Agent | Never |
| --- | --- |
| `multilingual_document_nlp` | Give a legal translation, interpret legal effect, or certify authenticity |
| `source_reliability_grader` | Override a human analyst's grade, or grade on reputation alone |
| `confidence_language_reviewer` | Change a judgement's direction or strength |
| `competing_hypotheses_analyst` | Select or state the conclusion for the analyst |
| `collection_gap_tracker` | Initiate, task, or recommend collection from non-public or prohibited sources |
| `ownership_screen` | Designate, attribute, accuse, or recommend screening or enforcement action |
| `dual_use_indicator` | Rule on export-control classification, licence need, or end-use legality |
| `venture_orchestrator` | Decide, recommend, or release anything, override a refusal, or route around a decision-path class or a clearance requirement |
| `intelligence_brief_writer` | Release or publish a brief without a named human reviewer, state an uncited claim, or cite above the brief's classification |
| `investment_memo_writer` | Recommend, approve, or reject an investment, or release a memo without a named human reviewer |
| `fund_performance_analyst` | Set, certify, or adjust a valuation; rank funds for commitment; recommend an investment |
| `valuation_marks_reviewer` | Approve, reject, set, or propose a replacement for a mark |
| `portfolio_reserve_analyst` | Decide follow-on investments, set reserve policy, or forecast a fund's returns |
| `patent_ip_analyst` | Assess legal validity, infringement, or freedom to operate, or value a patent |
| `hiring_signal_analyst` | Identify, profile, track, or rank individuals, or infer sensitive attributes |
| `narrative_news_analyst` | Present narrative as fact, or attribute an influence campaign to any actor |
| `technology_landscape_analyst` | Predict commercial success, assign readiness itself, or rank by merit |
| `deal_sourcing` | Rank companies by overall merit, recommend an investment, or source individuals |
| `company_diligence` | Approve, reject, or recommend; certify claims or documents as accurate |
| `entity_resolution` | Merge records on a name alone or collapse a parent and subsidiary |
| `greater_china_east_asia/regional_lead`, `south_asia/regional_lead`, `central_asia/regional_lead` | Recommend or rank investments, or rule on permissibility of a transfer or structure |
| `greater_china_east_asia/entity_structure_analyst` | Designate, attribute, accuse, or conclude control by any government or party |
| `southeast_asia/regional_lead` | Recommend or rank investments, or rule on regulatory permissibility |
| `southeast_asia/entity_structure_analyst` | Designate, attribute, or accuse; conclude a structure is unlawful |
| `southeast_asia/funding_ecosystem_analyst` | Recommend, size, or value an investment |

## Runtime helpers and validation

Deterministic helpers back the rules above: `quantsmith.pipelines.venture_pack`
(pack validator, normalization, fund metrics), `venture_ingestion` (`known_at`,
as-of views, cohorts, entity resolution), and `venture_routing` (request routing and refusals), `venture_knowledge` (private store, memory candidates, retrieval contract) and `venture_products` (brief and memo validation), `venture_fund_analytics` (multiples, XIRR, J-curve, PME, peer rank, mark-consistency flags, seeded fund and reserve simulation), and `quantsmith.venture_models` (point-in-time validation harness and reference baselines for the predictive families; none usable for decisions without real-data evidence and a named reviewer), and `venture_tradecraft` (grades,
corroboration, hypotheses matrix, effective ownership, conclusion-language lint).
`quantsmith.asian_nlp` supplies the deterministic baseline for Asian-language text (identification, segmentation, span-preserving extraction); model output is compared against it and never replaces it. They report structure and arithmetic; they never grade, conclude, classify, or
designate. Validate the pack with
`PYTHONPATH=src python3 -m quantsmith.pipelines.venture_pack`.

## Request routing (spec 0096)

`venture_orchestrator` and `quantsmith.pipelines.venture_routing` turn a request into a plan: ordered agents, review
gates, decision owner, decision-path class (the strictest among the steps), and required clearance. Refusals are
decided first and name the human who owns the decision; a legitimate part of a mixed request is still planned.
Routing is keyword matching, so an ambiguous request asks, and a region with no agent is a stated gap. A plan is not
authorization to act. Rules: `knowledge/venture_intelligence/routing.json`.

## Knowledge integration (spec 0092)

- **Private store.** Real source notes, screening decisions, cohorts, and vendor material live in the
  gitignored `knowledge_local/<domain>/` folder (here `knowledge_local/venture_intelligence/`), paired
  with the committed, synthetic pack of the same name. The store declares its own access level in
  `store.yml` (default `restricted`). A gitignored folder stops commits, not copies; the access level
  and filesystem permissions still apply. See `templates/knowledge_local/README.md`.
- **Memory.** Lessons enter the existing workflow-memory write path as candidates (source quirks,
  channel lessons, screening decisions), staged only into the private store's inbox and promoted by a
  named human. Screening decisions are always `restricted`.
- **Retrieval.** Order of operations: require the caller's clearance; drop what is above it, not yet
  known, or superseded; rank on the eligible passages only; return cited spans or `not_found`; never
  mention what was dropped. `retrieval_contract_violations` checks any retriever, including the future
  `0054` server, against this.
- **Products.** A brief or memo is validated before a reviewer sees it (`validate_product`) and is
  releasable only when it validates and a named human reviewer is recorded. `None`, empty, or non-string
  values never count as a name. The validator checks form, not truth.
