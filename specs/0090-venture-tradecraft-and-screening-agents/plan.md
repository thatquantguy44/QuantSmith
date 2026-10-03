# Plan: Venture Tradecraft and Screening-Support Agents

- **Spec:** 0090-venture-tradecraft-and-screening-agents (`spec.md`)
- **Status:** Draft
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-10-02

> HOW. Requires the Draft spec.

## Approach

Six contract-only agents, generated from one script for consistent boundary
language, plus a pure helper module whose functions mirror the guardrails
(corroboration counts origins, the matrix demands a deception hypothesis, the
ownership product excludes contract links, the channel check refuses prohibited
classes). Conventions (grades, bands, prohibited classes) are read from
`conventions.json`, never redefined.

## Architecture & Components

```
agents/venture_intelligence/{source_reliability_grader,confidence_language_reviewer,
  competing_hypotheses_analyst,collection_gap_tracker,ownership_screen,dual_use_indicator}
src/quantsmith/pipelines/venture_tradecraft.py
tests/test_venture_tradecraft.py
knowledge/venture_intelligence/{coverage,workflows,glossary}.json
instructions/venture_intelligence.md, agents/README.md, agents/venture_intelligence/README.md
```

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Guardrails encoded as checks |
| P5 Reversibility | yes | Additive |
| P9 Security & data | yes | Indicator-level; prohibited-source refusal; no data |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | grader agent, `parse_grade`, `corroboration_status` | T-001 |
| REQ-002 | reviewer agent, `check_statement`, `vague_terms` | T-002 |
| REQ-003 | ACH agent, `ach_matrix`, `sensitivity` | T-003 |
| REQ-004 | tracker agent, `candidate_channel_check`, aging, orphans | T-004 |
| REQ-005 | ownership agent, `effective_ownership`, `crosses_threshold`, lint | T-005 |
| REQ-006 | dual-use agent | T-006 |
| REQ-007 | helper module | T-001..T-005 |
| REQ-008 | indexes and coverage | T-007 |
| NFR-001 | pure functions | T-008 |
| NFR-002 | note fields, lint docstring | T-005 |
| NFR-003 | gates | T-008 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected | Why |
| --- | --- | --- | --- |
| Ordering in ACH | Fewest inconsistencies, labelled as not a conclusion | A recommended hypothesis | The conclusion belongs to the analyst |
| Ownership arithmetic | Equity only, all paths | Include contractual links as ownership | Contract control is a different mechanism |
| Dual-use | Questions for counsel | Embed control-list rules | Rules change and are counsel-owned |
| Lint | Term finder | Verdict classifier | A heuristic that asks a human to look, not a judge |

## Validation Strategy

`tests/test_venture_tradecraft.py` (AC-001..AC-010, AC-012), pack validator (AC-011), gates and full suite (AC-013).

## Rollout, Observability & Rollback

Docs, data, and pure functions. Rollback: delete the six folders and the module and revert the listed edits.

## Open Questions

Control lists and thresholds for the proof of concept.
