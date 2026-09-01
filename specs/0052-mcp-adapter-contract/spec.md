# Spec: MCP Adapter Contract + Knowledge Resources Server

- **ID:** 0052-mcp-adapter-contract
- **Status:** Draft
- **Author:** QuantSmith
- **Last updated:** 2026-09-01

> WHAT and WHY only. No implementation detail — that belongs in `plan.md`.

## Problem & Context

QuantSmith agents retrieve knowledge from committed Markdown files, the 0048
workflow memory store, and the 0056 market-research catalog. Today those calls
are internal function calls, which works when agent and storage are co-located.
A team-scale deployment routes agents through MCP (Model Context Protocol)
clients, which expect a JSON-RPC 2.0 server that speaks the `resources`
primitive.

The architectural hazard is well-documented in `docs/handoff.md` (item 17): MCP
servers run with the *server's* credentials, not the caller's. A naive
implementation serves `restricted` content to any caller who can open a socket,
because clearance is never checked at the protocol layer. For an MNPI-adjacent
shop this is the difference between a compliance story and a compliance incident.

This spec establishes the adapter contract that 0053 (memory/knowledge-graph
server) and 0054 (RAG server) will share, and implements the resources primitive
that reads files declared in `knowledge_sources.yml`.

## Goals

1. Establish a typed, stdlib-only adapter contract for JSON-RPC 2.0 MCP
   `resources` messages that 0053 and 0054 can share without modification.
2. Implement the resources primitive server: reads `knowledge_sources.yml`,
   lists and reads text/Markdown files, enforces `caller_clearance` on every
   request.
3. Establish the `knowledge://` URI scheme so 0053, 0054, and 0056's MCP
   namespace share one scheme without collisions.

## Non-Goals

- MCP transport (stdio, SSE, HTTP+SSE): the adapter has no I/O; transport is
  injected. Standing up a live MCP server process is the adopter's task.
- The memory/knowledge-graph server (0053) and RAG server (0054).
- Binary file content (PDF, DOCX): URIs are listed; content delivery is 0054's
  scope.
- Writing or mutating resources (read-only server).
- Server-side authentication or TLS (host's responsibility).
- Multi-store federation or cross-authority search.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The adapter MUST define JSON-RPC 2.0 message types as stdlib frozen dataclasses only; no `mcp` package dependency is introduced. | must |
| REQ-002 | Every request MUST carry a `caller_clearance` parameter; the server MUST return a JSON-RPC error with code -32600 for requests that omit it or supply an unrecognized value. | must |
| REQ-003 | The server MUST implement `resources/list`, returning metadata for every resource whose `access_level` is within the caller's clearance, and no others. | must |
| REQ-004 | The server MUST implement `resources/read`, returning a resource's text content when the caller's clearance permits; returning an error otherwise. | must |
| REQ-005 | The adapter MUST adopt the `knowledge://<authority>/<path>` URI scheme; the current authorities are `sources`, `memory`, and `market_research`. | must |
| REQ-006 | The server MUST route `knowledge://sources/...` URIs to entries declared in `knowledge_sources.yml` and serve matching files. | must |
| REQ-007 | The server MUST scan resource content for credential-shaped text before serving; detection MUST raise before any content is delivered. | must |
| REQ-008 | An unrecognized URI authority in `resources/read` MUST produce a JSON-RPC error with code -32604. | must |
| REQ-009 | An unsupported JSON-RPC method MUST produce an error with code -32601. | must |
| REQ-010 | A caller requesting a `restricted` resource without `restricted` clearance MUST receive error -32600; the response MUST NOT disclose whether the resource exists. | must |
| REQ-011 | The `knowledge_sources.yml` path MUST be a caller-supplied parameter; no path is hard-coded in the adapter. | must |
| REQ-012 | The server MUST reject a file path that resolves outside the declared source root (path-traversal protection). | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Standard library only. | No new entry in `pyproject.toml`. |
| NFR-002 | Deterministic output for identical inputs. | Same request → same response, stable list order. |
| NFR-003 | Clearance rank order (public < internal < restricted) is stated as a named constant in code, not only in the spec. | Code-level invariant. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a JSON-RPC request missing `caller_clearance`, when dispatched, then the response error code is -32600. | REQ-002 |
| AC-002 | Given `resources/list` with `caller_clearance: internal`, when dispatched, then every returned resource has `access_level` in `{public, internal}` and no `restricted` resource appears. | REQ-003 |
| AC-003 | Given `resources/list` with `caller_clearance: public`, when dispatched, then only `public` resources are listed. | REQ-003 |
| AC-004 | Given `resources/read` for `knowledge://sources/<name>/<file>` with sufficient clearance, when dispatched, then the returned text matches the file's content. | REQ-004, REQ-006 |
| AC-005 | Given `resources/read` for `knowledge://unknown/foo`, when dispatched, then the response error code is -32604. | REQ-008 |
| AC-006 | Given `resources/read` for a `restricted` resource with `caller_clearance: internal`, when dispatched, then the response error code is -32600 and the resource text is absent. | REQ-010 |
| AC-007 | Given resource file content containing the string `api_key=secret123`, when dispatched, then dispatch raises `ValueError` before any content is delivered. | REQ-007 |
| AC-008 | Given an unsupported method `memory/query`, when dispatched, then the response error code is -32601. | REQ-009 |
| AC-009 | Given `resources/read` for a URI that maps to a nonexistent file, when dispatched, then the response error code is -32604. | REQ-004 |
| AC-010 | Given a file path component `../../etc/passwd` in a URI, when dispatched, then dispatch raises before reading the file. | REQ-012 |
| AC-011 | Given `resources/list` with `caller_clearance: restricted`, when dispatched, then resources of all three access levels may appear. | REQ-003, NFR-003 |

## Data & Dependencies

- **`templates/knowledge/knowledge_sources.yml`** — the schema for source manifests this server parses.
- **`src/quantsmith/adapters/alert_delivery/result.py`** — pattern source for `contains_secret()` and the frozen-dataclass contract approach.
- **`src/quantsmith/pipelines/access_control.py`** — defines `ACCESS_LEVELS`; this spec reuses those same three values (`public`, `internal`, `restricted`) and does not introduce new ones.
- **0048 workflow memory runtime** — 0053 will call `load_store`/`query` through the same adapter contract this spec defines; no dependency in this spec.
- **0056 market research** — 0054 will call `market_research.py` through the same adapter contract; no dependency in this spec.

No private data in the adapter itself. Resource content comes from the adopter's file system; the spec requires a credential scan before delivery (REQ-007).

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | MCP servers run with the server's credentials, not the caller's. A shared resources server reachable by the whole team serves `restricted` content to any caller who can open a connection. | Compliance incident for an MNPI-adjacent team. | `caller_clearance` is a required parameter; the server denies -32600 when it is absent. The clearance rank is in code (NFR-003), not only in the spec. |
| RISK-002 | A resource file containing a credential-shaped value leaks a secret over MCP. | Credential exposure via knowledge-base retrieval. | `contains_secret()` check before serving any resource text; raises on detection, never serves (REQ-007). |
| RISK-003 | Returning -32604 (not found) for a restricted resource reveals that it exists, leaking metadata. | Metadata leakage of restricted resource existence. | Restricted resources always return -32600 regardless of existence (REQ-010). |
| RISK-004 | A crafted URI with `..` traverses outside the declared source root. | Arbitrary file read. | `Path.resolve()` + prefix check before any file read (REQ-012). |

## Assumptions & Open Questions

- Assumption: `knowledge_sources.yml` uses the inline flow-sequence syntax for `include`/`exclude` (matching the committed template). Block-sequence syntax is not supported in this spec's parser; adopters who need it can convert.
- Assumption: The three access levels from spec 0058 (`public`/`internal`/`restricted`) cover all 0052 use cases; a fourth tier would require a new spec.
- Open question: Should `resources/list` support pagination for large source trees? Deferred to 0054; 0052's sources are expected to be small (< 1 000 files).

## Exceptions

None.
