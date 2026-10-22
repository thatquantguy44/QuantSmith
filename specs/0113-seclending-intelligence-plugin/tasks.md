# Tasks: SFMeridian — Securities Finance Intelligence Plugin (Foundation)

- **Spec:** 0113-seclending-intelligence-plugin (`spec.md`, `plan.md`, `roadmap.md`)
- **Last updated:** 2026-10-22

> Ordered, testable units of work across the whole plugin program. Each task
> cites the requirement(s) it advances and the spec that delivers it. Tasks
> owned by `0113` are documents and templates; runtime tasks are delivered by
> the child specs named in the *Delivered in* column, which copy their rows
> into their own `tasks.md` when they are written.

## Definition of Done (applies to every task)

- Work matches `plan.md`; deviations are recorded there (or in the child plan).
- Tests exist, name their `AC-*`, and pass deterministically offline.
- Reproducibility preserved (pinned repo refs, dated catalog snapshots,
  config hash in every run envelope, seeded LLM evaluation runs).
- No secrets, credentials, real query text, schemas, counterparties, or
  positions introduced; fixtures flagged synthetic per `0025`.
- Docs, config template, and agent catalog updated alongside the change.

## Task List

| ID | Task | Covers | Delivered in | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| T-001 | Specify tool contract v1: tool names, JSON-schema inputs/outputs, error codes, contract version and SemVer rules. | REQ-001, NFR-007, AC-001, AC-023 | `0113` (`plan.md`) → schemas in `0118` | in-progress | Contract table and error codes in `plan.md`; JSON Schema files land with `0118`. |
| T-002 | Publish the configuration template with placeholders only; gitignore the real file. | REQ-003, REQ-004 | `0113` | done | `templates/sfmeridian/sfmeridian.yml`; `/sfmeridian.yml` in `.gitignore`. |
| T-003 | Publish the query front-matter convention template. | REQ-005 | `0113` | done | `templates/sfmeridian/query_front_matter.sql` (synthetic). |
| T-004 | Publish roster, coverage matrix (C-01…C-09), reused-agent table, and workflow charters W1–W6. | REQ-015, REQ-019, AC-015, AC-019 | `0113` (`plan.md`) | done | Machine-readable `coverage.json` follows in `0114`. |
| T-005 | Implement config schema, loader, layered resolution, per-call allowlist, validate-only mode, and config hash. | REQ-003, NFR-009, AC-003 | `0114` | todo | |
| T-006 | Implement query-repository fetchers (`local`, `git` at pinned ref, `object_store`) with include/exclude and incremental change detection. | REQ-004, AC-004 | `0114` | todo | Git via subprocess or `dulwich` extra; no network in tests (local bare repo fixture). |
| T-007 | Implement front-matter/sidecar parser; reject malformed, index un-annotated as `unreviewed`. | REQ-005, AC-005 | `0114` | todo | Front-matter parsed as data only (RISK-005). |
| T-008 | Implement SQL structure extraction and the exemplar store, join graph, metric candidates, filter patterns, and lexical index (incremental, content-addressed JSONL). | REQ-006, NFR-001, NFR-005, AC-006 | `0114` | todo | Optional embeddings via `0071` seam behind `[embeddings]`. |
| T-009 | Implement the feedback inbox (propose/stage/promote/discard) on the `0049` pattern; retrieval ignores candidates until promoted. | REQ-014, AC-014 | `0114` | todo | |
| T-010 | Implement catalog snapshots: read-only introspection per dialect and declared catalog files; dated, versioned. | REQ-007 | `0115` | todo | |
| T-011 | Implement drift reconciliation between catalog snapshots and indexed exemplars; exclude drifted exemplars; hand classification to `schema_evolution`. | REQ-007, AC-007 | `0115` | todo | |
| T-012 | Implement the semantic mapping (`0063` concept → physical expression, grain, PIT column, viewpoint, unit) on `0008` governed-metric rules. | REQ-008, REQ-013, AC-008 | `0115` | todo | Create agent `semantic_mapping_steward` (C-02). |
| T-013 | Implement access layer: secret-pointer resolution via `secrets_management`, schema/table allowlists, redaction classes, `0058` clearance; log/trace scrubbing. | REQ-017, NFR-004, AC-017 | `0115` | todo | |
| T-014 | Implement the retrieval-first composer (`reuse` → `adapt` → `generate`) through `adapters/llm_runtime/`, recording path and sources. | REQ-009, AC-009 | `0116` | todo | Create agent `sql_composer` (C-03). |
| T-015 | Implement the deterministic verifier (read-only, single statement, identifier resolution, join keys, bound params, PIT predicate, limit, timeout, `EXPLAIN` cost guard) and verification tokens; fail closed. | REQ-010, NFR-004, NFR-005, AC-010, AC-021 | `0116` | todo | Adversarial suite is part of the DoD. |
| T-016 | Implement the read-only execution seam over `0023` `SQLDataSource` and adopter drivers; provenance record and `0070` run envelope; replay. | REQ-011, REQ-020, NFR-004, AC-011 | `0116` | todo | Wrap, do not modify, `sql_data.py`. |
| T-017 | Create agents `sfmeridian_orchestrator` (C-04) and `query_librarian` (C-01) with the four contract files, `Spec-Driven Role`, catalog row, registry and skills export rebuild. | REQ-015 | `0114` (C-01), `0116` (C-04) | todo | |
| T-018 | Implement the grounding check (claim extraction, citation resolution, deterministic recompute, `0063` term and viewpoint checks, abstention) and agent `answer_grounding_reviewer` (C-05). | REQ-012, REQ-013, AC-012, AC-013 | `0117` | todo | |
| T-019 | Build the synthetic fixture database, synthetic query repository, versioned golden-question set, metrics, thresholds, and the `eval.run` release gate. | REQ-016, NFR-001, NFR-002, NFR-006, AC-016 | `0117` | todo | Extends `0023` `seed_demo_data`; all records `0025`-flagged. |
| T-020 | Create the `plugins/sfmeridian/` distributable (`sfmeridian`): stdlib core, optional extras, contract module. | REQ-001, NFR-003, AC-001 | `0118` | todo | |
| T-021 | Implement the Python API surface. | REQ-002, AC-002 | `0118` | todo | |
| T-022 | Implement the MCP server surface on the `0052` adapter contract (stdio JSON-RPC). | REQ-002, AC-002 | `0118` | todo | |
| T-023 | Package the Claude Code plugin (skills + `.mcp.json`) with `0110` tooling; cross-surface contract tests; SemVer and migration-note rules; release notify per `0047`. | REQ-002, NFR-007, AC-002, AC-023 | `0118` | todo | |
| T-024 | Publish the child-spec roadmap with scope, dependencies, closed coverage rows, and phase exit criteria; reserve `0114`–`0120` in the spec index and handoff. | REQ-018, AC-018 | `0113` | done | `roadmap.md`; `specs/README.md`; `docs/handoff.md`. |
| T-025 | Add PostgreSQL, Oracle, and Databricks SQL dialect fixtures (identifier quoting, parameter style, `LIMIT`/`FETCH FIRST`, date functions, catalog introspection) and run the golden set against them unchanged. | REQ-020, AC-020 | `0115` (introspection), `0116` (verify/execute), `0118` (golden set) | todo | Decided 2026-10-22. PostgreSQL executes in CI; Oracle and Databricks verify statically plus adopter-side execution. |
| T-026 | Create analytics agents C-06/C-07/C-08 and workflows W2–W5; then C-09 and the reporting-completeness workflow. | REQ-015, REQ-019 | `0119`, `0120` | todo | |
| T-027 | Verify repo gates and disclosure: `spec`, `spec-index`, `handoff-sync`, `agent-catalog`, `skills-export`, `secret-scan`, `data-provenance`; confirm no existing agent or runtime behaviour changed. | NFR-006, NFR-008, NFR-009, AC-022, AC-024 | `0113`, then every child | in-progress | `0113` adds documents only. |
| T-028 | Publish the specialist handoff map (optimization, risk, portfolio management, knowledge, machine learning) with trigger, evidence, output, never-boundary, and workflow per agent; add workflows W7–W12. | REQ-021, AC-025 | `0113` (`plan.md`) | done | Machine-checkable `handoffs.json` follows in `0114` alongside `coverage.json`. |
| T-029 | Implement handoff payloads (run IDs, PIT panels, citations, redaction) for W7–W12 and wire `optimization_orchestrator`, `pm_orchestrator`, and `ml_orchestrator` routing from `sfmeridian_orchestrator`. | REQ-021, REQ-022, AC-025 | `0116` (payload), `0119` (workflows) | todo | No change to the receiving agents' charters; add a `Related` pointer in each only. |
| T-030 | Implement the decision-support output envelope: optimizer results carry solver status, diagnostics, sensitivities; model results carry baseline, interval/calibration, PIT feature attestation; reject action-phrased outputs in grounding. | REQ-022, AC-026 | `0117` (check), `0119` (producers) | todo | Borrow-demand models validated with `0006`/`0046` folds. |
| T-031 | Implement the `governed/` adapter: call `0080` `answer()` with the configured interpreter, `0081` pack selection, and caller clearance; route by outcome (answer → return; clarification among governed candidates → return, no fall-through; no governed metric → fall through); record the tier. | REQ-023, AC-027 | `0116` | todo | The only module importing `quantsmith`; pinned version. |
| T-032 | Implement the `0080` `Reader` over metric source queries: bind each governed metric to a reviewed exemplar and a column map, run through `sql.verify`/`sql.execute` with the plan's as-of and filters as parameters, emit `0008` `Fact` rows with provenance; mark unbound, unreviewed, or drifted metrics unavailable. | REQ-024, AC-028 | `0115` (binding), `0116` (Reader) | todo | |
| T-033 | Seed the semantic mapping from `0081` `securities_financing_prime` via `resolve_packs` (local overlay first); draft pack amendments for missing concepts (rebate rate, lendable value, on-loan quantity, recall quantity, collateral value, days-to-cover) through `0081`'s review flow; propagate the unreviewed-pack caveat. | REQ-025, REQ-008, AC-029 | `0115` | todo | Amendments are a separate `0081` change, reviewed by the named pack owner. |
| T-034 | Default `governed_tier.writeback.enabled: false`; refuse publish requests with a reason; reject write-back targets classed as lending, trading, or books-and-records in config validation. | REQ-026, AC-030 | `0114` (config), `0116` (refusal) | todo | |
| T-035 | Add governed and tier-agreement questions to the golden set; report governed-tier share, tier-agreement rate, and wrong-tier rate; flag disagreeing exemplars or bindings for review. | REQ-023, REQ-016 | `0117` | todo | RISK-012. |
| T-036 | Screen the community *Awesome Quant* list into `tooling_catalog.md` with rings, SFMeridian use, extras, and exclusions; then publish the machine-readable catalog with a validator (required fields, ring rules, no core import of non-stdlib packages). | REQ-027, NFR-003, AC-031 | `0113` (screen), `0114` (JSON + validator) | in-progress | Screening done; licenses `to verify`. |
| T-037 | Run admission reviews for every `adopt`/`trial` entry before its extra ships (license at pinned version, maintenance, hash pin, advisory scan, named reviewer); add the catalog-only recommendation check to grounding. | REQ-027, AC-031 | each child that adds an extra; grounding check in `0117` | todo | `rateslib`, `ArcticDB`, `mlfinlab` held on license. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

Every acceptance criterion is named by at least one test. Tests are written by
the delivering child spec under `plugins/sfmeridian/tests/`; document-level
criteria are checked by gates and review.

| Acceptance criterion | Test(s) | Delivered in | Status |
| --- | --- | --- | --- |
| AC-001 | `test_contract_lists_every_tool_and_error_code` (names AC-001) | `0118` | todo |
| AC-002 | `test_surfaces_return_identical_results_and_provenance` (names AC-002) | `0118` | todo |
| AC-003 | `test_config_validation_errors_and_layer_order` (names AC-003) | `0114` | todo |
| AC-004 | `test_two_configured_repos_indexed_no_hardcoded_location` (names AC-004) | `0114` | todo |
| AC-005 | `test_front_matter_valid_malformed_absent` (names AC-005) | `0114` | todo |
| AC-006 | `test_learning_artifacts_match_golden_extraction_with_citations` (names AC-006) | `0114` | todo |
| AC-007 | `test_catalog_drift_excludes_affected_exemplars` (names AC-007) | `0115` | todo |
| AC-008 | `test_utilization_governed_ratio_reconciles_by_counterparty` (names AC-008) | `0115` | todo |
| AC-009 | `test_compose_records_reuse_and_generate_paths` (names AC-009) | `0116` | todo |
| AC-010 | `test_verifier_rejects_adversarial_queries_with_codes` (names AC-010) | `0116` | todo |
| AC-011 | `test_execution_provenance_and_replay` (names AC-011) | `0116` | todo |
| AC-012 | `test_grounding_flags_uncited_mismatched_undefined` (names AC-012) | `0117` | todo |
| AC-013 | `test_viewpoint_error_rejected_with_0063_convention` (names AC-013) | `0117` | todo |
| AC-014 | `test_feedback_candidate_not_retrievable_until_promoted` (names AC-014) | `0114` | todo |
| AC-015 | `test_coverage_matrix_distinct_workflows_and_boundaries` (names AC-015) | `0114` | todo |
| AC-016 | `test_eval_reports_all_metrics_and_blocks_on_threshold_miss` (names AC-016) | `0117` | todo |
| AC-017 | `test_redaction_by_clearance_and_no_credentials_in_logs` (names AC-017) | `0115` | todo |
| AC-018 | review: `roadmap.md` + `spec-index` gate (names AC-018) | `0113` | done |
| AC-019 | review: workflow charters W1–W6 in `plan.md` (names AC-019) | `0113` | done |
| AC-020 | `test_golden_set_runs_unchanged_on_second_dialect` (names AC-020) | `0118` | todo |
| AC-021 | `test_cost_guard_and_incremental_reindex_limits` (names AC-021) | `0116` | todo |
| AC-022 | `data-provenance` + `secret-scan` gates over `plugins/sfmeridian/fixtures/` (names AC-022) | `0117` | todo |
| AC-023 | `test_contract_and_config_schema_versions_compatible` (names AC-023) | `0118` | todo |
| AC-024 | gates: `spec`, `spec-index`, `handoff-sync`, `agent-catalog`, `skills-export` (names AC-024) | `0113` | in-progress |
| AC-025 | `test_handoff_map_agents_exist_and_are_bounded` + review of W7–W12 (names AC-025) | `0114` | todo |
| AC-026 | `test_decision_support_envelope_for_optimizer_and_model_outputs` (names AC-026) | `0117` | todo |
| AC-027 | `test_governed_first_tier_routing_and_no_fallthrough_on_ambiguity` (names AC-027) | `0116` | todo |
| AC-028 | `test_reader_facts_reproduce_metric_source_queries` (names AC-028) | `0116` | todo |
| AC-029 | `test_mapping_seeded_from_0081_pack_and_amendments_not_private` (names AC-029) | `0115` | todo |
| AC-030 | `test_writeback_refused_by_default_and_unsafe_targets_rejected` (names AC-030) | `0116` | todo |
| AC-031 | `test_tooling_catalog_admission_and_catalog_only_recommendations` (names AC-031) | `0114`, `0117` | todo |

## Follow-ups

Tracked work intentionally deferred (no silent "temporary" shortcuts — P8).

- Name the reviewer for the `0081` `securities_financing_prime` pack (owner
  action; Phase 0 exit). Until then governed answers carry the unreviewed-pack
  caveat and write-back stays refused.
- Viewpoint, dialects, retrieval mode, and `0119`/`0120` order resolved
  2026-10-22 (`spec.md`). The pack reviewer remains open (needed for `0115`).
- Fine-tuning on promoted exemplars: roadmap Phase 6, only if the evaluation
  shows a gap retrieval cannot close.
- Expose the query index as `0052` resources (`knowledge://sfmeridian/...`):
  decide in `0118`.
- Coordinate golden-set red-team cases with `0103` evaluation once it is written.
