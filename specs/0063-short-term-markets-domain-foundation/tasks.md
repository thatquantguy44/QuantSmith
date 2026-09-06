# Tasks: Short-Term Markets Domain Foundation

- **Spec:** 0063-short-term-markets-domain-foundation (`spec.md`, `plan.md`)
- **Last updated:** 2026-09-05

## Definition of Done (applies to every task)

- Work matches the approved spec and plan; deviations are recorded before code
  or content changes.
- Every machine-readable artifact validates offline and every acceptance
  criterion has deterministic evidence.
- Units, economic viewpoint, jurisdiction, knowledge/as-of time, effective time,
  source support, and review status are explicit wherever applicable.
- No unsupported statement is promoted to `reviewed`; no automation
  self-certifies domain expertise.
- No proprietary data, licensed agreement text, secrets, PII, MNPI, or internal
  counterparty terms are committed.
- Existing runtime behavior is unchanged by `0063`; behavioral corrections stay
  with `0064`–`0067`.
- Documentation and indexes are updated in the same change, and repository gates
  report reality.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Create the `0063` spec chain, index it, add handoff item 21, reserve `0064`–`0069` with dependencies/activation rules, remove stale planned rows, and set `0070` as next unreserved. | REQ-001, REQ-010, REQ-011 | done | Planning/roadmap work only; implementation remains gated on spec approval. |
| T-002 | Create `knowledge/short_term_markets/README.md` and the common JSON record/review contract; state U.S.-first scope, navigation, citation use, review/promotion rules, and explicit exclusions. | REQ-001, REQ-011, REQ-013, NFR-004, NFR-005 | todo | Do not claim the pack is expert-reviewed until T-010. |
| T-003 | Author `taxonomy.json`: products, processes, roles, transaction sides, aliases, relations, and ambiguity rules; include all required term distinctions and economic viewpoints. | REQ-002, REQ-003 | todo | Stable IDs become child-spec interfaces once approved. |
| T-004 | Author `conventions.json`: rates/yields/prices, units, signs, day counts, compounding/discount bases, calendars, settlement, rounding, haircuts, margin, and formulas. | REQ-003, REQ-004 | todo | No unsourced universal thresholds or implicit defaults. |
| T-005 | Author `lifecycles.json` for repo, securities lending, cash products, and collateral, including normal, periodic, partial, substitution, fail/default, and termination paths. | REQ-005 | todo | Legal enforceability remains outside the artifact. |
| T-006 | Write `source_policy.md`, register the first authoritative public sources through `sources/`, and implement evidence, conflict, access/license, knowledge-time, effective-time, freshness, and supersession rules. | REQ-006, REQ-007, REQ-013, NFR-002, NFR-003, NFR-006 | todo | Reuse `0027`; do not create a competing source catalog. |
| T-007 | Author `coverage.json` and `gap_register.md`; crosswalk every relevant current agent/instruction/runtime/source/test and dispose all six mandatory discrepancies to `0063` or a named child spec. | REQ-001, REQ-008, REQ-012, NFR-005 | todo | Finding a problem is not evidence that it was fixed. |
| T-008 | Author `golden_cases.json`, implement the standard-library validator, and add deterministic tests for structure, references, time, lifecycles, signs, conversions, thresholds, review gates, and repeatability. | REQ-002, REQ-003, REQ-004, REQ-005, REQ-006, REQ-007, REQ-009, REQ-013, NFR-001, NFR-002, NFR-003 | todo | Allow-listed operations only; no hidden general-purpose pricer. |
| T-009 | Add `instructions/short_term_markets.md`; update securities-financing and fixed-income agent documentation to retrieve/cite the canonical pack and correct or explicitly defer inconsistent local prose. | REQ-011, REQ-012 | todo | Existing agent roles remain narrow; no new agent in this spec. |
| T-010 | Complete two-part human review: practitioner review of viewpoints/conventions/lifecycles and data/quant review of temporal/numerical cases; record reviewer handles, scope, dates, conflicts, and dispositions. | REQ-006, REQ-013, NFR-003, NFR-004 | todo | Structural automation cannot satisfy this task. |
| T-011 | Run domain tests, full pytest, required repository gates, source/license/secret checks, and `git diff --check`; record exact evidence without changing an existing runtime result. | NFR-001, NFR-006 | todo | Covers AC-015 and confirms AC-013 by diff inspection. |
| T-012 | Resolve open questions, approve/freeze the foundation interfaces, update coverage states honestly, and select only the first ready child spec for activation. | REQ-010, REQ-013 | todo | Do not draft `0064`–`0069` en masse. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_required_capability_domains_AC_001` in `tests/test_short_term_markets_knowledge.py` | todo |
| AC-002 | `test_taxonomy_ids_aliases_and_distinctions_AC_002` | todo |
| AC-003 | `test_repo_specialness_viewpoint_and_sign_AC_003` | todo |
| AC-004 | `test_convention_records_are_complete_and_compatible_AC_004` | todo |
| AC-005 | `test_lifecycle_graphs_and_invalid_transition_AC_005` | todo |
| AC-006 | `test_reviewed_records_require_resolvable_evidence_AC_006` | todo |
| AC-007 | `test_later_known_version_excluded_from_earlier_asof_AC_007` | todo |
| AC-008 | `test_required_discrepancies_have_evidence_and_owners_AC_008` | todo |
| AC-009 | `test_golden_cases_are_complete_and_repeatable_AC_009` | todo |
| AC-010 | `test_classification_thresholds_are_sourced_or_parameterized_AC_010` | todo |
| AC-011 | `test_handoff_reserves_child_specs_and_next_number_AC_011` | todo |
| AC-012 | `test_relevant_agents_reference_canonical_foundation_AC_012` | todo |
| AC-013 | Release-review diff inspection: no existing pricing/allocation runtime behavior changed | todo |
| AC-014 | `test_review_promotion_rejects_missing_reviewer_or_high_gap_AC_014` | todo |
| AC-015 | Domain test + `spec`, `docs-link`, `spec-index`, `doc-counts`, `handoff-sync`, `source-catalog`, `data-provenance`, `secret-scan`; full `pytest -q`; `git diff --check` | todo |

## Follow-ups

These are reserved in `docs/handoff.md`, not active specs. Create one only after
T-012 confirms its foundation dependency and first consumer.

- `0064` — repo economics and lifecycle runtime.
- `0065` — cash products and pricing conventions.
- `0066` — securities-lending model correction and expansion.
- `0067` — collateral, margin, and allocation optimization.
- `0068` — short-term-markets source ingestion and data contracts.
- `0069` — regulatory, legal, and market-structure knowledge pack.

Later extensions may add other jurisdictions, a broader secured/unsecured
funding universe, derivatives collateral, or a distinct specialist agent only
after a concrete consumer and coverage evidence justify them.
