# Plan: Venture Sources, Point-in-Time Ingestion & Entity Resolution

- **Spec:** 0088-venture-sources-pit-ingestion (`spec.md`)
- **Status:** Draft
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-10-02

> HOW. Requires the Draft spec.

## Approach

Make the `0083` contracts executable in one small stdlib module, register sources
in the existing catalog format, and add a thin agent contract. No adapters, no
network: the module consumes caller-supplied records so behaviour is testable.

## Architecture & Components

```
sources/{patentsview,openalex,usaspending,sbir_gov,gleif_lei,trade_csl,
         opensanctions,uk_companies_house,gh_archive,gdelt,venture_fixture}.yml
knowledge/venture_intelligence/conventions.json   (+ known_at_policies, entity_resolution)
src/quantsmith/pipelines/venture_ingestion.py     (derive_known_at, build_fact, as_of_view,
                                                   form_cohort, cohort_rate, normalize_name,
                                                   resolve_entities)
agents/venture_intelligence/entity_resolution/
tests/test_venture_ingestion.py
```

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | known_at policies, outcome-independent cohorts |
| P5 Reversibility | yes | Additive |
| P9 Security & data | yes | No credentials; synthetic fixtures |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | source entries | T-001 |
| REQ-002 | policies, `derive_known_at` | T-002 |
| REQ-003 | late-retrieval flag | T-002 |
| REQ-004 | `as_of_view` | T-003 |
| REQ-005 | `form_cohort`, `cohort_rate` | T-003 |
| REQ-006 | `resolve_entities` | T-004 |
| REQ-007 | `normalize_name`, `script_of` | T-004 |
| REQ-008 | agent contract | T-005 |
| REQ-009 | indexes | T-006 |
| NFR-001 | pure functions, tests | T-007 |
| NFR-002 | source entry wording, scan test | T-001 |
| NFR-003 | gate runs | T-007 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected | Why |
| --- | --- | --- | --- |
| known_at for timestamped sources | Public time, flagged if retrieved late | Always retrieval time | Public time is the honest knowability date; the late flag protects against backfill |
| Name matching | Deterministic candidates | Fuzzy or learned matcher | A learned matcher needs labelled pairs and validation first (gap) |
| Adapters | None yet | Build now | Licences, terms, and endpoints unconfirmed |

## Validation Strategy

`tests/test_venture_ingestion.py` for AC-002..AC-007, AC-010, AC-011; gates for AC-001, AC-003 (source-catalog), AC-008, AC-009.

## Rollout, Observability & Rollback

Additive. Rollback: delete the listed files and index rows.

## Open Questions

Which adapters first, after the bake-off.
