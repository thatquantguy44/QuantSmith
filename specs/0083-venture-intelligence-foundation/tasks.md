# Tasks: Venture & Non-Traditional Intelligence Foundation

- **Spec:** 0083-venture-intelligence-foundation (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-02

> Every task cites the requirement(s) it advances and carries a Definition of Done.

## Definition of Done (applies to every task)

- Stable IDs; every claim cited or `unverified`.
- Synthetic data only, disclosed per `0025`; no real entity, person, or filing.
- Validator and gates pass; reproducible offline.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Write `instructions/venture_intelligence.md` incl. multilingual section | REQ-001, REQ-018 | done | |
| T-002 | Taxonomy pack | REQ-002 | done | |
| T-003 | Convention registry (valuation, dilution, fund metrics) | REQ-003 | done | |
| T-004 | Data-time and bias contract | REQ-004 | done | |
| T-005 | Source grade and confidence conventions | REQ-005 | done | |
| T-006 | Channel catalog with licence and PIT statements | REQ-006, NFR-006 | done | |
| T-007 | Glossary JSON and dictionary section | REQ-007 | done | |
| T-008 | Coverage matrix, agent roster, roadmap in `specs/README.md` | REQ-008, REQ-016, REQ-019 | done | |
| T-009 | Model catalog | REQ-009 | done | |
| T-010 | Workflow registry with decision-path classes | REQ-010, REQ-011, REQ-017 | done | |
| T-011 | Gap register and golden cases (incl. per-language normalization) | REQ-012, REQ-018 | done | |
| T-012 | Stdlib validator and tests | REQ-011, REQ-013, NFR-001, NFR-004 | done | |
| T-013 | Overlay template and gitignore | REQ-015 | done | |
| T-014 | Document reuse of 0070/0071/0052-0054/0025/0026 | REQ-014 | done | |
| T-016 | Review status fields and sign-off validation | REQ-020 | done | Validator prints review summary |
| T-015 | Run gates, synthetic disclosure, additive-diff check | NFR-002, NFR-003, NFR-005, NFR-004 | done | Gates pass; see commit |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | tests/test_venture_pack.py::test_ac001_* | done |
| AC-002 | tests/test_venture_pack.py::test_ac002_* | done |
| AC-003 | tests/test_venture_pack.py::test_ac003_* | done |
| AC-004 | tests/test_venture_pack.py::test_ac004_* | done |
| AC-005 | tests/test_venture_pack.py::test_ac005_* | done |
| AC-006 | tests/test_venture_pack.py::test_ac006_* | done |
| AC-007 | tests/test_venture_pack.py::test_ac007_* | done |
| AC-008 | tests/test_venture_pack.py::test_ac008_* | done |
| AC-009 | tests/test_venture_pack.py::test_ac009_* | done |
| AC-010 | tests/test_venture_pack.py::test_ac010_* | done |
| AC-011 | tests/test_venture_pack.py::test_ac011_* | done |
| AC-012 | tests/test_venture_pack.py::test_ac012_* | done |
| AC-013 | tests/test_venture_pack.py::test_ac013_* | done |
| AC-014 | tests/test_venture_pack.py::test_ac014_* | done |
| AC-015 | tests/test_venture_pack.py::test_ac015_* | done |
| AC-016 | tests/test_venture_pack.py::test_ac016_* | done |
| AC-022 | tests/test_venture_pack.py::test_ac022_* | done |
| AC-017 | run-stage.sh spec + agent-catalog (manual) | todo |
| AC-018 | tests/test_venture_pack.py::test_ac018_* | done |
| AC-019 | tests/test_venture_pack.py::test_ac019_every_claim_cited_or_unverified + git diff | todo |
| AC-020 | tests/test_venture_pack.py::test_ac020_* | done |
| AC-021 | tests/test_venture_pack.py::test_ac021_* | done |
