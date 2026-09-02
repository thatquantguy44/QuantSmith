# MCP Servers Adapter

Typed, stdlib-only adapter contract for MCP (Model Context Protocol) knowledge
servers, plus the `resources` primitive implementation (spec `0052`).

## What this adapter does

Implements JSON-RPC 2.0 `resources/list` and `resources/read` for files
declared in a `knowledge_sources.yml` manifest. The adapter has no I/O of
its own — transport (stdio, SSE, HTTP) is the host's responsibility.

## Security contract

MCP servers run with the *server's* credentials, not the caller's.
`caller_clearance` is therefore a **required parameter on every request**.
The server returns -32600 (access denied) when it is absent.

The three clearance tiers (`public < internal < restricted`) match spec 0058's
`ACCESS_LEVELS`. `ACCESS_RANK` in `contract.py` is the enforcement constant —
not a comment in a spec.

Additional invariants (spec RISK-001 – RISK-004):

- Resource content is scanned for credential-shaped strings before delivery;
  detection raises `ValueError` before any text is served.
- A restricted resource always returns -32600 whether or not the file exists
  (to prevent existence probing by lower-clearance callers).
- File paths are resolved and checked against the declared source root before
  any read (path-traversal protection).

## Usage

```python
from quantsmith.adapters.mcp_servers.knowledge_resources import dispatch
from pathlib import Path

response = dispatch(
    {
        "jsonrpc": "2.0",
        "method": "resources/list",
        "id": 1,
        "params": {"caller_clearance": "internal"},
    },
    sources_config_path=Path("knowledge_sources.yml"),
)
# response is a JSON-serializable dict — pass to json.dumps() before sending
```

## Files

| File | Purpose |
| --- | --- |
| `contract.py` | Shared types: clearance constants, `KnowledgeUri`, `McpRequest/Response`, `clearance_allows`, `contains_secret` |
| `knowledge_resources.py` | Resources server: `parse_sources_config`, `list_resources`, `read_resource`, `dispatch` — `sources` authority |
| `memory_resources.py` | Resources server: `dispatch_memory`, `list_memory_resources`, `read_memory_resource` — `memory` authority (spec 0053) |
| `market_research_resources.py` | Resources server: `dispatch_market_research`, `list_market_research_resources`, `read_market_research_resource` — `market_research` authority (spec 0056 T-003) |
| `adapter_contract.md` | Full contract spec — inputs, outputs, error codes, URI scheme |

## URI scheme

```
knowledge://<authority>/<path>
```

| Authority | Status | Served by |
| --- | --- | --- |
| `sources` | Live (0052) | `knowledge_resources.dispatch` — files from `knowledge_sources.yml` |
| `memory` | Live (0053) | `memory_resources.dispatch_memory` — `workflow_memory.Record` objects |
| `market_research` | Live (0056 T-003) | `market_research_resources.dispatch_market_research` — `market_research.MarketResearchItem` objects |

## Downstream specs

- **0054** — RAG server: semantic search with citations, one index per access
  tier, no post-retrieval leakage. Uses the same adapter contract.
