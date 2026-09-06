# Spec: Prompt / Context / Harness Engineering Foundation

- **ID:** 0070-prompt-context-harness-foundation
- **Status:** Draft
- **Author:** Codex
- **Approver:**
- **Last updated:** 2026-09-06

## Problem & Context

QuantSmith already has a strong spec-driven scaffold, prompt templates,
provider-neutral LLM runtime notes, knowledge and memory stores, model/plugin
adapter contracts, and many deterministic quality gates. Those pieces make
individual workflows easier to review, but they do not yet create one typed
record of an agentic run.

That gap matters more as the SDK moves from single-purpose reference runtimes
to orchestration across specialist agents, frontier LLMs, local LLMs, MCP
resources, model plugins, data sources, and evaluation harnesses. Without a
common orchestration envelope, it is hard to answer the questions that matter
for an agentic quant SDK:

- Which prompt version, model/provider, tools, plugins, and system constraints
  produced the decision?
- Which context records, source passages, assumptions, data contracts, and
  freshness rules were available at the time?
- Which gates validated each layer, and which findings were accepted,
  remediated, or left open?
- Which decision, human approval, rejected alternative, or tool result changed
  the run outcome?
- Can a reviewer replay the run with the same inputs, or identify exactly which
  non-deterministic dependency prevents replay?

This spec establishes a foundation for prompt engineering, context engineering,
and harness engineering as first-class infrastructure. It turns orchestration
state into typed, validated, replayable artifacts rather than scattered prose.

## Goals

- Define a typed orchestration run envelope that binds prompt, context,
  assumptions, tools/plugins, model/provider metadata, data/source contracts,
  gates, audit events, and replay instructions into one portable record.
- Create a prompt manifest contract for prompt IDs, versions, hashes, variables,
  model constraints, tool permissions, safety boundaries, and evaluation links.
- Create a context manifest contract for retrieved knowledge, memory, source
  passages, data contracts, access level, as-of semantics, freshness, and
  context-window budgeting.
- Create an assumption ledger that gives every material assumption an owner,
  scope, evidence, confidence/status, expiry or review cadence, and downstream
  consumer list.
- Create an evaluation harness contract that validates prompt, context,
  assumptions, tool/plugin calls, LLM outputs, quant leakage controls, and final
  artifacts at the right layer.
- Create an audit event schema for append-only records of decisions, tool calls,
  model invocations, gate results, human approvals, overrides, and rejected
  alternatives.
- Create a reproducible replay command that can rerun or explain a run from its
  envelope, including fixture mode for provider or plugin dependencies.
- Add gate coverage so missing or inconsistent prompt, context, assumption,
  harness, audit, or replay evidence is visible before release.

## Non-Goals

- No new frontier LLM provider integration, local LLM server, embedding model,
  vector database, or MCP RAG runtime is implemented by this spec. Existing
  adapter contracts are consumed rather than replaced.
- No attempt to train, fine-tune, or benchmark an LLM. The harness validates
  orchestration evidence, not model quality claims beyond supplied fixtures and
  evaluator outputs.
- No live network calls, credentials, vendor APIs, private plugins, or external
  data access are owned by the SDK.
- No proprietary prompts, private research content, MNPI, secrets, credentials,
  account names, or licensed data values are committed.
- No existing quant model, backtest, source adapter, scheduler, or knowledge
  runtime behavior changes silently under this foundation.
- No guarantee that a replay exactly reproduces a non-deterministic hosted LLM
  response unless the original response, seedable local model, or fixture is
  part of the envelope.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The system shall define a typed orchestration run envelope with stable schema version, run ID, repo revision, spec/stage, actor, objective, timestamps, mode, environment summary, prompt manifest reference, context manifest reference, assumption ledger reference, evaluation harness reference, audit ledger reference, gate results, and replay command metadata. | must |
| REQ-002 | The system shall define a prompt manifest contract covering prompt ID, version, source path or URI, content hash, prompt role layers, variables and defaults, model/provider constraints, allowed tools/plugins, prohibited data/classes, safety policy references, evaluation references, and owner/review metadata. | must |
| REQ-003 | The system shall define a context manifest contract covering every retrieved or injected context item, including source authority, locator, content hash or chunk ID, access level, caller clearance, retrieval query or selection rule, rank/order, token or character budget use, as-of time, effective time where applicable, freshness status, citations, and exclusions. | must |
| REQ-004 | The system shall define an assumption ledger contract covering assumption ID, statement, type, scope, owner, source/evidence, confidence, status, introduced date, review/expiry date, dependent artifacts, invalidation trigger, and disposition history. | must |
| REQ-005 | The system shall define an evaluation harness contract that composes layer-specific checks for envelope structure, prompt rendering, context retrieval/access/PIT behavior, assumption coverage, tool/plugin invocation shape, model output constraints, quant leakage controls, final artifact validation, and regression fixtures. | must |
| REQ-006 | The system shall define an audit event schema for append-only JSONL events covering model invocation, prompt render, context retrieval, tool/plugin call, data/source read, gate result, human approval, override, rejected alternative, assumption change, replay attempt, and release decision. | must |
| REQ-007 | The system shall provide a reproducible replay command that loads a run envelope, verifies all referenced artifacts and hashes, supports offline fixture mode, refuses missing or changed required inputs unless explicitly overridden, and emits a replay report with diffs and non-reproducible dependencies. | must |
| REQ-008 | The system shall add gate coverage for prompt manifests, context manifests, assumption ledgers, evaluation harnesses, audit events, and replay metadata; gates shall be runnable through `hooks/stages/run-stage.sh` and produce actionable findings without requiring credentials or network access. | must |
| REQ-009 | The foundation shall interoperate with existing SDD, workflow memory, market research, MCP resource, LLM runtime, model-plugin, data-source, data-contract, leakage, backtest, repro, and secret-scan surfaces without duplicating their ownership. | must |
| REQ-010 | Frontier LLMs, local LLMs, LangChain-style chains, MCP tools, and private model plugins shall be represented through provider/tool metadata and fixtureable calls, so the envelope can audit and replay orchestration without owning provider-specific logic. | should |
| REQ-011 | The foundation shall include examples/templates for at least one deterministic quant pipeline run and one LLM-eligible agentic run where the LLM response is fixture-backed rather than network-backed. | should |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Deterministic offline validation | All schemas, validators, gates, examples, and replay fixture checks run without network access or credentials. |
| NFR-002 | Reproducibility | A run envelope records enough artifact hashes, versions, as-of times, inputs, configuration, and fixture references to reproduce deterministic layers or explain any non-reproducible layer. |
| NFR-003 | Leakage resistance | Context and data records enforce caller clearance, source access, point-in-time availability, and effective-time rules before prompts or model calls are composed. |
| NFR-004 | Auditability | Every material decision, override, gate result, tool/plugin call, prompt render, context retrieval, and human approval can be traced through append-only events. |
| NFR-005 | Provider neutrality | The schema supports hosted frontier models, local/self-hosted models, deterministic rule-based mode, and adapter-backed plugin calls without encoding a single vendor as the source of truth. |
| NFR-006 | Data security | No secret value, credential, private key, token, MNPI, personal identifier, proprietary model payload, or licensed content body is required in a committed artifact. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a valid orchestration run envelope fixture, when the validator runs, then every referenced manifest/ledger/harness/audit/replay artifact resolves, required hashes match, and the envelope validates offline. | REQ-001, NFR-001, NFR-002 |
| AC-002 | Given an invalid prompt manifest with an unversioned prompt, missing hash, undeclared variable, or unauthorized tool/plugin, when the prompt-manifest check runs, then it emits a finding tied to the failing field. | REQ-002, REQ-008 |
| AC-003 | Given a context manifest containing restricted content for an internal caller, stale context marked current, or a source known after the run's as-of time, when validation runs, then the context is rejected before prompt composition. | REQ-003, NFR-003, NFR-006 |
| AC-004 | Given a material model or data assumption with no owner, evidence, review date, status, or dependent artifact, when the assumption-ledger check runs, then the ledger fails validation. | REQ-004, REQ-008 |
| AC-005 | Given an evaluation harness fixture, when tests are enumerated, then each layer named in REQ-005 has at least one deterministic check or an explicit, justified exception. | REQ-005, NFR-001 |
| AC-006 | Given an audit ledger with malformed events, missing event IDs, non-monotonic timestamps, broken parent references, or an override lacking a reason, when audit validation runs, then it emits actionable findings. | REQ-006, NFR-004 |
| AC-007 | Given a replay command for a deterministic fixture run, when executed twice from a clean checkout, then the replay reports equivalent results and matching artifact hashes. | REQ-007, NFR-002 |
| AC-008 | Given a replay command for a fixture-backed LLM/tool run, when the original provider response is unavailable, then replay uses the declared fixture or reports the provider call as non-reproducible instead of fabricating equivalence. | REQ-007, REQ-010, NFR-005 |
| AC-009 | Given the full gate suite, when `hooks/stages/run-stage.sh` is run for the new gate coverage, then prompt, context, assumption, evaluation, audit, and replay findings are discoverable through the standard gate interface. | REQ-008, REQ-009 |
| AC-010 | Given existing SDD, memory, market-research, MCP, LLM-runtime, model-plugin, source-catalog, data-contract, leakage, backtest, repro, and secret-scan artifacts, when the foundation is validated, then it references their outputs without changing their ownership or behavior. | REQ-009, NFR-006 |
| AC-011 | Given the committed examples/templates, when inspected, then they include one deterministic quant pipeline envelope and one fixture-backed LLM-eligible envelope with prompt, context, assumptions, harness, audit, and replay references. | REQ-011 |
| AC-012 | Given a clean checkout, when targeted tests, new gates, `spec`, `docs-link`, `spec-index`, `doc-counts`, `handoff-sync`, and `secret-scan` run, then they pass without credentials, network access, or private data. | NFR-001, NFR-006 |

## Data & Dependencies

This foundation depends on existing repository contracts rather than replacing
them:

- `instructions/spec_driven_development.md` and `templates/spec/` for SDD
  traceability.
- `instructions/reproducibility.md`, `instructions/point_in_time.md`,
  `instructions/data_provenance.md`, `instructions/knowledge_base.md`, and
  `instructions/model_plugin_integration.md` for reproducibility, temporal,
  evidence, knowledge, and plugin boundaries.
- `adapters/llm_runtime/`, `adapters/model_plugin/`, and `adapters/mcp_servers/`
  for provider/tool/resource boundaries.
- `src/quantsmith/pipelines/workflow_memory.py`,
  `src/quantsmith/pipelines/market_research.py`, and `sources/` for current
  knowledge, research, and source-catalog contracts.
- Existing gates under `hooks/stages/`, especially `spec`, `leakage`,
  `backtest`, `repro`, `data-contract`, `source-catalog`, `secret-scan`, and
  `model-plugin`.

No private data source is required. Examples must use deterministic fixtures,
public metadata, or synthetic content that is explicitly disclosed.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | The envelope becomes a large bureaucratic artifact that slows small research tasks. | Teams bypass it or create low-quality boilerplate. | Make the schema layered: minimal required fields for every run, richer manifests only when prompts, context, tools, plugins, or LLM calls are present. |
| RISK-002 | A replay report is mistaken for exact reproduction of hosted LLM behavior. | Reviewers trust a result that cannot be regenerated. | Distinguish deterministic replay, fixture replay, and non-reproducible provider calls in REQ-007 and AC-008. |
| RISK-003 | Context is access-filtered after retrieval instead of before retrieval or indexing. | Restricted or MNPI-adjacent information can leak through prompt content or retrieval metadata. | Reuse the `0052`/`0054` caller-clearance and per-access-tier design, and fail context validation before prompt composition. |
| RISK-004 | Prompt, context, and eval ownership overlaps with existing agents and gates. | Conflicting responsibilities make the system harder to trust. | REQ-009 requires integration by reference: this foundation records and validates orchestration evidence without owning existing domain decisions. |
| RISK-005 | Audit logs accidentally store secrets, prompt bodies containing private data, or licensed context excerpts. | Committed artifacts become a confidentiality or licensing incident. | Store hashes, locators, redacted summaries, and fixture IDs; run `secret-scan`; keep private envelopes local-only when needed. |
| RISK-006 | Evaluators become shallow checklist passes rather than meaningful harness checks. | The system appears governed while missing layer-specific failures. | REQ-005 and AC-005 require one check or justified exception per layer; future domain specs can add stricter evaluators. |

## Assumptions & Open Questions

- Assumption: the first implementation should be standard-library Python plus
  shell gates, matching the repository's dependency-free reference-runtime
  pattern.
- Assumption: JSON/JSONL are the right initial interchange formats for machine
  validation; Markdown remains the human-facing explanation layer.
- Assumption: replay must support deterministic rule-based mode before claiming
  strong guarantees for LLM-backed runs.
- Open question: should the runtime live under `src/quantsmith/pipelines/` for
  consistency with previous specs, or under a new `src/quantsmith/orchestration/`
  package to make the cross-cutting boundary explicit?
- Open question: should this spec add separate gate names for each manifest type
  or one composite `orchestration` gate with sub-findings?
- Open question: what is the minimum required envelope for an exploratory
  notebook or ad-hoc agent request, versus a release-bound model change?

## Exceptions

None.
