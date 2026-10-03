# Spec: Venture & Non-Traditional Intelligence Foundation

- **ID:** 0083-venture-intelligence-foundation
- **Status:** Draft
- **Author:** Joshua Lutkemuller, CFA
- **Approver:**
- **Last updated:** 2026-10-02

> WHAT and WHY only. Implementation lives in `plan.md`. This is an **umbrella
> foundation spec** in the shape of `0063` and `0072`: it defines the domain
> contract, vocabulary, guardrails, roster, and child-spec roadmap. It ships no
> agents and no models itself; each agent group is created by a bounded child
> spec (`0084`–`0092`) only when this spec's coverage matrix justifies it.

## Problem & Context

The SDK has deep coverage of public-market quant research, credit, and
enterprise risk, but nothing for **venture capital and non-traditional
intelligence channels**: private-company and early-stage technology
assessment, and the alternative signals (patents, publications, open-source
activity, hiring, grants and procurement, filings, trade flows, narrative
data) that precede or substitute for conventional financial disclosure. A
Lead Data Scientist in this domain needs three things the repo does not yet
provide: a shared **dictionary** so analysts, engineers, and reviewers mean the
same thing by "round", "TVPI", "source reliability", or "technology readiness";
a **knowledge base** of channels, sources, and their documented failure modes;
and **models and agents** that are correct by construction in a domain whose
data is unusually hostile to naive modelling.

Why the domain needs its own foundation rather than reusing quant defaults:

- **Venture data is biased by construction.** Databases backfill, survive
  selectively, report late, and omit stealth companies. A leak-free backtest on
  the standard quant pattern (`instructions/point_in_time.md`) is necessary but
  not sufficient; survivorship, backfill, and selection need domain-specific
  contracts.
- **Non-traditional channels are not interchangeable with evidence.** A hiring
  spike, a patent filing, and a procurement award have different lead times,
  coverage, and deception risks. Treating them as one "alt-data" bucket is the
  same failure `0072` fixed for credit measures.
- **Intelligence work has its own tradecraft.** Source reliability grading,
  calibrated confidence language, competing-hypothesis analysis, and
  collection-gap tracking are standards of the profession, and an LLM-assisted
  workflow that omits them produces fluent, unauditable judgement.
- **Some workflows touch people and sovereign interests.** Founder and network
  analysis, foreign-ownership screening, and dual-use technology assessment sit
  next to privacy law, export control, and enforcement decisions. The boundary
  between *informing* a human decision and *making* it must be structural.

## Goals

- Define the venture and non-traditional-intelligence domain once: taxonomy,
  conventions, vocabulary, and signal-channel catalog, as a governed,
  versioned, public knowledge pack plus human-readable standard.
- Make the bias problems structural: venture-specific point-in-time,
  survivorship, backfill, and reporting-lag contracts that later models must
  satisfy.
- Adopt intelligence tradecraft as first-class conventions: source reliability
  and information credibility grading, calibrated confidence language, and a
  separation of evidence, assumption, and judgement.
- State the decision boundary up front: every agent and model in this domain
  informs a human; none invests, designates, attributes, sanctions, or
  recommends action against a named person or entity.
- Specify the full agent roster, model catalog, and workflows at charter level,
  gated by a coverage matrix, with an ordered child-spec roadmap so the suite
  is built incrementally and traceably rather than all at once.
- Serve as a knowledge base and dictionary: every term and channel has one
  definition, one owner document, and a citation or an explicit
  `unverified` label.

## Non-Goals

- **No agents, runtimes, or trained models in this spec.** Charters are
  designed here; creation is gated to child specs (same rule as `0072`'s
  standing rule against adding agents to fill a map). The first child,
  `0084`, builds the multilingual document agent and the Southeast Asia
  regional group.
- **No real data, no real company or person records, and no classified,
  controlled-unclassified (CUI), or employer-proprietary content in this
  repository.** The repo is a public scaffold; sensitive deployment is an
  adopter-local overlay (REQ-015).
- **Not an investment, intelligence-collection, or enforcement system.** It
  specifies analysis support; it does not collect from non-public sources,
  does not de-anonymize, and does not target private individuals.
- **Not legal advice.** Statutory regimes (export control, foreign-investment
  review, privacy, records) are named as constraints for adopter counsel to
  apply; this spec does not interpret them.
- **Not a replacement for existing agents.** Public-market, credit, and
  enterprise-risk work stays with its current agents; this domain reuses
  `0070`/`0071`/`0052`–`0054`/`0026` rather than redefining them.
- **Not vendor selection.** Commercial venture databases are named as source
  *types*; choosing and licensing one is an adopter decision.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The SDK shall add `instructions/venture_intelligence.md`, the domain standard stating scope, the shared decision boundary (inform, never decide), lawful-collection rules, and per-workflow "never does this" entries. | must |
| REQ-002 | The SDK shall define a domain taxonomy (`knowledge/venture_intelligence/taxonomy.json`) covering at least: company, round, instrument, investor, fund, limited partner, technology domain, government program, signal, source, and analytic product, with stable IDs and relationship types. People appear only as professional roles tied to public, organization-level facts. | must |
| REQ-003 | The SDK shall define a convention registry (`conventions.json`) for venture mechanics — pre/post-money valuation, option-pool treatment, dilution, liquidation preference, round and stage naming, and fund metrics (DPI, RVPI, TVPI, IRR, MOIC, PME, J-curve) — each with formula, sign, unit, and the date it is measured on. | must |
| REQ-004 | The SDK shall define venture-specific data-time semantics: event time vs announced vs filed vs database-ingested vs first-observed time; required `known_at` on every fact; and explicit contracts for survivorship, backfill, reporting lag, and stealth-company omission. | must |
| REQ-005 | The SDK shall define source and analytic grading conventions: a two-axis source reliability / information credibility grade, calibrated confidence language mapped to probability bands, and the separation of evidence, assumption, and judgement in every analytic product. | must |
| REQ-006 | The SDK shall catalog non-traditional signal channels (`channels.json`) — at minimum patents, publications, open-source activity, hiring and labour data, grants and procurement, regulatory filings, trade and customs, web and app telemetry, narrative/news data, and satellite or geospatial — each with lead time, coverage, known biases, deception risks, licensing/legal constraints, and a point-in-time support statement. | must |
| REQ-007 | The SDK shall extend `agentic_dictionary.md` with a Venture & Intelligence section and ship a machine-readable `glossary.json`; every term has one definition, one owning document, and a citation or an `unverified` label. | must |
| REQ-008 | The SDK shall publish an agent roster and coverage matrix (`coverage.json`) listing proposed agents by group, each with a distinct workflow, inputs, outputs, a "never does" boundary, and the child spec that creates it; no agent may be created without a coverage row showing a workflow no existing agent holds. | must |
| REQ-009 | The SDK shall publish a model catalog covering at least: entity resolution, round-progression survival, technology-emergence detection, network and link analysis, funding-flow anomaly detection, sector-funding nowcasting, and fund-outcome simulation — each with target, point-in-time feature rules, baseline, validation design, and documented failure modes. | must |
| REQ-010 | The SDK shall classify every workflow with a **decision-path class**: `analytic_support`, `person_adjacent`, or `sovereign_adjacent`. The latter two are valid only as `decision_support_only`, require named human review, and carry stricter obligations (REQ-011). | must |
| REQ-011 | `person_adjacent` workflows shall use only public, lawfully collected, organization-level or professional-role facts, minimize retained personal data, and never infer sensitive attributes. `sovereign_adjacent` workflows (foreign-ownership, dual-use, export-control, investment-screening support) shall present findings as indicators with stated confidence and shall never designate, attribute, or recommend action against a named person or entity. | must |
| REQ-012 | The SDK shall publish a gap register (`gaps.json`) of known-unknowns with severity, and golden cases (deterministic worked examples: dilution, TVPI/DPI, source grade, confidence mapping, survivorship-biased vs corrected hit rate). | must |
| REQ-013 | The SDK shall ship a stdlib-only offline validator for the knowledge pack checking referential integrity (IDs resolve), convention arithmetic against golden cases, and governance invariants (REQ-010/REQ-011 classes present and consistent). | must |
| REQ-014 | The foundation shall reuse, not redefine, `0070` (run envelope, assumption ledger), `0071` (governed corpora, LLM evidence boundary), `0052`–`0054` (access-tiered retrieval), `0025` (synthetic-data disclosure), and `0026` (adopter-owned model plugins). | must |
| REQ-015 | The SDK shall define an adopter-local overlay for sensitive deployment: a gitignored configuration naming data handling environment, access tiers, retention, and prohibited sources, following the `memory/manifest.yaml` and `role_context.yml` local-only patterns. | should |
| REQ-016 | The SDK shall publish an ordered child-spec roadmap (`0084`–`0092`), each with scope, dependency, and the coverage rows it closes. | must |
| REQ-018 | The SDK shall define a multilingual document-intelligence standard for start-up financial and legal documents (term sheets, shareholder agreements, financial statements, prospectuses, registry filings, pitch decks) covering at least Mandarin (Simplified and Traditional), Bahasa Indonesia/Malay, Vietnamese, Thai, and Filipino: source-span preservation, translation as labelled derived evidence, unit/numeral/calendar/currency normalization, legal-entity-suffix handling, and bilingual-clause precedence. | must |
| REQ-019 | The SDK shall organize regional venture agents by world region under `agents/venture_intelligence/`, one region folder per region with a regional lead and only those specialists a coverage row justifies; Southeast Asia is built first and the remaining regions are reserved with scope in the regional roster. | must |
| REQ-017 | The SDK shall define canonical workflow definitions (`workflows.md` entries) for at least: deal sourcing to diligence memo, signal-to-thesis, technology landscape scan, portfolio and fund review, and counter-diligence screening. | should |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Offline determinism | The validator and golden cases run offline, stdlib-only, and produce identical output on repeat runs. |
| NFR-002 | Data provenance | Every example record is synthetic and disclosed per `0025`; no real entity, person, or filing appears anywhere in the repo. |
| NFR-003 | Catalog consistency | `hooks/stages/run-stage.sh spec` and the required-docs, agent-catalog, and shell-syntax gates pass. |
| NFR-004 | Citation discipline | Every non-trivial claim in the pack cites a public reference or carries `unverified`; no claim is stated as settled without one. |
| NFR-005 | Reversibility | Removing the foundation is deleting its directories and doc sections; it modifies no existing agent, pack, or runtime. |
| NFR-006 | Licence hygiene | Source entries record licence and redistribution terms; no commercial-database content is vendored. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given `instructions/venture_intelligence.md`, when read, then it states the inform-never-decide rule, lawful-collection rules, and a per-workflow never-table. | REQ-001 |
| AC-002 | Given `taxonomy.json`, when validated, then every listed entity type has a stable ID, every relationship endpoint resolves, and no entity type models a natural person except as a public professional role. | REQ-002 |
| AC-003 | Given `conventions.json` and its golden cases, when recomputed, then post-money, dilution, DPI, RVPI, TVPI, and MOIC cases reproduce expected values exactly and signs/units match the registry. | REQ-003, NFR-001 |
| AC-004 | Given the data-time contract, when a fact lacks `known_at`, then the validator rejects the golden record; and a survivorship-biased cohort hit rate differs from the corrected one in the golden case. | REQ-004 |
| AC-005 | Given the grading conventions, when a golden analytic product is checked, then it carries a source grade, a confidence level mapped to a probability band, and distinct evidence/assumption/judgement sections. | REQ-005 |
| AC-006 | Given `channels.json`, when validated, then every channel has lead time, coverage, bias, deception risk, licensing note, and a point-in-time statement, and covers all ten channel families named in REQ-006. | REQ-006 |
| AC-007 | Given the dictionary and `glossary.json`, when diffed, then every term appears in both with one owning document and a citation or `unverified` label, and no term has two definitions. | REQ-007 |
| AC-008 | Given `coverage.json`, when validated, then every proposed agent has a distinct workflow, a never-boundary, and a creating child spec, and no two rows share a workflow. | REQ-008, REQ-016 |
| AC-009 | Given the model catalog, when validated, then each model names target, PIT feature rule, baseline, validation design, and failure modes, and the seven required families are present. | REQ-009 |
| AC-010 | Given the workflow registry, when validated, then every workflow has a decision-path class, and each `person_adjacent`/`sovereign_adjacent` workflow is `decision_support_only` with a named human-review requirement. | REQ-010, REQ-011 |
| AC-011 | Given the gap register and golden cases, when loaded, then every gap has severity and an owning child spec, and every golden case runs deterministically. | REQ-012, NFR-001 |
| AC-012 | Given the repository, when the validator runs, then it reports zero errors and the test module covers the referential, arithmetic, and governance checks. | REQ-013 |
| AC-013 | Given the plan, when read, then it names the `0070`/`0071`/`0052`–`0054`/`0025`/`0026` reuse points and defines no competing envelope, corpus, or access tier. | REQ-014 |
| AC-014 | Given the overlay template, when copied and populated, then it is gitignored, contains no secrets, and the validator refuses an overlay that enables a prohibited source class. | REQ-015 |
| AC-015 | Given `specs/README.md`, when read, then `0084`–`0092` are reserved with scope, dependency, and closed coverage rows. | REQ-016 |
| AC-016 | Given the workflow definitions, when read, then each of the five required workflows names its agents, inputs, outputs, review gates, and decision-path class. | REQ-017 |
| AC-020 | Given the multilingual standard, when read, then it specifies span preservation, derived-evidence labelling of translations, and normalization rules for Mandarin numerals (万/亿), Thai Buddhist-era dates, and local legal-entity suffixes, with a synthetic golden case per language family. | REQ-018 |
| AC-021 | Given `agents/venture_intelligence/`, when listed, then each region folder has a regional lead, each agent has the four contract files and a never-boundary, and the regional roster names every unbuilt region with its scope and creating child spec. | REQ-019 |
| AC-017 | Given the full repository, when `run-stage.sh spec`, agent-catalog, and required-docs gates run, then they pass with no new findings. | NFR-003 |
| AC-018 | Given a repo-wide scan, when searching examples and fixtures, then every record is flagged synthetic and none matches a real entity, person, or filing identifier. | NFR-002, NFR-006 |
| AC-019 | Given the pack, when sampled, then every claim cited or `unverified`, and the git diff shows no existing agent, pack, or runtime modified. | NFR-004, NFR-005 |

## Data & Dependencies

- **Reuses (not redefines):** `0070` run envelope and assumption ledger;
  `0071` governed corpora and LLM-evidence boundary; `0052`–`0054` access-tiered
  MCP retrieval; `0025` synthetic-data disclosure; `0026` adopter-owned model
  plugins; `instructions/point_in_time.md`, `data_provenance.md`,
  `data_source_catalog.md`, `knowledge_base.md`.
- **Public source *types* named in the channel catalog** (adapters belong to
  `0084`, not here): SEC EDGAR (Form D, 13F, S-1), USPTO / PatentsView,
  OpenAlex / arXiv / Semantic Scholar, GitHub archive, USAspending / SAM.gov /
  SBIR.gov, GDELT and news corpora, BLS/Census trade and labour series,
  job-posting aggregates, and licensed commercial venture databases.
- **Constraints named for adopter counsel:** privacy and records law, export
  control (EAR/ITAR classification), foreign-investment review, outbound
  investment rules, vendor licence terms, and any authority limits that govern
  the adopting agency's collection. This spec does not interpret them.
- **Access:** repo content is public. Anything sensitive lives in the REQ-015
  overlay and in adopter-controlled storage with `0052`-style access tiers.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | Survivorship, backfill, or reporting-lag bias makes a signal look predictive when it is not. | Confident but false theses; wasted or harmful allocation. | REQ-004 contracts; golden survivorship case; child `0090` requires bias-corrected baselines before any model is called useful. |
| RISK-002 | Founder or network analysis drifts into profiling private individuals. | Privacy harm; legal exposure. | REQ-001/REQ-011 person-adjacent class; people modelled only as public professional roles; sensitive-attribute inference prohibited. |
| RISK-003 | Sovereign-adjacent screening output is read as an attribution or enforcement finding. | Wrongful action against an entity or person. | `decision_support_only`, indicators with confidence, never-designate rule, named human review. |
| RISK-004 | LLM-extracted facts about companies are fabricated or stale and enter a memo as evidence. | Unauditable false claims. | Reuse `0071`/`0070` evidence boundary; derived-evidence label; REQ-005 evidence/assumption/judgement split. |
| RISK-005 | Adversarial manipulation of public signals (fake hiring, inflated GitHub stars, seeded press). | Signal reflects deception, not reality. | Per-channel deception-risk field (REQ-006); corroboration rule across independent channels in child `0087`. |
| RISK-006 | Agent roster grows to fill the map. | Overlapping charters, review noise. | REQ-008 coverage-gating; no agent without a distinct-workflow row. |
| RISK-007 | Scaffold is mistaken for a safe place to put sensitive or proprietary material. | Disclosure of controlled or employer data. | Non-goal stated in the standard and README; REQ-015 overlay; gitignore and secret-scan gates. |
| RISK-008 | Small-sample venture outcomes overfit models. | Spurious "power-law" or hit-rate conclusions. | Child `0090` mandates interval estimates, simulation of the null, and honest-reporting language. |

## Assumptions & Open Questions

- Assumption: the work is analytic support for investment and technology
  assessment by a government-affiliated venture/intelligence function, and
  the first deployment is in an **unclassified** environment.
- Assumption: licensed commercial venture data is available to the adopter but
  not redistributable here.
- **Resolved for the proof of concept (2026-10-02):** no legal limits are
  imposed yet because this is a proof of concept; the lawful-collection rules in
  `instructions/venture_intelligence.md` still apply, and limits must be set
  before any operational use. Missions: technology scouting, portfolio
  consulting, foreign-influence screening. Candidate databases:
  `docs/venture_database_recommendations.md` (local-only, gitignored).
- **Open question (before operational use):** the adopting agency's legal authorities
  and collection limits (e.g. rules on US-person data, public-source
  collection, retention). The overlay (REQ-015) is designed to carry the
  answer; the answer itself comes from counsel, not this repo.
- **Open question:** primary mission weighting — portfolio investing, technology
  scouting, counter-diligence/foreign-influence screening, or equal. Affects
  child-spec ordering, not the foundation.
- **Open question:** which licensed venture databases are in scope, since their
  schemas and backfill behaviour drive the survivorship contract.
- **Open question:** is the ten-family channel list complete for the mission
  (e.g. dark-web, maritime/AIS, or telecom metadata are deliberately excluded
  pending legal review).

## Exceptions

None.
