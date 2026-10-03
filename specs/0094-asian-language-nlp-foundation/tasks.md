# Tasks: Asian-Language NLP Foundation

- **Spec:** 0094-asian-language-nlp-foundation (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-02

> Every task cites a requirement and carries a Definition of Done.

## Definition of Done (applies to every task)

- Tests exist and pass deterministically; standard library only.
- Fixtures synthetic and flagged; no real document, entity, or credential.
- Span integrity holds on every fixture; metrics reported per language.
- Gates pass and no existing test regresses.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Language and script identification, Simplified/Traditional heuristic | REQ-001, REQ-002 | done | |
| T-002 | Segmentation baseline with segmenter slot and tokenizer ID | REQ-003 | done | |
| T-003 | Rule-based extraction with spans, offsets, full-width handling, ambiguity flags, span verification | REQ-004, REQ-005, REQ-006, REQ-012 | done | |
| T-004 | Synthetic labelled fixtures per language and extraction type | REQ-007, NFR-004 | done | 199 extraction + 41 identification cases; minimum 6 per applicable cell |
| T-005 | Per-language evaluation and publish guard | REQ-008, NFR-003 | done | Pooled score refused below n=6 per cell |
| T-006 | Baseline versus model comparison harness | REQ-009 | done | |
| T-007 | Update multilingual agent contract with provenance and reviewer boundary | REQ-010 | done | |
| T-008 | Update gap register | REQ-011 | done | |
| T-009 | Determinism and span-integrity tests; run gates and full suite | NFR-001, NFR-002, NFR-005 | done | |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | tests/test_asian_nlp.py::test_ac001_* | done |
| AC-002 | tests/test_asian_nlp.py::test_ac002_* | done |
| AC-003 | tests/test_asian_nlp.py::test_ac003_* | done |
| AC-004 | tests/test_asian_nlp.py::test_ac004_* | done |
| AC-005 | tests/test_asian_nlp.py::test_ac005_* | done |
| AC-006 | tests/test_asian_nlp.py::test_ac006_* | done |
| AC-007 | tests/test_asian_nlp.py::test_ac007_* | done |
| AC-008 | tests/test_asian_nlp.py::test_ac008_* | done |
| AC-009 | tests/test_asian_nlp.py::test_ac009_* | done |
| AC-010 | tests/test_asian_nlp.py::test_ac010_* | done |
| AC-011 | tests/test_asian_nlp.py::test_ac011_* | done |
| AC-012 | tests/test_asian_nlp.py::test_ac012_* | done |
| AC-013 | tests/test_asian_nlp.py::test_ac013_* | done |
| AC-014 | run-stage.sh gates + full pytest (1022 passed) | done |
