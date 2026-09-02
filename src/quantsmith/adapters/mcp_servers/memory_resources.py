"""Memory-Graph Resources Server — spec 0053.

Implements the MCP ``resources`` primitive for the ``knowledge://memory/...``
authority, wiring the 0052 adapter contract to the 0048 workflow-memory
runtime (``workflow_memory.py``).

Usage::

    from quantsmith.adapters.mcp_servers.memory_resources import dispatch_memory
    from quantsmith.pipelines.workflow_memory import load_records

    records = load_records(text, file="memory/equity/index.yaml")
    resp = dispatch_memory(
        {"jsonrpc": "2.0", "method": "resources/list", "id": 1,
         "params": {"caller_clearance": "internal"}},
        records=records,
    )

The host is responsible for JSON (de)serialization, transport, and loading
records from YAML. This module has no I/O of its own.

**Governance invariants:**

- ``caller_clearance`` is required; absent → -32600 (RISK-001 from 0052).
- Clearance filtering uses ``clearance_allows`` from ``contract.py``, which
  enforces ``ACCESS_RANK`` (int comparison), never string equality (RISK-004).
- Restricted and missing records both return -32600 so callers cannot probe
  for existence of restricted records (RISK-003).
- Record text is a citation summary; raw YAML and evidence details are never
  included in the response (RISK-002).
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

from .contract import (
    AUTHORITY_MEMORY,
    ERR_ACCESS_DENIED,
    ERR_METHOD_NOT_FOUND,
    ERR_NOT_FOUND,
    KnowledgeUri,
    METHOD_LIST,
    METHOD_READ,
    SUPPORTED_CLEARANCES,
    McpResponse,
    ResourceContent,
    ResourceMeta,
    clearance_allows,
    error_response,
    parse_request,
)


def _citation_text(rec: Any) -> str:
    """Render a citation summary of a memory record for MCP delivery."""
    corroborated = len({e.get("source_run", "") for e in rec.evidence if e.get("source_run")})
    corr_str = f"{corroborated}×" if corroborated else "undeclared"
    uri = f"knowledge://memory/{rec.scope}/{rec.id}"
    return (
        f"[{rec.type}] {rec.scope}\n"
        f"ID: {rec.id}\n"
        f"Statement: {rec.statement}\n"
        f"Confidence: {rec.confidence} (corroborated {corr_str})\n"
        f"First seen: {rec.first_seen}  Last confirmed: {rec.last_confirmed}\n"
        f"Status: {rec.status}\n"
        f"PIT scope: {rec.pit_scope}\n"
        f"Access level: {rec.access_level}\n"
        f"URI: {uri}"
    )


def list_memory_resources(
    records: Sequence[Any],
    caller_clearance: str,
) -> List[ResourceMeta]:
    """Return metadata for all memory records the caller may access.

    Denied records are silently excluded (not named in the response). Sorted
    by URI for determinism (REQ-003, REQ-006).
    """
    metas: List[ResourceMeta] = []
    for rec in records:
        if not clearance_allows(rec.access_level, caller_clearance):
            continue
        uri = f"knowledge://memory/{rec.scope}/{rec.id}"
        metas.append(ResourceMeta(
            uri=uri,
            name=rec.id,
            description=f"{rec.type} · {rec.scope}",
            mime_type="text/plain",
            access_level=rec.access_level,
        ))
    metas.sort(key=lambda m: m.uri)
    return metas


def read_memory_resource(
    records: Sequence[Any],
    uri: str,
    caller_clearance: str,
) -> ResourceContent:
    """Return a citation summary for the memory record at ``uri``.

    Raises ``PermissionError`` if access is denied or the record does not exist
    — the same error in both cases so callers cannot probe for existence of
    restricted records (RISK-003 / REQ-005). Raises ``FileNotFoundError``
    only for malformed URIs or wrong authority, where existence masking does
    not apply.
    """
    try:
        ku = KnowledgeUri.parse(uri)
    except ValueError:
        raise FileNotFoundError(f"invalid URI: {uri!r}")

    if ku.authority != AUTHORITY_MEMORY:
        raise FileNotFoundError(f"wrong authority: {ku.authority!r}")

    # URI path: <scope>/<record_id>
    parts = ku.path.split("/")
    if len(parts) < 2:
        raise FileNotFoundError(f"URI path too short — expected <scope>/<id>: {uri!r}")

    record_id = parts[1]

    # Existence masking: look up the record first; if missing → PermissionError
    # (not FileNotFoundError) so caller cannot tell "denied" from "not found".
    rec = next((r for r in records if r.id == record_id), None)
    if rec is None:
        raise PermissionError(f"access denied: {uri!r}")

    if not clearance_allows(rec.access_level, caller_clearance):
        raise PermissionError(f"access denied ({rec.access_level}): {uri!r}")

    return ResourceContent(
        uri=uri,
        text=_citation_text(rec),
        mime_type="text/plain",
    )


def dispatch_memory(
    message: Dict[str, Any],
    *,
    records: Sequence[Any],
) -> Dict[str, Any]:
    """Dispatch a JSON-RPC 2.0 message to the memory resources server.

    Returns a JSON-serializable dict. No I/O — ``records`` must be
    pre-loaded by the caller (REQ-001, NFR-002).

    ``records`` is a sequence of ``workflow_memory.Record`` objects. The
    adapter does not import ``workflow_memory`` at the module level to avoid
    coupling specs that use only the adapter contract.
    """
    try:
        req = parse_request(message)
    except ValueError as exc:
        return error_response(message.get("id"), ERR_ACCESS_DENIED, str(exc)).to_dict()

    # caller_clearance required on every request (RISK-001, REQ-002)
    clearance = req.caller_clearance
    if not clearance:
        return error_response(req.id, ERR_ACCESS_DENIED, "caller_clearance is required").to_dict()
    if clearance not in SUPPORTED_CLEARANCES:
        return error_response(
            req.id, ERR_ACCESS_DENIED,
            f"unrecognized caller_clearance {clearance!r}",
        ).to_dict()

    if req.method not in (METHOD_LIST, METHOD_READ):
        return error_response(
            req.id, ERR_METHOD_NOT_FOUND,
            f"method {req.method!r} not supported",
        ).to_dict()

    if req.method == METHOD_LIST:
        metas = list_memory_resources(records, clearance)
        return McpResponse(
            id=req.id,
            result={
                "resources": [
                    {
                        "uri": m.uri,
                        "name": m.name,
                        "description": m.description,
                        "mimeType": m.mime_type,
                        "access_level": m.access_level,
                    }
                    for m in metas
                ]
            },
        ).to_dict()

    # METHOD_READ
    uri = req.params.get("uri", "")
    if not uri:
        return error_response(req.id, ERR_NOT_FOUND, "missing 'uri' parameter").to_dict()

    try:
        ku = KnowledgeUri.parse(uri)
    except ValueError:
        return error_response(req.id, ERR_NOT_FOUND, f"invalid URI: {uri!r}").to_dict()

    if ku.authority != AUTHORITY_MEMORY:
        return error_response(
            req.id, ERR_NOT_FOUND,
            f"authority {ku.authority!r} not handled by memory server",
        ).to_dict()

    try:
        content = read_memory_resource(records, uri, clearance)
    except PermissionError as exc:
        return error_response(req.id, ERR_ACCESS_DENIED, str(exc)).to_dict()
    except FileNotFoundError as exc:
        return error_response(req.id, ERR_NOT_FOUND, str(exc)).to_dict()

    return McpResponse(
        id=req.id,
        result={
            "contents": [
                {"uri": content.uri, "text": content.text, "mimeType": content.mime_type}
            ]
        },
    ).to_dict()
