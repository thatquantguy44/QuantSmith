# Tasks: MCP Adapter Contract + Knowledge Resources Server

- **Spec:** 0052-mcp-adapter-contract (`spec.md`, `plan.md`)
- **Last updated:** 2026-09-01

## Definition of Done (applies to every task)

- Standard library only; no new dependency in `pyproject.toml`.
- `caller_clearance` is a required parameter on every request; absent or
  unrecognized clearance returns -32600, never serves content.
- `contains_secret()` is called before any resource content is delivered.
- Path-traversal check (`Path.resolve()` + prefix) runs before any file read.
- Every `AC-*` has a named test; the clearance rank order is in `ACCESS_RANK`
  in code, not only in the spec.
- A restricted resource always returns -32600, whether or not it exists.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | `contract.py`: `PUBLIC/INTERNAL/RESTRICTED`, `ACCESS_RANK`, `KnowledgeUri`, `ResourceMeta`, `ResourceContent`, `McpRequest`, `McpResponse`, `McpError`, `clearance_allows`, `parse_request`, `error_response`, `contains_secret`. | REQ-001, REQ-002, REQ-005, NFR-001, NFR-003 | done | `caller_clearance` absent or unrecognized → -32600. `ACCESS_RANK` is the enforcement, not the name string. |
| T-002 | `knowledge_resources.py`: `dispatch(message, *, sources_config_path)` — routes `resources/list` / `resources/read`; clearance filter; credential scan; path-traversal check; authority routing; error codes. | REQ-003, REQ-004, REQ-007, REQ-008, REQ-009, REQ-010, REQ-011, REQ-012, NFR-002 | done | `resources/list` sorts by URI. Restricted existence masked (-32600, not -32604). |
| T-003 | `knowledge_resources.py`: `SourceEntry`, `parse_sources_config(path)`, `list_resources(sources, clearance, base_path)`, `read_resource(sources, uri, clearance, base_path)` — YAML subset parser, glob include/exclude, URI↔file mapping. | REQ-006, REQ-011, REQ-012 | done | Inline flow-sequence only (`["*.md"]`). Path outside source root → `ValueError`. |
| T-004 | `tests/test_mcp_servers.py` — one test per AC. | REQ-001–REQ-012, NFR-002, NFR-003 | done | `tmp_path` fixtures only. No live MCP process. |
| T-005 | `adapters/mcp_servers/README.md` + `adapter_contract.md`; wire into `src/quantsmith/pipelines/README.md`, root `README.md`, `specs/README.md`, `docs/handoff.md`. | REQ-001 | done | doc-counts and spec-index gates enforce this. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Verification | Status |
| --- | --- | --- |
| AC-001 | `test_missing_clearance_returns_access_denied_AC_001` | done |
| AC-002 | `test_list_internal_clearance_excludes_restricted_AC_002` | done |
| AC-003 | `test_list_public_clearance_only_public_AC_003` | done |
| AC-004 | `test_read_resource_returns_file_content_AC_004` | done |
| AC-005 | `test_unknown_authority_returns_not_found_AC_005` | done |
| AC-006 | `test_restricted_resource_denied_to_internal_AC_006` | done |
| AC-007 | `test_credential_in_content_raises_AC_007` | done |
| AC-008 | `test_unsupported_method_returns_method_not_found_AC_008` | done |
| AC-009 | `test_nonexistent_file_returns_not_found_AC_009` | done |
| AC-010 | `test_path_traversal_raises_AC_010` | done |
| AC-011 | `test_list_restricted_clearance_sees_all_AC_011` | done |

## Sequencing

T-001 gates everything — `contract.py` types are imported by T-002/T-003.
T-002 and T-003 are co-written in `knowledge_resources.py` since `dispatch`
and the source handlers are tightly coupled. T-004 requires T-001–T-003.
T-005 can proceed once T-001 exists (the README describes the contract
before all handlers are wired).
