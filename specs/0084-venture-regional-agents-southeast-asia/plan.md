# Plan: Venture Regional Agents — Southeast Asia & Multilingual Document NLP

- **Spec:** 0084-venture-regional-agents-southeast-asia (`spec.md`)
- **Status:** Draft
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-10-02

> HOW. Requires the Draft spec.

## Approach

Contract-only agents following `0082`: four files per agent, shared standard,
catalog row, no runtime. Region folders sit under `agents/venture_intelligence/`;
the regional lead routes, specialists are added only on a coverage row. The four
agent files were generated from one script so boundary language is consistent.

## Architecture & Components

`agents/venture_intelligence/{multilingual_document_nlp, southeast_asia/{regional_lead, entity_structure_analyst, funding_ecosystem_analyst}}`, plus group README, `instructions/venture_intelligence.md`, catalog and dictionary sections.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Source-span and as-of rules |
| P5 Reversibility | yes | Additive |
| P9 Security & data | yes | No data; public sources only |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | multilingual agent | T-001 |
| REQ-002 | three SEA agents | T-002 |
| REQ-003 | class in README/instructions | T-001, T-002 |
| REQ-004 | group README roster | T-003 |
| REQ-005 | `agents/README.md` section | T-004 |
| REQ-006 | standard, dictionary | T-005 |
| NFR-001 | gates | T-006 |
| NFR-002 | review | T-006 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected | Why |
| --- | --- | --- | --- |
| Per-market agents | One regional lead plus 2 specialists | One agent per country | Markets differ in data, not in workflow; the lead splits by market |
| Language handling | One cross-cutting agent | Mandarin-only agent | Same normalization logic across languages |

## Validation Strategy

`agent-catalog-check.sh`, `run-stage.sh spec`, manual reads for contract content.

## Rollout, Observability & Rollback

Docs only. Rollback: delete `agents/venture_intelligence/`, the standard, and catalog/dictionary sections.

## Open Questions

Registry access; additional languages.
