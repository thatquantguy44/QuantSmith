# Spec: NLP, LLM, and Quant Text Intelligence Foundation

- **ID:** 0071-nlp-llm-quant-text-intelligence-foundation
- **Status:** Draft (foundation implemented)
- **Author:** Codex
- **Approver:**
- **Last updated:** 2026-09-09

## Problem & Context

QuantSmith already has useful but separate pieces for text-driven workflows:
knowledge agents for ingestion, curation, retrieval, and institutional memory;
provider-neutral `llm_runtime` adapter contracts; MCP resources and memory
servers; planned governed RAG work; a market-research knowledge-base contract;
an approved source catalog; and the prompt/context/harness foundation in spec
`0070`.

What is missing is one governed layer that composes those pieces into
reproducible NLP, LLM, retrieval, embedding, and text-derived signal workflows.
Today a team can describe an LLM provider or retrieve a cited research item, but
there is no shared contract that can answer all of these questions:

- Which approved source documents and point-in-time corpus snapshot were used?
- Which normalization, chunking, redaction, deduplication, labeling, embedding,
  retrieval, reranking, generation, and aggregation steps produced the output?
- Which frontier model, local model, plugin, prompt, tokenizer, checkpoint, or
  index snapshot was invoked, and under which access and license constraints?
- Were train, validation, test, retrieval, and backtest windows protected from
  future documents, duplicate documents, revised text, and benchmark
  contamination?
- Can each classification, extracted fact, summary claim, or numerical signal be
  traced to source spans and replayed deterministically or with declared
  fixtures?

This foundation makes text intelligence a governed quant-data product rather
than an informal model call. It composes existing ownership boundaries and adds
typed text-specific contracts, validation, and evidence without turning the SDK
into a hosted model service, vector database, or licensed-content repository.

## Goals

- Define a typed text-intelligence manifest that extends a `0070` orchestration
  run with corpus, transformation, model-capability, task, evaluation, output,
  and downstream-signal lineage.
- Define point-in-time document, span, corpus-snapshot, and transformation
  contracts for unstructured quant sources.
- Define provider-neutral capability contracts for frontier LLMs, local LLMs,
  embedding models, rerankers, and optional local training or adaptation
  plugins.
- Define embedding and retrieval artifact contracts that pin model revisions,
  preprocessing, access tiers, source spans, and index snapshots.
- Define structured output contracts for quant-relevant text tasks, including
  classification, entity/event/value extraction, sentiment or stance, theme
  detection, retrieval, reranking, summarization, and evidence-backed synthesis.
- Define a text-derived signal contract that preserves decision time, source
  availability, universe, horizon, aggregation, confidence, missingness,
  citations, and lineage to every contributing text span.
- Extend the `0070` evaluation harness, audit events, gates, and replay behavior
  with text-specific leakage, quality, safety, access, and reproducibility
  checks.
- Give existing research, knowledge, economist, portfolio, risk, and strategy
  agents one governed interface for consuming text intelligence without each
  inventing storage, provider, or provenance logic.

## Non-Goals

- No hosted LLM, local inference server, GPU platform, vector database, model
  registry, OCR service, or third-party plugin is selected or deployed by this
  spec.
- No live provider call, web crawl, email scan, paid research feed, or licensed
  dataset is required for the reference implementation.
- No foundation model is trained or fine-tuned by this spec. The foundation
  defines contracts for optional training/adaptation plugins and reproducible
  training evidence; concrete model work requires a bounded follow-on spec.
- No MCP RAG server is implemented here. Spec `0054` owns semantic-search
  transport, cited passages, and access-tier index isolation.
- No market-research storage or entitlement model is redefined here. Spec
  `0056` remains authoritative for that domain.
- No prompt, context, audit, gate-result, assumption, or replay envelope is
  duplicated. Spec `0070` owns those cross-cutting artifacts.
- No raw proprietary prompt, confidential research body, MNPI, PII, credential,
  private model artifact, or licensed source content is committed.
- No claim is made that a fixture replay exactly reproduces a non-deterministic
  hosted model or a mutable external index.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The system shall define a versioned text-intelligence manifest that references a `0070` run envelope and binds task purpose, approved source/corpus snapshot, transformations, model capabilities, outputs, evaluations, audit events, and downstream consumers. | must |
| REQ-002 | The system shall define document, span, and corpus-snapshot contracts with stable IDs, source-catalog ID, content hash, source locator, publication/event/effective/ingestion/observation times, revision or supersession state, language, content type, access level, entitlement/license class, and split membership. | must |
| REQ-003 | The system shall record each text transformation, including extraction or OCR, normalization, redaction, language handling, chunking, overlap, deduplication, labeling, and filtering, with code/config version, parameters, input/output hashes, and ordered lineage. | must |
| REQ-004 | The system shall define a provider-neutral model-capability profile for hosted frontier models, local or self-hosted models, embedding models, rerankers, tokenizers, and training/adaptation plugins, including capability, provider/runtime, model and revision, artifact checksum where available, license, execution location, privacy class, deterministic settings, limits, and fallback behavior. | must |
| REQ-005 | The system shall define embedding and index-snapshot contracts that bind every vector to an authorized approved source span and record embedding model revision, tokenizer, pooling, normalization, dimension, quantization, preprocessing hash, creation time, corpus snapshot, index algorithm/config, access tier, and immutable snapshot ID. | must |
| REQ-006 | The system shall define an optional training/adaptation run contract with base model, immutable training corpus snapshot, labels, split policy, label provenance, objective, seed strategy, environment/hardware, checkpoint hashes, metrics, contamination checks, and model-card or plugin-manifest reference. | should |
| REQ-007 | The system shall define versioned task contracts and structured result schemas for classification, entity/event/value extraction, sentiment or stance, theme detection, semantic retrieval, reranking, summarization, and evidence-backed synthesis, with abstention and unsupported-output states. | must |
| REQ-008 | The system shall define a text-derived quant signal artifact that records decision timestamp, availability lag, universe, entity/instrument mapping, horizon, aggregation rule, source and span lineage, model/task versions, confidence or calibration, missingness, revision policy, and downstream dataset/backtest references. | must |
| REQ-009 | The system shall use only registered `sources/` entries or explicitly local governed knowledge manifests as source authorities, preserving access, credentials-by-reference, quality, freshness, retention, and license constraints through all derived artifacts. | must |
| REQ-010 | Retrieval and generation shall compose the `0052`-`0054` MCP contracts and `0056` market-research governance so caller clearance and entitlement select an eligible index before search, returned claims carry accessible citations, and restricted-resource existence is not leaked. | must |
| REQ-011 | The system shall define text-specific evaluation suites for corpus integrity, temporal correctness, document and near-duplicate overlap, benchmark contamination, retrieval and reranking quality, extraction/classification quality, calibration, citation coverage, faithfulness, robustness, prompt injection, unsafe tool use, privacy, latency, cost, and signal stability. | must |
| REQ-012 | The system shall extend `0070` prompt/context manifests, assumption ledger, evaluation harness, audit event schema, gates, and replay command by reference, including events for corpus selection, text transformation, model/plugin invocation, embedding/index creation, retrieval, citation, evaluation, human review, and signal publication. | must |
| REQ-013 | The system shall prevent point-in-time leakage by excluding text, labels, revisions, embeddings, index contents, and model checkpoints unavailable at the declared decision time, and shall reject train/evaluation/backtest overlap that violates the declared split policy. | must |
| REQ-014 | The system shall support deterministic offline fixtures for all reference flows and shall distinguish deterministic replay, pinned local-model replay, fixture-backed provider/plugin replay, and non-reproducible external execution. | must |
| REQ-015 | Material text-derived outputs shall expose human-review status, reviewer/owner, overrides, rejected alternatives, uncertainty, and escalation conditions before they can be treated as approved research evidence or a production signal. | must |
| REQ-016 | Existing QuantSmith agents shall consume text-intelligence results through shared typed artifacts or MCP resources, without agent-specific provider credentials, direct vector-store access, or private storage logic. | should |
| REQ-017 | Untrusted retrieved text shall be treated as data rather than instructions; the system shall preserve source boundaries and detect or quarantine prompt-injection content, secret/PII/MNPI indicators, unsupported tool requests, and prohibited data classes before model or tool invocation. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Point-in-time correctness | Every output and signal is reproducible from artifacts known at or before its declared decision time; future or revised content is rejected. |
| NFR-002 | Provenance and citation coverage | Every result resolves to the exact corpus snapshot, transformation chain, model/task version, and contributing source spans; sourced claims are cited or marked unsupported. |
| NFR-003 | Access and information barriers | Access and entitlement are enforced before retrieval/index selection; derived artifacts never widen source permissions or reveal restricted-resource existence. |
| NFR-004 | Reproducibility | Reference validation is offline and deterministic; local artifacts are checksum-pinned; remote dependencies use immutable fixtures or are reported as non-reproducible. |
| NFR-005 | Provider and backend neutrality | Contracts do not require one model vendor, orchestration library, vector database, embedding model, hardware target, or storage backend. |
| NFR-006 | Leakage resistance | Exact and near-duplicate documents, future text, revised filings, label leakage, benchmark contamination, and cross-split corpus overlap are checked before promotion. |
| NFR-007 | Security, privacy, and licensing | No secret, credential, PII, MNPI, restricted position, proprietary prompt body, private model payload, or unlicensed content body is required in committed fixtures or audit records. |
| NFR-008 | Auditability | Every material source selection, transformation, invocation, retrieval, evaluation, approval, override, and signal-publication decision is reconstructable without storing unnecessary confidential text. |
| NFR-009 | Operational observability | Runtime profiles expose latency, token/vector volume, failure/retry status, estimated cost where available, model/index drift, freshness, and fallback behavior. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a valid fixture-backed text-intelligence run, when its manifest is validated, then its `0070` envelope, source/corpus snapshot, transformations, model capabilities, outputs, evaluations, audit events, and consumers all resolve with matching versions and hashes. | REQ-001, REQ-012, NFR-002, NFR-004 |
| AC-002 | Given documents from SEC filings, public economic releases, approved news metadata, local knowledge, and governed market research, when corpus snapshots are built, then every document and span carries the required authority, temporal, revision, access, license, and split fields. | REQ-002, REQ-009 |
| AC-003 | Given a document transformed through extraction, redaction, normalization, chunking, and deduplication, when lineage is inspected, then every output span resolves through an ordered, hash-verified transformation chain to the source document. | REQ-003, NFR-002 |
| AC-004 | Given hosted generation, local generation, embedding, reranking, and local-training plugin fixtures, when capability validation runs, then supported operations are accepted and missing revisions, licenses, privacy limits, checksums, or fallback behavior produce actionable findings. | REQ-004, REQ-006, NFR-005, NFR-007 |
| AC-005 | Given an embedding/index fixture, when validation runs, then vector dimensions, preprocessing/model hashes, corpus snapshot, source-span lineage, index config, immutable snapshot ID, and access tier agree; a cross-tier or changed-model vector is rejected. | REQ-005, NFR-003, NFR-004 |
| AC-006 | Given classification, extraction, retrieval, reranking, summarization, and synthesis fixtures, when task results are validated, then each matches its versioned output schema and either carries evidence/confidence or uses an explicit abstention/unsupported state. | REQ-007, NFR-002 |
| AC-007 | Given a text-derived signal used by a dataset or backtest, when lineage is checked, then its decision time, availability lag, universe mapping, horizon, aggregation, confidence, revisions, task/model versions, and contributing spans resolve without future information. | REQ-008, REQ-013, NFR-001 |
| AC-008 | Given an unregistered source, a raw credential, or content whose entitlement forbids indexing, when corpus construction runs, then the item is rejected or quarantined before transformation, embedding, retrieval, or generation. | REQ-009, REQ-017, NFR-007 |
| AC-009 | Given a lower-clearance caller and a mixed-access corpus, when semantic retrieval runs, then only the caller-eligible access-tier index is searched, returned passages are cited, and no result or score reveals restricted-resource existence. | REQ-010, NFR-003 |
| AC-010 | Given future publications, revised filings, duplicated syndication, near-duplicate documents, contaminated benchmarks, or cross-split overlap, when text-specific leakage evaluation runs, then the affected corpus, model, or signal fails promotion with source/span-level findings. | REQ-011, REQ-013, NFR-001, NFR-006 |
| AC-011 | Given retrieval and generation outputs, when the evaluation harness runs, then it reports task metrics, retrieval/reranking quality, calibration, citation coverage, faithfulness, robustness, injection/tool-safety findings, latency/cost, and signal stability or an explicit justified exception for an inapplicable layer. | REQ-011, REQ-012, NFR-009 |
| AC-012 | Given the same deterministic fixture run twice, when the `0070` replay command is invoked, then text artifacts and signal outputs match; a pinned local model or remote fixture is labeled by replay mode, and an unpinned external dependency cannot claim equivalence. | REQ-012, REQ-014, NFR-004 |
| AC-013 | Given retrieved text containing instruction-like content or a request for an undeclared tool, when context is assembled, then the content remains source-delimited data and the unsafe instruction or tool request is blocked and audited. | REQ-017, NFR-007, NFR-008 |
| AC-014 | Given a material text-derived research conclusion or signal, when promotion is requested, then review ownership, status, uncertainty, overrides, rejected alternatives, and escalation criteria are present and auditable. | REQ-015, NFR-008 |
| AC-015 | Given research, knowledge, economist, portfolio, risk, and strategy consumers, when they request text intelligence, then they receive the shared typed result or MCP resource without direct provider credentials or backend-specific logic. | REQ-016, NFR-005 |
| AC-016 | Given a clean checkout, when targeted tests and the `spec`, `docs-link`, `spec-index`, `doc-counts`, `handoff-sync`, `source-catalog`, `knowledge`, `access`, `leakage`, `repro`, `model-plugin`, and `secret-scan` gates run, then the reference foundation passes without network access, credentials, private data, or licensed content. | REQ-011, REQ-014, NFR-004, NFR-007 |

## Data & Dependencies

This foundation composes existing repository contracts and keeps their ownership
intact:

- `agents/deep_learning/nlp_llm/` supplies specialist task framing and review;
  `agents/knowledge/` owns knowledge ingestion, curation, retrieval, and durable
  institutional memory.
- `adapters/llm_runtime/` and
  `src/quantsmith/agentic_code_tools/llm.py` supply the provider-neutral model
  invocation boundary and current deterministic scaffold mode.
- `src/quantsmith/adapters/mcp_servers/` supplies the implemented resources,
  memory, and market-research authorities. Planned spec `0054` remains the owner
  of semantic search, cited passages, and one index per access tier.
- Spec `0056` and `src/quantsmith/pipelines/market_research.py` own normalized
  market-research records, point-in-time filtering, governance, citations,
  audit records, and lifecycle states.
- `sources/` and `instructions/data_source_catalog.md` own approved source
  authority and credentials-by-reference. Current text-capable registrations
  include SEC EDGAR/public SEC materials and the approved news-provider
  metadata entries; economic and market-structure sources may contribute
  releases or documents where their source contract permits it.
- Spec `0070` owns the shared prompt manifest, context manifest, assumption
  ledger, evaluation harness, audit event schema, gates, and replay command.
- `instructions/deep_learning.md`, `instructions/knowledge_base.md`,
  `instructions/point_in_time.md`, `instructions/data_provenance.md`,
  `instructions/reproducibility.md`, and
  `instructions/model_plugin_integration.md` define the governing standards.

Reference fixtures must be fictional, synthetic, or public metadata. Source
locators and hashes may be committed; confidential or licensed text bodies and
private model artifacts must remain in adopter-controlled storage.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | This spec duplicates `0070`, `0054`, or `0056` instead of composing them. | Competing envelopes, audit logs, and retrieval rules make evidence inconsistent. | Freeze ownership in REQ-010/REQ-012 and the plan matrix; text-specific records extend shared artifacts by reference. |
| RISK-002 | Publication date is mistaken for information availability. | Future or revised text leaks into training, retrieval, or a historical signal. | Require publication, ingestion, observation, revision, and decision times plus source-specific availability lag. |
| RISK-003 | Syndicated or lightly edited text crosses train/test/backtest boundaries. | Evaluation and signal quality are overstated. | Evaluate exact hashes, canonical-document groups, and near-duplicate clusters before split assignment and promotion. |
| RISK-004 | Restricted material influences embeddings or ranking before post-search filtering. | Distance scores or outputs reveal protected information. | Select one caller-eligible access-tier index before search and preserve access on every derivative. |
| RISK-005 | Generated synthesis is treated as a primary source or numeric fact. | Unsupported claims become research evidence or trading features. | Preserve source-span citations, output class, confidence, and explicit unsupported/abstention states; require review for material outputs. |
| RISK-006 | Prompt injection in filings, web text, or research triggers model tools. | Untrusted source content changes orchestration behavior or exfiltrates data. | Delimit source text as data, allow only manifest-declared tools, run injection checks, and audit blocked requests. |
| RISK-007 | A mutable hosted model or index is described as reproducible. | Reviewers cannot regenerate the published signal. | Distinguish deterministic, pinned-local, fixture-backed, and non-reproducible replay modes. |
| RISK-008 | Model/plugin flexibility becomes an ungoverned provider escape hatch. | Privacy, license, cost, or output controls vary silently by backend. | Require the same capability, privacy, artifact, evaluation, audit, and fallback contract for every provider. |
| RISK-009 | Licensed research or PII is copied into fixtures, indexes, or audit events. | Compliance, privacy, or vendor breach. | Commit metadata and fictional fixtures only; inherit source entitlements; minimize audit payloads; run secret and access gates. |
| RISK-010 | Rich embeddings or LLMs replace simpler text baselines without evidence. | Cost and complexity increase without durable signal value. | Require lexical/rules-based baselines and task-appropriate lift, calibration, robustness, and stability evidence. |

## Assumptions & Resolved Foundation Decisions

- Assumption: `0071` is a domain extension to `0070`; a text-intelligence run
  has one shared orchestration envelope, not a second run ledger.
- Assumption: existing knowledge agents remain agent contracts; executable text
  pipelines live under `src/quantsmith/` and use those contracts as policy.
- Assumption: corpus, transformation, task, embedding, index, and signal
  manifests use JSON/JSONL for deterministic reference validation.
- Assumption: a minimal lexical or rules-based baseline is required before an
  embedding model or LLM can claim task value.
- Decision: the executable foundation lives in the dedicated
  `src/quantsmith/text_intelligence/` package and remains standard-library only.
- Decision: the reference embedding is an explicitly non-semantic,
  four-dimensional SHA-256 fixture with a whitespace-tokenizer declaration. It
  validates lineage and index contracts and makes no production model claim.
- Decision: no live vector/index backend is selected. `0054` remains the owner
  of cited semantic retrieval and must preserve `0071`'s immutable,
  pre-retrieval access-tier contract when activated.
- Decision: hosted, pinned-local, fixture-backed, and unpinned-external model
  capabilities are represented as provider-neutral profiles. No live model,
  weights, license, hardware target, quantization, or adaptation method is
  approved by this foundation.
- Decision: the first source is `text_intelligence_fixture`, with immutable
  synthetic timestamps and content hashes. Each real source class requires a
  bounded consumer spec to approve availability, revision, retention, license,
  and entitlement rules.
- Decision: fixture ontologies use versioned funding/liquidity labels solely to
  test schema behavior. Production entity, event, stance, theme, instrument,
  and reliability taxonomies remain consumer-owned decisions.
- Decision: every reference output is `fixture_only`, human-reviewed in its
  evidence record, and prohibited from production, client, trading, or real
  backtest use. Promotion thresholds belong to a bounded adopter spec.

## Exceptions

None.
