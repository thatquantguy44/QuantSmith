# Plan: Venture Regional Agent — Central Asia

- **Spec:** 0086-venture-regional-agents-central-asia (`spec.md`)
- **Status:** Draft
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-10-02

> HOW. Requires the Draft spec.

## Approach

Same contract-only pattern as `0084`/`0085`, plus two code-level changes the
region needs: Cyrillic in `script_of`/`normalize_name`, and a space-thousands
locale in `localized_number`. The roadmap is rewritten so Asia comes first and
other regions are explicitly deferred.

## Architecture & Components

`agents/venture_intelligence/central_asia/regional_lead`; `venture_ingestion.py` (Cyrillic script, legal-form lists); `venture_pack.py` (`localized_number`); `conventions.json`, `golden_cases.json`, `glossary.json`, `coverage.json`; `tests/test_venture_central_asia.py`; catalog, standard, dictionary, roster.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Cross-script never merged; look-alike regression test |
| P5 Reversibility | yes | Additive plus roadmap reassignment |
| P9 Security & data | yes | No data |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | regional lead | T-001 |
| REQ-002 | Cyrillic script and suffixes | T-002 |
| REQ-003 | locale rule and parser | T-003 |
| REQ-004 | golden cases, glossary, rule | T-004 |
| REQ-005 | coverage and roadmap | T-005 |
| REQ-006 | indexes | T-006 |
| NFR-001 | pure functions | T-002, T-003 |
| NFR-002 | draft/unverified labels | T-004 |
| NFR-003 | gates, full suite | T-007 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected | Why |
| --- | --- | --- | --- |
| Specialist | None | Structure analyst per region | No distinct workflow shown yet |
| Latin legal-form look-alikes (`too`, `ao`) | Not stripped | Strip them | They are ordinary words in other contexts |
| Non-Asian regions | Deferred to `0087` | Build now | Focus is Asia |

## Validation Strategy

`tests/test_venture_central_asia.py`, the pack validator, and the gates and full suite.

## Rollout, Observability & Rollback

Docs, data, and small pure functions. Rollback: delete the region folder and revert the listed edits.

## Open Questions

Registry access; West Asia scope.
