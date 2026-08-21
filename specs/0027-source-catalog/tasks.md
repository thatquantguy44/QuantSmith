# Tasks: Data Source Catalog

- **Spec:** 0027-source-catalog (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-10

## Definition of Done (applies to every task)

- Every `sources/*.yml` declares the required fields and is indexed.
- `credential_ref` is a pointer in every entry, never a value.
- The gate degrades gracefully when `sources/` is absent.
- No fabricated quality claims — `unknown` is a valid, expected value.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Add the per-source schema template. | REQ-001 | done | `templates/data/source_catalog_entry.yml`. |
| T-002 | Add the index and a filled-in reference entry. | REQ-002 | done | `sources/README.md`, `sources/fred.yml`. |
| T-003 | Add the `source-catalog` gate. | REQ-003, NFR-001, NFR-003 | done | `hooks/stages/source-catalog-check.sh`; tested against the real `fred.yml` plus three negative cases (unindexed, missing field, token-shaped credential). |
| T-004 | Wire the catalog into existing docs/agents. | REQ-004 | done | `templates/data/data_contract.md`, `agents/secrets_management/credential_access/{README,instructions}.md`, `agents/data_ingestion/README.md` + each of the three ingestion agents' `instructions.md`, `instructions/data_quality.md`, `instructions/point_in_time.md`. |
| T-005 | Wire catalogs and run validation gates. | NFR-002 | done | `specs/README.md`, root `README.md`, `hooks/README.md`, `run-stage.sh`, CI workflow, `docs/handoff.md`; `spec agent-catalog docs-link spec-index secret-scan source-catalog`; full `pytest tests/ -q`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `hooks/stages/source-catalog-check.sh` run against `sources/fred.yml` | done |
| AC-002 | Same gate run against a copy missing a required field | done |
| AC-003 | Same gate run against an unindexed copy | done |
| AC-004 | Same gate run against a copy with a token-shaped `credential_ref` | done |
| AC-005 | Direct inspection of `data_contract.md`, `credential_access/instructions.md`, `data_ingestion/*/instructions.md` | done |

## Follow-ups

- A `model_plugin_registration`-style review agent for source registrations,
  if the catalog grows enough that manual review of new entries doesn't
  scale.
- An optional staleness signal on `quality.last_assessed` (advisory), if
  stale assessments turn out to be a real recurring problem.
- Populate `sources/fred.yml`'s `data_contract_refs` once a concrete
  dataset pulled from FRED gets its own `data_contract.md`.
