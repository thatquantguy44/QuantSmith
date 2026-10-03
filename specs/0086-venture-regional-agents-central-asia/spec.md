# Spec: Venture Regional Agent — Central Asia

- **ID:** 0086-venture-regional-agents-central-asia
- **Status:** Draft
- **Author:** Joshua Lutkemuller, CFA
- **Approver:**
- **Last updated:** 2026-10-02

> WHAT and WHY only. Child of `0083-venture-intelligence-foundation`; third regional wave. Scope narrowed to Asia: Caucasus, Middle East and North Africa, Europe, and the other non-Asian regions are deferred to `0087`.

## Problem & Context

Central Asia's start-up evidence arrives in Russian, Kazakh, Uzbek, Kyrgyz, and
Tajik, in Cyrillic or Latin script, often with Chinese and English in
cross-border documents. The same company can appear under a Cyrillic and a Latin
name, numbers use a space thousands separator and a decimal comma, and
holding-company domicile frequently differs from where the business operates.
The existing regional agents do not cover these script and format problems, and
the entity-resolution and number-parsing code did not know Cyrillic.

## Goals

- A Central Asia regional lead following the `0084`/`0085` pattern.
- Script-aware entity resolution and Russian-locale number handling, with golden cases.
- Reclassify the roadmap so Asia is built first and non-Asian regions are explicitly deferred.

## Non-Goals

- No Central Asia specialist: no coverage row shows a workflow the lead plus shared agents cannot hold.
- No Caucasus, MENA, Europe, or other regions (deferred to `0087`).
- No legal rulings on investment, sanctions, or export-control status; those are counsel's, framed as questions.
- No runtime, adapters, or real data.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | Add `central_asia/regional_lead` with four contract files and a never-boundary, treating Kazakhstan, Uzbekistan, Kyrgyzstan, and Tajikistan as separate markets with Turkmenistan noted as very thin. | must |
| REQ-002 | Recognize Cyrillic as a script in entity resolution so Cyrillic and Latin forms of a name yield `candidate_cross_script`, and strip Russian-language and Uzbek legal-form markers (ООО, ТОО, АО, MChJ) for comparison only. | must |
| REQ-003 | Parse Russian-locale numbers (space or non-breaking-space thousands separator, decimal comma) and record the locale rule in `conventions.json`. | must |
| REQ-004 | Add golden cases, a `Script Variant` glossary term, and a script-variant rule to the conventions. | must |
| REQ-005 | Update the coverage matrix and roadmap so `0086` closes Central Asia only and the deferred regions, including a new Caucasus row, move to `0087`; update the regional roster to match. | must |
| REQ-006 | Update the catalog, standard, and dictionary for the new agent and term. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Determinism | Normalization and parsing remain pure, stdlib-only functions. |
| NFR-002 | Honesty | New conventions are `unverified` and `draft`; no real entity or filing appears. |
| NFR-003 | Gates | `agent-catalog`, `spec`, `handoff-sync`, `doc-counts` pass; no existing test regresses. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given `central_asia/regional_lead`, when read, then it has four files, names the four markets and Turkmenistan as thin, and states the never-boundary. | REQ-001 |
| AC-002 | Given a Cyrillic and a Latin name for one company, when resolved without a registry ID, then the decision is `candidate_cross_script`; and given Cyrillic legal-form markers, when normalized, then they are removed for comparison only. | REQ-002 |
| AC-003 | Given "1 250 000,5" with locale `ru` and a non-breaking-space variant, when parsed, then the values are 1250000.5 and 2000000. | REQ-003 |
| AC-004 | Given the pack, when validated, then the golden cases, glossary term, and script-variant rule exist and the validator reports zero errors. | REQ-004 |
| AC-005 | Given `coverage.json`, when read, then `central_asia_lead` is built under `0086`, `caucasus_lead` is planned under `0087`, and every agent is closed by exactly one spec. | REQ-005 |
| AC-006 | Given the catalog, standard, and dictionary, when read, then each mentions the agent and the new term. | REQ-006 |
| AC-007 | Given the repository, when gates and the full suite run, then no gate has findings and no previously passing test fails. | NFR-003 |
| AC-008 | Given a Latin phrase such as "Too Good Company", when normalized, then it is not stripped as a legal form. | NFR-001, NFR-002 |

## Data & Dependencies

Depends on `0083`, `0084`, `0085`, `0088` (entity resolution). Inputs are caller-supplied.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | Transliteration differences cause missed or false joins. | Wrong company identity. | Cross-script is never merged without a registry ID. |
| RISK-002 | A legal-form marker is stripped from an ordinary word. | False equality. | Only Cyrillic and unambiguous markers are stripped; a regression test covers Latin look-alikes. |
| RISK-003 | Sanctions or export-control status is read from a structure map. | Wrongful conclusion. | Never-boundary; questions for counsel. |

## Assumptions & Open Questions

- Open question: which Central Asian registers and exchange or financial-centre filings the adopter may use.
- Open question: whether West Asia (Gulf, Israel, Turkey) is in the Asia focus; currently deferred with MENA.

## Exceptions

None.
