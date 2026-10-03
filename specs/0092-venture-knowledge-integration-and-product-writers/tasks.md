# Tasks: Venture Knowledge Integration and Product Writers

- **Spec:** 0092-venture-knowledge-integration-and-product-writers (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-03

> Every task cites a requirement and carries a Definition of Done.

## Definition of Done (applies to every task)

- Tests pass deterministically; standard library only; synthetic data only.
- Nothing private is committed; the store is ignored and never tracked.
- Gates pass and no existing test regresses.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Ignore rule, templates, gate edits, tracked-files check, overlay rule | REQ-001, REQ-003, NFR-003 | done | |
| T-002 | Store manifest validation | REQ-002 | done | |
| T-003 | Memory candidate builders and local-only staging | REQ-004, REQ-005, NFR-003 | done | |
| T-004 | Memory-manifest and knowledge-sources template entries | REQ-006 | done | |
| T-005 | Retrieval with clearance-first, point-in-time, eligible-only ranking | REQ-007, REQ-008, REQ-009 | done | |
| T-006 | Contract checker and corpus validation | REQ-010, REQ-011 | done | |
| T-007 | Product validation, release rule, rendering | REQ-012, REQ-013, REQ-014 | done | |
| T-008 | Fix None-as-a-name in the pack, tradecraft, and product sign-off checks | REQ-013 | done | |
| T-009 | Agents, conventions, workflows, indexes, registry, glossary, gaps | REQ-015, NFR-002 | done | |
| T-010 | Determinism, gates, full suite | NFR-001, NFR-004 | done | |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | tests/test_venture_knowledge.py::test_ac001_* | done |
| AC-002 | tests/test_venture_knowledge.py::test_ac002_* | done |
| AC-003 | tests/test_venture_knowledge.py::test_ac003_* | done |
| AC-004 | tests/test_venture_knowledge.py::test_ac003_staging_stays_inside_knowledge_local_and_promotes_nothing | done |
| AC-005 | tests/test_venture_knowledge.py::test_ac004_* | done |
| AC-006 | tests/test_venture_knowledge.py::test_ac005_retrieval_returns_cited_spans_that_slice_back | done |
| AC-007 | tests/test_venture_knowledge.py::test_ac005_chinese_query_uses_the_asian_nlp_segmenter | done |
| AC-008 | tests/test_venture_knowledge.py::test_ac005_not_found_is_an_answer, test_ac006_clearance_is_required_and_applied_before_ranking | done |
| AC-009 | tests/test_venture_knowledge.py::test_ac006_a_restricted_match_is_indistinguishable_from_no_match, test_ac006_restricted_documents_cannot_move_a_lower_callers_scores | done |
| AC-010 | tests/test_venture_knowledge.py::test_ac007_* | done |
| AC-011 | tests/test_venture_knowledge.py::test_ac008_* | done |
| AC-012 | tests/test_venture_knowledge.py::test_ac009_* | done |
| AC-013 | tests/test_venture_knowledge.py::test_ac010_* | done |
| AC-014 | tests/test_venture_knowledge.py::test_ac011_*, test_ac012_*, tests/test_venture_pack.py::test_none_is_never_a_name_in_review_signoff | done |
| AC-015 | run-stage.sh gates + full pytest | done |
