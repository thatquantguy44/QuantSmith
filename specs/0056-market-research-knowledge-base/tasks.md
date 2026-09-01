# Tasks: Market Research Knowledge Base

- **Spec:** 0056-market-research-knowledge-base (`spec.md`, `plan.md`)
- **Last updated:** 2026-09-01

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
| T-001 | Define the market research item schema and core taxonomy. | REQ-001, REQ-003, REQ-004, REQ-005 | done | 1 | — | AC-001. Confidentiality reuses `0058`'s `ACCESS_LEVELS` (plan.md Dependency status). `MarketResearchItem` dataclass in `market_research.py`. |
| T-002 | Implement ingestion normalization for user notes, generated reports, firm research, manager letters, sell-side notes, and transcripts using synthetic fixtures. | REQ-001, REQ-004, REQ-010 | done | 1 | — | AC-001. `ingest_item()` + `_scan_quarantine()` with secret/PII/MNPI/license heuristics in `market_research.py`. |
| T-004 | Add a storage adapter contract that separates metadata catalog, original content store, and index tier. | REQ-003, NFR-004 | done | 1 | — | AC-002. `ResearchCatalog` abstract contract + `InMemoryResearchCatalog` reference adapter in `market_research.py`. |
| T-005 | Implement classification and freshness metadata for asset class, source type, theme, entity, stale, and superseded states. | REQ-005, REQ-009, NFR-009 | done | 1 | — | AC-009. `is_stale()` + `classify_item()` in `market_research.py`. |
| T-008 | Implement point-in-time filtering across publication date, effective date, ingestion date, and supersession status. | REQ-007, NFR-003 | done | 1 | — | AC-004. `point_in_time_filter()` pure function in `market_research.py`. |
| T-010 | Implement review, quarantine, supersession, deprecation, deletion, and rebuild lifecycle states. | REQ-010, REQ-011, NFR-008, NFR-010 | done | 1 | — | AC-006, AC-009. `VALID_TRANSITIONS`, `validate_lifecycle_transition()`, `transition_status()` in `market_research.py`. |
| T-006 | Add governance policy checks for caller clearance, entitlement class, confidentiality, and information barriers. | REQ-006, REQ-011, NFR-001, NFR-008 | done | 3 | — | AC-003, AC-006. `check_governance()` delegates clearance to `access_control.access_level_allows()`; entitlement check is net-new in `market_research.py`. |
| T-007 | Ensure search/index selection happens by access tier before query execution. | REQ-006, NFR-001 | done | 3 | — | AC-003. `filter_by_access_tier()` in `market_research.py`; filters before search, not after. |
| T-009 | Implement citation rendering and unsupported-gap reporting. | REQ-008, REQ-009, NFR-002 | done | 3 | — | AC-005. `render_citation()`, `render_unsupported_gap()`, `CitationResult`, `UnsupportedGap` in `market_research.py`. |
| T-011 | Add an audit ledger for ingestion, review, retrieval, citation, denial, and lifecycle events. | REQ-012, NFR-007 | done | 3 | — | AC-008. `ResearchAuditLedger` append-only JSONL in `market_research.py`. |
| T-013 | Add curation support for conflicting sources and canonical-source selection. | REQ-014 | done | 3 | — | AC-007. `find_conflicts()`, `select_canonical()`, `ConflictGroup` in `market_research.py`. |
| T-015 | Add validation tests for citation coverage and point-in-time correctness. | NFR-002, NFR-003 | done | 3 | — | AC-004, AC-005. `TestValidationT015` in `tests/test_market_research.py`. |
| T-016 | Add synthetic capacity and latency benchmark fixtures for catalog/index scale. | NFR-005, NFR-006 | done | 3 | — | `generate_synthetic_catalog(n, seed)` iterator in `market_research.py`; `TestBenchmarkFixturesT016` in tests. |
| T-014 | Integrate scheduled research reports and knowledge-candidate review handoff with `0055`. | REQ-015 | done | 4 | — | AC-010. `propose_knowledge_candidate()` + `KnowledgeCandidate` in `market_research.py`; deterministic candidate_id; always pending_review. |
| T-017 | Add freshness, compaction, deprecation, deletion, and index rebuild tests. | NFR-009, NFR-010 | done | 4 | — | AC-009. Covered in `TestStaleSuperssededAC009` (`TestStaleSuperssededAC009` in tests). |
| T-012 | Add integration examples for research, portfolio-management, economist, role-operations, and knowledge agents. | REQ-013 | done | 2 | — | AC-002. Examples added to `agents/knowledge/knowledge_retrieval/`, `agents/research_analyst/`, `agents/portfolio_management/data_signal_intake/`, `agents/economists/macro_backdrop_summarizer/`, and `agents/role_operations/prior_art_scanner/`. |
| T-003 | Define the `knowledge://market_research/...` MCP namespace and agent-facing retrieval contract. | REQ-002, REQ-013 | done | 2 | — | AC-002. `dispatch_market_research` in `adapters/mcp_servers/market_research_resources.py`; 9 tests in `tests/test_mcp_servers.py` (clearance guard, list/read, existence masking, authority routing). |
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
| AC-001 | `TestIngestionMetadataAC001` (8 tests) in `tests/test_market_research.py` | done |
| AC-002 | `TestMCPNamespaceAC002` (6 tests) in `tests/test_market_research.py`; `test_mr_*` (9 tests) in `tests/test_mcp_servers.py` | done |
| AC-003 | `TestRestrictedDenialAC003` (9 tests) in `tests/test_market_research.py` | done |
| AC-004 | `TestPointInTimeFilterAC004` (7 tests) in `tests/test_market_research.py` | done |
| AC-005 | `TestCitationCoverageAC005` (6 tests) in `tests/test_market_research.py` | done |
| AC-006 | `TestQuarantineAC006` (7 tests) in `tests/test_market_research.py` | done |
| AC-007 | `TestConflictCurationAC007` (7 tests) in `tests/test_market_research.py` | done |
| AC-008 | `TestAuditLedgerAC008` (7 tests) in `tests/test_market_research.py` | done |
| AC-009 | `TestStaleSuperssededAC009` (10 tests) in `tests/test_market_research.py` | done |
| AC-010 | `TestScheduledCandidateAC010` (6 tests) in `tests/test_market_research.py` | done |
| AC-011 | `test_email_market_color_tag_scope_ac011` | todo (Slice 5, blocked on email provider choice) |
| AC-012 | `test_email_market_color_thread_normalization_ac012` | todo (Slice 5, blocked on email provider choice) |
| AC-013 | `test_email_market_color_sender_policy_ac013` | todo (Slice 5, blocked on email provider choice) |

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
