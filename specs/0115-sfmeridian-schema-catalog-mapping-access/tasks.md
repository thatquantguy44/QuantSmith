# Tasks: SFMeridian — Schema Catalog, Semantic Mapping & Access

- **Spec:** 0115-sfmeridian-schema-catalog-mapping-access (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-22

## Definition of Done (applies to every task)

- Code matches `plan.md`; deviations noted there.
- Tests name their `AC-*` and pass deterministically offline on Python 3.11+.
- Core imports only the standard library; `quantsmith` only under `governed/`.
- No secrets, real schemas, rosters, or counterparties; fixtures disclosed.
- Docs, catalogs, registry, and skills export updated alongside the change.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Snapshots from declared files and introspection; allowlists; content-addressed store and dated history. | REQ-001, AC-001 | done | `catalog.py`. |
| T-002 | Fixed dictionary queries for SQLite, PostgreSQL, Databricks, Oracle; case-insensitive resolution; coded, text-free driver errors. | REQ-002, AC-002 | done | `catalog.INTROSPECTION_SQL`. |
| T-003 | Snapshot diff and classification; `schema_evolution` handoff. | REQ-003, AC-003 | done | |
| T-004 | Drift reconciliation, `drift.json`, retrieval exclusion, `warn` policy. | REQ-004, AC-004 | done | `index.load_index` reads `drift.json`. |
| T-005 | Vocabulary from the `0081` pack, shipped amendments, and `0063`. | REQ-005, AC-005 | done | `mapping.Vocabulary`. |
| T-006 | Binding validation rules and codes; ratio checks. | REQ-006, AC-006, AC-007 | done | `mapping.py`. |
| T-007 | Pack-amendment proposals, `0081` validation of the amended pack, staging, caveat; reviewer recorded. | REQ-007, AC-005 | done | `data/pack_amendments.json`. |
| T-008 | Metric-source validation and availability. | REQ-008, AC-008 | done | Binding half of `0113` T-032. |
| T-009 | Roster clearance, column classes, research integration, row masking. | REQ-009, REQ-010, AC-009, AC-010 | done | `access.py`, `research/tools.py`. |
| T-010 | Credential scrubbing in traces and errors; injected connections only. | REQ-011, AC-011 | done | |
| T-011 | Governed bridge: pack resolution, amended-pack validation, `0008` compilation, file fallback. | REQ-012, AC-007, AC-015 | done | `governed/packs.py`. |
| T-012 | Ten tools in the registry and the `0113` contract. | REQ-013, AC-012 | done | `semantic_tools.py`, `governance.py`. |
| T-013 | `semantic_mapping_steward` policy, report, verifiers, manifest, CLI. | REQ-014, AC-013 | done | `steward.py`. |
| T-014 | Agent files, catalog rows, registry, skills export; C-02 built. | REQ-015, AC-014 | done | |
| T-015 | Config shapes for `catalog`, bindings, `metric_sources`; template updated. | REQ-001, REQ-006, REQ-008, AC-016 | done | |
| T-016 | Synthetic fixtures, disclosure, gates, docs and counts. | NFR-001, NFR-002, NFR-003, NFR-004, NFR-005, AC-017 | done | |

## Test Coverage Map

All in `tests/test_sfmeridian_mapping.py`.

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_ac001_declared_snapshot_content_addressed_and_dated` | done |
| AC-002 | `test_ac002_sqlite_introspection_and_dialect_dictionary_queries` | done |
| AC-003 | `test_ac003_diff_classifies_and_hands_off` | done |
| AC-004 | `test_ac004_drift_excludes_from_retrieval_until_clean` | done |
| AC-005 | `test_ac005_pack_vocabulary_amendments_and_caveat` | done |
| AC-006 | `test_ac006_binding_validation_codes` | done |
| AC-007 | `test_ac007_ratio_over_the_same_rows` | done |
| AC-008 | `test_ac008_metric_sources_available_or_unavailable` | done |
| AC-009 | `test_ac009_clearance_from_the_roster` | done |
| AC-010 | `test_ac010_research_withholds_columns_above_clearance` | done |
| AC-011 | `test_ac011_no_credentials_in_traces_errors_or_artifacts` | done |
| AC-012 | `test_ac012_tools_registered_with_effects` | done |
| AC-013 | `test_ac013_steward_loop` | done |
| AC-014 | `test_ac014_agent_files_catalog_and_governance` | done |
| AC-015 | `test_ac015_portability_and_fallback` | done |
| AC-016 | `test_ac016_config_shapes_and_template` | done |
| AC-017 | `test_ac017_fixtures_disclosed_and_deterministic` + all gates under `QF_STAGE_ENFORCE=1` | done |

## Follow-ups

- `0116`: the governed tier and `Reader` over the available metric sources;
  `sql.verify` resolves identifiers against these snapshots.
- The named reviewer reviews `securities_financing_prime` and the staged
  amendments through the `0081` flow; until then answers carry the caveat.
- Live introspection against adopter PostgreSQL, Oracle, and Databricks
  (drivers injected by the host; admission reviews before any extra ships).
