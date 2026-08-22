# Tasks: Market Research Knowledge Base

- **Spec:** 0056-market-research-knowledge-base (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-22

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

**Scoping update (this pass):** the original ordering implied most of this
work waits on a storage-provider decision. It doesn't. `0058-viewer-access-
control` proved the pattern — real, tested governance logic can be built and
verified entirely against the local `research/` reference store, with no
external backend and no MCP server, and generalized later without changing
the logic itself. Re-auditing task-by-task against that pattern: **18 of 21
tasks are buildable today, unblocked.** Only the MCP surface (needs `0052`,
unbuilt) and the email connector (needs a provider choice, an open business
question) are genuinely blocked. The table below adds a `Slice`/`Blocked by`
pair to make that explicit — `Slice` mirrors `plan.md`'s five-slice rollout,
reordered here by what can actually start, not by narrative sequence.

| ID | Task | Covers | Status | Slice | Blocked by | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| T-001 | Define the market research item schema and core taxonomy. | REQ-001, REQ-003, REQ-004, REQ-005 | todo | 1 | — | AC-001. Confidentiality reuses `0058`'s `ACCESS_LEVELS` (plan.md Dependency status). |
| T-002 | Implement ingestion normalization for user notes, generated reports, firm research, manager letters, sell-side notes, and transcripts using synthetic fixtures. | REQ-001, REQ-004, REQ-010 | todo | 1 | — | AC-001 |
| T-004 | Add a storage adapter contract that separates metadata catalog, original content store, and index tier. | REQ-003, NFR-004 | todo | 1 | — | AC-002. Contract shape only — the real backend choice is deferred (Follow-ups), the *contract* is not. |
| T-005 | Implement classification and freshness metadata for asset class, source type, theme, entity, stale, and superseded states. | REQ-005, REQ-009, NFR-009 | todo | 1 | — | AC-009 |
| T-008 | Implement point-in-time filtering across publication date, effective date, ingestion date, and supersession status. | REQ-007, NFR-003 | todo | 1 | — | AC-004. Pure function over the schema; no backend needed, same shape as `0048`'s `point_in_time_filter`. |
| T-010 | Implement review, quarantine, supersession, deprecation, deletion, and rebuild lifecycle states. | REQ-010, REQ-011, NFR-008, NFR-010 | todo | 1 | — | AC-006, AC-009 |
| T-006 | Add governance policy checks for caller clearance, entitlement class, confidentiality, and information barriers. | REQ-006, REQ-011, NFR-001, NFR-008 | todo | 3 | — | AC-003, AC-006. Clearance half calls `access_control.access_level_allows()` directly (built, tested); `entitlement_class`/info-barrier half is net-new but needs no external backend to build or test against the reference store. |
| T-007 | Ensure search/index selection happens by access tier before query execution. | REQ-006, NFR-001 | todo | 3 | — | AC-003. Testable today as "filter before search" over the local reference store; only the index *technology* is a later, backend-specific concern. |
| T-009 | Implement citation rendering and unsupported-gap reporting. | REQ-008, REQ-009, NFR-002 | todo | 3 | — | AC-005 |
| T-011 | Add an audit ledger for ingestion, review, retrieval, citation, denial, and lifecycle events. | REQ-012, NFR-007 | todo | 3 | — | AC-008. Same append-only-JSONL shape `0055`'s `ExecutionLedger` already uses — reuse the pattern, not necessarily the class. |
| T-013 | Add curation support for conflicting sources and canonical-source selection. | REQ-014 | todo | 3 | — | AC-007 |
| T-015 | Add validation tests for citation coverage and point-in-time correctness. | NFR-002, NFR-003 | todo | 3 | — | AC-004, AC-005 |
| T-016 | Add synthetic capacity and latency benchmark fixtures for catalog/index scale. | NFR-005, NFR-006 | todo | 3 | — | Synthetic by design (NFR-005/006 name synthetic metadata explicitly) — no real content or backend required. |
| T-014 | Integrate scheduled research reports and knowledge-candidate review handoff with `0055`. | REQ-015 | todo | 4 | — | AC-010. `0055` is built; `examples/scheduled_daily_report/` is the pattern to extend (a job target reusing existing read logic, dispatched through the registry). |
| T-017 | Add freshness, compaction, deprecation, deletion, and index rebuild tests. | NFR-009, NFR-010 | todo | 4 | — | AC-009 |
| T-012 | Add integration examples for research, portfolio-management, economist, role-operations, and knowledge agents. | REQ-013 | todo | 2 | `0052` MCP resources server (unbuilt) | AC-002. Agent examples need a server to call. |
| T-003 | Define the `knowledge://market_research/...` MCP namespace and agent-facing retrieval contract. | REQ-002, REQ-013 | todo | 2 | `0052` MCP resources server (unbuilt) | AC-002. The *contract* (URI shape, request/response fields) is already written in `plan.md`'s Interfaces section and could be drafted as a Python protocol/dataclass today; wiring it to a live MCP server is what's blocked. |
| T-018 | Add a provider-neutral tagged email market-color source contract and template. | REQ-016, REQ-017, NFR-011 | todo | 5 | email provider choice (spec.md Open Question) | AC-011, AC-012. The *provider-neutral* contract itself doesn't strictly need the choice made — see Follow-ups. |
| T-019 | Implement email scan policy validation for labels/tags/folders, saved searches, mailbox scope, cursors, and read-only permissions. | REQ-016, REQ-018, NFR-011 | todo | 5 | email provider choice (spec.md Open Question) | AC-011, AC-013 |
| T-020 | Implement email thread/message normalization with per-message citations, sent/received timestamps, tag provenance, and attachment decisions. | REQ-017, REQ-019, NFR-012 | todo | 5 | email provider choice (spec.md Open Question) | AC-012 |
| T-021 | Add sender/domain allowlist/denylist and privacy-minimization tests before message extraction or indexing. | REQ-018, REQ-011, REQ-012, NFR-012 | todo | 5 | email provider choice (spec.md Open Question) | AC-013 |

Status values: `todo` | `in-progress` | `blocked` | `done`. Slice numbers
follow `plan.md`'s Rollout section (1 contract-only, 2 read-only MCP
resources, 3 governed RAG, 4 scheduled-ops integration, 5 tagged email).

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

- Choose first external storage provider adapter. **No longer blocks Slice 1
  or Slice 3** (this scoping pass) — the schema, governance logic, citation
  rendering, and audit ledger are all buildable and testable against the
  local `research/` reference store first, same as `0058`. It still blocks
  actually deploying a real (non-reference) backend at NFR-004/005/006 scale.
- Decide whether licensed manager and sell-side research can be passage-indexed,
  metadata-only indexed, or excluded from indexes. Still blocks nothing in
  Slice 1/3/4 — `entitlement_class` can be modeled and enforced as a field
  today; *which* content each class actually permits indexing is the open
  compliance question, not the mechanism.
- Choose the first tagged-email provider adapter and label naming convention.
  Still blocks T-018–T-021 (Slice 5) — a provider-neutral *contract* could be
  drafted without the choice, but nothing in Slice 5 can be verified against
  a real shape without picking one.
- Add provider-specific deployment documentation only after compliance and
  entitlement owners approve the governance model.
- `entitlement_class`'s authoritative taxonomy is still an open compliance
  question (spec.md's Open Questions) distinct from the confidentiality
  question this pass resolved by reusing `0058`'s three-tier vocabulary —
  don't conflate the two when picking this back up.
