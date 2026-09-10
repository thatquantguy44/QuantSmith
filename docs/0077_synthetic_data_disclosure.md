# Synthetic Data Disclosure — Spec 0077 Credit Document Intelligence

- **Artifact:** `examples/credit_document_intelligence/`
- **Author:** QuantSmith spec `0077` maintainers
- **Last updated:** 2026-09-10
- **Reviewer / sign-off:** Fixture evidence is structurally approved by the
  recorded `spec0071` review objects carried through unchanged (the bundle
  is emitted by `0071`'s own producer); production and credit-decision use
  are not approved.

## Priority Check

- [x] Actual sourced data was considered first.
- [x] Real credit documents (memos, covenant letters, agreements) were
      intentionally not used because the acceptance target is a validated
      wiring proof for `0072`'s LLM evidence-admission boundary, with no
      obligor, counterparty, or licensing ambiguity, and no consumer-data
      handling question to resolve.

## Disclosure Table

| Location (section / chart / field) | What's synthetic | Why real data wasn't used | Generation method | Real-data follow-up |
| --- | --- | --- | --- | --- |
| `documents/credit-memo-obligor-001.txt`, `documents/credit-memo-covenant-001.txt` | Fictional borrower, leverage-ratio, and covenant-headroom commentary — no real obligor, agreement, or counterparty is named or implied | A real credit memo or covenant letter would carry licensing, confidentiality, and MNPI questions unrelated to proving the admission-boundary wiring | Fixed strings and timestamps in `generate_credit_document_examples`; `0071`'s existing deterministic normalization and lexical classification; no random sampling, no model call | Register and approve a real, licensed credit-document corpus, its access tier, and its entitlement policy before any real-document ingestion (`0072` gap `G-0072-006`) |
| `task_results.json`'s `entity_extraction`/`value_extraction`/`sentiment_stance`/`theme_detection` outputs | Fixed reference-fixture content from `0071`'s existing producer, unchanged and independent of this corpus's actual text (only `classification` is genuinely computed from the documents) | These outputs demonstrate the citation/admission/replay contract shape, not a working covenant-extraction model; building one is separate, scoped future work | `0071`'s existing fixed fixture stub, carried over verbatim | Build and separately validate a genuine, text-dependent extractor before any output here is treated as extracted content |

## Traceability

Every artifact is hash-linked by `text_intelligence_manifest.json`, produced
by `0071`'s unchanged producer. The matching `0070` run envelope records
prompt, context, assumptions, evaluation, audit events, expected outputs, and
replay classification. Source metadata resolves to
`sources/credit_document_fixture.yml`. The admission bridge itself
(`admission_input_from_bundle`, `review_from_task_result`,
`admit_bundle_result`) is proven against this exact artifact set in
`tests/test_credit_document_intelligence.py`.
