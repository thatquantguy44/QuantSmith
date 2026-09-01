"""Market Research Resources Server — spec 0056 T-003.

Implements the MCP ``resources`` primitive for the ``knowledge://market_research/...``
authority, wiring the 0052 adapter contract to the 0056 market-research catalog.

Usage::

    from quantsmith.adapters.mcp_servers.market_research_resources import (
        dispatch_market_research,
    )
    from quantsmith.pipelines.market_research import InMemoryResearchCatalog

    catalog = InMemoryResearchCatalog()
    # ... populate catalog ...

    raw_response = dispatch_market_research(
        {"jsonrpc": "2.0", "method": "resources/list", "id": 1,
         "params": {"caller_clearance": "internal"}},
        catalog=catalog,
    )

The host is responsible for JSON (de)serialization and transport. This module
has no I/O of its own.

**Governance invariants:**

- ``caller_clearance`` is required; absent → -32600 (RISK-001 from 0052).
- Governance check (clearance + entitlement + status) runs via
  ``market_research.check_governance`` before any content is served.
- Restricted item existence is never revealed to denied callers (-32600
  regardless of whether the item exists, mirroring 0052 RISK-003).
- Resource text is a citation summary, never raw licensed content.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .contract import (
    AUTHORITY_MARKET_RESEARCH,
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


def _import_market_research():  # type: ignore[return]
    """Lazy import to avoid hard coupling in specs that don't use this handler."""
    from quantsmith.pipelines.market_research import (  # type: ignore[import]
        ResearchCatalog,
        check_governance,
        render_citation,
    )
    return ResearchCatalog, check_governance, render_citation


def _citation_text(item: Any) -> str:
    """Render a short text summary of a market research item for MCP delivery."""
    return (
        f"[{item.source_type}] {item.title}\n"
        f"Author/Publisher: {item.author_or_publisher}\n"
        f"Published: {item.published_at}\n"
        f"Confidentiality: {item.confidentiality}\n"
        f"Entitlement: {item.entitlement_class}\n"
        f"URI: {item.knowledge_uri}\n"
        f"Status: {item.status}"
    )


def list_market_research_resources(
    catalog: Any,
    caller_clearance: str,
    caller_entitlements: Tuple[str, ...] = (),
) -> List[ResourceMeta]:
    """Return metadata for all market-research items the caller may access.

    Applies ``check_governance`` per item; denied items are silently excluded
    (not leaked as "access denied" entries). Sorted by URI.
    """
    _, check_governance, _ = _import_market_research()

    metas: List[ResourceMeta] = []
    for item in catalog.search():
        decision = check_governance(
            item,
            caller_clearance=caller_clearance,
            entitlements=caller_entitlements,
        )
        if not decision.allowed:
            continue
        metas.append(ResourceMeta(
            uri=item.knowledge_uri,
            name=item.title,
            description=f"{item.source_type} · {item.asset_class}",
            mime_type="text/plain",
            access_level=item.confidentiality,
        ))
    metas.sort(key=lambda m: m.uri)
    return metas


def read_market_research_resource(
    catalog: Any,
    uri: str,
    caller_clearance: str,
    caller_entitlements: Tuple[str, ...] = (),
) -> ResourceContent:
    """Return a citation summary for the market-research item at ``uri``.

    Raises ``PermissionError`` on denied access (same error whether or not the
    item exists — RISK-003 from 0052). Raises ``FileNotFoundError`` for genuinely
    missing items (after governance passes).
    """
    _, check_governance, render_citation = _import_market_research()

    # Parse and validate the URI
    try:
        ku = KnowledgeUri.parse(uri)
    except ValueError:
        raise FileNotFoundError(f"invalid URI: {uri!r}")

    if ku.authority != AUTHORITY_MARKET_RESEARCH:
        raise FileNotFoundError(f"wrong authority: {ku.authority!r}")

    # Extract item_id from the path: <asset_class>/<source_type>/<item_id>
    # or <asset_class>/<source_type>/<thread_id>/<message_id> for email
    parts = ku.path.split("/")
    if len(parts) < 3:
        raise FileNotFoundError(f"URI path too short to contain item_id: {uri!r}")
    item_id = parts[2]

    # Governance check first — same error whether item exists or not (RISK-003)
    item = catalog.get(item_id)
    if item is None:
        # Item doesn't exist; return access denied to avoid revealing that
        # restricted items don't exist in this catalog
        raise PermissionError(f"access denied: {uri!r}")

    decision = check_governance(
        item,
        caller_clearance=caller_clearance,
        entitlements=caller_entitlements,
    )
    if not decision.allowed:
        raise PermissionError(f"access denied ({decision.denial_class}): {uri!r}")

    citation = render_citation(item)
    text = _citation_text(item)

    return ResourceContent(uri=uri, text=text, mime_type="text/plain")


def dispatch_market_research(
    message: Dict[str, Any],
    *,
    catalog: Any,
    caller_entitlements: Tuple[str, ...] = (),
) -> Dict[str, Any]:
    """Dispatch a JSON-RPC 2.0 message to the market_research resources server.

    Returns a JSON-serializable dict. No I/O except catalog reads.

    ``catalog`` must be a ``ResearchCatalog`` (from ``market_research.py``) —
    it is always required for this handler (REQ-011 equivalent: the catalog path
    is caller-supplied, never hard-coded).
    ``caller_entitlements`` is an optional tuple of entitlement class strings
    the caller holds; defaults to empty (public access only).
    """
    try:
        req = parse_request(message)
    except ValueError as exc:
        return error_response(message.get("id"), ERR_ACCESS_DENIED, str(exc)).to_dict()

    # caller_clearance required on every request (RISK-001)
    clearance = req.caller_clearance
    if not clearance:
        return error_response(req.id, ERR_ACCESS_DENIED, "caller_clearance is required").to_dict()
    if clearance not in SUPPORTED_CLEARANCES:
        return error_response(
            req.id, ERR_ACCESS_DENIED,
            f"unrecognized caller_clearance {clearance!r}",
        ).to_dict()

    if req.method not in (METHOD_LIST, METHOD_READ):
        return error_response(req.id, ERR_METHOD_NOT_FOUND, f"method {req.method!r} not supported").to_dict()

    if req.method == METHOD_LIST:
        metas = list_market_research_resources(catalog, clearance, caller_entitlements)
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

    if ku.authority != AUTHORITY_MARKET_RESEARCH:
        return error_response(req.id, ERR_NOT_FOUND, f"authority {ku.authority!r} not handled by market_research server").to_dict()

    try:
        content = read_market_research_resource(catalog, uri, clearance, caller_entitlements)
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
