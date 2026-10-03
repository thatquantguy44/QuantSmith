# Tasks: Domain Visualization Packs and Executive Storytelling

- **Spec:** 0093-visualization-packs (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-03

## Definition of Done

Requirements are implemented, acceptance tests pass, examples reproduce, all
content references resolve, and verification results and limitations are recorded.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Catalog and seven domain packs | REQ-001, REQ-003, REQ-010, REQ-011 | in-progress | See plan for components and acceptance evidence. |
| T-002 | Authorized evidence and bindings | REQ-002, REQ-006, REQ-011, REQ-012, NFR-001 | in-progress | See plan for components and acceptance evidence. |
| T-003 | Story construction and policy assessments | REQ-003, REQ-004, REQ-005, REQ-006, REQ-007, REQ-008, REQ-012 | in-progress | See plan for components and acceptance evidence. |
| T-004 | Portable rendering and dashboard handoff | REQ-005, REQ-009, REQ-012, NFR-003 | in-progress | See plan for components and acceptance evidence. |
| T-005 | Three-domain reproducible example | REQ-013, NFR-001 | in-progress | See plan for components and acceptance evidence. |
| T-006 | Acceptance, regression, visual, and gate verification | NFR-002, NFR-003 | in-progress | See plan for components and acceptance evidence. |

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `tests/test_visualization_packs.py` (names AC-001) | todo |
| AC-002 | `tests/test_visualization_packs.py` (names AC-002) | todo |
| AC-003 | `tests/test_visualization_packs.py` (names AC-003) | todo |
| AC-004 | `tests/test_visualization_packs.py` (names AC-004) | todo |
| AC-005 | `tests/test_visualization_packs.py` (names AC-005) | todo |
| AC-006 | `tests/test_visualization_packs.py` (names AC-006) | todo |
| AC-007 | `tests/test_visualization_packs.py` (names AC-007) | todo |
| AC-008 | `tests/test_visualization_packs.py` (names AC-008) | todo |
| AC-009 | `tests/test_visualization_packs.py` (names AC-009) | todo |
| AC-010 | `tests/test_visualization_packs.py` (names AC-010) | todo |
| AC-011 | `tests/test_visualization_packs.py` (names AC-011) | todo |
| AC-012 | `tests/test_visualization_packs.py` (names AC-012) | todo |
| AC-013 | `tests/test_visualization_packs.py` (names AC-013) | todo |
| AC-014 | `tests/test_visualization_packs.py` (names AC-014) | todo |

## Follow-ups

Expand beyond seven initial domains through the coverage register; extend renderers
for domain conventions currently disclosed as table fallbacks. Human content review
remains separate from approving this feature specification.

## Checkpoint evidence

- 47 new acceptance/adversarial tests passed on 2026-10-03.
- Catalog CLI validates seven packs and fourteen recipes.
- Finance, credit, and macro demonstrations return ready; invalid PD summation
  returns invalid before producing a story.
- Targeted regression: 124 passed, one skipped (optional renderer dependency).
- Full repository suite, browser review, and final quality gates are pending at
  this checkpoint. Tasks remain in progress until verified.
