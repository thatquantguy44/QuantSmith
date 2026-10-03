# Spec: Venture Regional Agents — Greater China & East Asia, South Asia

- **ID:** 0085-venture-regional-agents-east-and-south-asia
- **Status:** Draft
- **Author:** Joshua Lutkemuller, CFA
- **Approver:**
- **Last updated:** 2026-10-02

> WHAT and WHY only. Child of `0083-venture-intelligence-foundation`; second regional wave after `0084`.

## Problem & Context

Greater China and East Asia carry most of the Mandarin, Japanese and Korean
start-up documentation the multilingual agent must handle, and the offshore-onshore
structures common there (offshore holding companies above onshore operating
entities, sometimes with contractual rather than equity control) matter directly
to the foreign-influence screening mission. South Asia adds lakh and crore
units, April-to-March fiscal years, and frequent domicile-versus-market
differences. Treating either as one market, or reading a contractual-control
link as ownership, would produce confident but wrong analysis.

## Goals

- Regional leads for Greater China and East Asia, and for South Asia, following the `0084` pattern.
- One specialist, the Greater China entity-structure analyst, justified by a distinct workflow: equity versus contractual-control mapping from filings.
- Extend the shared normalization conventions to Traditional Chinese, Japanese, Korean, and South Asian units and eras, with golden cases.

## Non-Goals

- No runtime, adapters, or real data.
- No South Asia specialist yet: no coverage row shows a workflow the lead plus shared agents cannot hold.
- No legal rulings on investment restrictions, outbound investment, or data security: those are counsel's, framed as questions.
- No inference of government or party control from names or ownership percentages.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | Add `greater_china_east_asia/regional_lead` with four contract files and a never-boundary, treating Mainland China, Hong Kong, Taiwan, Japan, and Korea as separate markets. | must |
| REQ-002 | Add `greater_china_east_asia/entity_structure_analyst` (`sovereign_adjacent`, decision_support_only) that shows equity and contractual links separately with original-language source spans. | must |
| REQ-003 | Add `south_asia/regional_lead` covering India, Bangladesh, Pakistan, and Sri Lanka with lakh/crore and fiscal-year normalization. | must |
| REQ-004 | Extend `conventions.json` with Traditional Chinese (萬, 億), Korean (만, 억, 조), lakh and crore units, Japanese era offsets (Reiwa, Heisei, Showa), a fiscal year-end convention list, and an ambiguity rule for 兆. | must |
| REQ-005 | Extend the validator and golden cases so each new rule is recomputed, and unknown or ambiguous units raise rather than guess. | must |
| REQ-006 | Update the multilingual agent, standard, dictionary, coverage matrix, catalog, and regional roster to include the new agents and rules. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Determinism | Normalization functions are pure and stdlib-only. |
| NFR-002 | Honesty | New conventions cite a source or are marked `unverified`; no real entity or filing appears. |
| NFR-003 | Gates | `agent-catalog`, `spec`, `handoff-sync`, `doc-counts` pass. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given `greater_china_east_asia/regional_lead`, when read, then it has four files, treats the five markets separately, and distinguishes onshore and offshore renminbi. | REQ-001 |
| AC-002 | Given the entity-structure analyst, when read, then it is `sovereign_adjacent`, separates equity from contractual links, requires source spans, and never concludes control by a government or party. | REQ-002 |
| AC-003 | Given `south_asia/regional_lead`, when read, then it normalizes lakh and crore and states fiscal year-ends. | REQ-003 |
| AC-004 | Given `conventions.json`, when validated, then the new units, eras, fiscal-year conventions, and the 兆 ambiguity rule are present, cited or `unverified`, and `draft`. | REQ-004 |
| AC-005 | Given figures such as 2.5億, 350억, 1.2조, 5.2 lakh, and Reiwa 6, when parsed, then values match the golden cases, and given 兆 or an unknown unit, then parsing raises. | REQ-005, NFR-001 |
| AC-006 | Given the catalog, standard, dictionary, and coverage matrix, when read, then the three agents and new terms appear and the validator reports zero errors. | REQ-006 |
| AC-007 | Given the repository, when gates run, then they pass. | NFR-003 |
| AC-008 | Given the new conventions, when scanned, then each carries a citation or `unverified` and no real entity appears. | NFR-002 |

## Data & Dependencies

Depends on `0083`, `0084`, `0088` (`entity_resolution`), `0071`. Inputs are caller-supplied.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A contractual-control link is read as ownership. | Wrong control picture. | Equity and contract shown separately; mechanism field. |
| RISK-002 | A structure map is read as an accusation. | Wrongful action. | Indicators only; never-attribute rule; counsel questions. |
| RISK-003 | Era, unit, or fiscal-year assumption wrong for a document. | Mis-scaled or mis-dated figure. | Stated rules, ambiguity raises, per-document flag. |
| RISK-004 | Native-language registry access is restricted or unreliable. | Gaps. | Coverage stated; sources assessed by the adopter before use. |

## Assumptions & Open Questions

- Open question: which Greater China and East Asia registries and exchange filings the adopter may lawfully use.
- Open question: whether a South Asia specialist is justified once real work is routed through the lead.

## Exceptions

None.
