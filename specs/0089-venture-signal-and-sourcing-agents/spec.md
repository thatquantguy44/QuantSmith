# Spec: Venture Signal Analysts and Sourcing Agents

- **ID:** 0089-venture-signal-and-sourcing-agents
- **Status:** Draft
- **Author:** Joshua Lutkemuller, CFA
- **Approver:**
- **Last updated:** 2026-10-02

> WHAT and WHY only. Child of `0083-venture-intelligence-foundation`; depends on `0088` (sources, point-in-time, entity resolution).

## Problem & Context

The regional agents describe markets, but technology scouting needs agents that
read the non-traditional channels themselves — patents, hiring, news — and turn
them into a landscape, a longlist, and a diligence memo. Each channel has its
own bias and deception risk (`channels.json`): patent filings are not inventions,
postings are not hires, repeated news is not corroboration. Without agents that
carry those rules, a fluent analysis will overstate single-channel signals and
quietly profile people.

## Goals

- Three signal analysts (patent and IP, hiring, narrative and news) that apply their channel's point-in-time and bias rules.
- A technology-landscape analyst that combines channels with an explicit corroboration status.
- A deal-sourcing agent (stated-criteria longlists) and a company-diligence agent (evidence, assumption, judgement memos).
- Keep the hiring agent `person_adjacent` and make workflow classes consistent with the agents they contain.

## Non-Goals

- No runtime, adapters, trained models, or real data.
- No ranking by merit, investment recommendation, or approval of any company.
- No individual-level analysis, and no attribution of influence campaigns.
- No new source entries (a patent-office adapter set follows the bake-off).
- No tradecraft agents (`0090`) or fund analytics (`0091`).

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | Add `patent_ip_analyst` that counts patent families, dates signals by publication, resolves assignees via `entity_resolution`, and never assesses legal validity or value. | must |
| REQ-002 | Add `hiring_signal_analyst` (`person_adjacent`) that works at organization level only, deduplicates postings, and never profiles individuals or infers sensitive attributes. | must |
| REQ-003 | Add `narrative_news_analyst` that collapses syndication, separates events from sentiment, grades sources, and reports amplification as indicators without attribution. | must |
| REQ-004 | Add `technology_landscape_analyst` that reports corroboration across independent channels, labels single-channel findings, and quotes readiness only as sources state it. | must |
| REQ-005 | Add `deal_sourcing` that screens against caller-stated criteria, shows its formula, labels order as non-merit, and lists what discovery could not see. | must |
| REQ-006 | Add `company_diligence` that produces an evidence, assumptions, judgement, and open-gaps memo from supplied evidence, with a claim-versus-evidence table. | must |
| REQ-007 | Record each agent's decision-path class in the coverage matrix and require a workflow's class to be at least as strict as its agents'. | must |
| REQ-008 | Mark the six agents built in the coverage matrix, update the workflows, catalog, standard, group README, and dictionary. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Contract completeness | Each agent has four contract files and a stated never-boundary. |
| NFR-002 | Honesty | No real entity or data; channel claims keep their `unverified` status. |
| NFR-003 | Gates | `agent-catalog`, `spec`, `handoff-sync`, `doc-counts` pass and no test regresses. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given `patent_ip_analyst`, when read, then it counts families, uses publication date as `known_at`, and states the legal-validity boundary. | REQ-001 |
| AC-002 | Given `hiring_signal_analyst`, when read, then it is `person_adjacent`, organization-level only, and bars individual profiling. | REQ-002 |
| AC-003 | Given `narrative_news_analyst`, when read, then it collapses syndication, treats amplification as indicators, and bars attribution. | REQ-003 |
| AC-004 | Given `technology_landscape_analyst`, when read, then it labels single-channel findings and bars assigning readiness itself. | REQ-004 |
| AC-005 | Given `deal_sourcing`, when read, then it uses caller-stated criteria, shows the formula, and bars merit ranking. | REQ-005 |
| AC-006 | Given `company_diligence`, when read, then it requires the four memo sections and a claim-versus-evidence table and bars approval. | REQ-006 |
| AC-007 | Given a workflow containing a `person_adjacent` agent but classed `analytic_support`, when validated, then the validator rejects it; and given the correct class, it passes. | REQ-007 |
| AC-008 | Given the coverage matrix, standard, catalog, and group README, when read, then the six agents are built and listed, and each has four files. | REQ-008, NFR-001 |
| AC-009 | Given the repository, when gates and the full suite run, then no gate has findings and no previously passing test fails. | NFR-003 |
| AC-010 | Given the new files, when scanned, then no real entity or credential appears. | NFR-002 |

## Data & Dependencies

Depends on `0083`, `0088` (sources, `known_at`, `entity_resolution`), `0084`/`0085`/`0086` regional leads, `0071`. Inputs are caller-supplied.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | Single-channel signals presented as established. | Overconfident thesis. | Corroboration status and single-channel label. |
| RISK-002 | Hiring analysis drifts to individuals. | Privacy harm. | `person_adjacent` class; organization-level rule; never-boundary. |
| RISK-003 | Longlist order read as recommendation. | Implied endorsement. | Order labelled as criteria-only; no merit language. |
| RISK-004 | Diligence memo reads unverified claims as fact. | Wrong decisions. | Claim-versus-evidence table; evidence/assumption/judgement split. |
| RISK-005 | News amplification indicator read as attribution. | Wrongful accusation. | Indicators only; never-attribute rule. |

## Assumptions & Open Questions

- Assumption: contract-only agents are useful before adapters exist, as in `0082`/`0084`.
- Open question: which patent offices and job or news panels the adopter can license.

## Exceptions

None.
