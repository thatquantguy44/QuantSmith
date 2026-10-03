# Plan: Venture Signal Analysts and Sourcing Agents

- **Spec:** 0089-venture-signal-and-sourcing-agents (`spec.md`)
- **Status:** Draft
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-10-02

> HOW. Requires the Draft spec.

## Approach

Contract-only agents generated from one script (shared boundary language), placed
directly under `agents/venture_intelligence/` because they are cross-cutting. One
validator rule is added so a workflow can never be classed more leniently than an
agent it contains.

## Architecture & Components

`agents/venture_intelligence/{patent_ip_analyst,hiring_signal_analyst,narrative_news_analyst,technology_landscape_analyst,deal_sourcing,company_diligence}`; `coverage.json` (built paths, `decision_path_class`); `workflows.json`; `venture_pack.py` (workflow-class check); `tests/test_venture_signals.py`; catalog, standard, group README, dictionary.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Class consistency enforced in the validator |
| P5 Reversibility | yes | Additive |
| P9 Security & data | yes | Organization-level only; no data |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | patent agent | T-001 |
| REQ-002 | hiring agent | T-002 |
| REQ-003 | news agent | T-003 |
| REQ-004 | landscape agent | T-004 |
| REQ-005 | sourcing agent | T-005 |
| REQ-006 | diligence agent | T-006 |
| REQ-007 | coverage classes and validator rule | T-007 |
| REQ-008 | indexes and coverage | T-008 |
| NFR-001 | four files each | T-001..T-006 |
| NFR-002 | review of content | T-009 |
| NFR-003 | gates, full suite | T-009 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected | Why |
| --- | --- | --- | --- |
| Hiring class | `person_adjacent` | `analytic_support` | Workforce data can drift to individuals; stricter by default |
| Ordering in sourcing | Criteria formula, labelled | Merit score | A merit score is an investment judgement |
| Workflow class | At least as strict as agents | Free choice | Prevents lenient labelling of strict workflows |

## Validation Strategy

`tests/test_venture_signals.py`, the pack validator, and gates and full suite.

## Rollout, Observability & Rollback

Docs and data. Rollback: delete the six folders and revert the listed edits.

## Open Questions

Licensed patent, job, and news sources after the bake-off.
