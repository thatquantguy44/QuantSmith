# Spec: Credit Document Intelligence

- **ID:** 0077-credit-document-intelligence
- **Status:** Approved
- **Author:** Joshua Lutkemuller, CFA
- **Approver:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-09-10

## Problem & Context

`0072`'s credit risk domain foundation reserved `0077` for credit document
intelligence and defined its contract in advance: an evidence-admission
boundary (its requirement that any LLM- or NLP-derived value arrive as a
`0071` text artifact inside a `0070` run envelope, labeled `derived_evidence`,
promotable to `decision_input` only by named human review. That boundary was
written and validated against hand-typed fixtures authored specifically to
satisfy it — the one thing `0072`'s own gap register (`G-0072-006`) named as
unproven: whether the boundary holds when a real `0071` bundle, produced by
the real `0071` producer, actually flows through it.

`0077` closes that gap. It is deliberately narrow. It does not build a
covenant-extraction model, a document classifier, or an NLP engine — `0070`
and `0071` are both dependency-light, standard-library, no-live-model-call
foundations by design, and `0077` inherits that constraint rather than
introducing the SDK's first live model dependency to prove a plumbing
contract. What `0077` builds is the **wiring**: a credit-domain corpus
registered and disclosed as synthetic; a real emission of that corpus through
`0071`'s existing, Approved, unchanged producer; and a bridge that carries one
of that producer's real task results into `0072`'s admission function,
proving both branches (`derived_evidence` and `decision_input`) and the
rejection branch against actual artifacts rather than fixtures written to
pass.

Building this exposed one genuine integration gap that no amount of spec
review would have surfaced: `0071`'s task-result `review` object
(`reviewer`, `reviewed_at`, `owner`, `uncertainty`, ...) and `0072`'s review
object (`reviewer`, `review_date`, `scope`) do not share field names. Neither
schema is wrong — they were designed for different documents, a text-task
result and a credit knowledge record — but wiring them together without an
explicit adapter would have silently miscoerced one into the other, or
required a caller to reimplement the mapping ad hoc every time. `0077` makes
that adapter a first-class, tested function rather than a one-off patch.

## Goals

- Register and disclose a synthetic credit-document corpus, distinct from
  `0071`'s generic `text_intelligence_fixture`, so a consumer never mistakes
  general liquidity commentary for credit-specific content.
- Emit a real `0071` bundle — corpus snapshot, transform chain, model
  capabilities, task results, signals, evaluation, audit events, and a `0070`
  run envelope — over that corpus, using `0071`'s existing
  `emit_lexical_signal_evidence` producer unchanged.
- Bridge a real task result from that bundle into `0072`'s
  `admit_derived_evidence`, proving admission as `derived_evidence`
  (unreviewed), promotion to `decision_input` (reviewed), and rejection
  (a required field absent) against genuinely emitted data.
- Make the `0071`-to-`0072` review-field mismatch an explicit, tested adapter
  function, not a silent coercion.
- Prove replay determinism on the resulting bundle using `0070`'s and
  `0071`'s existing replay engines, not a bespoke one.
- Ship one committed, regenerable example (matching `0071`'s own pattern) and
  one credit-domain agent contract (`credit_document_analyst`) now that a
  real, tested runtime justifies it under `0072`'s rule that an agent needs
  a coverage-matrix row before it may exist.
- Resolve `0072`'s open question about `0054` (the MCP RAG server): record
  that a fixture-scale, two-document corpus needs no vector search, so `0077`
  does not activate `0054`.

## Non-Goals

- No covenant-extraction, financial-spreading, or document-classification
  model is built or claimed. `0071`'s existing deterministic-lexical producer
  is reused verbatim; its `entity_extraction`, `value_extraction`,
  `sentiment_stance`, and `theme_detection` outputs are its own fixed
  reference-fixture stubs, disclosed as such, not credit-specific extraction.
  Only the `classification` result is genuinely computed from this corpus's
  text.
- No live model provider, plugin, or vector-store call. No network I/O.
- No promotion of any value to a decision input by this module itself.
  Promotion requires named human review recorded on the source task result;
  `0077` proves the gate opens and closes, it does not open it on anyone's
  behalf.
- No activation of `0054`. See Goals; this spec's own first consumer does not
  need it, and activating it here would be exactly the "build the server
  before there is content worth reaching for" mistake `0071`'s own roadmap
  warned against.
- No change to `0070`'s or `0071`'s approved modules. `text_intelligence/`
  and `orchestration/` are used through their existing public functions only.
- No real credit document, obligor data, or licensed agreement text. Every
  document is authored fiction, disclosed under `0025`.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | A source `credit_document_fixture` shall be registered under `sources/`, distinct from `text_intelligence_fixture`, with its synthetic/fictional nature disclosed in its `known_issues`. | must |
| REQ-002 | `quantsmith.pipelines.credit_document_intelligence` shall emit a bundle via `0071`'s unchanged `emit_lexical_signal_evidence`, over documents citing `credit_document_fixture`; a document citing any other source shall be rejected before emission. | must |
| REQ-003 | The module shall provide `admission_input_from_bundle`, which loads a real emitted bundle's corpus snapshot, task results, and run envelope and constructs a `0072`-shaped admission input, resolving `evidence_span_ids` against the corpus's real `spans` array. An unresolvable span ID shall raise rather than silently omit. | must |
| REQ-004 | The module shall provide `review_from_task_result`, mapping `0071`'s review object (`reviewer`, `reviewed_at`, `owner`, `uncertainty`) to `0072`'s review shape (`reviewer`, `review_date`, `scope`), with a dedicated test asserting the mapping. | must |
| REQ-005 | The module shall provide `admit_bundle_result`, composing REQ-003 and REQ-004 with `0072`'s `admit_derived_evidence`, and shall be proven against a real bundle to: (a) return `derived_evidence` when no review is included; (b) return `decision_input` when the adapted review is included; (c) return `admitted: False` naming the missing field when a required field is absent. | must |
| REQ-006 | Replay of the emitted bundle shall be proven deterministic using `0071`'s `replay_text_intelligence_manifest_file` and `0070`'s `replay_envelope_file`, run twice, with identical results and no output diffs. | must |
| REQ-007 | One committed example shall exist under `examples/credit_document_intelligence/`, regenerable byte-identically (by manifest and task-result hash) via `generate_credit_document_examples`. | must |
| REQ-008 | `0072`'s coverage matrix, gap register, and workflow contract for credit document intelligence shall be updated to reflect what this spec actually proves — a validated wiring path, not a working extraction model — and no coverage level shall claim more than the evidence supports. | must |
| REQ-009 | One agent, `agents/credit_risk/credit_document_analyst/`, shall be created, satisfying `0072`'s agent-gating rule via the coverage row this spec updates, with the standard four files and a `Spec-Driven Role` section. | must |
| REQ-010 | `0072`'s open question on `0054` activation shall be resolved in `0072`'s own spec text, not left open a second time in `0077`. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | No live dependency | The module calls no model provider, plugin, or network endpoint; `pytest -q tests/test_credit_document_intelligence.py` passes offline. |
| NFR-002 | Determinism | Two runs of `generate_credit_document_examples` into fresh directories with the same inputs produce identical `corpus_snapshot` and `task_results` hashes. |
| NFR-003 | Honest disclosure | No spec, code comment, docstring, or test description represents `0071`'s fixed fixture outputs (entity/value/stance/theme) as content genuinely extracted from this corpus's documents. |
| NFR-004 | Synthetic-only | Every committed document is fictional and the source registration discloses it; no real obligor, counterparty, or agreement text is present. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given `sources/credit_document_fixture.yml`, when the `source-catalog` gate runs, then it validates with no findings and is listed in `sources/README.md`. | REQ-001 |
| AC-002 | Given a document citing `source_id="text_intelligence_fixture"`, when passed to `emit_credit_document_evidence`, then a `CreditDocumentIntelligenceError` naming `credit_document_fixture` is raised before any emission occurs. | REQ-002 |
| AC-003 | Given the committed bundle, when `admission_input_from_bundle` resolves its `value_extraction` result's evidence spans, then each resolved span carries `span_id`, `document_id`, `start`, and `end` with `end > start`; an unresolvable span ID raises. | REQ-003 |
| AC-004 | Given a `0071` review object, when `review_from_task_result` adapts it, then `reviewer` passes through unchanged, `review_date` is the date portion of `reviewed_at`, and `scope` combines `owner` and `uncertainty`. | REQ-004 |
| AC-005 | Given the committed bundle's real task result, when admitted with the adapted review, then the result is `{"admitted": True, "evidence_class": "decision_input", "missing": []}`; without review, `{"admitted": True, "evidence_class": "derived_evidence", "missing": []}`; with `envelope_ref` removed, `{"admitted": False, "evidence_class": None, "missing": ["envelope_ref"]}`. | REQ-005 |
| AC-006 | Given the committed bundle, when replayed twice via `replay_text_intelligence_manifest_file` and `replay_envelope_file`, then both runs are identical, `status == "replayed"`, `replay_mode == "deterministic"`, and no output diffs are reported. | REQ-006 |
| AC-007 | Given a freshly regenerated bundle, when compared to the committed example, then `corpus_snapshot` and `task_results` hashes match exactly. | REQ-007 |
| AC-008 | Given `knowledge/credit_risk/coverage.json`, when `capability.document_intelligence` is inspected after this spec, then its coverage level, current artifacts, and limitation describe exactly what REQ-002–REQ-006 prove, and no field claims covenant-extraction capability. | REQ-008, NFR-003 |
| AC-009 | Given `agents/credit_risk/credit_document_analyst/`, when the `agent-catalog` gate runs, then it validates with no findings and the agent's `README.md` names this spec's runtime module and workflow. | REQ-009 |
| AC-010 | Given `specs/0072-credit-risk-domain-foundation/spec.md`'s Assumptions & Open Questions, when inspected, then the `0054` question is marked resolved with its rationale, not repeated as open in `0077`. | REQ-010 |
| AC-011 | Given the task-result outputs asserted in the test suite, when `entity_extraction`, `value_extraction`, `sentiment_stance`, and `theme_detection` are inspected, then each carries `"reference fixture"` or `"not production-calibrated"` language in its `uncertainty` field. | NFR-003 |

## Data & Dependencies

- `0070-prompt-context-harness-foundation` — `replay_envelope_file`, `load_json`, the run-envelope schema. Used unchanged.
- `0071-nlp-llm-quant-text-intelligence-foundation` — `TextDocumentInput`, `emit_lexical_signal_evidence`, `replay_text_intelligence_manifest_file`, `validate_text_intelligence_manifest_file`. Used unchanged.
- `0072-credit-risk-domain-foundation` — `credit_risk_knowledge.admit_derived_evidence`, `knowledge/credit_risk/governance.json`'s `evidence_admission` rule, `decision_paths.json`'s `path.credit_document_intelligence`. Consumed, not redefined.
- `0025-data-provenance-guardrail` — synthetic-data disclosure for `credit_document_fixture` and the committed example.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | The fixed fixture outputs (entity/value/stance/theme) get quoted elsewhere as evidence of a working covenant extractor. | A false capability claim propagates into `0072`'s coverage matrix or external communication. | NFR-003, AC-011, and explicit module docstring/non-goals language; coverage.json's limitation field is worded to preclude the claim. |
| RISK-002 | The review-field adapter silently drops information when 0071's or 0072's review schema changes. | A promotion could succeed or fail incorrectly without anyone noticing. | `review_from_task_result` is a single, tested, named function — a schema change on either side breaks its test rather than silently miscoercing. |
| RISK-003 | A future caller reuses `text_intelligence_fixture` for credit content because it is more convenient than registering a new source. | Credit-domain provenance gets muddled with generic text fixtures. | REQ-002 makes this a hard rejection at emission time, not a style guideline. |

## Assumptions & Open Questions

- Assumption: a fixture-scale, two-document corpus is sufficient to prove the
  wiring this spec targets. A real, licensed corpus at retrieval scale is a
  separate, larger undertaking correctly left to a future spec once a real
  consumer needs it (see `0072` gap `G-0072-006`, updated but not closed by
  this spec).
- Resolved (was open in `0072`): `0077` does not require `0054` (the MCP RAG
  server). See Goals and Non-Goals above; recorded in `0072`'s own spec text
  per REQ-010.

## Exceptions

None.
