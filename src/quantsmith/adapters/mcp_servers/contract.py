"""Typed adapter contract for MCP (Model Context Protocol) knowledge servers.

Covers the ``resources`` primitive (spec 0052). The memory-graph (0053) and
RAG (0054) servers extend this contract without modifying it.

No ``mcp`` package dependency — all types are stdlib dataclasses (NFR-001).
Transport is injected by the host; this module has no I/O of its own.

**The clearance invariant (RISK-001):** MCP servers run with the *server's*
credentials, not the caller's. ``caller_clearance`` is therefore a *required*
parameter on every request. The server denies with -32600 when it is absent;
``ACCESS_RANK`` is the enforcement code, not just a comment in the spec (NFR-003).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Clearance levels — ordered weakest to strongest.
# Changing the strings or the rank requires a new spec; the rank is used as
# the access-control predicate, not the string itself.
# ---------------------------------------------------------------------------
PUBLIC = "public"
INTERNAL = "internal"
RESTRICTED = "restricted"

#: Enforcement constant — the rank, not the name, decides access.  NFR-003.
ACCESS_RANK: Dict[str, int] = {PUBLIC: 0, INTERNAL: 1, RESTRICTED: 2}

SUPPORTED_CLEARANCES: Tuple[str, ...] = (PUBLIC, INTERNAL, RESTRICTED)

# ---------------------------------------------------------------------------
# JSON-RPC 2.0 error codes
# ---------------------------------------------------------------------------
ERR_ACCESS_DENIED = -32600       # missing/insufficient clearance
ERR_METHOD_NOT_FOUND = -32601    # unknown method
ERR_PARSE_ERROR = -32700         # malformed envelope
ERR_NOT_FOUND = -32604           # resource or authority not found

# ---------------------------------------------------------------------------
# Supported MCP methods — resources primitive only (0052)
# ---------------------------------------------------------------------------
METHOD_LIST = "resources/list"
METHOD_READ = "resources/read"
SUPPORTED_METHODS: Tuple[str, ...] = (METHOD_LIST, METHOD_READ)

# ---------------------------------------------------------------------------
# knowledge:// URI scheme
# ---------------------------------------------------------------------------
URI_SCHEME = "knowledge"

# Authorities: sources (0052), memory (0053), market_research (0056/0054)
AUTHORITY_SOURCES = "sources"
AUTHORITY_MEMORY = "memory"
AUTHORITY_MARKET_RESEARCH = "market_research"
KNOWN_AUTHORITIES: Tuple[str, ...] = (
    AUTHORITY_SOURCES,
    AUTHORITY_MEMORY,
    AUTHORITY_MARKET_RESEARCH,
)


@dataclass(frozen=True)
class KnowledgeUri:
    """Parsed ``knowledge://<authority>/<path>`` URI."""

    authority: str
    path: str

    def __str__(self) -> str:
        return f"knowledge://{self.authority}/{self.path}"

    @classmethod
    def parse(cls, uri_str: str) -> "KnowledgeUri":
        if not uri_str.startswith("knowledge://"):
            raise ValueError(f"expected knowledge:// URI, got {uri_str!r}")
        rest = uri_str[len("knowledge://"):]
        if "/" in rest:
            authority, path = rest.split("/", 1)
        else:
            authority, path = rest, ""
        return cls(authority=authority, path=path)


@dataclass(frozen=True)
class ResourceMeta:
    """Metadata entry returned by ``resources/list``."""

    uri: str
    name: str
    description: str = ""
    mime_type: str = "text/plain"
    access_level: str = INTERNAL


@dataclass(frozen=True)
class ResourceContent:
    """Content returned by ``resources/read``."""

    uri: str
    text: str
    mime_type: str = "text/plain"


@dataclass(frozen=True)
class McpError:
    code: int
    message: str
    data: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            d["data"] = self.data
        return d


@dataclass(frozen=True)
class McpRequest:
    """Parsed JSON-RPC 2.0 request."""

    method: str
    id: Any
    params: Dict[str, Any] = field(default_factory=dict)
    jsonrpc: str = "2.0"

    @property
    def caller_clearance(self) -> Optional[str]:
        return self.params.get("caller_clearance")  # type: ignore[return-value]


@dataclass(frozen=True)
class McpResponse:
    """JSON-RPC 2.0 response."""

    id: Any
    result: Optional[Any] = None
    error: Optional[McpError] = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error is not None:
            d["error"] = self.error.to_dict()
        else:
            d["result"] = self.result
        return d


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clearance_allows(resource_level: str, caller_level: str) -> bool:
    """Return True when ``caller_level`` rank >= ``resource_level`` rank."""
    return ACCESS_RANK.get(caller_level, -1) >= ACCESS_RANK.get(resource_level, 99)


def parse_request(raw: Dict[str, Any]) -> McpRequest:
    """Parse a raw JSON-RPC dict into ``McpRequest``. Raises ``ValueError`` on malformed input."""
    method = raw.get("method", "")
    if not isinstance(method, str) or not method:
        raise ValueError("missing or non-string 'method' field")
    params = raw.get("params") or {}
    if not isinstance(params, dict):
        raise ValueError("'params' must be a JSON object")
    return McpRequest(
        jsonrpc=str(raw.get("jsonrpc", "2.0")),
        method=method,
        id=raw.get("id"),
        params=params,
    )


def error_response(req_id: Any, code: int, message: str) -> McpResponse:
    return McpResponse(id=req_id, error=McpError(code=code, message=message))


# ---------------------------------------------------------------------------
# Credential scan — mirrors adapters/alert_delivery/result.py
# ---------------------------------------------------------------------------
_SECRET_NEEDLES = (
    "api_key", "apikey", "secret_key", "client_secret", "aws_secret",
    "authorization: bearer ", "password=", "passwd=", "-----begin ",
)


def contains_secret(text: str) -> bool:
    """Return True when ``text`` contains a credential-shaped value (REQ-007)."""
    if not text:
        return False
    lowered = text.lower()
    return any(n in lowered for n in _SECRET_NEEDLES)
