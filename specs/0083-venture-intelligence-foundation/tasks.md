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
| T-002 | Taxonomy pack | REQ-002 | todo | |
| T-003 | Convention registry (valuation, dilution, fund metrics) | REQ-003 | todo | |
| T-004 | Data-time and bias contract | REQ-004 | todo | |
| T-005 | Source grade and confidence conventions | REQ-005 | todo | |
| T-006 | Channel catalog with licence and PIT statements | REQ-006, NFR-006 | todo | |
| T-007 | Glossary JSON and dictionary section | REQ-007 | in-progress | |
| T-008 | Coverage matrix, agent roster, roadmap in `specs/README.md` | REQ-008, REQ-016, REQ-019 | in-progress | |
| T-009 | Model catalog | REQ-009 | todo | |
| T-010 | Workflow registry with decision-path classes | REQ-010, REQ-011, REQ-017 | todo | |
| T-011 | Gap register and golden cases (incl. per-language normalization) | REQ-012, REQ-018 | todo | |
| T-012 | Stdlib validator and tests | REQ-011, REQ-013, NFR-001, NFR-004 | todo | |
| T-013 | Overlay template and gitignore | REQ-015 | todo | |
| T-014 | Document reuse of 0070/0071/0052-0054/0025/0026 | REQ-014 | todo | |
| T-015 | Run gates, synthetic disclosure, additive-diff check | NFR-002, NFR-003, NFR-005, NFR-004 | todo | |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | manual read of standard | todo |
| AC-002 | tests/test_venture_pack.py (to be written) | todo |
| AC-003 | tests/test_venture_pack.py (to be written) | todo |
| AC-004 | tests/test_venture_pack.py (to be written) | todo |
| AC-005 | tests/test_venture_pack.py (to be written) | todo |
| AC-006 | tests/test_venture_pack.py (to be written) | todo |
| AC-007 | test_glossary_matches_dictionary | todo |
| AC-008 | tests/test_venture_pack.py (to be written) | todo |
| AC-009 | tests/test_venture_pack.py (to be written) | todo |
| AC-010 | tests/test_venture_pack.py (to be written) | todo |
| AC-011 | tests/test_venture_pack.py (to be written) | todo |
| AC-012 | tests/test_venture_pack.py (to be written) | todo |
| AC-013 | tests/test_venture_pack.py (to be written) | todo |
| AC-014 | tests/test_venture_pack.py (to be written) | todo |
| AC-015 | manual read of specs/README.md | todo |
| AC-016 | manual read of workflows | todo |
| AC-017 | run-stage.sh spec + agent-catalog | todo |
| AC-018 | test_fixtures_synthetic | todo |
| AC-019 | git diff + citation check | todo |
| AC-020 | manual read + golden cases | todo |
| AC-021 | agent-catalog gate + manual roster read | todo |
