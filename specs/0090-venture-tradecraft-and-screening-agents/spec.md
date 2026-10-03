# Spec: Venture Tradecraft and Screening-Support Agents

- **ID:** 0090-venture-tradecraft-and-screening-agents
- **Status:** Draft
- **Author:** Joshua Lutkemuller, CFA
- **Approver:**
- **Last updated:** 2026-10-02

> WHAT and WHY only. Child of `0083-venture-intelligence-foundation`; builds on `0088` (origins, entity resolution) and the `0084`/`0085`/`0086` structure agents.

## Problem & Context

The signal analysts and the diligence agent produce findings; nothing yet checks
how the findings were graded, worded, challenged, or what is still missing, and
the foreign-influence mission needs ownership and dual-use *indicators* without
sliding into verdicts. `0083` defined the conventions (two-axis grades, likelihood
bands, evidence/assumption/judgement, `sovereign_adjacent` class); this spec makes
them operational as agents plus a small set of deterministic helpers so the
arithmetic and the guardrails are testable.

## Goals

- Agents for source/information grading, calibrated wording, competing-hypotheses analysis, and lawful collection-gap tracking.
- Screening-support agents for ownership/foreign-capital indicators and dual-use indicators, both `sovereign_adjacent` and decision-support-only.
- Deterministic helpers: grade parsing, origin-aware corroboration counting, likelihood-word checks, a competing-hypotheses matrix, effective ownership through chains, a conclusion-language lint, and a prohibited-source check.

## Non-Goals

- No agent grades a source *for* the analyst, chooses a conclusion, classifies a technology, or designates an entity.
- No export-control, sanctions, or foreign-investment rule is encoded; control lists and thresholds are caller-supplied and counsel-owned.
- No runtime, adapters, collection tooling, or real data.
- No fund analytics (`0091`) and no product writers (`0092`).

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | Add `source_reliability_grader`: proposes separate reliability and credibility grades each with a stated basis, uses `F`/`6` when no basis exists, counts independent origins, and never overrides a human grade. | must |
| REQ-002 | Add `confidence_language_reviewer`: checks likelihood words against the probability bands, keeps likelihood separate from evidence confidence, flags vague hedging, and never changes a judgement. | must |
| REQ-003 | Add `competing_hypotheses_analyst`: builds a matrix that always includes a deception-or-artifact hypothesis, separates diagnostic from non-diagnostic evidence, counts a shared origin once, reports sensitivity, and never selects the conclusion. | must |
| REQ-004 | Add `collection_gap_tracker`: records information requirements linked to a decision with lawful candidate channels, refuses prohibited source classes, and never tasks collection. | must |
| REQ-005 | Add `ownership_screen` (`sovereign_adjacent`): computes effective ownership over equity chains with every path shown, excludes contractual links from the product, presents list matches as indicators, uses caller-supplied thresholds, and never designates or accuses. | must |
| REQ-006 | Add `dual_use_indicator` (`sovereign_adjacent`): matches descriptions against caller-supplied control lists with a stated version, turns each resemblance into a question for counsel, and never classifies or rules on licensing. | must |
| REQ-007 | Provide deterministic helpers in `venture_tradecraft.py` for grade parsing, corroboration status, likelihood-band checking, vague-term finding, the hypotheses matrix and sensitivity, effective ownership and threshold comparison, conclusion-language findings, prohibited-channel checking, requirement aging, and orphan-requirement detection. | must |
| REQ-008 | Mark the six agents built in the coverage matrix, update workflows, the standard, the catalog, the group README, and the dictionary, keeping validator rules (including the workflow-class rule) passing. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Determinism | Helpers are pure and standard-library only; identical inputs give identical outputs. |
| NFR-002 | Honesty | The lint and matrix state that they report structure, not conclusions; no real entity or control-list content appears. |
| NFR-003 | Gates | `spec`, `agent-catalog`, `handoff-sync`, `doc-counts` pass and no existing test regresses. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given the grader contract and `parse_grade`, when a grade like `B2` or an invalid grade is parsed, then the first returns both axes and the second raises; and the contract states the `F6` rule and the human-override boundary. | REQ-001, REQ-007 |
| AC-002 | Given items sharing an origin, items from several origins in one channel, and items across channels, when counted, then statuses are echo, single_channel, and corroborated respectively, and a lone item is single_source. | REQ-001, REQ-007 |
| AC-003 | Given a probability and a stated word, when checked, then a matching band passes and a mismatch is flagged with the expected word; and vague terms are found with offsets. | REQ-002, REQ-007 |
| AC-004 | Given hypotheses lacking a deception-or-artifact hypothesis, when a matrix is built, then it raises; and given valid input it returns inconsistency counts, ordering, diagnostic and non-diagnostic evidence, and a note that it is not a conclusion. | REQ-003, REQ-007 |
| AC-005 | Given two evidence items sharing one origin, when the matrix is built, then the origin counts once, and sensitivity lists evidence whose removal changes the ordering. | REQ-003, REQ-007 |
| AC-006 | Given a requirement proposing a prohibited source class, when checked, then it raises; given a lawful class, it passes; and requirements with no decision are reported as orphans and aged by days. | REQ-004, REQ-007 |
| AC-007 | Given a two-path equity structure plus a contractual link, when effective ownership is computed, then the paths and product are exact, the contractual link is excluded, cycles are not followed, and a missing as-of date raises. | REQ-005, REQ-007 |
| AC-008 | Given an effective ownership and a caller threshold, when compared, then the result labels the threshold as the caller's. | REQ-005, REQ-007 |
| AC-009 | Given screening text with conclusion wording such as "evading" or "unlawful", when linted, then the terms are found with offsets and indicator wording passes. | REQ-005, REQ-007, NFR-002 |
| AC-010 | Given `dual_use_indicator`, when read, then it uses caller-supplied lists with versions, produces questions for counsel, and bars classification. | REQ-006 |
| AC-011 | Given the coverage matrix, workflows, standard, catalog, and group README, when read, then the six agents are built and listed with four files each, and the validator reports zero errors. | REQ-008 |
| AC-012 | Given repeated runs, when compared, then helper outputs are identical. | NFR-001 |
| AC-013 | Given the repository, when gates and the full suite run, then no gate has findings and no previously passing test fails. | NFR-003 |

## Data & Dependencies

Depends on `0083` conventions (grades, bands, prohibited source classes), `0088`
(origin concept, `entity_resolution`), `0084`/`0085` structure agents, `0089`
analysts. Inputs are caller-supplied.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A proposed grade is accepted unexamined. | Unfounded confidence. | Every grade states a basis; `F6` default; human owns the grade. |
| RISK-002 | The ACH ordering is read as the answer. | Conclusion by matrix. | Result note; never-boundary; sensitivity reported. |
| RISK-003 | Effective ownership treated as legal control. | Wrong control picture. | Contractual links excluded; thresholds the caller's; counsel questions. |
| RISK-004 | A list match read as a finding. | Wrongful accusation. | Indicator wording lint; false-positive notes; snapshot date. |
| RISK-005 | The tracker proposes unlawful collection. | Legal exposure. | Prohibited-class check refuses; nothing tasked. |
| RISK-006 | Dual-use indicator read as a classification. | Wrong compliance decision. | Questions for counsel only; control lists caller-supplied and versioned. |

## Assumptions & Open Questions

- Assumption: deterministic helpers are worth shipping because they pin the arithmetic and guardrails before any model drafts text.
- Open question: which control lists and ownership thresholds counsel will supply for the proof of concept.

## Exceptions

None.
