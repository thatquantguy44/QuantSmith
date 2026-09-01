# Adapter Contract: MCP Knowledge Resources Server

**Spec:** `0052-mcp-adapter-contract`
**Last updated:** 2026-09-01

## Overview

A JSON-RPC 2.0 server that implements the MCP `resources` primitive for files
declared in `knowledge_sources.yml`. Pure library; transport is injected by
the host.

## Input

Every request must be a JSON-RPC 2.0 object with `caller_clearance` in
`params`.

### `resources/list`

```json
{
  "jsonrpc": "2.0",
  "method": "resources/list",
  "id": <any>,
  "params": {
    "caller_clearance": "public" | "internal" | "restricted"
  }
}
```

### `resources/read`

```json
{
  "jsonrpc": "2.0",
  "method": "resources/read",
  "id": <any>,
  "params": {
    "caller_clearance": "public" | "internal" | "restricted",
    "uri": "knowledge://sources/<source_name>/<relative_path>"
  }
}
```

## Output

### `resources/list` success

```json
{
  "jsonrpc": "2.0",
  "id": <any>,
  "result": {
    "resources": [
      {
        "uri": "knowledge://sources/<source_name>/<relative_path>",
        "name": "<filename>",
        "description": "<source_name>",
        "mimeType": "text/plain",
        "access_level": "public" | "internal" | "restricted"
      }
    ]
  }
}
```

Resources are sorted by URI. Only resources the caller's clearance permits
are included.

### `resources/read` success

```json
{
  "jsonrpc": "2.0",
  "id": <any>,
  "result": {
    "contents": [
      {
        "uri": "knowledge://sources/<source_name>/<relative_path>",
        "text": "<file_content>",
        "mimeType": "text/plain"
      }
    ]
  }
}
```

## Errors

| Code | Meaning | Trigger |
| --- | --- | --- |
| -32600 | Access denied / Invalid Request | Missing or unrecognized `caller_clearance`; insufficient clearance for resource |
| -32601 | Method Not Found | Unsupported JSON-RPC method |
| -32604 | Not Found | Unknown URI authority; resource file not found |
| -32700 | Parse Error | Malformed JSON-RPC envelope |

**Note:** A `restricted` resource always returns -32600 regardless of whether
the file exists. This prevents existence probing by lower-clearance callers.

## URI Scheme

```
knowledge://<authority>/<path>
```

| Authority | Description |
| --- | --- |
| `sources` | Files from `knowledge_sources.yml` entries (0052) |
| `memory` | Workflow memory records (0053 — reserved) |
| `market_research` | Market research catalog (0056/0054 — reserved) |

## `knowledge_sources.yml` format (subset)

```yaml
sources:
  - name: <source_name>         # required; used in URIs
    path: /abs/path/or/relative  # required; resolved relative to config file
    access_level: internal        # public | internal | restricted
    include: ["*.md", "*.txt"]    # inline flow-sequence only
    exclude: ["**/drafts/**"]     # inline flow-sequence only
    freshness_days: 90            # advisory; not enforced here
    domains_from_subfolders: true # advisory metadata
```

Only inline flow-sequence syntax (`["*.md"]`) is supported for `include` and
`exclude`. Block sequences are not.

## Security Invariants

1. `caller_clearance` is required; absent → -32600 before any I/O.
2. `ACCESS_RANK = {public: 0, internal: 1, restricted: 2}` is the enforcement
   constant in code (`contract.py:ACCESS_RANK`), not only in documentation.
3. `contains_secret()` is called before any resource content is returned;
   credential-shaped content raises `ValueError`, never serves.
4. File path is resolved with `Path.resolve()` and checked against the source
   root before any read; path traversal raises `ValueError`.
5. Restricted resource existence is not revealed to lower-clearance callers.
