# Plan: Memory-Graph MCP Server (spec 0053)

## Architecture

The pattern mirrors 0056 T-003 (`market_research_resources.py`) exactly:
one module in `adapters/mcp_servers/`, one public `dispatch_memory` entry
point, no I/O of its own. The only difference is the underlying data source:
instead of `InMemoryResearchCatalog`, the adapter receives a pre-loaded
`Sequence[Record]` from `workflow_memory.py`.

```
dispatch_memory(message, *, records, caller_entitlements=())
  ├── parse_request(message)            # contract.py — validates envelope
  ├── caller_clearance required         # → -32600 if absent (RISK-001)
  ├── METHOD_LIST
  │     └── list_memory_resources(records, clearance)
  │           → [ResourceMeta] filtered by clearance_allows, sorted by URI
  └── METHOD_READ
        ├── parse + validate URI        # authority = "memory"
        └── read_memory_resource(records, uri, clearance)
              ├── find by record_id     # → -32600 if missing (RISK-003)
              ├── clearance_allows()    # → -32600 if denied
              └── _citation_text(rec)  → ResourceContent
```

## Key Decisions / Trade-offs

| Decision | Choice | Alternative considered |
| --- | --- | --- |
| Input type | `Sequence[Record]` (caller-injected) | Accepting a `Store` or a root path would add I/O or coupling to the YAML parser — both violate NFR-002. |
| Citation text | Structured summary (scope, type, statement, confidence, dates, access_level, URI) | Serving `format_record_line` only is too sparse for a retrieval response; raw YAML is forbidden (RISK-002). |
| Existence masking scope | All missing records, not only restricted ones | Simpler and fail-closed; a caller cannot infer clearance tiers from error codes. |
| URI path depth | `<scope>/<record_id>` (2 segments) | Single-segment URIs are ambiguous; 3+ segments have no natural third component. |

## Module Layout

```
src/quantsmith/adapters/mcp_servers/
    contract.py                 (0052, done)
    knowledge_resources.py      (0052, done)
    market_research_resources.py (0056 T-003, done)
    memory_resources.py         ← this spec
    __init__.py
    README.md
```

## Interfaces

### `dispatch_memory(message, *, records, caller_entitlements=())`

```python
from quantsmith.adapters.mcp_servers.memory_resources import dispatch_memory
from quantsmith.pipelines.workflow_memory import load_records

records = load_records(text, file="memory/equity/index.yaml")
resp = dispatch_memory(
    {"jsonrpc": "2.0", "method": "resources/list", "id": 1,
     "params": {"caller_clearance": "internal"}},
    records=records,
)
```

### Record URI

```
knowledge://memory/<scope>/<record_id>
```

### `resources/list` response

```json
{
  "jsonrpc": "2.0", "id": 1,
  "result": {
    "resources": [
      {
        "uri": "knowledge://memory/equity_momentum_signal/mem-0001",
        "name": "mem-0001",
        "description": "pattern · equity_momentum_signal",
        "mimeType": "text/plain",
        "access_level": "internal"
      }
    ]
  }
}
```

### `resources/read` response

```json
{
  "jsonrpc": "2.0", "id": 2,
  "result": {
    "contents": [
      {
        "uri": "knowledge://memory/equity_momentum_signal/mem-0001",
        "mimeType": "text/plain",
        "text": "[pattern] equity_momentum_signal\nID: mem-0001\nStatement: ...\nConfidence: high (corroborated 3×)\nFirst seen: 2025-01-10  Last confirmed: 2026-02-14\nStatus: active\nPIT scope: backtest_safe\nAccess level: internal\nURI: knowledge://memory/equity_momentum_signal/mem-0001"
      }
    ]
  }
}
```

## Traceability

| Spec element | Implementation |
| --- | --- |
| REQ-001 | `dispatch_memory` signature; lazy import of `workflow_memory.Record` |
| REQ-002 | `clearance` check before any record access |
| REQ-003 | `list_memory_resources`: `clearance_allows` per record; sorted by URI |
| REQ-004 | `_citation_text`: structured fields, no raw YAML |
| REQ-005 | `read_memory_resource`: missing record → `PermissionError` (→ -32600) |
| REQ-006 | `knowledge://memory/<scope>/<record_id>` URI format |
| REQ-007 | Authority check: `ku.authority != AUTHORITY_MEMORY` → `FileNotFoundError` (→ -32604) |
| REQ-008 | `req.method not in (METHOD_LIST, METHOD_READ)` → -32601 |
| REQ-009 | `clearance_allows(record.access_level, caller_clearance)` from `contract.py` |
| NFR-001 | No new import beyond stdlib + contract.py |
| NFR-002 | `records` is injected; no file reads in the adapter |
| NFR-003 | `ACCESS_RANK` in `contract.py` is the single enforcement constant |
