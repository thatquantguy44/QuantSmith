# Tasks: Credit Document Intelligence

- **Spec:** 0077-credit-document-intelligence (`spec.md`, `plan.md`)
- **Last updated:** 2026-09-10

## Definition of Done (applies to every task)

- Every claim in `spec.md` is proven by a named, passing test against real
  artifacts — a real emitted bundle, not a hand-typed fixture.
- No modification to any approved `0070`, `0071`, or `0072` module. `0077`
  composes their public functions only.
- No live model, provider, or network call anywhere in the module or tests.
- Every committed document is synthetic and disclosed; no real credit data.
- Documentation and indexes updated in the same change.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Register `sources/credit_document_fixture.yml` and index it in `sources/README.md`, disclosing its synthetic/fictional nature. | REQ-001, NFR-004 | done | `source-catalog` gate clean. |
| T-002 | Write `credit_document_intelligence.py`'s `emit_credit_document_evidence`, wrapping `0071`'s `emit_lexical_signal_evidence` unchanged with a source-id check rejecting any document not citing `credit_document_fixture`. | REQ-002, NFR-001 | done | Verified: a document citing `text_intelligence_fixture` raises before emission. |
| T-003 | Write `admission_input_from_bundle` and `_resolve_source_spans`, loading a real bundle's corpus/task-results/envelope and resolving real span IDs; an unresolvable ID raises. | REQ-003 | done | Accepts either the bundle directory or the manifest path `emit_lexical_signal_evidence` returns. |
| T-004 | Write `review_from_task_result`, the 0071-to-0072 review field adapter, with a dedicated test on hand-constructed input plus one against the real committed bundle's review object. | REQ-004 | done | Found the field-name mismatch (`reviewed_at`/no `scope` vs `review_date`/`scope`) while wiring the two systems together; documented in `spec.md`'s Problem & Context rather than silently patched. |
| T-005 | Write `admit_bundle_result`, composing T-003/T-004 with `0072`'s `admit_derived_evidence`; prove all three outcomes (`derived_evidence`, `decision_input`, rejected) against the real bundle. | REQ-005 | done | All three outcomes verified against the actual emitted bundle before this task was marked done, not only against illustrative dicts. |
| T-006 | Prove replay determinism via `0071`'s `replay_text_intelligence_manifest_file` and `0070`'s `replay_envelope_file`, each run twice on a freshly regenerated bundle and on the committed one. | REQ-006 | done | `status == "replayed"`, `replay_mode == "deterministic"`, no output diffs, both engines. |
| T-007 | Write `generate_credit_document_examples`; commit its output under `examples/credit_document_intelligence/`; add a hash-equality test against a fresh regeneration. | REQ-007, NFR-002 | done | Corpus and task-result hashes match a fresh regeneration exactly. |
| T-008 | Update `0072`'s `coverage.json` (`capability.document_intelligence` coverage level and artifacts), `gap_register.md` (`G-0072-006` disposition), and `workflows.json` (`workflow.credit_document_intelligence`'s `credit_document_analyst` agent status) to describe exactly what this spec proves — wiring, not extraction. | REQ-008, NFR-003 | done | Coverage level moved to `reference_runtime` for the wiring surface only; the limitation field states plainly that extraction accuracy is not claimed. |
| T-009 | Create `agents/credit_risk/credit_document_analyst/` (`README.md`, `instructions.md`, `prompt.md`, `tasks.md`, `Spec-Driven Role` section) and add its row to `agents/README.md`. | REQ-009 | done | First agent created under `0072`'s charter; justified by this spec's real, tested runtime, not created ahead of it. |
| T-010 | Resolve `0072`'s open question on `0054` activation in `0072`'s own `spec.md`, referencing this spec's resolution rather than repeating the question. | REQ-010 | done | `0072`'s Assumptions & Open Questions updated in place. |
| T-011 | Update `specs/README.md`, `docs/handoff.md`, and root `README.md` — index the spec, update the credit-risk chain description, add a handoff item, update spec/agent counts, bump badges. | REQ-007, REQ-009 | done | `doc-counts`, `spec-index`, `handoff-sync`, `agent-catalog` gates clean. Cites REQ-007/REQ-009 because indexing the committed example and the new agent is how each becomes discoverable, not a standalone requirement of its own. |
| T-012 | Run the full gate suite and `pytest -q`; record evidence without changing any existing runtime's result. | NFR-001 | done | Evidence recorded below. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `source-catalog` gate (no findings) | done |
| AC-002 | `test_documents_must_cite_the_credit_document_source` | done |
| AC-003 | `test_admission_input_resolves_real_spans_from_the_real_corpus`, `test_unresolvable_span_id_is_rejected` | done |
| AC-004 | `test_review_adapter_maps_0071_fields_to_0072_fields` | done |
| AC-005 | `test_reviewed_result_is_admitted_as_decision_input`, `test_unreviewed_result_is_admitted_only_as_derived_evidence`, `test_missing_envelope_ref_is_rejected_against_real_data` | done |
| AC-006 | `test_replay_is_deterministic_on_regeneration`, `test_committed_envelope_validates_and_replays` | done |
| AC-007 | `test_regenerated_bundle_matches_committed_hash` | done |
| AC-008 | Manual review of `coverage.json`/`gap_register.md` diff against this spec | done |
| AC-009 | `agent-catalog` gate (no findings) | done |
| AC-010 | Manual review of `0072` spec.md diff | done |
| AC-011 | `test_other_outputs_are_disclosed_fixture_content_not_extraction` | done |

## Validation Evidence

Captured 2026-09-10 on `claude/credit-risk-agents-spec-zttp6c`.

- `PYTHONPATH=src pytest -q tests/test_credit_document_intelligence.py` ->
  `15 passed`
- `PYTHONPATH=src pytest -q` -> `622 passed, 1 skipped` (was `607 passed, 1
  skipped` before this spec; no existing test's behavior changed)
- `hooks/stages/run-stage.sh spec spec-index handoff-sync doc-counts
  docs-link source-catalog data-provenance secret-scan agent-catalog
  readme-sync` -> clean except the pre-existing `readme-sync` finding for
  spec `0066`, which reproduces on `main`
- `git diff --check` -> no whitespace errors
- Manual smoke test: `admit_bundle_result` against the real committed bundle
  returned `decision_input` with review, `derived_evidence` without, and a
  correctly-named rejection with `envelope_ref` removed — before any test
  was written to assert it.

## Follow-ups

- A real, licensed credit-document corpus at retrieval scale, and whether it
  needs `0054` — deferred until a real consumer needs it (`0072` gap
  `G-0072-006`, updated but not closed by this spec).
- A genuine, text-dependent covenant or financial-value extractor. This spec
  deliberately proves the admission plumbing only; extraction accuracy is
  separate, scoped work with its own validation requirements.
