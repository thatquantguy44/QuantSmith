# Tasks: NLP, LLM, and Quant Text Intelligence Foundation

- **Spec:** 0071-nlp-llm-quant-text-intelligence-foundation (`spec.md`, `plan.md`)
- **Last updated:** 2026-09-09

> Ordered, testable units of work. Every task cites the requirement(s) it
> advances and carries a Definition of Done. The offline foundation is complete;
> provider, live-source, training, and `0054` activation remain separate work.

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
| T-001 | Define and validate the versioned text-intelligence manifest and references to the `0070` run envelope. | REQ-001, NFR-002 | done | 1 | Domain manifest is hash-listed by one validated `0070` envelope. |
| T-002 | Define document, span, source-policy, and corpus-snapshot records with source-catalog, temporal, revision, access, entitlement, license, and split fields. | REQ-002, REQ-009, NFR-002 | done | 1 | Reuses `sources/` and shared access vocabulary. |
| T-003 | Implement immutable corpus snapshots, source-specific availability rules, canonical/near-duplicate groups, and split-overlap validation. | REQ-002, REQ-013, NFR-001, NFR-006 | done | 1 | Fixture timestamp policy implemented; real-source policies stay consumer-owned. |
| T-004 | Implement ordered transformation lineage for extraction/OCR metadata, normalization, redaction, language handling, chunking, deduplication, labeling, and filtering. | REQ-003, REQ-017, NFR-002, NFR-007 | done | 1 | Typed operation vocabulary, hash validation, and pre-context quarantine implemented. |
| T-005 | Define model-capability and invocation profiles for deterministic, hosted, local, embedding, reranking, tokenization, and training/adaptation operations. | REQ-004, NFR-005, NFR-009 | done | 2 | Provider-neutral profiles only; live implementations remain external. |
| T-006 | Define embedding artifacts and immutable access-tier index snapshots with source-span lineage and model/preprocessing checks. | REQ-005, NFR-003, NFR-005, NFR-009 | done | 2 | Contract and hash-vector fixture complete; live semantic index waits on `0054`. |
| T-007 | Define and validate optional local training/adaptation manifests, split evidence, checkpoints, metrics, contamination findings, and model-card references. | REQ-006, NFR-005 | done | 2 | Checkpoint/model-card contract fixture only; no training performed. |
| T-008 | Define versioned task schemas and evidence-bearing outputs for classification, extraction, stance/sentiment, themes, retrieval, reranking, summarization, and synthesis. | REQ-007, REQ-015, NFR-002 | done | 2 | Supported and abstention/error paths validated. |
| T-009 | Define text-derived signal records and fail-closed materialization into dataset/backtest references. | REQ-008, REQ-015, NFR-001 | done | 3 | Fixture-only publication with PIT span checks and downstream references. |
| T-010 | Implement source registration, access/license propagation, prohibited-data checks, quarantine, and credentials-by-reference validation. | REQ-009, REQ-017, NFR-003, NFR-007 | done | 1 | Synthetic source registered; untrusted input is excluded before context/model use. |
| T-011 | Integrate shared MCP authorities, `0056` market research, and the future `0054` cited semantic-search interface without backend-specific agent logic. | REQ-010, NFR-003 | done | 4 | Shared contract and pre-search tier selection complete; live `0054` transport remains its own reserved spec. |
| T-012 | Add temporal, revision, exact/near-duplicate, split-overlap, label, benchmark-contamination, and backtest-leakage evaluators. | REQ-011, REQ-013, NFR-001, NFR-006 | done | 3 | Deterministic failure findings covered by AC-010. |
| T-013 | Add task-quality, retrieval/reranking, calibration, citation/faithfulness, robustness, injection/tool-safety, privacy, latency/cost, and signal-stability evaluators. | REQ-011, REQ-014, REQ-017, NFR-009 | done | 3 | Sixteen required layers demand metrics or justified exceptions. |
| T-014 | Define text-specific `0070` audit events plus review, override, rejected-alternative, uncertainty, escalation, and publication state. | REQ-012, REQ-015, NFR-008 | done | 4 | Text domain events are metadata within the authoritative `0070` ledger. |
| T-015 | Extend `0070` context/evaluation/replay handling with text manifests, hash verification, replay classifications, and artifact diffs. | REQ-001, REQ-012, REQ-014, NFR-004 | done | 4 | `0071` replay calls `replay_envelope_file`; no parallel replay engine. |
| T-016 | Add text-intelligence gate coverage and compose it with source, knowledge, access, leakage, repro, model-plugin, orchestration, and secret checks. | REQ-012, NFR-007 | done | 4 | `text-intelligence` is discoverable through `run-stage.sh`. |
| T-017 | Add one deterministic lexical extraction/signal example and one fixture-backed retrieval/generation example with complete replay evidence. | REQ-014, NFR-004 | done | 3 | Committed fictional fixtures plus disclosure. |
| T-018 | Add typed consumption examples for knowledge, research, economist, portfolio, risk, and strategy agents. | REQ-016, NFR-005 | done | 4 | `build_agent_consumption_view` serves all six declared consumer domains without backend details. |
| T-019 | Document approved open decisions, ownership boundaries, provider/plugin onboarding, and production promotion criteria. | REQ-004, REQ-015, REQ-016 | done | 4 | Foundation decisions recorded; all live activation remains bounded and fail-closed. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

Every acceptance criterion must be named by at least one test.

| Acceptance criterion | Planned test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_valid_text_intelligence_manifest_resolves_run_and_artifacts_AC_001` | done |
| AC-002 | `test_corpus_records_preserve_source_time_access_license_and_split_AC_002` | done |
| AC-003 | `test_transform_chain_resolves_hashes_to_source_spans_AC_003` | done |
| AC-004 | `test_model_capability_profiles_validate_required_evidence_AC_004` | done |
| AC-005 | `test_embedding_and_index_snapshot_reject_mismatch_or_cross_tier_AC_005` | done |
| AC-006 | `test_task_results_require_schema_evidence_or_abstention_AC_006` | done |
| AC-007 | `test_text_signal_lineage_is_point_in_time_and_complete_AC_007` | done |
| AC-008 | `test_unregistered_credential_or_unlicensed_source_is_quarantined_AC_008` | done |
| AC-009 | `test_mcp_retrieval_selects_caller_access_tier_before_search_AC_009` | done |
| AC-010 | `test_text_leakage_suite_rejects_future_revision_duplicate_and_overlap_AC_010` | done |
| AC-011 | `test_text_evaluation_suite_reports_each_required_layer_AC_011` | done |
| AC-012 | `test_replay_labels_deterministic_local_fixture_and_external_modes_AC_012` | done |
| AC-013 | `test_untrusted_text_cannot_issue_instruction_or_undeclared_tool_AC_013` | done |
| AC-014 | `test_material_output_requires_review_uncertainty_and_audit_AC_014` | done |
| AC-015 | `test_agents_consume_shared_artifacts_without_backend_credentials_AC_015` | done |
| AC-016 | `test_text_intelligence_gates_are_offline_and_discoverable_AC_016` | done |

## Follow-ups

- Review and approve the implemented Draft contracts in `0070` and `0071`; keep
  immutable historical schemas if later revisions change them.
- Activate and approve reserved spec `0054` before implementing live semantic
  retrieval or selecting a production vector/index backend.
- Create a separate bounded model-training spec before running fine-tuning,
  continued pretraining, or parameter-efficient adaptation.
- Add provider-specific hosted/local/embedding/reranking adapters only after
  privacy, license, cost, and execution-location policies are approved.
- Add source-specific text ingestion only through an approved source entry,
  data/knowledge contract, entitlement decision, and point-in-time policy.
- Do not activate or modify reserved specs `0064`-`0069` as part of this work.

## Validation Evidence

- `PYTHONPATH=src pytest -q tests/test_text_intelligence.py tests/test_orchestration_foundation.py`
- `PYTHONPATH=src python3 -m quantsmith.text_intelligence validate --discover examples/text_intelligence`
- deterministic replay and fixture-substitution replay through
  `quantsmith.orchestration.replay_envelope_file`
- `QF_STAGE_ENFORCE=1 hooks/stages/run-stage.sh text-intelligence orchestration`
