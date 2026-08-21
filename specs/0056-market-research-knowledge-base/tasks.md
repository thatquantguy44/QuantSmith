# Tasks: Market Research Knowledge Base

- **Spec:** 0056-market-research-knowledge-base (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-21

> Ordered, testable units of work. Every task cites the requirement(s) it advances
> and carries a Definition of Done. No task without a requirement.

## Definition of Done (applies to every task)

- Code matches the plan; deviations noted in `plan.md`.
- Tests exist and pass deterministically.
- Reproducibility preserved (pinned inputs, seeded randomness, no hidden state).
- No secrets, credentials, licensed third-party research, MNPI, or private firm
  content introduced.
- Docs/configs updated alongside the change.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Define the market research item schema and core taxonomy. | REQ-001, REQ-003, REQ-004, REQ-005 | todo | AC-001 |
| T-002 | Implement ingestion normalization for user notes, generated reports, firm research, manager letters, sell-side notes, and transcripts using synthetic fixtures. | REQ-001, REQ-004, REQ-010 | todo | AC-001 |
| T-003 | Define the `knowledge://market_research/...` MCP namespace and agent-facing retrieval contract. | REQ-002, REQ-013 | todo | AC-002 |
| T-004 | Add a storage adapter contract that separates metadata catalog, original content store, and index tier. | REQ-003, NFR-004 | todo | AC-002 |
| T-005 | Implement classification and freshness metadata for asset class, source type, theme, entity, stale, and superseded states. | REQ-005, REQ-009, NFR-009 | todo | AC-009 |
| T-006 | Add governance policy checks for caller clearance, entitlement class, confidentiality, and information barriers. | REQ-006, REQ-011, NFR-001, NFR-008 | todo | AC-003, AC-006 |
| T-007 | Ensure search/index selection happens by access tier before query execution. | REQ-006, NFR-001 | todo | AC-003 |
| T-008 | Implement point-in-time filtering across publication date, effective date, ingestion date, and supersession status. | REQ-007, NFR-003 | todo | AC-004 |
| T-009 | Implement citation rendering and unsupported-gap reporting. | REQ-008, REQ-009, NFR-002 | todo | AC-005 |
| T-010 | Implement review, quarantine, supersession, deprecation, deletion, and rebuild lifecycle states. | REQ-010, REQ-011, NFR-008, NFR-010 | todo | AC-006, AC-009 |
| T-011 | Add an audit ledger for ingestion, review, retrieval, citation, denial, and lifecycle events. | REQ-012, NFR-007 | todo | AC-008 |
| T-012 | Add integration examples for research, portfolio-management, economist, role-operations, and knowledge agents. | REQ-013 | todo | AC-002 |
| T-013 | Add curation support for conflicting sources and canonical-source selection. | REQ-014 | todo | AC-007 |
| T-014 | Integrate scheduled research reports and knowledge-candidate review handoff with `0055`. | REQ-015 | todo | AC-010 |
| T-015 | Add validation tests for citation coverage and point-in-time correctness. | NFR-002, NFR-003 | todo | AC-004, AC-005 |
| T-016 | Add synthetic capacity and latency benchmark fixtures for catalog/index scale. | NFR-005, NFR-006 | todo | |
| T-017 | Add freshness, compaction, deprecation, deletion, and index rebuild tests. | NFR-009, NFR-010 | todo | AC-009 |
| T-018 | Add a provider-neutral tagged email market-color source contract and template. | REQ-016, REQ-017, NFR-011 | todo | AC-011, AC-012 |
| T-019 | Implement email scan policy validation for labels/tags/folders, saved searches, mailbox scope, cursors, and read-only permissions. | REQ-016, REQ-018, NFR-011 | todo | AC-011, AC-013 |
| T-020 | Implement email thread/message normalization with per-message citations, sent/received timestamps, tag provenance, and attachment decisions. | REQ-017, REQ-019, NFR-012 | todo | AC-012 |
| T-021 | Add sender/domain allowlist/denylist and privacy-minimization tests before message extraction or indexing. | REQ-018, REQ-011, REQ-012, NFR-012 | todo | AC-013 |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

Every acceptance criterion must be named by at least one test.

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_market_research_ingestion_metadata_ac001` | todo |
| AC-002 | `test_market_research_mcp_namespace_ac002` | todo |
| AC-003 | `test_market_research_restricted_denial_ac003` | todo |
| AC-004 | `test_market_research_as_of_filter_ac004` | todo |
| AC-005 | `test_market_research_citation_coverage_ac005` | todo |
| AC-006 | `test_market_research_quarantine_ac006` | todo |
| AC-007 | `test_market_research_conflict_curation_ac007` | todo |
| AC-008 | `test_market_research_audit_record_ac008` | todo |
| AC-009 | `test_market_research_stale_superseded_ac009` | todo |
| AC-010 | `test_market_research_scheduled_candidate_ac010` | todo |
| AC-011 | `test_email_market_color_tag_scope_ac011` | todo |
| AC-012 | `test_email_market_color_thread_normalization_ac012` | todo |
| AC-013 | `test_email_market_color_sender_policy_ac013` | todo |

## Follow-ups

Tracked work intentionally deferred (no silent "temporary" shortcuts — P8).

- Choose first external storage provider adapter after the access taxonomy is
  approved.
- Decide whether licensed manager and sell-side research can be passage-indexed,
  metadata-only indexed, or excluded from indexes.
- Choose the first tagged-email provider adapter and label naming convention.
- Add provider-specific deployment documentation only after compliance and
  entitlement owners approve the governance model.
