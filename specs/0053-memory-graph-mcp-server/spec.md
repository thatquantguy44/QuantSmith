# Spec 0053 — Memory-Graph MCP Server

- **Status:** Draft
- **Author:** workflow_orchestrator
- **Created:** 2026-09-02
- **Depends on:** 0052 (MCP adapter contract), 0048 (workflow-memory runtime)
- **Unblocks:** 0054 (RAG server, which adds one index per access tier)

## Context

Spec 0052 built the `knowledge://sources/...` adapter and defined the
`knowledge://` URI scheme with three reserved authorities: `sources`
(implemented), `memory` (this spec), and `market_research` (0056 T-003,
implemented). The `knowledge_resources.dispatch` function returns -32604 for
`memory` URIs with the message "reserved for future specs (0053/0054)".

Spec 0048 made the workflow memory store machine-readable: `load_records`
parses YAML into typed `Record` objects; `query` filters by scope, type,
confidence, status, and access level; `point_in_time_filter` enforces the
look-ahead firewall; `format_record_line` renders a single-line citation.

This spec wires the `knowledge://memory/<scope>/<record_id>` MCP namespace
to the 0048 runtime, following the same adapter contract as 0056 T-003:
- The adapter is a pure function (no I/O beyond the injected records list).
- `caller_clearance` is required on every request (RISK-001 from 0052).
- Restricted and missing records return -32600 (existence masking, RISK-003).
- Content is a citation summary; raw YAML is never served (RISK-002).

## URI Scheme

```
knowledge://memory/<scope>/<record_id>
```

- `scope` — the workflow or dataset scope of the record (e.g.
  `equity_momentum_signal`, `macro_regime`).
- `record_id` — the record's `id` field (e.g. `mem-0001`).

The path has exactly two segments. A URI with fewer than two path segments
is rejected as -32604.

## Requirements

| ID | Requirement |
| --- | --- |
| REQ-001 | `dispatch_memory(message, *, records, ...)` — pure function, no I/O, returns JSON-RPC 2.0 dict. `records` is a caller-injected `Sequence[Record]`. |
| REQ-002 | `caller_clearance` required on every request; absent or unrecognized → -32600. Value must be in `SUPPORTED_CLEARANCES` from `contract.py`. |
| REQ-003 | `resources/list` returns metadata for all records whose `access_level` the caller's clearance permits, sorted by URI. Denied records are silently excluded, never named in the response. |
| REQ-004 | `resources/read` returns a citation summary for the record at the given URI; text never includes YAML source or evidence in raw form. |
| REQ-005 | Existence masking: a restricted or missing record always returns -32600, not -32604, so callers cannot probe for restricted record existence. |
| REQ-006 | URI for a record: `knowledge://memory/<scope>/<record_id>`. |
| REQ-007 | Authority routing: only `memory` URIs are handled; any other authority → -32604. |
| REQ-008 | Unsupported method → -32601. |
| REQ-009 | Access filtering uses `clearance_allows(record.access_level, caller_clearance)` from `contract.py` — the same enforcement constant (`ACCESS_RANK`) as every other knowledge server. |

## Non-Functional Requirements

| ID | NFR |
| --- | --- |
| NFR-001 | Standard library only; no new dependency in `pyproject.toml`. |
| NFR-002 | No I/O in the adapter; the `records` sequence is caller-injected. |
| NFR-003 | Clearance enforcement is `ACCESS_RANK` in `contract.py`, not string comparison. |

## Acceptance Criteria

| ID | Criterion |
| --- | --- |
| AC-001 | A request missing `caller_clearance` returns -32600. |
| AC-002 | An `internal` caller's list excludes records with `access_level = restricted`. |
| AC-003 | A `public` caller's list excludes `internal` and `restricted` records. |
| AC-004 | `resources/read` for an allowed record returns its citation text at the correct URI. |
| AC-005 | A URI with the wrong authority returns -32604. |
| AC-006 | A `restricted` record returns -32600 to an `internal` caller. |
| AC-007 | A non-existent record ID returns -32600 (existence masking, not -32604). |
| AC-008 | An unsupported method returns -32601. |
| AC-009 | A `restricted` caller's list includes `public`, `internal`, and `restricted` records. |
| AC-010 | The list response is sorted by URI. |

## Risks

| ID | Risk | Mitigation |
| --- | --- | --- |
| RISK-001 | Caller escalates by omitting `caller_clearance`. | Always require it; absent → -32600 before any record access. |
| RISK-002 | Raw YAML or evidence is served. | Citation text is a structured summary rendered by the adapter; the raw `Record` fields are never serialized to the response. |
| RISK-003 | Existence of restricted records is revealed. | Both "access denied" and "record not found" return -32600. |
| RISK-004 | Access-level filtering uses string comparison. | `clearance_allows` from `contract.py` uses `ACCESS_RANK` (int), not string equality. |
