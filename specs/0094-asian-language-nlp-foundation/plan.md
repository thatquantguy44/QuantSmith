# Plan: Asian-Language NLP Foundation

- **Spec:** 0094-asian-language-nlp-foundation (`spec.md`)
- **Status:** Draft
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-10-02

> HOW. Requires the Draft spec. Nothing is built yet; `tasks.md` tracks status.

## Approach

A small standard-library package, `quantsmith.asian_nlp`, alongside (not inside)
the `0071` runtime, so `0071` is untouched. It exposes pure functions for language
and script identification, segmentation, and rule-based extraction, an evaluation
harness, and a model-comparison harness. Normalization rules are read from
`knowledge/venture_intelligence/conventions.json` so there is one source of truth;
the package adds only extraction patterns and fixtures.

## Architecture & Components

```
src/quantsmith/asian_nlp/
  __init__.py
  identify.py      (script + language candidates, Simplified/Traditional heuristic)
  segment.py       (whitespace / char n-gram baseline, segmenter slot, tokenizer id)
  extract.py       (amounts, currencies, dates, era years, fiscal periods; spans, offsets)
  evaluate.py      (per-language precision/recall/exact; no pooled hiding)
  compare.py       (baseline vs model comparison; never overwrites)
  fixtures/        (synthetic labelled cases per language, JSON)
tests/test_asian_nlp.py
agents/venture_intelligence/multilingual_document_nlp/   (contract updated)
knowledge/venture_intelligence/gaps.json                (re-owned + new gaps)
```

## Interfaces & Data Contracts

- `identify(text) -> {"script", "candidates": [{"language", "score", "evidence"}], "status": "ok" | "undetermined", "reasons": []}`.
- `segment(text, language=None, segmenter=None) -> {"tokens": [...], "tokenizer": "<id>@<version>"}`.
- `extract(text, language=None) -> [{"type", "span", "start", "end", "language", "rule_id", "value", "unit", "ambiguous", "method": "rule"}]`; `ambiguous` items carry `value: null`.
- `verify_spans(text, items) -> list[str]` (errors).
- `evaluate(cases, predictions) -> {language: {type: {"precision", "recall", "exact", "n"}}}` and `publish(report, min_n)` which refuses a pooled figure if any language is below `min_n`.
- `compare(baseline, model) -> {"agree": [...], "disagree": [...], "model_only": [...], "baseline_only": [...]}` with model items marked `derived: true`; the baseline is returned unchanged.

## Languages and Minimum Fixtures

Initial in-scope: `zh-Hans`, `zh-Hant`, `ja`, `ko`, `th`, `vi`, `id`/`ms`, `fil`, `ru`, `kk`/`uz` (Cyrillic and Latin), `en` (including lakh and crore). Starting minimum: 12 labelled cases per language per extraction type, adjustable by decision recorded in this plan.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Span integrity check; ambiguity flagged |
| P5 Reversibility | yes | New package; no change to `0071` |
| P6 Observability | partial | Per-language metrics; no runtime service |
| P9 Security & data | yes | Synthetic fixtures; no network |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `identify.py` | T-001 |
| REQ-002 | `identify.py` variant heuristic | T-001 |
| REQ-003 | `segment.py` | T-002 |
| REQ-004 | `extract.py` | T-003 |
| REQ-005 | conventions reuse, ambiguity flag | T-003 |
| REQ-006 | `verify_spans` | T-003 |
| REQ-007 | `fixtures/` | T-004 |
| REQ-008 | `evaluate.py` | T-005 |
| REQ-009 | `compare.py` | T-006 |
| REQ-010 | agent contract update, provenance fields | T-007 |
| REQ-011 | gap register | T-008 |
| REQ-012 | full-width normalization with offset map | T-003 |
| NFR-001 | pure functions, tests | T-009 |
| NFR-002 | `verify_spans` over evaluation sets | T-009 |
| NFR-003 | report format | T-005 |
| NFR-004 | fixture flags | T-004 |
| NFR-005 | gates, full suite | T-009 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected | Why |
| --- | --- | --- | --- |
| Segmentation | Char n-gram baseline plus slot | Bundle a dictionary segmenter | A dictionary or model is a licensing and dependency decision for the adopter; the slot pins the interface |
| Language ID | Rule-based with `undetermined` | Statistical model | No training data or dependency yet; rules are checkable and honest on short text |
| Extraction | Rules over conventions | LLM extraction first | Rules are deterministic and give a baseline to judge model output against |
| Package location | New `asian_nlp` package | Edit `0071` | `0071` is Approved and frozen; additive is safer |
| Metrics | Per language, refuse pooled hiding | One overall score | A pooled score hides the weakest language |

## Validation Strategy

`tests/test_asian_nlp.py` for AC-001..AC-013 using synthetic fixtures; span integrity
asserted over every fixture; gates and the full suite for AC-014.

## Rollout, Observability & Rollback

Additive package and data. Rollback: delete `src/quantsmith/asian_nlp/`, its tests and
fixtures, and revert the agent-contract and gap-register edits.

## Open Questions

Which segmenter or multilingual model profiles to declare; the minimum fixture size.
