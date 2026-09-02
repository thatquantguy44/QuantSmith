"""Knowledge Resources Server — spec 0052.

Implements the MCP ``resources`` primitive for files declared in
``knowledge_sources.yml``. Every public function is pure I/O except for file
reads; no network, no state mutation.

Usage::

    from quantsmith.adapters.mcp_servers.knowledge_resources import dispatch
    from pathlib import Path

    raw_response = dispatch(
        {"jsonrpc": "2.0", "method": "resources/list", "id": 1,
         "params": {"caller_clearance": "internal"}},
        sources_config_path=Path("knowledge_sources.yml"),
    )
    # raw_response is a JSON-serializable dict

The host is responsible for JSON (de)serialization, transport (stdio / SSE),
and process management. This module has no I/O beyond file reads.

**Security invariants** (see spec RISK-001 – RISK-004):

- ``caller_clearance`` is required; absent → -32600 before any I/O.
- A restricted resource returns -32600 whether or not the file exists.
- ``contains_secret()`` is called before any content is returned.
- ``Path.resolve()`` + prefix check prevents traversal outside the source root.
"""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .contract import (
    AUTHORITY_SOURCES,
    ERR_ACCESS_DENIED,
    ERR_METHOD_NOT_FOUND,
    ERR_NOT_FOUND,
    KNOWN_AUTHORITIES,
    METHOD_LIST,
    METHOD_READ,
    SUPPORTED_CLEARANCES,
    SUPPORTED_METHODS,
    KnowledgeUri,
    McpResponse,
    ResourceContent,
    ResourceMeta,
    clearance_allows,
    contains_secret,
    error_response,
    parse_request,
)


# ---------------------------------------------------------------------------
# Source manifest types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceEntry:
    """One entry from ``knowledge_sources.yml``."""

    name: str
    path: str
    access_level: str = "internal"
    include: Tuple[str, ...] = field(default_factory=tuple)
    exclude: Tuple[str, ...] = field(default_factory=tuple)
    freshness_days: int = 90
    domains_from_subfolders: bool = False


# ---------------------------------------------------------------------------
# Subset YAML parser for knowledge_sources.yml
# ---------------------------------------------------------------------------

def _parse_flow_sequence(val: str) -> List[str]:
    """Parse an inline YAML flow sequence: ``["*.md", "*.txt"]`` → list."""
    inner = val[1:-1].strip()
    if not inner:
        return []
    items = []
    for part in inner.split(","):
        item = part.strip().strip('"').strip("'")
        if item:
            items.append(item)
    return items


def _parse_scalar(val: str) -> Any:
    """Parse a YAML scalar: bool, int, flow-sequence, or string."""
    stripped = val.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        return _parse_flow_sequence(stripped)
    if stripped.lower() == "true":
        return True
    if stripped.lower() == "false":
        return False
    try:
        return int(stripped)
    except ValueError:
        pass
    return stripped.strip('"').strip("'")


def parse_sources_config(path: Path) -> List[SourceEntry]:
    """Parse a ``knowledge_sources.yml`` file into ``SourceEntry`` objects.

    Only the inline flow-sequence syntax (``["*.md"]``) is supported for
    ``include`` and ``exclude``; block sequences are not (see spec Assumptions).
    Raises ``ValueError`` with file + line on malformed input.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"cannot read sources config {path}: {exc}") from exc

    sources: List[SourceEntry] = []
    current: Optional[Dict[str, Any]] = None
    in_sources = False

    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if not in_sources:
            if stripped == "sources:":
                in_sources = True
            continue

        if stripped.startswith("- "):
            if current is not None:
                sources.append(_entry_from_dict(current, path, lineno))
            current = {}
            rest = stripped[2:].strip()
            if ":" in rest:
                key, _, val = rest.partition(":")
                current[key.strip()] = _parse_scalar(val.strip())
        elif ":" in stripped and current is not None:
            key, _, val = stripped.partition(":")
            current[key.strip()] = _parse_scalar(val.strip())
        elif stripped and current is None:
            raise ValueError(
                f"{path}:{lineno}: unexpected content outside a sources list entry"
            )

    if current is not None:
        sources.append(_entry_from_dict(current, path, len(lines)))

    return sources


def _entry_from_dict(d: Dict[str, Any], path: Path, lineno: int) -> SourceEntry:
    if "name" not in d:
        raise ValueError(f"{path}:{lineno}: source entry missing 'name'")
    if "path" not in d:
        raise ValueError(f"{path}:{lineno}: source entry missing 'path'")
    include = d.get("include", [])
    exclude = d.get("exclude", [])
    return SourceEntry(
        name=str(d["name"]),
        path=str(d["path"]),
        access_level=str(d.get("access_level", "internal")),
        include=tuple(include) if isinstance(include, list) else (),
        exclude=tuple(exclude) if isinstance(exclude, list) else (),
        freshness_days=int(d.get("freshness_days", 90)),
        domains_from_subfolders=bool(d.get("domains_from_subfolders", False)),
    )


# ---------------------------------------------------------------------------
# File discovery helpers
# ---------------------------------------------------------------------------

def _matches_patterns(rel_path: str, patterns: Tuple[str, ...]) -> bool:
    """Return True if ``rel_path`` matches any of the glob ``patterns``."""
    if not patterns:
        return False
    for pat in patterns:
        if fnmatch.fnmatch(rel_path, pat) or fnmatch.fnmatch(os.path.basename(rel_path), pat):
            return True
    return False


def _iter_source_files(
    source: SourceEntry,
    base_path: Optional[Path],
) -> List[Tuple[Path, str]]:
    """Return ``(absolute_file_path, relative_path_str)`` for all matching files.

    ``base_path`` is prepended to relative ``source.path`` values.
    """
    root = Path(source.path)
    if not root.is_absolute() and base_path is not None:
        root = base_path / root
    if not root.exists():
        return []

    results: List[Tuple[Path, str]] = []
    for dirpath, _dirs, filenames in os.walk(root):
        for fname in filenames:
            abs_path = Path(dirpath) / fname
            try:
                rel = str(abs_path.relative_to(root))
            except ValueError:
                continue

            if source.include and not _matches_patterns(rel, source.include):
                continue
            if source.exclude and _matches_patterns(rel, source.exclude):
                continue

            results.append((abs_path, rel))

    return results


# ---------------------------------------------------------------------------
# List and read handlers
# ---------------------------------------------------------------------------

def list_resources(
    sources: List[SourceEntry],
    caller_clearance: str,
    base_path: Optional[Path] = None,
) -> List[ResourceMeta]:
    """Return metadata for all files the caller's clearance permits (REQ-003).

    Output is sorted by URI for determinism (NFR-002).
    """
    metas: List[ResourceMeta] = []
    for source in sources:
        if not clearance_allows(source.access_level, caller_clearance):
            continue
        for _abs, rel in _iter_source_files(source, base_path):
            uri = str(KnowledgeUri(authority=AUTHORITY_SOURCES, path=f"{source.name}/{rel}"))
            metas.append(ResourceMeta(
                uri=uri,
                name=os.path.basename(rel),
                description=source.name,
                mime_type="text/plain",
                access_level=source.access_level,
            ))
    metas.sort(key=lambda m: m.uri)
    return metas


def read_resource(
    sources: List[SourceEntry],
    uri: str,
    caller_clearance: str,
    base_path: Optional[Path] = None,
) -> ResourceContent:
    """Return content for ``uri`` when ``caller_clearance`` permits (REQ-004).

    Raises ``PermissionError`` on clearance failure (RISK-003: same error
    whether the file exists or not, so the caller cannot probe for restricted
    resource existence). Raises ``FileNotFoundError`` for genuinely missing
    files (after clearance passes). Raises ``ValueError`` on credential content
    (RISK-002) or path traversal (RISK-004).
    """
    try:
        ku = KnowledgeUri.parse(uri)
    except ValueError:
        raise FileNotFoundError(f"invalid URI: {uri!r}")

    if ku.authority != AUTHORITY_SOURCES:
        raise FileNotFoundError(f"authority {ku.authority!r} not handled here")

    # URI path: <source_name>/<relative_path>
    if "/" not in ku.path:
        raise FileNotFoundError(f"URI missing source name component: {uri!r}")
    source_name, rel_path = ku.path.split("/", 1)

    source = next((s for s in sources if s.name == source_name), None)
    if source is None:
        # Treat unknown source as access denied (RISK-003: don't reveal structure)
        raise PermissionError(f"access denied: {uri!r}")

    # Clearance check — same error for restricted resources regardless of file
    # existence (RISK-003).
    if not clearance_allows(source.access_level, caller_clearance):
        raise PermissionError(f"access denied: {uri!r}")

    root = Path(source.path)
    if not root.is_absolute() and base_path is not None:
        root = base_path / root

    # Path-traversal check (RISK-004)
    try:
        resolved = (root / rel_path).resolve()
        resolved_root = root.resolve()
    except OSError as exc:
        raise ValueError(f"cannot resolve path for {uri!r}: {exc}") from exc

    if not str(resolved).startswith(str(resolved_root)):
        raise ValueError(f"path traversal detected in URI: {uri!r}")

    if not resolved.exists():
        raise FileNotFoundError(f"resource not found: {uri!r}")

    try:
        text = resolved.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise FileNotFoundError(f"cannot read resource {uri!r}: {exc}") from exc

    # Credential scan before delivery (RISK-002, REQ-007)
    if contains_secret(text):
        raise ValueError(f"resource {uri!r} contains a credential-shaped value; not served")

    return ResourceContent(uri=uri, text=text, mime_type="text/plain")


# ---------------------------------------------------------------------------
# Dispatch — the single public entry point
# ---------------------------------------------------------------------------

def dispatch(
    message: Dict[str, Any],
    *,
    sources_config_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Dispatch a JSON-RPC 2.0 message to the knowledge resources server.

    Returns a JSON-serializable dict.  No I/O except file reads.

    ``sources_config_path`` is required for ``resources/list`` and
    ``resources/read``; pass the path to ``knowledge_sources.yml`` (REQ-011).
    """
    # Parse envelope
    try:
        req = parse_request(message)
    except ValueError as exc:
        return error_response(message.get("id"), ERR_ACCESS_DENIED, str(exc)).to_dict()

    # caller_clearance required on every request (REQ-002, RISK-001)
    clearance = req.caller_clearance
    if not clearance:
        return error_response(req.id, ERR_ACCESS_DENIED, "caller_clearance is required").to_dict()
    if clearance not in SUPPORTED_CLEARANCES:
        return error_response(
            req.id, ERR_ACCESS_DENIED,
            f"unrecognized caller_clearance {clearance!r}; expected one of {SUPPORTED_CLEARANCES}"
        ).to_dict()

    # Method routing
    if req.method not in SUPPORTED_METHODS:
        # Check if the authority is known but method is unsupported
        return error_response(req.id, ERR_METHOD_NOT_FOUND, f"method {req.method!r} not supported").to_dict()

    # Load sources config
    sources: List[SourceEntry] = []
    if sources_config_path is not None:
        try:
            sources = parse_sources_config(sources_config_path)
        except ValueError as exc:
            return error_response(req.id, ERR_ACCESS_DENIED, str(exc)).to_dict()

    if req.method == METHOD_LIST:
        metas = list_resources(sources, clearance)
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

    # Check authority first (REQ-008)
    try:
        ku = KnowledgeUri.parse(uri)
    except ValueError:
        return error_response(req.id, ERR_NOT_FOUND, f"invalid URI: {uri!r}").to_dict()

    if ku.authority not in KNOWN_AUTHORITIES:
        return error_response(req.id, ERR_NOT_FOUND, f"unknown authority {ku.authority!r}").to_dict()

    if ku.authority != AUTHORITY_SOURCES:
        hints = {
            "memory": "use memory_resources.dispatch_memory (spec 0053)",
            "market_research": "use market_research_resources.dispatch_market_research (spec 0056 T-003)",
        }
        hint = hints.get(ku.authority, "reserved for a future spec")
        return error_response(
            req.id, ERR_NOT_FOUND,
            f"authority {ku.authority!r} not handled here — {hint}"
        ).to_dict()

    try:
        content = read_resource(sources, uri, clearance)
    except PermissionError as exc:
        return error_response(req.id, ERR_ACCESS_DENIED, str(exc)).to_dict()
    except (FileNotFoundError, ValueError) as exc:
        code = ERR_NOT_FOUND if isinstance(exc, FileNotFoundError) else ERR_ACCESS_DENIED
        return error_response(req.id, code, str(exc)).to_dict()

    return McpResponse(
        id=req.id,
        result={
            "contents": [
                {"uri": content.uri, "text": content.text, "mimeType": content.mime_type}
            ]
        },
    ).to_dict()
