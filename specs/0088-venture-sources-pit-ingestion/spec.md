# Spec: Venture Sources, Point-in-Time Ingestion & Entity Resolution

- **ID:** 0088-venture-sources-pit-ingestion
- **Status:** Draft
- **Author:** Joshua Lutkemuller, CFA
- **Approver:**
- **Last updated:** 2026-10-02

> WHAT and WHY only. Child of `0083-venture-intelligence-foundation`.

## Problem & Context

The venture agents run on caller-supplied text. Before any model or signal is
trusted, three things must be fixed: which public sources the work draws on
and what each one's quirks are, how every record gets an honest `known_at`
date despite backfill and late arrival, and how records for the same company
are joined across sources and scripts without false merges. `0083` states the
contracts; this spec makes them executable and testable on synthetic data.

## Goals

- Register the first public venture and intelligence sources in the source catalog with their point-in-time behaviour.
- Provide deterministic functions that derive `known_at`, build as-of views, and form outcome-independent cohorts.
- Provide an entity-resolution contract that never merges on a name alone, with an agent contract that applies it.

## Non-Goals

- **No network adapters or live pulls.** Callers supply records; adapters are later work once licences and terms are confirmed.
- **No commercial database content or schema.** Licensed vendors are chosen after the adopter's bake-off.
- **No probabilistic matching model.** Fuzzy or learned matching is a later, separately validated model.
- **No real entities in fixtures.** All test records are synthetic (`0025`).

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The SDK shall add `sources/*.yml` entries for patents, scholarly works, federal awards, SBIR/STTR awards, LEI data, restricted-party lists, sanctions aggregates, a company register, open-source events, and news events, each declaring a `known_at_policy`, quality notes, and `evaluating` status, plus a synthetic fixture source. | must |
| REQ-002 | The SDK shall define the five `known_at` policies (`filed`, `published`, `event`, `snapshot`, `retrieved`) in `conventions.json` and implement `derive_known_at`, which errors rather than guesses when the field a policy needs is missing. | must |
| REQ-003 | The SDK shall flag a record as `late_retrieval` when it was retrieved more than a stated number of days after its public time, and shall allow an as-of view to exclude such records. | must |
| REQ-004 | The SDK shall build as-of views that return only facts known on the as-of date, with the latest known version per entity and field. | must |
| REQ-005 | The SDK shall form cohorts from companies known by a formation date, independent of later outcomes, and report outcome rates with their denominators. | must |
| REQ-006 | The SDK shall implement entity-resolution decisions `match`, `candidate`, `candidate_cross_script`, `needs_registry_id`, and `no_match`, merging only on equal registry identifier within one jurisdiction or equal LEI, and never across scripts without an identifier. | must |
| REQ-007 | The SDK shall normalize names for comparison across Latin, Han, Thai, and Vietnamese forms while preserving the original name and legal-form suffix. | must |
| REQ-008 | The SDK shall add an `entity_resolution` agent contract with four files and a never-boundary. | must |
| REQ-009 | The SDK shall index the new sources in `sources/README.md` and the agent in the catalog, standard, and dictionary. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Determinism | All functions are pure and stdlib-only; identical inputs give identical outputs. |
| NFR-002 | Honesty | Source entries mark endpoints and terms `unverified` until confirmed; no credential or real record appears. |
| NFR-003 | Gates | `source-catalog`, `agent-catalog`, `spec`, and `handoff-sync` gates pass. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given `sources/`, when the venture entries are read, then each declares a `known_at_policy` that exists in `conventions.json`, and the source-catalog gate passes. | REQ-001, NFR-003 |
| AC-002 | Given a record missing the field its policy needs, when `derive_known_at` runs, then it raises, and given a complete record it returns the policy's timestamp. | REQ-002 |
| AC-003 | Given a record retrieved 400 days after its filing, when processed, then it is flagged `late_retrieval`, and an as-of view with `exclude_late` omits it. | REQ-003 |
| AC-004 | Given facts with different known_at dates, when an as-of view is built, then later facts are excluded and the latest earlier version wins. | REQ-004 |
| AC-005 | Given a universe in which failed companies are later removed, when a cohort is formed at an early date, then removed companies stay in the denominator. | REQ-005 |
| AC-006 | Given pairs with equal registry ID, differing registry ID, equal names in one script, and names in different scripts, when resolved, then decisions are match, no_match, candidate, and candidate_cross_script, with reasons. | REQ-006 |
| AC-007 | Given names with Latin, Han, Thai, and Vietnamese legal-form markers, when normalized, then markers are removed for comparison and the originals are untouched. | REQ-007 |
| AC-008 | Given `agents/venture_intelligence/entity_resolution/`, when listed, then it has four contract files and a never-boundary. | REQ-008 |
| AC-009 | Given the indexes, when read, then sources, agent, standard, and dictionary entries exist. | REQ-009 |
| AC-010 | Given repeated runs on the same inputs, when compared, then outputs are identical. | NFR-001 |
| AC-011 | Given the new source files, when scanned, then none contains a credential and endpoints are marked unverified in the description. | NFR-002 |

## Data & Dependencies

Depends on `0083` (fact record, bias contracts), `0025` (synthetic data), the
`0027` source-catalog format. Inputs are caller-supplied.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A normalization rule wrongly equates distinct companies. | False merge. | Name equality is only ever a candidate; merges need identifiers. |
| RISK-002 | Source terms or endpoints differ from entries. | Wrong integration. | `unverified` labels; confirm before building adapters. |
| RISK-003 | `late_retrieval` threshold is too coarse. | Backfill passes unflagged. | Threshold is data in `conventions.json`; revisit with vendor evidence. |

## Assumptions & Open Questions

- Assumption: public sources first; licensed vendors follow the bake-off.
- Open question: which sources need adapters first, once the bake-off reports.

## Exceptions

None.
