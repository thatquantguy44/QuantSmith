# Tasks: Memory-Graph MCP Server

- **Spec:** 0053-memory-graph-mcp-server (`spec.md`, `plan.md`)
- **Last updated:** 2026-09-02

## Definition of Done (applies to every task)

- Standard library only; no new dependency in `pyproject.toml`.
- `caller_clearance` required on every request; absent or unrecognized → -32600.
- Restricted and missing records always return -32600 (existence masking).
- Every `AC-*` has a named test.
- `ACCESS_RANK` from `contract.py` is the enforcement constant in code, not a string comparison.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | `adapters/mcp_servers/memory_resources.py`: `dispatch_memory`, `list_memory_resources`, `read_memory_resource`, `_citation_text`. Lazy import of `workflow_memory.Record`. | REQ-001–REQ-009, NFR-001–NFR-003 | done | |
| T-002 | Tests in `tests/test_mcp_servers.py`: one per AC, named for the AC. Record fixtures use `workflow_memory.build_record`. | REQ-001–REQ-009, NFR-002, NFR-003 | done | |
| T-003 | Update `knowledge_resources.dispatch` reserved message for `memory` authority to name `dispatch_memory`. Update `adapters/mcp_servers/README.md` with `memory` authority row. Add 0053 to `specs/README.md`. | REQ-001 | done | |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test | Status |
| --- | --- | --- |
| AC-001 | `test_mem_missing_clearance_returns_access_denied_AC_001` | done |
| AC-002 | `test_mem_list_excludes_restricted_from_internal_AC_002` | done |
| AC-003 | `test_mem_list_public_sees_only_public_AC_003` | done |
| AC-004 | `test_mem_read_returns_citation_for_allowed_record_AC_004` | done |
| AC-005 | `test_mem_wrong_authority_returns_not_found_AC_005` | done |
| AC-006 | `test_mem_restricted_record_denied_to_internal_AC_006` | done |
| AC-007 | `test_mem_missing_record_existence_masked_AC_007` | done |
| AC-008 | `test_mem_unsupported_method_returns_method_not_found_AC_008` | done |
| AC-009 | `test_mem_restricted_clearance_sees_all_AC_009` | done |
| AC-010 | `test_mem_list_sorted_by_uri_AC_010` | done |
