# Plan: NLP, LLM, and Quant Text Intelligence Foundation

- **Spec:** 0071-nlp-llm-quant-text-intelligence-foundation (`spec.md`)
- **Status:** Draft
- **Author:** Codex
- **Last updated:** 2026-09-06

> HOW. Implementation begins only after the Draft's open decisions are approved.
> Every requirement in `spec.md` appears in the traceability matrix below.

## Approach

Implement a dependency-light, typed text-intelligence layer that extends the
`0070` orchestration run envelope with domain artifacts. The layer will record
what text was eligible at decision time, how it was transformed, which model or
plugin capability operated on it, how outputs were evaluated, and how any
downstream quant signal was derived.

The implementation will keep model execution and storage replaceable. A small
deterministic reference path will use synthetic/public-metadata fixtures and a
lexical baseline. Frontier LLMs, local LLMs, embedding models, rerankers, vector
indexes, and training systems attach through typed capability profiles and
fixtureable adapter calls. The foundation validates evidence around those calls;
it does not make a provider claim trustworthy merely because an adapter returned
success.

Work is divided into four slices:

1. Governed corpus: source authority, document/span schemas, temporal fields,
   transformation lineage, deduplication groups, and immutable corpus snapshots.
2. Model capabilities: hosted/local generation, embeddings, reranking, optional
   training/adaptation, index snapshots, task schemas, and deterministic fixtures.
3. Quant validation: text-specific harness checks, output evidence, review state,
   and point-in-time text-signal lineage into datasets and backtests.
4. Orchestration integration: `0070` manifests/audit/replay/gates plus `0054` MCP
   semantic retrieval when those dependencies are implemented.

## Architecture & Components

```text
sources/ + governed knowledge manifests
  -> source eligibility and access policy
  -> document/span records
  -> ordered transform lineage
  -> immutable corpus snapshot + split/dedup groups
  -> model capability adapter
       |-- lexical/rules baseline
       |-- hosted frontier LLM fixture or invocation
       |-- pinned local LLM fixture or invocation
       |-- embedding/reranker fixture or invocation
       `-- optional training/adaptation plugin
  -> task result + source-span evidence
  -> embedding/index snapshot or text-derived signal
  -> text-specific evaluation suite
  -> 0070 audit, gates, and replay report
```

Planned implementation surfaces:

| Surface | Responsibility |
| --- | --- |
| `src/quantsmith/text_intelligence/` or approved existing package | Dataclasses, parsers, validators, temporal eligibility, transform lineage, model-capability profiles, task results, signal records, and replay extensions. Final package location is an open question. |
| `templates/text_intelligence/` | Minimal manifests for source/corpus, transformations, model capabilities, tasks, embeddings/index snapshots, evaluations, and text-derived signals. |
| `examples/text_intelligence/` | One deterministic extraction/signal flow and one fixture-backed retrieval/generation flow using fictional or public metadata. |
| `src/quantsmith/adapters/mcp_servers/` | Integration with existing authorities and future `0054` semantic retrieval; no duplicate transport. |
| `adapters/llm_runtime/` | Expanded provider-neutral capability documentation for generation, embedding, reranking, and optional local training/adaptation. |
| `hooks/stages/` | Text-intelligence validation, composed into `0070` orchestration and existing source/access/leakage/repro/secret gates. |
| `tests/test_text_intelligence.py` plus gate/CLI tests | Deterministic acceptance evidence for contracts, leakage failures, access isolation, task quality, signal lineage, and replay modes. |

## Ownership Boundaries

| Concern | Existing owner | `0071` responsibility |
| --- | --- | --- |
| Knowledge ingestion, curation, retrieval, durable memory | `agents/knowledge/`, knowledge standards, current knowledge runtimes | Consume their governed records; add typed text-processing and model lineage. |
| Provider request execution | `adapters/llm_runtime/` and provider-specific adopter code | Define capabilities and required evidence across generation, embedding, reranking, and training plugins. |
| MCP resource transport and authorities | `0052`, `0053`, current MCP adapters | Consume without creating an agent-specific transport. |
| Semantic RAG transport and index isolation | Planned `0054` | Define index-snapshot and text-evaluation records that `0054` must expose or reference. |
| Market-research storage, entitlement, lifecycle, citations | `0056` | Consume normalized items and preserve their governance in text derivatives. |
| Source registration and credential pointers | `sources/` and data-source standard | Require an approved source ID and preserve source quality/access/license metadata. |
| Prompt, context, assumptions, audit, evaluation envelope, replay | `0070` | Add text-domain manifest references, audit event types, evaluators, and replay evidence. |
| Text tasks, embeddings, model adaptation evidence, text signals | `0071` | Own the new typed domain contracts and validation behavior. |

## Interfaces & Data Contracts

### Text Intelligence Manifest

Required fields include schema version, manifest ID, `0070` run ID, task and
decision purpose, corpus snapshot ID, transform-chain ID, model capability IDs,
task-schema version, output artifact IDs, evaluation-suite ID, review status,
signal artifact IDs, audit correlation ID, and downstream consumers.

### Document, Span, and Corpus Snapshot

`DocumentRecord` identifies the source, immutable content hash, canonical and
revision groups, source locator, content type, language, temporal fields,
access/license classes, and lifecycle status. `TextSpan` adds stable offsets or a
provider-neutral span locator, transform version, and parent document. A
`CorpusSnapshot` freezes eligible document/span IDs, point-in-time cutoff,
source filters, deduplication policy, split policy, exclusions, and a manifest
hash.

Temporal eligibility uses the latest of all required availability constraints,
including ingestion/observation time and source-specific publication or release
lag. A revision is a new document version; it never rewrites an earlier snapshot.

### Transformation Chain

Each transform record carries operation type, implementation/config version,
parameters, input/output artifact hashes, timestamp, and deterministic status.
Chunking records boundaries and overlap; redaction records categories without
secret values; deduplication records canonical-document and near-duplicate group
IDs before data splits are assigned.

### Model Capability and Invocation

Capability profiles declare `generation`, `embedding`, `rerank`, `tokenize`, or
`train_adapt` operations. Profiles identify provider/runtime, model and revision,
local artifact checksum where applicable, model license, execution location,
privacy eligibility, context/output limits, deterministic controls, cost/latency
budget, supported tool behavior, and fallback. Invocation records reuse
`llm_runtime` and `0070` identifiers instead of storing private payloads.

### Embedding and Index Snapshot

An embedding artifact maps vector IDs to exact span IDs and pins model,
tokenizer, pooling, normalization, dimension, quantization, preprocessing,
creation time, and corpus snapshot. An index snapshot records immutable ID,
access tier, algorithm/config, vector-set hash, build code/version, distance
metric, corpus cutoff, and source-license eligibility. Index selection occurs by
caller clearance and entitlement before retrieval.

### Task Result and Evidence

Every task has a versioned input/output schema, label or ontology version,
confidence/calibration representation, abstention rules, evidence span IDs,
citations, and error taxonomy. Extracted values preserve units, currency, period,
entity/instrument mapping, and whether the value is stated, inferred, or
generated. Synthesis results separate sourced facts, source opinion, model
synthesis, and unsupported gaps.

### Training or Adaptation Run

Optional plugin records pin the base model, training corpus snapshot, split and
dedup policies, labels, objective, hyperparameters, seeds, environment/hardware,
checkpoints, metrics, contamination findings, and model-card reference. The
reference implementation validates fixtures only; a concrete training workflow
requires a follow-on approved spec.

### Text-Derived Signal

The signal record binds observation and decision timestamps, availability lag,
universe/entity mapping, horizon, aggregation and missing-data policy, task and
model revisions, source/span contributions, calibration/confidence, revision
policy, and downstream dataset/backtest IDs. Signal materialization must fail if
any contributing artifact was unavailable at decision time or violates the
declared split policy.

### Evaluation and Replay Extension

Text evaluators plug into the `0070` harness and emit its standard gate/audit
records. They cover schema and corpus integrity, temporal eligibility, exact and
near-duplicate overlap, benchmark contamination, task metrics, calibration,
retrieval/reranking, citation/faithfulness, adversarial or injection inputs,
privacy/access, cost/latency, robustness, and signal stability. Replay verifies
all hashes and labels execution as deterministic, pinned local, fixture-backed,
or non-reproducible external.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Immutable snapshots, temporal eligibility, pre-split deduplication, pre-search access-tier selection, and fail-closed signal materialization prevent known leakage and access failures. |
| P5 Reversibility | yes | Versioned manifests and immutable snapshots allow a model, index, transform, or signal version to be deprecated without rewriting historical evidence. |
| P6 Observability | yes | Model/index versions, latency/cost, evaluation findings, audit events, review state, and replay mode are explicit. |
| P9 Security & data | yes | Credentials remain references; access/license classes propagate; private bodies and model payloads are not required in tracked artifacts. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | Text intelligence manifest | T-001, T-015 |
| REQ-002 | Document/span and corpus snapshot contracts | T-002, T-003 |
| REQ-003 | Ordered transformation lineage | T-004 |
| REQ-004 | Model capability profile and invocation evidence | T-005 |
| REQ-005 | Embedding artifact and index snapshot | T-006 |
| REQ-006 | Training/adaptation fixture contract | T-007 |
| REQ-007 | Versioned task schemas and evidence results | T-008 |
| REQ-008 | Text-derived signal contract | T-009 |
| REQ-009 | Source-authority and policy propagation | T-002, T-010 |
| REQ-010 | MCP/RAG and market-research composition | T-011 |
| REQ-011 | Text-specific evaluation suites | T-012, T-013 |
| REQ-012 | `0070` manifest, audit, gate, and replay extension | T-014, T-015, T-016 |
| REQ-013 | Temporal, duplicate, split, and benchmark leakage prevention | T-003, T-012 |
| REQ-014 | Offline fixtures and replay modes | T-013, T-015, T-017 |
| REQ-015 | Review, override, uncertainty, and escalation | T-008, T-009, T-014 |
| REQ-016 | Shared agent consumption examples | T-018 |
| REQ-017 | Untrusted-text and prohibited-data controls | T-004, T-010, T-013 |
| NFR-001 | Temporal validator and signal materialization guard | T-003, T-009, T-012 |
| NFR-002 | Hash and source-span lineage | T-001, T-004, T-008 |
| NFR-003 | Access/license propagation and index isolation | T-006, T-010, T-011 |
| NFR-004 | Immutable fixtures, hashes, and replay classifications | T-015, T-017 |
| NFR-005 | Provider-neutral contracts | T-005, T-006, T-007 |
| NFR-006 | Duplicate, contamination, and overlap evaluation | T-003, T-012 |
| NFR-007 | Redaction, quarantine, fixture policy, and gates | T-004, T-010, T-016 |
| NFR-008 | `0070` audit extensions and review events | T-014 |
| NFR-009 | Invocation/index metrics and drift checks | T-005, T-006, T-013 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Orchestration model | Extend `0070` by reference | Create a text-specific run envelope | One run should have one authoritative audit/replay chain. |
| Runtime architecture | Provider-neutral capabilities with deterministic fixtures | Bind directly to one frontier or local-model SDK | The repository must support private adopter choices and offline validation. |
| Corpus history | Immutable point-in-time snapshots | Mutable latest-document index | Historical model and signal evidence must survive revisions and deletions. |
| Access isolation | Select an eligible index before retrieval | Search everything and filter returned passages | Post-search filtering leaks restricted-document existence through ranking. |
| Leakage defense | Canonical/near-duplicate groups before splits plus temporal checks | Random row-level splits | Text syndication, amendments, and repeated passages make row splits misleading. |
| Foundation training scope | Validate training/adaptation manifests and fixtures | Ship a model-training pipeline immediately | Hardware, license, model, and adaptation choices are unresolved and need a bounded spec. |
| Baseline | Lexical/rules reference path | LLM-only reference path | Deterministic baselines expose whether added model complexity creates measurable value. |

## Validation Strategy

- Unit tests validate every parser, enum, hash, temporal rule, lineage edge,
  capability profile, output schema, and signal materialization failure.
- Synthetic corpus fixtures include future documents, revisions, syndication,
  near duplicates, contaminated labels, mixed access tiers, prompt injection,
  unsupported claims, and unregistered sources.
- Golden task fixtures exercise classification, extraction, retrieval/reranking,
  synthesis with citations, explicit abstention, and a deterministic text signal.
- Property-style tests verify that adding future or higher-clearance documents
  cannot alter an earlier/lower-clearance corpus, retrieval result, or signal.
- Replay tests run deterministic fixtures twice and verify hashes; pinned-local,
  provider-fixture, and non-reproducible modes are asserted explicitly.
- Gate tests verify discoverability through `run-stage.sh` and composition with
  source, knowledge, access, leakage, reproducibility, plugin, and secret checks.
- No external model, network, private content, or licensed content is required.

## Rollout, Observability & Rollback

Roll out the four slices in dependency order, but allow contract-only work in
slices 1-3 before `0070` and `0054` runtimes land. Do not publish a production
text signal until source policy, leakage tests, task metrics, review ownership,
and replay evidence pass.

Emit structured findings for source rejection, temporal exclusion, duplicate or
contamination groups, model/plugin failure, access denial, unsupported output,
evaluation failure, review override, and signal publication. Aggregate latency,
cost, token/vector volume, freshness, task quality, citation coverage, drift,
abstention, and fallback rates without storing confidential content.

Rollback deprecates the affected corpus, transform, capability, task, index, or
signal version and returns consumers to the last approved immutable snapshot.
Historical manifests and audit events remain append-only. Provider integrations
must have a deterministic or explicitly degraded fallback, and signal consumers
must support disabling the text feature without changing unrelated models.

## Open Questions

- Approve the first embedding/tokenizer/local-runtime reference profile.
- Approve the first `0054` vector/index backend and immutable snapshot behavior.
- Decide the package location for executable text-intelligence contracts.
- Approve local model licenses, hardware profiles, and any adaptation methods.
- Define source-specific information-availability timestamps and licensing
  policies for the first corpus.
- Choose canonical entity, event, stance/sentiment, theme, instrument, and source
  reliability taxonomies.
- Set promotion thresholds for exploratory outputs, approved research evidence,
  and production/backtest-eligible text signals.
