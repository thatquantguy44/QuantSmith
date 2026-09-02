# Plan: MCP Adapter Contract + Knowledge Resources Server

- **Spec:** 0052-mcp-adapter-contract (`spec.md`)
- **Status:** Draft
- **Author:** QuantSmith
- **Last updated:** 2026-09-01

> HOW. This plan requires an approved `spec.md`. Every requirement in the spec
> must appear in the traceability matrix below.

## Approach

Follow the `alert_delivery` adapter pattern: typed stdlib frozen dataclasses
define the contract; the adapter has no I/O of its own; transport is injected
by the host. The `dispatch` function is a pure function from a raw JSON dict to
a raw JSON dict — unit-testable without any MCP client or server process.

The three-tier clearance (`public < internal < restricted`) is the same rank
already defined in `access_control.py` (spec 0058) and used in 0056's market
research catalog. Reusing those values rather than inventing a parallel system
keeps the whole stack consistent.

The `knowledge://` URI scheme routes by authority so 0053, 0054, and 0056 can
each sit behind the same scheme without a naming collision. This spec handles
`knowledge://sources/...` only; the other authorities are reserved namespace
for downstream specs.

## Architecture & Components

```
Host process (stdio / SSE / HTTP+SSE)
        │  raw JSON string
        ▼
  json.loads()              # host's responsibility
        │  dict
        ▼
  dispatch(message, *, sources_config_path)     ← contract.py + knowledge_resources.py
        │
        ├── parse_request()           validate JSON-RPC envelope + caller_clearance
        ├── route by method
        │     resources/list  ──►  list_resources(sources, clearance)
        │     resources/read  ──►  read_resource(sources, uri, clearance)
        │     other           ──►  ERR_METHOD_NOT_FOUND (-32601)
        │
        ├── clearance_allows()        access_level vs caller_clearance
        ├── contains_secret()         credential scan before delivery
        └── McpResponse.to_dict()
        │  dict
        ▼
  json.dumps()              # host's responsibility
        │  raw JSON string
        ▼
  MCP client
```

**`contract.py`** — all types shared across 0052/0053/0054:
- `PUBLIC`, `INTERNAL`, `RESTRICTED` constants + `ACCESS_RANK` (the code-level
  rank, NFR-003)
- `KnowledgeUri` — parsed `knowledge://authority/path`
- `ResourceMeta`, `ResourceContent` — list/read outputs
- `McpRequest`, `McpResponse`, `McpError` — JSON-RPC 2.0 envelope
- `clearance_allows()`, `parse_request()`, `error_response()`
- `contains_secret()` — credential-pattern scan (mirrors `alert_delivery`)

**`knowledge_resources.py`** — the 0052 resources server:
- `SourceEntry` dataclass — one parsed entry from `knowledge_sources.yml`
- `parse_sources_config(path)` — subset YAML parser for the sources manifest
- `list_resources(sources, caller_clearance, base_path)` → `List[ResourceMeta]`
- `read_resource(sources, uri, caller_clearance, base_path)` → `ResourceContent`
- `dispatch(message, *, sources_config_path)` → raw dict

## Interfaces & Data Contracts

**URI scheme**
```
knowledge://<authority>/<path>
  authority = sources | memory | market_research
  path      = <source_name>/<relative_file_path>   (for authority=sources)
```

**`resources/list` request**
```json
{
  "jsonrpc": "2.0",
  "method": "resources/list",
  "id": 1,
  "params": {"caller_clearance": "internal"}
}
```

**`resources/list` result**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "resources": [
      {
        "uri": "knowledge://sources/research_archive/equity/overview.md",
        "name": "overview.md",
        "description": "research_archive",
        "mimeType": "text/plain",
        "access_level": "internal"
      }
    ]
  }
}
```

**`resources/read` request**
```json
{
  "jsonrpc": "2.0",
  "method": "resources/read",
  "id": 2,
  "params": {
    "caller_clearance": "internal",
    "uri": "knowledge://sources/research_archive/equity/overview.md"
  }
}
```

**`resources/read` result**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "contents": [{"uri": "...", "text": "...", "mimeType": "text/plain"}]
  }
}
```

**Error shape**
```json
{"jsonrpc": "2.0", "id": 1, "error": {"code": -32600, "message": "access denied"}}
```

**`knowledge_sources.yml` subset parsed**
```yaml
sources:
  - name: research_archive
    path: /mnt/knowledge/research
    access_level: internal
    include: ["*.md", "*.txt"]
    exclude: ["**/drafts/**"]
    freshness_days: 90
    domains_from_subfolders: true
```
Supported scalar types: string, int, bool, inline flow-sequence (`[...]`).

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | `caller_clearance` required; clearance rank in code; credential scan before delivery; path-traversal check. |
| P5 Reversibility | yes | Pure adapter with no storage writes; no side-effects; removing it leaves 0053/0054 stubs. |
| P6 Observability | yes | Every denied request has a named error code; list returns explicit count; caller sees exactly what it can see. |
| P9 Security & data | yes | RISK-001: clearance required. RISK-002: credential scan. RISK-003: restricted existence masked. RISK-004: path-traversal check. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `contract.py` frozen dataclasses; `pyproject.toml` unchanged | T-001 |
| REQ-002 | `parse_request` → `caller_clearance` missing → -32600; `SUPPORTED_CLEARANCES` check | T-001 |
| REQ-003 | `list_resources` + `clearance_allows` filter | T-002 |
| REQ-004 | `read_resource` + clearance check | T-002 |
| REQ-005 | `KnowledgeUri` + `KNOWN_AUTHORITIES` in `contract.py` | T-001 |
| REQ-006 | `parse_sources_config` + file globbing in `knowledge_resources.py` | T-003 |
| REQ-007 | `contains_secret()` in `contract.py`; called before returning content | T-002 |
| REQ-008 | authority not in `KNOWN_AUTHORITIES` → -32604 in `dispatch` | T-002 |
| REQ-009 | method not in `SUPPORTED_METHODS` → -32601 in `dispatch` | T-002 |
| REQ-010 | clearance check returns -32600 regardless of file existence | T-002 |
| REQ-011 | `sources_config_path` parameter in `dispatch`; no default | T-003 |
| REQ-012 | `Path.resolve()` + prefix check in `read_resource` | T-002 |
| NFR-001 | No new imports beyond stdlib; `pyproject.toml` untouched | T-001 |
| NFR-002 | `list_resources` sorts by URI | T-002 |
| NFR-003 | `ACCESS_RANK = {PUBLIC: 0, INTERNAL: 1, RESTRICTED: 2}` in code | T-001 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| No `mcp` package | stdlib dataclasses + dict I/O | `mcp` Python SDK | `mcp` is not in pyproject.toml; adding it violates NFR-001; the JSON-RPC 2.0 envelope is simple enough to implement directly. |
| Inline flow-sequence only in YAML | Support `["*.md"]` syntax | Full block-sequence parser | Matches the committed template; a full parser adds 100+ lines for a syntax nobody has used yet. |
| `caller_clearance` always required | Error -32600 on missing | Optional with default `public` | Defaulting to the least restrictive level is a security failure mode; requiring it makes the gate explicit (RISK-001). |
| Restricted existence masked | Always -32600 for restricted | -32404 if not found, -32600 if found | The two-error approach leaks existence (RISK-003). |

## Validation Strategy

All ACs verified by `tests/test_mcp_servers.py` using `tmp_path` fixtures.
No live MCP server needed; `dispatch` is a pure function. Fixture
`knowledge_sources.yml` is written inline in each test; no committed source
fixture. AC-007 (credential scan) injects a synthetic file with an API key
pattern; the test asserts `dispatch` raises `ValueError`.

## Rollout, Observability & Rollback

No deployment step; this is a library module. Downstream callers
(`knowledge://memory/...` in 0053, `knowledge://market_research/...` in 0056
T-003) depend on the URI contract; removing the module would break them.
Rollback: revert the commit; no storage touched.

## Open Questions

- Should `resources/list` include resource size and last-modified date? Deferred;
  not required by any current consumer.
