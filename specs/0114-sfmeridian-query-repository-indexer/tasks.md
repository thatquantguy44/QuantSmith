# Tasks: SFMeridian — Query Repository Connector & Indexer

- **Spec:** 0114-sfmeridian-query-repository-indexer (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-22

## Definition of Done (applies to every task)

- Code matches `plan.md`; deviations noted there.
- Tests name their `AC-*` and pass deterministically offline on Python 3.11+.
- Package code imports only the standard library.
- No secrets, real queries, schemas, or counterparties; fixtures disclosed.
- Docs, catalogs, registry, and skills export updated alongside the change.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Strict YAML-subset reader for config and front-matter. | REQ-002, AC-002 | done | `yamlsubset.py`; equals PyYAML on the template and fixture. |
| T-002 | Config schema, defaults, environment layering, validation codes, hash, per-call overrides. | REQ-001, NFR-004, AC-001 | done | `config.py`; adds `index.dir`. |
| T-003 | Local, Git (bare cache, pinned commit), and injected object-store fetchers with `**` globs and escape refusal. | REQ-003, NFR-003, AC-003 | done | `repos.py`, `globs.py`. |
| T-004 | Front-matter and sidecar parsing; field, placeholder, parameter, and duplicate-ID checks. | REQ-004, AC-004 | done | `frontmatter.py`; a reviewed file keeps a contested ID. |
| T-005 | Standard-library SQL structure extraction across SQLite, PostgreSQL, Oracle, Databricks quoting. | REQ-005, AC-005 | done | `sqlstructure.py`; CTEs resolve to base tables; literals redacted. |
| T-006 | Content-addressed exemplars, join graph, metric candidates (conflict flag), filter patterns; incremental, byte-stable writes. | REQ-006, NFR-002, AC-006, AC-013 | done | `index.py`. |
| T-007 | BM25 search with normalized scores and review-status eligibility. | REQ-007, AC-007 | done | `index.py`. |
| T-008 | Feedback inbox with distinct-promoter rule and pseudonymous handles. | REQ-008, AC-008 | done | `feedback.py`. |
| T-009 | `coverage.json`, `handoffs.json`, `tooling_catalog.json` (generated from `0113`), validators, and the stdlib import scan. | REQ-009, NFR-001, AC-009, AC-012 | done | `governance.py`; strict mode lists 26 pending admissions. |
| T-010 | `query_librarian` agent files, catalog rows, registry, skills export. | REQ-010, AC-010 | done | `agents/securities_financing/sfmeridian/`. |
| T-011 | CLI over the tool registry and agent runner. | REQ-011, AC-011 | done | `cli.py`, `__main__.py`. |
| T-012 | Portability and determinism checks. | NFR-001, NFR-002, AC-012, AC-013 | done | Suite passes on Python 3.11 and 3.13. |
| T-013 | Synthetic fixtures and disclosure. | NFR-004, AC-014 | done | `plugins/sfmeridian/fixtures/`. |
| T-014 | Gates green under enforcement; spec index, handoff, README counts updated. | NFR-005, AC-014 | done | |
| T-015 | Shared tool registry with schemas and effects; `human_only` promotion and discard. | REQ-012, AC-015 | done | `tools.py`. |
| T-016 | Agent loop harness, manifests, `ModelPolicy`, deterministic run IDs and traces. | REQ-013, AC-016 | done | `agent.py`. |
| T-017 | `query_librarian` deterministic policy, three verifiers, manifest. | REQ-014, AC-017 | done | `librarian.py`, `data/agents/query_librarian.json`. |

## Test Coverage Map

All in `tests/test_sfmeridian_indexer.py`.

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_ac001_config_validation_codes_hash_and_overrides` | done |
| AC-002 | `test_ac002_yaml_subset_matches_pyyaml_and_rejects` | done |
| AC-003 | `test_ac003_local_and_git_repos_pinned_no_hardcoded_location` | done |
| AC-004 | `test_ac004_front_matter_valid_malformed_unannotated` | done |
| AC-005 | `test_ac005_sql_structure_extraction` | done |
| AC-006 | `test_ac006_learned_artifacts_cited_and_incremental` | done |
| AC-007 | `test_ac007_search_eligibility_ranking` | done |
| AC-008 | `test_ac008_feedback_promotion_rules` | done |
| AC-009 | `test_ac009_governance_catalogs_and_imports` | done |
| AC-010 | `test_ac010_query_librarian_catalogued` | done |
| AC-011 | `test_ac011_cli` | done |
| AC-012 | `test_ac012_stdlib_only_imports` | done |
| AC-013 | `test_ac013_determinism` | done |
| AC-014 | `test_ac014_fixtures_disclosed_and_credential_free` + `data-provenance`/`secret-scan` gates | done |
| AC-015 | `test_ac015_tool_registry_shared_schema_and_human_only` | done |
| AC-016 | `test_ac016_harness_denies_budgets_repairs_and_replays` | done |
| AC-017 | `test_ac017_query_librarian_loop` | done |

## Follow-ups

- `0115`: catalog snapshots and drift; bind canonical metrics — built
  2026-10-22 (pack reviewer named; review pending).
- Admission reviews (`0113` T-037) before any optional extra ships.
- Packaged test entry point inside the distributable (`0118`).
