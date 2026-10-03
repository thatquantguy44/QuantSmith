# Plan: Venture Regional Agents — Greater China & East Asia, South Asia

- **Spec:** 0085-venture-regional-agents-east-and-south-asia (`spec.md`)
- **Status:** Draft
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-10-02

> HOW. Requires the Draft spec.

## Approach

Repeat the `0084` pattern: contract-only agents generated from one script for
consistent boundary language, plus data-level convention extensions the
validator recomputes. The specialist exists because structure mapping from
native-language filings is a distinct workflow; South Asia stays lead-only until
real work shows otherwise.

## Architecture & Components

`agents/venture_intelligence/{greater_china_east_asia/{regional_lead,entity_structure_analyst}, south_asia/regional_lead}`; `knowledge/venture_intelligence/{conventions,golden_cases,glossary,coverage}.json`; `venture_pack.py` (`cn_number`, `era_to_gregorian`); `tests/test_venture_regions.py`; catalog, standard, dictionary, roster updates.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Unknown units raise; fiscal year always stated |
| P5 Reversibility | yes | Additive |
| P9 Security & data | yes | No data; indicator-level only |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | East Asia lead | T-001 |
| REQ-002 | structure analyst | T-002 |
| REQ-003 | South Asia lead | T-003 |
| REQ-004 | convention data | T-004 |
| REQ-005 | parser, era function, golden cases | T-005 |
| REQ-006 | indexes | T-006 |
| NFR-001 | pure functions | T-005 |
| NFR-002 | citation labels | T-004 |
| NFR-003 | gates | T-007 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected | Why |
| --- | --- | --- | --- |
| Specialist count | One (structure) | Specialists per market | Only structure mapping is a distinct workflow today |
| Ambiguous 兆 | Raise | Pick 10^12 | A guessed multiplier is worse than a flag |
| Contractual control | Separate link type | Treat as ownership | Control mechanism affects interpretation |

## Validation Strategy

`tests/test_venture_regions.py`, the pack validator, and gates.

## Rollout, Observability & Rollback

Docs and data only. Rollback: delete the two region folders and revert convention additions.

## Open Questions

Registry access; South Asia specialist.
