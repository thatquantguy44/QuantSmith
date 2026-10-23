# Tasks: SFMeridian — Governed SQL Composition, Verification & Execution

- **Spec:** 0116-sfmeridian-governed-sql-composition (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-23

> Ordered, testable implementation units. Implementation begins only after the
> owner approves `spec.md` and `plan.md`.

## Definition of Done (applies to every task)

- Code matches the approved plan; deviations are recorded before implementation.
- Tests name their `AC-*` and pass deterministically offline on Python 3.11+.
- Core imports only the standard library; only `governed/` imports `quantsmith`.
- No source write path, raw-SQL execute tool, credential, signing material,
  real schema, counterparty, position, or query text is introduced.
- Fixtures are synthetic and disclosed; artifacts, errors, traces, envelopes,
  and handoffs are scrubbed and clearance-aware.
- Docs, config, coverage, catalogs, registry, and skills export stay in sync.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Build the deterministic synthetic SQLite fixture and known-result manifest matching the declared v1 catalog; add disclosure and catalog/exemplar consistency tests. | REQ-001, NFR-001, NFR-005, AC-001 | done | `fixtures/execution/fixture_db.py`, `expected_results.json`; all end-to-end work builds on it. |
| T-002 | Implement fail-closed structural verification, catalog/allowlist resolution, exact join-key validation, parameter matching, PIT proof, limit enforcement, canonical records, and token issuance; add the adversarial and token-mutation suites. | REQ-003, REQ-005, NFR-002, AC-003, AC-005 | done | `verify.py`; builds before execution. |
| T-003 | Add SQLite/PostgreSQL/Oracle/Databricks dialect policies, injected timeout and normalized `EXPLAIN` cost guard, configurable token TTL, and static fixtures. | REQ-004, REQ-005, NFR-004, AC-004 | done | `dialect_queries.json`; no driver extra ships. |
| T-004 | Implement the token-only query seam, query-only adapter, redaction, scrubbed errors, provenance, deterministic run identity, `0070` envelope, and replay comparison. | REQ-006, REQ-007, NFR-002, NFR-003, NFR-005, AC-006, AC-007 | done | `execute.py`; wraps only `query`, never exposes `execute`/`transaction`. |
| T-005 | Implement retrieval-first composition (`reuse` → `adapt` → `generate`) with eligibility, bound parameters, canonical evidence, catalog constraints, and injected completion. | REQ-002, AC-002 | done | `compose.py`; generated SQL remains outside the index. |
| T-006 | Implement the governed `Reader`: available-source lookup, plan binding, verified execution, exact output-to-`Fact` mapping, batch provenance, and unavailable-source handling. | REQ-008, NFR-003, AC-008 | done | `governed/reader.py`; completes parent T-032. |
| T-007 | Implement typed governed-first `ask` routing and the shadow-mode tail, including terminal clarification/unavailable outcomes and bounded repair. | REQ-009, REQ-010, AC-009, AC-010 | done | `governed/ask.py`; shadow output explicitly carries the deferred `0117` caveat. |
| T-008 | Register strict schemas/effects for `sql.compose`, `sql.verify`, `sql.execute`, and `ask`; add runtime write-back refusal and contract/governance checks. | REQ-011, REQ-012, AC-011, AC-012 | done | `governed/tools.py`; token-only execution schema, no write-effect tool. |
| T-009 | Build `sql_composer` and `sfmeridian_orchestrator` policies, reports, verifiers, manifests, four-file agent contracts, catalog rows, coverage updates, and deterministic harness tests. | REQ-013, REQ-014, REQ-010, AC-013, AC-014 | done | C-03 and C-04 are built loop agents with least-privilege grants and verified finishes. |
| T-010 | Implement and validate bounded W7–W12 specialist handoff payloads and `0070` evidence references without changing receiver behavior. | REQ-007, REQ-015, NFR-005, AC-015 | todo | Receiving agents may get a `Related` pointer only. |
| T-011 | Add repeatability, rejection/fabrication counters, overhead/cost assertions, import boundary, secret/redaction scans, and optional connector skips. | NFR-001, NFR-002, NFR-003, NFR-004, NFR-005, AC-016, AC-017 | todo | Adversarial rejection must be 100%; executed fabrication zero. |
| T-012 | Update configuration template, CLI/help, plugin and SDK docs, spec index, parent task status, handoff, counts, registry and skills export; run SFMeridian tests, full suite, ruff, and every enforced gate. | NFR-006, AC-018 | todo | Do not mark complete with pre-existing or new gate findings. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

All implementation tests live in `tests/test_sfmeridian_sql.py` unless noted.

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_ac001_fixture_matches_catalog_exemplars_and_manifest` | done |
| AC-002 | `test_ac002_composition_reuse_adapt_generate_with_evidence` | done |
| AC-003 | `test_ac003_verifier_rejects_adversarial_queries_without_execution` | done |
| AC-004 | `test_ac004_dialect_limits_pit_timeout_and_cost_guard` | done |
| AC-005 | `test_ac005_token_binds_every_context_field_and_expires` | done |
| AC-006 | `test_ac006_query_only_execution_redacts_and_scrubs` | done |
| AC-007 | `test_ac007_execution_provenance_envelope_and_replay` | done |
| AC-008 | `test_ac008_reader_facts_reproduce_sources_and_drift_is_unavailable` | done |
| AC-009 | `test_ac009_governed_first_routing_and_terminal_clarification` | done |
| AC-010 | `test_ac010_tail_trace_repair_citations_and_envelope` | done |
| AC-011 | `test_ac011_writeback_always_refused_and_no_write_tool` | done |
| AC-012 | `test_ac012_shared_registry_schemas_effects_and_no_raw_execute` | done |
| AC-013 | `test_ac013_sql_composer_loop_boundaries_and_verifiers` | done |
| AC-014 | `test_ac014_orchestrator_routes_repairs_escalates_and_replays` | done |
| AC-015 | `test_ac015_specialist_handoffs_are_bounded_and_redacted` | todo |
| AC-016 | `test_ac016_repeatability_rejection_fabrication_and_overhead` | todo |
| AC-017 | `test_ac017_import_fixture_secret_and_clearance_boundaries` | todo |
| AC-018 | full suite, ruff, registry/skills freshness, and enforced stage gates | todo |

## Follow-ups

- `0117`: claim-level grounding, recomputation, viewpoint enforcement,
  abstention, versioned golden questions, and the release gate.
- `0118`: contract JSON Schemas, Python/MCP/Claude surfaces, SemVer, second-
  dialect execution contract tests, and `1.0.0` packaging.
- `0119`: wire and validate specialist workflows consuming the handoff payloads.
- Named review of the `0081` pack and staged amendments; until accepted,
  governed answers keep the caveat and write-back remains refused.
- Admission reviews for optional drivers and any stricter SQL parser before an
  extra ships.
