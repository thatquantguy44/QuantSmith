# Tasks: Knowledge Console — analytics & UI for the memory store

- **Spec:** 0057-knowledge-console (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-21

> Ordered, testable units of work. Every task cites the requirement(s) it advances
> and carries a Definition of Done. No task without a requirement.

## Definition of Done (applies to every task)

- Code matches the plan; deviations noted in `plan.md`.
- Tests exist and pass deterministically.
- Reproducibility preserved (pinned inputs, seeded randomness, no hidden state).
- No secrets, credentials, or private data introduced.
- Docs/configs updated alongside the change.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | `load_store(root)`: walk `manifest.yaml`, read each `index.yaml`/`provenance.yaml` via `workflow_memory.load_records`, tag each record with workflow + source file; degrade to empty on missing tree. | REQ-001, NFR-001, NFR-005 | done | |
| T-002 | `build_model(store, as_of, changes)`: record detail, counts, trend series; pure/deterministic, stable ordering, `generated_at` separated. | REQ-002, REQ-003, REQ-013, NFR-004 | done | |
| T-003 | `build_graph(store)`: record/dataset-scope/evidence-run/workflow nodes and edges, deterministic. | REQ-004 | done | |
| T-004 | `git_changes(root)`: `git log` over `memory/`, parse to changes; degrade to empty on any git failure. | REQ-005, NFR-005 | done | |
| T-005 | `build_review_queue(...)`: combine freshness decay, `validate` findings, unsupported confidence, low corroboration into a reasoned, severity-ranked queue. | REQ-006 | done | |
| T-006 | `server.py` + `__main__.py`: stdlib router for `/api/model`, `/api/health`, `/api/query`, static serving with traversal guard, loopback bind, 404s. | REQ-007, NFR-001, NFR-003 | done | |
| T-007 | `query.py`: `QueryEngine` protocol, `KeywordQueryEngine`, `resolve_engine`/`register_engine`; grounded, empty-on-no-match, deterministic. | REQ-008, REQ-009, NFR-006 | done | |
| T-008 | `web/` scaffold (Vite+React+TS), `api.ts` embedded-vs-fetch + Ask server-vs-local fallback, routing across six views. | REQ-010, REQ-011 | done | |
| T-009 | View components: Overview/analytics, Trends (hand-drawn SVG charts), Graph (Canvas force layout), Changes, Review, Ask; provenance shown on every record. | REQ-010, REQ-013, NFR-002 | done | |
| T-010 | Snapshot builder: run single-file Vite build, inject `window.__KB_MODEL__`, emit one self-contained HTML with no external requests. | REQ-012 | done | |
| T-011 | `tests/test_knowledge_console.py`: one test per AC; stdlib + pytest, no Node required. | REQ-001, REQ-002, REQ-006, REQ-007, REQ-009, NFR-004, NFR-006 | done | |
| T-012 | Wire catalogs/docs: `specs/README.md`, root `README.md` runtime table, `docs/handoff.md`, doc-counts; run gates + pytest green. | REQ-010 | done | |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

Every acceptance criterion is named by at least one test.

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_load_store_tags_workflow_and_source_AC_001` | done |
| AC-002 | `test_model_is_byte_identical_AC_002` | done |
| AC-003 | `test_counts_sum_to_total_AC_003` | done |
| AC-004 | `test_cumulative_trend_monotone_ends_at_total_AC_004` | done |
| AC-005 | `test_staleness_split_at_freshness_AC_005` | done |
| AC-006 | `test_graph_edges_record_to_workflow_and_scope_AC_006` | done |
| AC-007 | `test_changes_feed_real_and_empty_AC_007` | done |
| AC-008 | `test_review_queue_reasons_AC_008` | done |
| AC-009 | `test_api_model_and_health_AC_009` | done |
| AC-010 | `test_query_cites_vintage_record_AC_010` | done |
| AC-011 | `test_query_no_match_empty_citations_AC_011` | done |
| AC-012 | `test_default_engine_is_keyword_AC_012` | done |
| AC-013 | `test_frontend_prefers_embedded_model_AC_013` | done |
| AC-014 | `test_unknown_path_404_and_traversal_guard_AC_014` | done |
| AC-015 | `test_empty_store_yields_empty_model_AC_015` | done |

## Follow-ups

Tracked work intentionally deferred (no silent "temporary" shortcuts — P8).

- Per-viewer access-level enforcement (v1 displays access level; it does not
  filter by viewer authorisation) — RISK-003, a later spec.
- The approval **write path** (confirm/retire/edit a record with reviewer
  identity + audit trail) — the state machine `0048` defers; this console is its
  read surface.
- A registered LLM query engine (config/key handling, prompt, guardrails) behind
  the `QueryEngine` contract shipped here.
- Large-store graph layout (clustering, level-of-detail) and view-model
  pagination if the store outgrows a single response.
- Full DOM/interaction tests for the front end (v1 pins the data-source contract
  structurally via AC-013).
