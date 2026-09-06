# Tasks: NLP, LLM, and Quant Text Intelligence Foundation

- **Spec:** 0071-nlp-llm-quant-text-intelligence-foundation (`spec.md`, `plan.md`)
- **Last updated:** 2026-09-06

> Ordered, testable units of work. Every task cites the requirement(s) it
> advances and carries a Definition of Done. This Draft creates the work package;
> implementation starts only after its open decisions are approved.

## Definition of Done (applies to every task)

- Code matches the approved plan; deviations and decisions are recorded.
- Tests exist and pass deterministically without network access.
- Point-in-time, deduplication, split, benchmark-contamination, access, and
  license controls are correct by construction.
- All outputs retain source-span, transform, model/task, evaluation, and run
  lineage through the `0070` envelope.
- No secrets, credentials, private prompts, PII, MNPI, proprietary model
  payloads, or licensed content bodies are introduced.
- Documentation, templates, gates, audit evidence, and replay fixtures are
  updated alongside behavior.

## Task List

| ID | Task | Covers | Status | Slice | Dependency / Notes |
| --- | --- | --- | --- | --- | --- |
| T-001 | Define and validate the versioned text-intelligence manifest and references to the `0070` run envelope. | REQ-001, NFR-002 | todo | 1 | Contract work is unblocked; runtime integration waits on `0070`. |
| T-002 | Define document, span, source-policy, and corpus-snapshot records with source-catalog, temporal, revision, access, entitlement, license, and split fields. | REQ-002, REQ-009, NFR-002 | todo | 1 | Reuse `sources/`, knowledge, access, and `0056` vocabularies. |
| T-003 | Implement immutable corpus snapshots, source-specific availability rules, canonical/near-duplicate groups, and split-overlap validation. | REQ-002, REQ-013, NFR-001, NFR-006 | todo | 1 | Requires approved timestamp policy for each first-slice source class. |
| T-004 | Implement ordered transformation lineage for extraction/OCR metadata, normalization, redaction, language handling, chunking, deduplication, labeling, and filtering. | REQ-003, REQ-017, NFR-002, NFR-007 | todo | 1 | Reference fixtures use text input; no OCR service dependency. |
| T-005 | Define model-capability and invocation profiles for deterministic, hosted, local, embedding, reranking, tokenization, and training/adaptation operations. | REQ-004, NFR-005, NFR-009 | todo | 2 | Compose `adapters/llm_runtime/`; provider implementations remain external. |
| T-006 | Define embedding artifacts and immutable access-tier index snapshots with source-span lineage and model/preprocessing checks. | REQ-005, NFR-003, NFR-005, NFR-009 | todo | 2 | Contract/fixtures unblocked; live semantic index waits on `0054`. |
| T-007 | Define and validate optional local training/adaptation manifests, split evidence, checkpoints, metrics, contamination findings, and model-card references. | REQ-006, NFR-005 | todo | 2 | Fixture-only until a separate training spec approves model, license, hardware, and method. |
| T-008 | Define versioned task schemas and evidence-bearing outputs for classification, extraction, stance/sentiment, themes, retrieval, reranking, summarization, and synthesis. | REQ-007, REQ-015, NFR-002 | todo | 2 | Include abstention and unsupported states. |
| T-009 | Define text-derived signal records and fail-closed materialization into dataset/backtest references. | REQ-008, REQ-015, NFR-001 | todo | 3 | Requires approved decision-time and promotion policy. |
| T-010 | Implement source registration, access/license propagation, prohibited-data checks, quarantine, and credentials-by-reference validation. | REQ-009, REQ-017, NFR-003, NFR-007 | todo | 1 | Reuse source, knowledge, access, model-plugin, and secret controls. |
| T-011 | Integrate shared MCP authorities, `0056` market research, and the future `0054` cited semantic-search interface without backend-specific agent logic. | REQ-010, NFR-003 | todo | 4 | Resource integration can start; semantic retrieval waits on `0054`. |
| T-012 | Add temporal, revision, exact/near-duplicate, split-overlap, label, benchmark-contamination, and backtest-leakage evaluators. | REQ-011, REQ-013, NFR-001, NFR-006 | todo | 3 | Extend existing leakage/PIT evidence. |
| T-013 | Add task-quality, retrieval/reranking, calibration, citation/faithfulness, robustness, injection/tool-safety, privacy, latency/cost, and signal-stability evaluators. | REQ-011, REQ-014, REQ-017, NFR-009 | todo | 3 | Every inapplicable layer needs a justified exception. |
| T-014 | Define text-specific `0070` audit events plus review, override, rejected-alternative, uncertainty, escalation, and publication state. | REQ-012, REQ-015, NFR-008 | todo | 4 | Schema extension can be drafted before `0070` runtime implementation. |
| T-015 | Extend `0070` context/evaluation/replay handling with text manifests, hash verification, replay classifications, and artifact diffs. | REQ-001, REQ-012, REQ-014, NFR-004 | todo | 4 | Runtime work waits on `0070`; fixture contract is unblocked. |
| T-016 | Add text-intelligence gate coverage and compose it with source, knowledge, access, leakage, repro, model-plugin, orchestration, and secret checks. | REQ-012, NFR-007 | todo | 4 | Wire through `hooks/stages/run-stage.sh`. |
| T-017 | Add one deterministic lexical extraction/signal example and one fixture-backed retrieval/generation example with complete replay evidence. | REQ-014, NFR-004 | todo | 3 | Fictional or public metadata only. |
| T-018 | Add typed consumption examples for knowledge, research, economist, portfolio, risk, and strategy agents. | REQ-016, NFR-005 | todo | 4 | Consumers receive artifacts/MCP resources, never provider credentials. |
| T-019 | Document approved open decisions, ownership boundaries, provider/plugin onboarding, and production promotion criteria. | REQ-004, REQ-015, REQ-016 | todo | 4 | Must not imply that an adapter or model claim is independently verified. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

Every acceptance criterion must be named by at least one test.

| Acceptance criterion | Planned test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_valid_text_intelligence_manifest_resolves_run_and_artifacts_AC_001` | todo |
| AC-002 | `test_corpus_records_preserve_source_time_access_license_and_split_AC_002` | todo |
| AC-003 | `test_transform_chain_resolves_hashes_to_source_spans_AC_003` | todo |
| AC-004 | `test_model_capability_profiles_validate_required_evidence_AC_004` | todo |
| AC-005 | `test_embedding_and_index_snapshot_reject_mismatch_or_cross_tier_AC_005` | todo |
| AC-006 | `test_task_results_require_schema_evidence_or_abstention_AC_006` | todo |
| AC-007 | `test_text_signal_lineage_is_point_in_time_and_complete_AC_007` | todo |
| AC-008 | `test_unregistered_credential_or_unlicensed_source_is_quarantined_AC_008` | todo |
| AC-009 | `test_mcp_retrieval_selects_caller_access_tier_before_search_AC_009` | todo |
| AC-010 | `test_text_leakage_suite_rejects_future_revision_duplicate_and_overlap_AC_010` | todo |
| AC-011 | `test_text_evaluation_suite_reports_each_required_layer_AC_011` | todo |
| AC-012 | `test_replay_labels_deterministic_local_fixture_and_external_modes_AC_012` | todo |
| AC-013 | `test_untrusted_text_cannot_issue_instruction_or_undeclared_tool_AC_013` | todo |
| AC-014 | `test_material_output_requires_review_uncertainty_and_audit_AC_014` | todo |
| AC-015 | `test_agents_consume_shared_artifacts_without_backend_credentials_AC_015` | todo |
| AC-016 | `test_text_intelligence_gates_are_offline_and_discoverable_AC_016` | todo |

## Follow-ups

- Implement `0070` before claiming integrated audit/gate/replay acceptance for
  T-001 and T-014-T-016.
- Activate and approve reserved spec `0054` before implementing live semantic
  retrieval or selecting a production vector/index backend.
- Create a separate bounded model-training spec before running fine-tuning,
  continued pretraining, or parameter-efficient adaptation.
- Add provider-specific hosted/local/embedding/reranking adapters only after
  privacy, license, cost, and execution-location policies are approved.
- Add source-specific text ingestion only through an approved source entry,
  data/knowledge contract, entitlement decision, and point-in-time policy.
- Do not activate or modify reserved specs `0064`-`0069` as part of this work.
