# Plan: Venture & Non-Traditional Intelligence Foundation

- **Spec:** 0083-venture-intelligence-foundation (`spec.md`)
- **Status:** Draft
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-10-02

> HOW. Requires an approved `spec.md`; every requirement appears in the matrix below.

## Approach

Follow `0063`/`0072`: one versioned public domain pack, Markdown for narrative and
citations, JSON for stable IDs and conventions, and a stdlib validator that checks
referential, arithmetic, and governance invariants offline. Semantics first
(taxonomy, conventions, data-time), tradecraft second (grading, confidence),
channels and models last, so later runtimes have a contract to reproduce.

Three departures from the credit pack: (1) a **data-time contract** specific to
venture (survivorship, backfill, stealth omission); (2) **tradecraft conventions**
(source grade, calibrated confidence) as first-class data; (3) a **decision-path
class** with a `sovereign_adjacent` tier. Agents are created only by child specs,
gated by `coverage.json`.

## Architecture & Components

```
instructions/venture_intelligence.md      (standard: rule, classes, lawful collection)
knowledge/venture_intelligence/
  taxonomy.json  conventions.json  channels.json  models.json
  workflows.json glossary.json coverage.json gaps.json golden_cases.json
  README.md
src/quantsmith/pipelines/venture_pack.py  (stdlib validator)
tests/test_venture_pack.py
agentic_dictionary.md                     (+ Venture & Intelligence section)
agents/venture_intelligence/              (regions + cross-cutting; built by children)
config/venture_overlay.example.yml        (adopter-local overlay template; real one gitignored)
```

## Child-spec roadmap

| Spec | Scope | Status |
| --- | --- | --- |
| 0084 | Multilingual document NLP agent + first regional agents | Built (Draft) |
| 0085 | Further regional agents (kept local) | Built (Draft) |
| 0086 | Further regional agent (kept local; remaining regions deferred to `0087`) | Built (Draft) |
| 0087 | Deferred regions: MENA, Europe, Caucasus, Africa, Latin America, North America, Oceania | Reserved |
| 0088 | Source adapters/entries, point-in-time ingestion, entity resolution | Built (Draft); live adapters not built |
| 0089 | Signal analysts and sourcing/diligence agents | Built (Draft) |
| 0090 | Tradecraft and screening-support agents | Built (Draft) |
| 0091 | Fund and portfolio analytics (predictive models split out to `0095`) | Built (Draft) |
| 0092 | Private store, memory candidates, retrieval contract (live search stays `0054`), and brief and memo writers | Built (Draft) |
| 0094 | Multilingual NLP foundation (`0093` is the visualization packs spec) | Built (Draft) |
| 0095 | Predictive-model reference baselines and deployability gate (synthetic validation only) | Built (Draft) |

## Interfaces & Data Contracts

Every fact record: `entity_id`, `value`, `unit`, `source_id`, `source_grade`,
`event_time`, `announced_time`, `filed_time`, `ingested_time`, `known_at`,
`language`, `derived` (bool), `confidence`. Validator rejects records without
`known_at` (AC-004). Workflows carry `decision_path_class`.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P1 Spec is truth | yes | Agents only via child specs |
| P4 Correct by construction | yes | Data-time and bias contracts |
| P5 Reversibility | yes | Additive only (NFR-005) |
| P6 Observability | partial | Runtime deferred to children |
| P9 Security & data | yes | Public scaffold, overlay for sensitive use |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `instructions/venture_intelligence.md` | T-001 |
| REQ-002 | `taxonomy.json` | T-002 |
| REQ-003 | `conventions.json` | T-003 |
| REQ-004 | data-time contract in `conventions.json` | T-004 |
| REQ-005 | grading in `conventions.json` | T-005 |
| REQ-006 | `channels.json` | T-006 |
| REQ-007 | `glossary.json` + dictionary | T-007 |
| REQ-008 | `coverage.json` | T-008 |
| REQ-009 | `models.json` | T-009 |
| REQ-010 | `workflows.json` classes | T-010 |
| REQ-011 | class obligations in validator | T-010, T-012 |
| REQ-012 | `gaps.json`, `golden_cases.json` | T-011 |
| REQ-013 | `venture_pack.py` | T-012 |
| REQ-014 | reuse table in this plan | T-014 |
| REQ-015 | overlay template | T-013 |
| REQ-016 | roadmap above, `specs/README.md` | T-008 |
| REQ-017 | `workflows.json`, `docs/workflows.md` | T-010 |
| REQ-018 | multilingual section of standard; golden cases | T-001, T-011 |
| REQ-019 | `agents/venture_intelligence/` roster | T-008 |
| REQ-020 | `review_status`/`review` fields and `validate_review` | T-016 |
| NFR-001 | validator and golden cases | T-012 |
| NFR-002 | synthetic disclosure per `0025` | T-015 |
| NFR-003 | gates | T-015 |
| NFR-004 | citation check in validator | T-012, T-015 |
| NFR-005 | additive diff | T-015 |
| NFR-006 | licence field in channels | T-006 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected | Why |
| --- | --- | --- | --- |
| Build order | Foundation then children | Build all agents now | Avoids roster-filling-the-map (RISK-006) |
| Regions | Region folders, lead first | One global agent per function | Language, registry, and regulation are regional |
| Multilingual | Cross-cutting agent | Per-language agents | Normalization logic is shared; language notes are data |
| People | Professional roles only | Founder graph | Privacy risk (RISK-002) |

## Validation Strategy

Validator and `tests/test_venture_pack.py` (AC-002..AC-014), manual reads for
narrative ACs, `run-stage.sh spec` and agent-catalog gates (AC-017).

## Rollout, Observability & Rollback

Documentation only. Rollback: delete the listed directories and doc sections.

## Open Questions

See `spec.md` (agency authorities, mission weighting, licensed databases, channel completeness).
