# Plan: Credit Document Intelligence

- **Spec:** 0077-credit-document-intelligence (`spec.md`)
- **Status:** Approved
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-09-10

## Approach

Compose, don't reinvent. `0070` and `0071` already ship a complete, tested,
Approved pipeline for emitting a hash-linked evidence bundle over text
documents; `0072` already defines exactly what an admitted piece of LLM
evidence must carry. `0077` is the thin, honest bridge between the two:

1. A new source registration and two synthetic documents give the pipeline
   something credit-flavored to run on.
2. `0071`'s own `emit_lexical_signal_evidence` — unchanged — produces the real
   bundle. No fork of `_emit_bundle`, no new schema.
3. A small adapter (`review_from_task_result`) and a small loader
   (`admission_input_from_bundle`) translate that bundle's real output into
   `0072`'s admission input shape.
4. `0072`'s own `admit_derived_evidence` — unchanged — decides admission.

The only genuinely new logic is the adapter and the loader; everything else
is calling existing, approved functions with credit-shaped inputs. This
keeps `0077` small and keeps the two foundations it composes untouched.

## Architecture & Components

```text
sources/credit_document_fixture.yml   registration + synthetic disclosure
                    |
                    v
TextDocumentInput (0071, unchanged) x2 synthetic credit documents
                    |
                    v
emit_lexical_signal_evidence (0071, unchanged)
                    |
                    v
examples/credit_document_intelligence/   real corpus, transforms, task
  corpus_snapshot.json                   results, audit events, and a
  task_results.json                      0070 run envelope — identical
  run_envelope.json                      in kind to 0071's own examples
  ... (rest of the 0071 bundle)
                    |
                    v
credit_document_intelligence.py (0077, new — this spec's only new module)
  admission_input_from_bundle()   loads corpus + task_results + envelope,
                                   resolves real evidence_span_ids into spans
  review_from_task_result()       0071 review shape -> 0072 review shape
  admit_bundle_result()           composes the above with 0072's gate
                    |
                    v
admit_derived_evidence (0072, unchanged)  -> derived_evidence | decision_input | rejected
```

### Component responsibilities

| Component | Responsibility |
| --- | --- |
| `sources/credit_document_fixture.yml` | Registers and discloses the synthetic corpus, kept distinct from `text_intelligence_fixture` so credit-domain provenance is never ambiguous. |
| `credit_document_intelligence.py` | The one new module. `emit_credit_document_evidence` (thin, source-checked wrapper), `admission_input_from_bundle` (real-artifact loader), `review_from_task_result` (the field-name adapter), `admit_bundle_result` (composition), `generate_credit_document_examples` (regenerates the committed example). |
| `examples/credit_document_intelligence/` | The one committed, regenerable example — same pattern as `examples/text_intelligence/`. |
| `agents/credit_risk/credit_document_analyst/` | The one agent this spec's real runtime justifies under `0072`'s agent-gating rule; a thin routing contract naming this module and `0072`'s `workflow.credit_document_intelligence`. |

## Interfaces & Data Contracts

### The bridge, precisely

`admission_input_from_bundle(bundle_dir, result_task_type="value_extraction", include_review=True)`:

1. Loads `corpus_snapshot.json`, `task_results.json`, `run_envelope.json` from
   the real bundle (accepting either the bundle directory or the manifest
   path `emit_lexical_signal_evidence` returns).
2. Picks the first task result matching `result_task_type`.
3. Resolves its `evidence_span_ids` against the corpus's real `spans` array —
   an unresolvable ID raises `CreditDocumentIntelligenceError`, not a silent
   skip.
4. Builds `{artifact_ref, source_spans, envelope_ref, prompt_context_manifest,
   assumption_ledger_entry, replay_ref}` — every field sourced from the real
   bundle, none hand-typed.
5. Optionally adds `review`, via `review_from_task_result`.

### The adapter, precisely

| 0071 field | 0072 field | Mapping |
| --- | --- | --- |
| `reviewer` | `reviewer` | passthrough |
| `reviewed_at` (timestamp) | `review_date` (date) | first 10 characters |
| `owner` + `uncertainty` | `scope` | `f"{owner}: {uncertainty}"` |

Neither schema changes. This table is the seam, and it is exactly one
function (`review_from_task_result`) with its own test — not scattered
inline coercion at every call site.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | An unresolvable span ID raises rather than silently omits; a document citing the wrong source is rejected before emission; the admission gate itself is `0072`'s unchanged, already-hardened function. |
| P5 Reversibility | yes | Purely additive: a new source, a new module, a new example, a new agent, one spec. Nothing in `0070`/`0071`/`0072` is modified. |
| P6 Observability | yes | Every claim this spec makes is a passing, named test against real artifacts, not an assertion in prose. |
| P9 Security & data | yes | Every document is synthetic and disclosed; no network I/O; no real credit data anywhere in the module or its tests. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `sources/credit_document_fixture.yml` + `sources/README.md` | T-001 |
| REQ-002 | `emit_credit_document_evidence`'s source check | T-002 |
| REQ-003 | `admission_input_from_bundle` + `_resolve_source_spans` | T-003 |
| REQ-004 | `review_from_task_result` | T-004 |
| REQ-005 | `admit_bundle_result` | T-005 |
| REQ-006 | Replay tests via `0070`/`0071`'s existing replay functions | T-006 |
| REQ-007 | `generate_credit_document_examples` + committed `examples/` | T-007 |
| REQ-008 | `0072` coverage/gap-register/workflow updates | T-008 |
| REQ-009 | `agents/credit_risk/credit_document_analyst/` | T-009 |
| REQ-010 | `0072` spec.md open-question resolution | T-010 |
| NFR-001 | No import of any network/provider client anywhere in the module | T-002 |
| NFR-002 | `test_regenerated_bundle_matches_committed_hash` | T-007 |
| NFR-003 | `test_other_outputs_are_disclosed_fixture_content_not_extraction` | T-008 |
| NFR-004 | Source registration disclosure + `0025` reference | T-001 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Extraction fidelity | Reuse 0071's fixed fixture stub outputs, disclosed as such | Build a real, if small, regex-based covenant parser producing text-dependent values | A real parser is a genuine, separate piece of engineering with its own accuracy claims to validate; bolting it onto a plumbing-proof spec would blur what `0077` actually demonstrates. Deferred to a future spec with its own scoped accuracy requirements. |
| Corpus source | Register a new `credit_document_fixture` | Reuse `text_intelligence_fixture` | `0072`'s own gap register already flagged the generic fixture as not credit-specific; reusing it here would repeat the exact ambiguity `0072` named. |
| Field mismatch | One named, tested adapter function | Rename fields in 0071 or 0072 to match | Both schemas are correct for their own document; forcing one to match the other for this one integration point would be a larger, riskier change to two Approved specs for a problem a five-line function solves. |
| RAG dependency | None; direct span citation over a small corpus | Activate `0054` for retrieval | Vector search matters at corpus scale; a two-document fixture corpus does not need it. Resolves `0072`'s open question rather than deferring it again. |

## Validation Strategy

Every `AC-*` is proven by `tests/test_credit_document_intelligence.py`,
against the real committed bundle and a freshly regenerated one — not
hand-typed fixtures. `tests/test_credit_risk_knowledge.py`'s existing
admission tests continue to prove the contract's shape in isolation; this
module's tests prove the same contract holds under real data flow, which is
the gap this spec exists to close.

## Rollout, Observability & Rollback

Additive only. Rollback is deleting the new source, module, example, agent,
and spec directory, and reverting the `0072` index/gap-register edits — no
existing runtime or approved spec is modified. Observability is the test
suite itself: any future change to `0070` or `0071` that breaks this bridge
fails a named test here, not silently.

## Open Questions

None. `0072`'s prior open question about `0054` is resolved in Goals/Non-Goals
above and recorded in `0072`'s own spec text.
