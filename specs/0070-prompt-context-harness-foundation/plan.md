# Plan: Prompt / Context / Harness Engineering Foundation

- **Spec:** 0070-prompt-context-harness-foundation (`spec.md`)
- **Status:** Draft (foundation implemented)
- **Author:** Codex
- **Last updated:** 2026-09-06

## Approach

Implement a small, dependency-free orchestration foundation that records an
agentic run as typed JSON/JSONL artifacts and validates those artifacts before
release. The core abstraction is a run envelope that points to richer manifests:
prompt, context, assumptions, evaluation harness, audit events, and replay
metadata. The envelope is deliberately a record of orchestration state, not a
new LLM provider, RAG index, scheduler, or model runtime.

The design should support three modes from day one:

- deterministic QuantSmith runtime or rules-based agent flow;
- fixture-backed LLM/tool flow, where provider responses and plugin outputs are
  captured as fixtures; and
- externally executed provider/plugin flow, where replay can verify metadata and
  explain why exact reproduction is unavailable.

## Architecture & Components

```text
agent or pipeline run
  -> prompt manifest          # prompt IDs, hashes, variables, tool permissions
  -> context manifest         # memory/source/context items, access, as-of, hashes
  -> assumption ledger        # assumptions, owners, evidence, expiry, consumers
  -> evaluation harness       # layer checks and expected fixtures
  -> audit events JSONL       # append-only events from every material step
  -> orchestration envelope   # typed index binding the run together
  -> replay command           # validates hashes, reruns deterministic layers, diffs
  -> gate coverage            # prompt/context/assumption/eval/audit/replay checks
```

Planned implementation surfaces:

| Component | Responsibility |
| --- | --- |
| `src/quantsmith/orchestration/` | Dataclasses, parsers, schema validators, hash checks, audit helpers, replay report builder. The package is separate from `pipelines/` because the envelope governs cross-cutting orchestration evidence. |
| `src/quantsmith/orchestration/replay_cli.py` | CLI entry point for loading an envelope, validating references, and producing a replay report. |
| `src/quantsmith/orchestration/producers.py` | Producer adapters that turn real runtime outputs into 0070 evidence bundles without making those runtimes import the orchestration package. First producer: `emit_quant_factory_evidence`. |
| `templates/orchestration/` | Template envelope, prompt manifest, context manifest, assumption ledger, evaluation harness, and audit events. |
| `examples/orchestration/` | One deterministic quant example and one fixture-backed LLM-eligible example. |
| `hooks/stages/orchestration-check.sh` | Composite gate coverage for prompt, context, assumptions, evaluation harness, audit events, and replay metadata, wired through `run-stage.sh`. |
| `tests/test_orchestration_foundation.py` and CLI/gate tests | Acceptance-criterion evidence for schema validation, layer failures, fixture replay, and gate discoverability. |

## Interfaces & Data Contracts

### Orchestration Run Envelope

Required fields:

- `schema_version`, `run_id`, `objective`, `spec_id`, `stage`, `mode`,
  `created_at`, `actor`, `repo_revision`, and `environment`.
- References to `prompt_manifest`, `context_manifest`, `assumption_ledger`,
  `evaluation_harness`, `audit_events`, `gate_results`, and `replay`.
- `artifacts[]` entries with path/URI, content hash, type, access class, and
  producing event ID.

### Prompt Manifest

Records prompt source, version, hash, variables, role layers, allowed
tools/plugins, provider/model constraints, safety policy references, owner,
review status, and evaluator references. It must distinguish prompt metadata
from private prompt bodies when bodies cannot be committed.

### Context Manifest

Records retrieved memory, source passages, research items, data contracts, and
manually supplied context. Each item carries locator, hash or chunk ID, access
level, caller clearance, retrieval rule, ordering, budget use, as-of time,
effective time where applicable, freshness, citation fields, and exclusion
reason where context was deliberately withheld.

### Assumption Ledger

JSONL or JSON list of assumptions, each with ID, statement, class, scope, owner,
evidence, confidence, status, introduced date, review or expiry date, dependent
artifacts, invalidation trigger, and disposition history.

### Evaluation Harness

Declarative list of checks by layer:

- envelope schema and hash integrity;
- prompt render and variable coverage;
- context access, point-in-time, freshness, and citation checks;
- assumption coverage and expiry checks;
- tool/plugin call shape and fixture availability;
- model output structural constraints and deterministic fixture comparisons;
- quant leakage, backtest, data-contract, and source-catalog gate references;
- final artifact checks and replay expectations.

### Audit Events

Append-only JSONL records with `event_id`, `run_id`, `event_type`, `timestamp`,
`actor`, `parent_event_ids`, `payload_ref` or redacted payload metadata,
`artifact_refs`, `finding_refs`, and optional `reason`. Overrides and approvals
must include a reason and actor.

### Replay Report

The replay command emits a report with input hash verification, deterministic
step results, fixture substitutions, output diffs, gate status, and a clear list
of non-reproducible dependencies.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | The envelope binds prompt, context, assumptions, gates, and replay metadata before release, and context validation happens before prompt composition. |
| P5 Reversibility | yes | Runtime, templates, examples, and gates are additive; rollback is reverting one spec implementation. |
| P6 Observability | yes | Audit events and gate results make decisions, overrides, and failures visible. |
| P9 Security & data | yes | Artifacts use locators, hashes, redacted summaries, access classes, and local-only/private envelope options rather than committed secrets or private content. |
| P10 Honest reporting | yes | Replay reports distinguish deterministic replay, fixture replay, and non-reproducible provider/plugin calls. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | Run envelope schema and validator | T-001 |
| REQ-002 | Prompt manifest schema, templates, and gate coverage | T-002, T-008 |
| REQ-003 | Context manifest schema, templates, access/PIT checks, and gate coverage | T-003, T-008 |
| REQ-004 | Assumption ledger schema, validators, and gate coverage | T-004, T-008 |
| REQ-005 | Evaluation harness schema and layer-check runner | T-005, T-008, T-010 |
| REQ-006 | Audit event schema, JSONL validator, and append-only checks | T-006, T-008 |
| REQ-007 | Replay CLI and replay report contract | T-007, T-010 |
| REQ-008 | New or composite gate scripts wired through `run-stage.sh` | T-008 |
| REQ-009 | Integration references to existing SDD, memory, MCP, LLM, model-plugin, source, data, leakage, backtest, repro, and secret-scan surfaces | T-001, T-003, T-005, T-008, T-009 |
| REQ-010 | Provider/tool/plugin metadata and fixtureable call records | T-001, T-002, T-005, T-006, T-007 |
| REQ-011 | Templates and examples for deterministic and fixture-backed runs | T-009 |
| NFR-001 | Offline validators, fixtures, gate runs, and tests | T-001, T-002, T-003, T-004, T-005, T-006, T-007, T-008, T-010 |
| NFR-002 | Hashes, repo revision, as-of values, deterministic fixture replay, and replay report | T-001, T-003, T-007 |
| NFR-003 | Access, source, as-of, effective-time, and freshness checks before prompt composition | T-003, T-008 |
| NFR-004 | Append-only audit events and gate evidence | T-006, T-008 |
| NFR-005 | Provider-neutral metadata and fixtureable calls | T-001, T-002, T-006, T-007 |
| NFR-006 | Redaction, locator/hash-only committed artifacts, local-only private files, and secret-scan compatibility | T-002, T-003, T-006, T-008, T-010 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Foundation boundary | Typed orchestration evidence and gates | A new monolithic agent runtime | The SDK already has agents, runtimes, and adapters; the missing layer is the evidence contract binding them together. |
| Replay guarantee | Deterministic replay where possible, fixture replay for LLM/tool calls, explicit non-reproducible findings otherwise | Claim exact replay for hosted frontier LLM calls | Hosted providers can change behavior or infrastructure; exactness requires captured fixtures or deterministic local execution. |
| Context validation timing | Validate access, as-of, freshness, and source fields before prompt composition | Validate only final answers | Late validation can still leak context into prompts, logs, embeddings, or tool calls. |
| Gate shape | Allow one composite gate or several focused gates, but require field-level findings per manifest type | One broad "AI safety" check | Broad checks are easy to satisfy without proving prompt, context, assumption, audit, and replay integrity separately. |
| Schema format | JSON/JSONL with Markdown explanation | YAML-only manifests | JSON/JSONL keeps parsing dependency-free and deterministic in the standard library. |

## Validation Strategy

Implementation should add deterministic tests named by acceptance criterion:

- valid and invalid envelope fixtures for AC-001;
- prompt manifest failure fixtures for AC-002;
- context access, stale, and point-in-time failure fixtures for AC-003;
- assumption ledger failure fixtures for AC-004;
- evaluation harness coverage fixtures for AC-005;
- malformed audit event fixtures for AC-006;
- deterministic replay and fixture-backed replay tests for AC-007 and AC-008;
- gate discoverability and run-stage integration tests for AC-009;
- integration/reference tests proving existing ownership boundaries for AC-010;
- example/template inspection for AC-011;
- repository gate evidence for AC-012.

Run targeted tests, new gates, `hooks/stages/run-stage.sh spec docs-link
spec-index doc-counts handoff-sync secret-scan`, and `git diff --check`.
Run full `pytest -q` when implementation touches runtime modules or CLI behavior.

## Rollout, Observability & Rollback

Roll out in two slices:

1. Contracts, templates, validators, tests, and examples.
2. Gate/CLI wiring once the validators are stable.
3. Producer integrations that let existing runtimes emit validated envelopes.
   The first producer consumes `0061` Quant Model Factory decisions and writes
   the 0070 bundle beside caller-owned runtime artifacts.

All new artifacts are additive. A release should publish the new envelope schema,
gate names, example runs, and replay command. Rollback is reverting the
implementation commit and removing the gate names from `run-stage.sh`; existing
quant runtimes and adapters should continue to work because this foundation
observes and validates their evidence rather than changing their execution path.

## Resolved Decisions

- Runtime code lives under `src/quantsmith/orchestration/`.
- Gate coverage is exposed through one composite `orchestration` gate with
  field-level sub-findings.
- The smallest exploratory run still needs an envelope, actor, objective,
  environment, audit/replay metadata, and an explicit `release_profile`; richer
  manifests are required for release-bound examples and validated references.
