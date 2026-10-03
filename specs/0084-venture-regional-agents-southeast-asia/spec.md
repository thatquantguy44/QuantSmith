# Spec: Venture Regional Agents — Southeast Asia & Multilingual Document NLP

- **ID:** 0084-venture-regional-agents-southeast-asia
- **Status:** Draft
- **Author:** Joshua Lutkemuller, CFA
- **Approver:**
- **Last updated:** 2026-10-02

> WHAT and WHY only. Child of `0083-venture-intelligence-foundation`.

## Problem & Context

Start-up evidence in Southeast Asia arrives in Mandarin, Bahasa, Vietnamese, Thai,
Filipino and English, under different registries, accounting bases, and
holding-company structures. A single "Asia" or "SEA" view hides market
differences and domicile effects; fluent machine translation hides provenance.
This spec creates the first regional agent group and the cross-cutting
multilingual document agent that every later region reuses.

## Goals

- A cross-cutting multilingual document agent, Mandarin included.
- A Southeast Asia group: regional lead plus entity-structure and funding-ecosystem specialists.
- The regional pattern (lead first, specialists by coverage row) the other regions copy.

## Non-Goals

- No runtime, model training, or data adapters (`0088`, `0091`).
- No legal translation, legal rulings, investment recommendations, or attribution.
- No other regions (`0085`–`0087`); no real data.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | Add `agents/venture_intelligence/multilingual_document_nlp/` with the four contract files, source-span preservation, derived-evidence labelling, and normalization rules. | must |
| REQ-002 | Add `southeast_asia/regional_lead`, `entity_structure_analyst`, `funding_ecosystem_analyst`, each with four contract files and a stated never-boundary. | must |
| REQ-003 | Each agent declares its decision-path class; `entity_structure_analyst` is `sovereign_adjacent` and decision_support_only. | must |
| REQ-004 | Add `agents/venture_intelligence/README.md` with the regional roster reserving all other regions. | must |
| REQ-005 | Register all four agents in `agents/README.md`. | must |
| REQ-006 | Add `instructions/venture_intelligence.md` and a dictionary section. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Catalog consistency | `agent-catalog-check.sh` and `run-stage.sh spec` pass |
| NFR-002 | No data | No real entity, person, filing, or credential in any file |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given the multilingual agent, when read, then it requires original-language spans, labels translations as derived evidence, and names normalization rules for 万/亿, Buddhist-era years, and legal-entity suffixes. | REQ-001 |
| AC-002 | Given `southeast_asia/`, when listed, then three agents each have four files and a never-boundary. | REQ-002 |
| AC-003 | Given each README, when read, then a decision-path class is stated and the entity agent is `sovereign_adjacent`. | REQ-003 |
| AC-004 | Given the group README, when read, then every other region is either built or reserved with scope and spec number. | REQ-004 |
| AC-005 | Given `agents/README.md`, when read, then the four agents are listed. | REQ-005 |
| AC-006 | Given the standard and dictionary, when read, then both exist and agree. | REQ-006 |
| AC-007 | Given the repo, when gates run, then they pass. | NFR-001, NFR-002 |

## Data & Dependencies

Depends on `0083`, `0071` (evidence boundary), `0070`. Inputs are caller-supplied.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | Machine translation errors read as facts | False evidence | Span preservation, derived-evidence label, bilingual reviewer |
| RISK-002 | Structure mapping read as an accusation | Wrongful action | Indicators only, never-designate rule |
| RISK-003 | Jurisdiction rules asserted from memory | Wrong guidance | Rules framed as `unverified` questions for counsel |

## Assumptions & Open Questions

- Open question: which Southeast Asian registries the adopter can lawfully and practically access.
- Open question: which languages beyond the six named are needed first (e.g. Khmer, Burmese).

## Exceptions

None.
