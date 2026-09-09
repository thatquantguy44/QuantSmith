# Tasks: Short-Term Markets Domain Foundation

- **Spec:** 0063-short-term-markets-domain-foundation (`spec.md`, `plan.md`)
- **Last updated:** 2026-09-06

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
| T-002 | Create `knowledge/short_term_markets/README.md` and the common JSON record/review contract; state U.S.-first scope, navigation, citation use, review/promotion rules, and explicit exclusions. | REQ-001, REQ-011, REQ-013, NFR-004, NFR-005 | done | Added README and shared record envelope; all initial records remain `draft`. |
| T-003 | Author `taxonomy.json`: products, processes, roles, transaction sides, aliases, relations, and ambiguity rules; include all required term distinctions and economic viewpoints. | REQ-002, REQ-003 | done | Stable IDs, aliases, viewpoints, relations, and non-interchangeable pairs validate offline. |
| T-004 | Author `conventions.json`: rates/yields/prices, units, signs, day counts, compounding/discount bases, calendars, settlement, rounding, haircuts, margin, and formulas. | REQ-003, REQ-004 | done | Includes sourced/draft conventions and parameterized assumptions for existing threshold constants. |
| T-005 | Author `lifecycles.json` for repo, securities lending, cash products, and collateral, including normal, periodic, partial, substitution, fail/default, and termination paths. | REQ-005 | done | Four lifecycle graphs validate for reachability, terminal states, declared roles, and transition admission. |
| T-006 | Write `source_policy.md`, register the first authoritative public sources through `sources/`, and implement evidence, conflict, access/license, knowledge-time, effective-time, freshness, and supersession rules. | REQ-006, REQ-007, REQ-013, NFR-002, NFR-003, NFR-006 | done | Reuses the `0027` source catalog; new public metadata registrations are locator-only and live ingestion remains `0068`. |
| T-007 | Author `coverage.json` and `gap_register.md`; crosswalk every relevant current agent/instruction/runtime/source/test and dispose all six mandatory discrepancies to `0063` or a named child spec. | REQ-001, REQ-008, REQ-012, NFR-005 | done | All six required discrepancies carry evidence paths, severity, disposition, and owner specs; no runtime correction is claimed. |
| T-008 | Author `golden_cases.json`, implement the standard-library validator, and add deterministic tests for structure, references, time, lifecycles, signs, conversions, thresholds, review gates, and repeatability. | REQ-002, REQ-003, REQ-004, REQ-005, REQ-006, REQ-007, REQ-009, REQ-013, NFR-001, NFR-002, NFR-003 | done | `short_term_markets_knowledge.py` exposes allow-listed validation helpers only, not a pricing/trading runtime. |
| T-009 | Add `instructions/short_term_markets.md`; update securities-financing and fixed-income agent documentation to retrieve/cite the canonical pack and correct or explicitly defer inconsistent local prose. | REQ-011, REQ-012 | done | Existing agent roles remain narrow and point to the canonical foundation. No new agent was added. |
| T-010 | Complete two-part human review: practitioner review of viewpoints/conventions/lifecycles and data/quant review of temporal/numerical cases; record reviewer handles, scope, dates, conflicts, and dispositions. | REQ-006, REQ-013, NFR-003, NFR-004 | blocked | Requires named human practitioner/data reviewers. Structural automation cannot satisfy this task, so records remain `draft`. |
| T-011 | Run domain tests, full pytest, required repository gates, source/license/secret checks, and `git diff --check`; record exact evidence without changing an existing runtime result. | NFR-001, NFR-006 | done | Evidence recorded below. Restricted sandbox blocks localhost socket tests; unsandboxed full pytest passed. |
| T-012 | Resolve open questions, approve/freeze the foundation interfaces, update coverage states honestly, and select only the first ready child spec for activation. | REQ-010, REQ-013 | blocked | Draft open decisions remain unresolved; no `0064`-`0069` spec was drafted or activated. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_required_capability_domains_AC_001` in `tests/test_short_term_markets_knowledge.py` | done |
| AC-002 | `test_taxonomy_ids_aliases_and_distinctions_AC_002` | done |
| AC-003 | `test_repo_specialness_viewpoint_and_sign_AC_003` | done |
| AC-004 | `test_convention_records_are_complete_and_compatible_AC_004` | done |
| AC-005 | `test_lifecycle_graphs_and_invalid_transition_AC_005` | done |
| AC-006 | `test_reviewed_records_require_resolvable_evidence_AC_006` | done |
| AC-007 | `test_later_known_version_excluded_from_earlier_asof_AC_007` | done |
| AC-008 | `test_required_discrepancies_have_evidence_and_owners_AC_008` | done |
| AC-009 | `test_golden_cases_are_complete_and_repeatable_AC_009` | done |
| AC-010 | `test_classification_thresholds_are_sourced_or_parameterized_AC_010` | done |
| AC-011 | `test_handoff_reserves_child_specs_and_next_number_AC_011` | done |
| AC-012 | `test_relevant_agents_reference_canonical_foundation_AC_012` | done |
| AC-013 | Release-review diff inspection: no existing pricing/allocation runtime behavior changed | done |
| AC-014 | `test_review_promotion_rejects_missing_reviewer_or_high_gap_AC_014` | done |
| AC-015 | Domain test + `spec`, `docs-link`, `spec-index`, `doc-counts`, `handoff-sync`, `source-catalog`, `data-provenance`, `secret-scan`; full `pytest -q`; `git diff --check` | done |

## Draft Decision Review

Reviewed `spec.md` and `plan.md` before implementation. Status as of
2026-09-09 (reviewer Joshua Lutkemuller, CFA, per
`knowledge/short_term_markets/README.md`'s Draft Decisions):

- Named practitioner/data-quant reviewer: **resolved** — Joshua Lutkemuller,
  CFA. This names the reviewer and unblocks the review process; it is not
  itself a per-record `reviewed` promotion for all 65 draft records, which
  still requires individual scope/date/evidence per `README.md`'s Review
  Status rules. T-010 therefore remains `blocked` for full per-record
  promotion, with the reviewer now named.
- Licensed industry/master-agreement material policy: **resolved** — public
  citation only (name/link/date to a public source), never verbatim licensed
  text. This pack continues to store public locators and derived structure
  only.
- `0067` optimizer boundary: **resolved** — contract-only, no reference
  optimizer; a real, externally-built optimizer registers through `0026`
  using the new `0067-collateral-margin-optimizer-contract` schema.
- First non-Treasury `0065` cash-product consumer: still open. Candidate
  order recorded for when `0065` is activated: commercial paper, certificate
  of deposit, money market fund shares.
- Direct MCP/resource-server exposure: still open. Recommendation on record:
  route through the existing `0052` resource discovery pattern rather than a
  new direct-access path.

## Validation Evidence

Captured on 2026-09-06 from
`spec0063-short-term-markets-domain-foundation`, rebased on `main`/`origin/main`
commit `4c4d38d`.

- `PYTHONPATH=src python3 -m quantsmith.pipelines.short_term_markets_knowledge`
  -> `short-term-markets validation OK (capabilities=7, concepts=36,
  conventions=10, draft=65, golden_cases=8, lifecycles=4, records=65,
  reviewed=0)`
- `PYTHONPATH=src pytest -q tests/test_short_term_markets_knowledge.py`
  -> `14 passed`
- `PYTHONPATH=src pytest -q` inside the restricted sandbox -> `509 passed,
  1 skipped, 4 errors`; the four errors were existing knowledge-console tests
  blocked by `PermissionError: [Errno 1] Operation not permitted` on localhost
  socket binding.
- `PYTHONPATH=src pytest -q` rerun outside the restricted sandbox -> `513 passed,
  1 skipped`.
- `hooks/stages/run-stage.sh spec docs-link spec-index doc-counts handoff-sync
  source-catalog data-provenance secret-scan` -> all stages returned no
  findings; `data-provenance` emitted its existing synthetic/simulated-data
  disclosure advisory without failing.
- `git diff --check` -> no whitespace errors.
- AC-013 diff inspection: this branch adds the 0063 knowledge validator,
  machine-readable pack, tests, source metadata, and documentation/instruction
  links only. It does not change existing pricing, trading, allocation, or
  optimization runtimes such as `sec_lending.py`,
  `financing_cost_analysis.py`, backtesting, or optimizer modules.

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
