# Tasks: Asian-Language NLP Foundation

- **Spec:** 0094-asian-language-nlp-foundation (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-02

> Every task cites a requirement and carries a Definition of Done. Nothing is built yet.

## Definition of Done (applies to every task)

- Tests exist and pass deterministically; standard library only.
- Fixtures synthetic and flagged; no real document, entity, or credential.
- Span integrity holds on every fixture; metrics reported per language.
- Gates pass and no existing test regresses.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Language and script identification, Simplified/Traditional heuristic | REQ-001, REQ-002 | todo | |
| T-002 | Segmentation baseline with segmenter slot and tokenizer ID | REQ-003 | todo | |
| T-003 | Rule-based extraction with spans, offsets, full-width handling, ambiguity flags, span verification | REQ-004, REQ-005, REQ-006, REQ-012 | todo | |
| T-004 | Synthetic labelled fixtures per language and extraction type | REQ-007, NFR-004 | todo | |
| T-005 | Per-language evaluation and publish guard | REQ-008, NFR-003 | todo | |
| T-006 | Baseline versus model comparison harness | REQ-009 | todo | |
| T-007 | Update multilingual agent contract with provenance and reviewer boundary | REQ-010 | todo | |
| T-008 | Update gap register | REQ-011 | todo | |
| T-009 | Determinism and span-integrity tests; run gates and full suite | NFR-001, NFR-002, NFR-005 | todo | |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | tests/test_asian_nlp.py::test_ac001_* (to be written) | todo |
| AC-002 | tests/test_asian_nlp.py::test_ac002_* (to be written) | todo |
| AC-003 | tests/test_asian_nlp.py::test_ac003_* (to be written) | todo |
| AC-004 | tests/test_asian_nlp.py::test_ac004_* (to be written) | todo |
| AC-005 | tests/test_asian_nlp.py::test_ac005_* (to be written) | todo |
| AC-006 | tests/test_asian_nlp.py::test_ac006_* (to be written) | todo |
| AC-007 | tests/test_asian_nlp.py::test_ac007_* (to be written) | todo |
| AC-008 | tests/test_asian_nlp.py::test_ac008_* (to be written) | todo |
| AC-009 | tests/test_asian_nlp.py::test_ac009_* (to be written) | todo |
| AC-010 | tests/test_asian_nlp.py::test_ac010_* (to be written) | todo |
| AC-011 | tests/test_asian_nlp.py::test_ac011_* (to be written) | todo |
| AC-012 | tests/test_asian_nlp.py::test_ac012_* (to be written) | todo |
| AC-013 | tests/test_asian_nlp.py::test_ac013_* (to be written) | todo |
| AC-014 | tests/test_asian_nlp.py::test_ac014_* (to be written) | todo |
