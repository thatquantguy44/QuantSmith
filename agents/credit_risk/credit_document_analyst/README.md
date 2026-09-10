# Credit Document Analyst Agent

## Purpose

The Credit Document Analyst Agent turns unstructured credit documents — credit
memos, covenant letters, financial commentary — into cited, governed evidence
that a human can promote into a credit decision. It does not decide anything
itself: it produces `derived_evidence`, never a `decision_input`, and only
named human review can change that.

## Use When

- A credit memo or covenant letter needs its claims surfaced with citations
  rather than summarized freehand.
- A credit workflow needs an LLM- or NLP-derived value admitted safely,
  through `0072`'s evidence-admission boundary rather than as an unattributed
  fact.
- Someone asks "what does this document say" about a credit exposure and the
  answer needs to trace back to a specific span of text, not a paraphrase.

## Inputs

- One or more documents registered against a disclosed, synthetic-or-real
  source under `sources/` — never an unregistered file.
- The `0072` decision path the extraction will eventually feed
  (`path.credit_document_intelligence` by default).

## Outputs

- A `0071` corpus snapshot, transform chain, task-result set, and audit
  ledger, wrapped in a `0070` run envelope — reproducible by replay.
- A `0072` admission result: `derived_evidence` by default, `decision_input`
  only once a named human reviewer, review date, and review scope are
  recorded on the source task result.
- An explicit statement of what was *not* extracted with confidence, never a
  silently omitted gap.

## Example Requests

- "Pull the leverage-ratio covenant out of this credit agreement excerpt and
  cite exactly where it says so."
- "Is this extracted value ready to feed the ECL measurement, or does it
  still need review?"
- "Show me the replay of last week's covenant extraction run — did anything
  change?"

## Required Review Themes

- Every claim carries a citation (`evidence_span_ids`) into the actual
  document text; an unresolvable citation is a defect, not a detail.
- No value is treated as a decision input without a named human reviewer,
  review date, and review scope recorded — see `0072` REQ-016.
- The extraction's own confidence and limitations are stated plainly; a
  fixture or reference-quality result is labeled as such, never presented as
  production-calibrated.
- No protected attribute, consumer PII, or licensed agreement text is ever
  reproduced in the extracted output.

## Runtime

A tested, runnable bridge exists (spec `0077-credit-document-intelligence`):
`src/quantsmith/pipelines/credit_document_intelligence.py` — emits a real
`0071` bundle over a registered credit-document source
(`sources/credit_document_fixture.yml`) via `0071`'s own
`emit_lexical_signal_evidence`, then bridges one real task result into
`0072`'s `admit_derived_evidence` via `admission_input_from_bundle` and
`review_from_task_result`. One committed, regenerable example lives at
`examples/credit_document_intelligence/`.

**What the runtime does not yet do:** it does not run a real covenant or
financial-value extraction model. The underlying `0071` producer's
`entity_extraction`/`value_extraction`/`sentiment_stance`/`theme_detection`
outputs are fixed reference-fixture content, disclosed as such — only the
`classification` result is genuinely computed from the input text. This
agent's review themes (citation integrity, review-before-promotion, honest
disclosure of fixture-versus-real content) apply regardless of whether the
underlying extraction is a fixture or, eventually, a real model.
