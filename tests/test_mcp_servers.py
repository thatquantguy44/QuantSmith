"""Tests for spec 0052 — MCP adapter contract + knowledge resources server.

One test per acceptance criterion, named for the AC it verifies, so the
coverage map in ``specs/0052-mcp-adapter-contract/tasks.md`` can be checked
mechanically.

All fixtures are written to ``tmp_path``; nothing in the committed repo is
mutated. No live MCP server process is needed — ``dispatch`` is a pure function.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

from quantsmith.adapters.mcp_servers.contract import (
    ACCESS_RANK,
    ERR_ACCESS_DENIED,
    ERR_METHOD_NOT_FOUND,
    ERR_NOT_FOUND,
    INTERNAL,
    PUBLIC,
    RESTRICTED,
    KnowledgeUri,
    clearance_allows,
    contains_secret,
)
from quantsmith.adapters.mcp_servers.knowledge_resources import (
    SourceEntry,
    dispatch,
    list_resources,
    parse_sources_config,
    read_resource,
)
from quantsmith.adapters.mcp_servers.market_research_resources import (
    dispatch_market_research,
    list_market_research_resources,
    read_market_research_resource,
)
from quantsmith.pipelines.market_research import InMemoryResearchCatalog, MarketResearchItem


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_sources_yml(tmp_path: Path, entries: str) -> Path:
    p = tmp_path / "knowledge_sources.yml"
    p.write_text(f"sources:\n{entries}", encoding="utf-8")
    return p


def _make_file(tmp_path: Path, rel: str, content: str) -> Path:
    abs_path = tmp_path / rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(content, encoding="utf-8")
    return abs_path


def _req(method: str, params: Dict[str, Any], req_id: int = 1) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "method": method, "id": req_id, "params": params}


# ---------------------------------------------------------------------------
# AC-001: missing caller_clearance → -32600
# ---------------------------------------------------------------------------

def test_missing_clearance_returns_access_denied_AC_001(tmp_path: Path) -> None:
    yml = _make_sources_yml(tmp_path, "")
    resp = dispatch({"jsonrpc": "2.0", "method": "resources/list", "id": 1, "params": {}},
                    sources_config_path=yml)
    assert resp["error"]["code"] == ERR_ACCESS_DENIED


def test_unrecognized_clearance_returns_access_denied_AC_001(tmp_path: Path) -> None:
    yml = _make_sources_yml(tmp_path, "")
    resp = dispatch(_req("resources/list", {"caller_clearance": "secret"}),
                    sources_config_path=yml)
    assert resp["error"]["code"] == ERR_ACCESS_DENIED


# ---------------------------------------------------------------------------
# AC-002: internal clearance excludes restricted resources
# ---------------------------------------------------------------------------

def test_list_internal_clearance_excludes_restricted_AC_002(tmp_path: Path) -> None:
    src = tmp_path / "docs"
    src.mkdir()
    (src / "public.md").write_text("public content")
    (src / "secret.md").write_text("secret content")

    restricted_src = tmp_path / "classified"
    restricted_src.mkdir()
    (restricted_src / "mnpi.md").write_text("mnpi content")

    yml = _make_sources_yml(tmp_path, (
        f'  - name: open_docs\n'
        f'    path: {src}\n'
        f'    access_level: internal\n'
        f'    include: ["*.md"]\n'
        f'  - name: classified_docs\n'
        f'    path: {restricted_src}\n'
        f'    access_level: restricted\n'
        f'    include: ["*.md"]\n'
    ))
    resp = dispatch(_req("resources/list", {"caller_clearance": INTERNAL}),
                    sources_config_path=yml)
    assert "error" not in resp
    uris = [r["uri"] for r in resp["result"]["resources"]]
    assert all("classified_docs" not in u for u in uris), "restricted source leaked to internal caller"
    assert any("open_docs" in u for u in uris)


# ---------------------------------------------------------------------------
# AC-003: public clearance lists only public resources
# ---------------------------------------------------------------------------

def test_list_public_clearance_only_public_AC_003(tmp_path: Path) -> None:
    pub_src = tmp_path / "public"
    pub_src.mkdir()
    (pub_src / "doc.md").write_text("public doc")
    int_src = tmp_path / "internal"
    int_src.mkdir()
    (int_src / "doc.md").write_text("internal doc")

    yml = _make_sources_yml(tmp_path, (
        f'  - name: pub\n    path: {pub_src}\n    access_level: public\n    include: ["*.md"]\n'
        f'  - name: internal\n    path: {int_src}\n    access_level: internal\n    include: ["*.md"]\n'
    ))
    resp = dispatch(_req("resources/list", {"caller_clearance": PUBLIC}),
                    sources_config_path=yml)
    assert "error" not in resp
    uris = [r["uri"] for r in resp["result"]["resources"]]
    assert all("pub/" in u for u in uris), f"non-public URI found: {uris}"


# ---------------------------------------------------------------------------
# AC-004: resources/read returns file content
# ---------------------------------------------------------------------------

def test_read_resource_returns_file_content_AC_004(tmp_path: Path) -> None:
    src = tmp_path / "kb"
    src.mkdir()
    (src / "note.md").write_text("# Hello\nThis is a note.")

    yml = _make_sources_yml(tmp_path, (
        f'  - name: kb\n    path: {src}\n    access_level: internal\n    include: ["*.md"]\n'
    ))
    uri = "knowledge://sources/kb/note.md"
    resp = dispatch(_req("resources/read", {"caller_clearance": INTERNAL, "uri": uri}),
                    sources_config_path=yml)
    assert "error" not in resp, resp
    contents = resp["result"]["contents"]
    assert len(contents) == 1
    assert "Hello" in contents[0]["text"]
    assert contents[0]["uri"] == uri


# ---------------------------------------------------------------------------
# AC-005: unknown authority → -32604
# ---------------------------------------------------------------------------

def test_unknown_authority_returns_not_found_AC_005(tmp_path: Path) -> None:
    yml = _make_sources_yml(tmp_path, "")
    resp = dispatch(
        _req("resources/read", {"caller_clearance": INTERNAL, "uri": "knowledge://unknown/foo"}),
        sources_config_path=yml,
    )
    assert resp["error"]["code"] == ERR_NOT_FOUND


# ---------------------------------------------------------------------------
# AC-006: restricted resource denied to internal caller
# ---------------------------------------------------------------------------

def test_restricted_resource_denied_to_internal_AC_006(tmp_path: Path) -> None:
    src = tmp_path / "classified"
    src.mkdir()
    (src / "mnpi.md").write_text("MNPI content here")

    yml = _make_sources_yml(tmp_path, (
        f'  - name: classified\n    path: {src}\n    access_level: restricted\n    include: ["*.md"]\n'
    ))
    uri = "knowledge://sources/classified/mnpi.md"
    resp = dispatch(
        _req("resources/read", {"caller_clearance": INTERNAL, "uri": uri}),
        sources_config_path=yml,
    )
    assert resp["error"]["code"] == ERR_ACCESS_DENIED
    # Response must not contain the file's text
    assert "MNPI" not in str(resp)


# ---------------------------------------------------------------------------
# AC-007: credential in content raises before delivery
# ---------------------------------------------------------------------------

def test_credential_in_content_raises_AC_007(tmp_path: Path) -> None:
    src = tmp_path / "kb"
    src.mkdir()
    (src / "creds.md").write_text("api_key=supersecret12345")

    sources = [SourceEntry(name="kb", path=str(src), access_level=INTERNAL, include=("*.md",))]
    with pytest.raises(ValueError, match="credential"):
        read_resource(sources, "knowledge://sources/kb/creds.md", INTERNAL)


def test_contains_secret_detects_api_key() -> None:
    assert contains_secret("api_key=abc123")
    assert contains_secret("Authorization: Bearer mytoken")
    assert not contains_secret("This is safe prose about keys and passwords in a story")


# ---------------------------------------------------------------------------
# AC-008: unsupported method → -32601
# ---------------------------------------------------------------------------

def test_unsupported_method_returns_method_not_found_AC_008(tmp_path: Path) -> None:
    yml = _make_sources_yml(tmp_path, "")
    resp = dispatch(
        _req("memory/query", {"caller_clearance": INTERNAL}),
        sources_config_path=yml,
    )
    assert resp["error"]["code"] == ERR_METHOD_NOT_FOUND


# ---------------------------------------------------------------------------
# AC-009: nonexistent file → -32604
# ---------------------------------------------------------------------------

def test_nonexistent_file_returns_not_found_AC_009(tmp_path: Path) -> None:
    src = tmp_path / "kb"
    src.mkdir()
    # no files created

    yml = _make_sources_yml(tmp_path, (
        f'  - name: kb\n    path: {src}\n    access_level: internal\n    include: ["*.md"]\n'
    ))
    resp = dispatch(
        _req("resources/read", {
            "caller_clearance": INTERNAL,
            "uri": "knowledge://sources/kb/missing.md",
        }),
        sources_config_path=yml,
    )
    assert resp["error"]["code"] == ERR_NOT_FOUND


# ---------------------------------------------------------------------------
# AC-010: path traversal raises before file read
# ---------------------------------------------------------------------------

def test_path_traversal_raises_AC_010(tmp_path: Path) -> None:
    src = tmp_path / "kb"
    src.mkdir()

    sources = [SourceEntry(name="kb", path=str(src), access_level=INTERNAL, include=("*.md",))]
    with pytest.raises((ValueError, FileNotFoundError)):
        read_resource(sources, "knowledge://sources/kb/../../etc/passwd", INTERNAL)


# ---------------------------------------------------------------------------
# AC-011: restricted clearance sees all three levels
# ---------------------------------------------------------------------------

def test_list_restricted_clearance_sees_all_AC_011(tmp_path: Path) -> None:
    for level, name in [(PUBLIC, "pub"), (INTERNAL, "int"), (RESTRICTED, "res")]:
        d = tmp_path / name
        d.mkdir()
        (d / "doc.md").write_text(f"{level} content")

    yml = _make_sources_yml(tmp_path, (
        f'  - name: pub\n    path: {tmp_path / "pub"}\n    access_level: public\n    include: ["*.md"]\n'
        f'  - name: int\n    path: {tmp_path / "int"}\n    access_level: internal\n    include: ["*.md"]\n'
        f'  - name: res\n    path: {tmp_path / "res"}\n    access_level: restricted\n    include: ["*.md"]\n'
    ))
    resp = dispatch(_req("resources/list", {"caller_clearance": RESTRICTED}),
                    sources_config_path=yml)
    assert "error" not in resp
    levels = {r["access_level"] for r in resp["result"]["resources"]}
    assert levels == {PUBLIC, INTERNAL, RESTRICTED}


# ---------------------------------------------------------------------------
# Additional unit tests for contract helpers
# ---------------------------------------------------------------------------

def test_clearance_rank_order() -> None:
    assert ACCESS_RANK[PUBLIC] < ACCESS_RANK[INTERNAL] < ACCESS_RANK[RESTRICTED]


def test_clearance_allows_matrix() -> None:
    assert clearance_allows(PUBLIC, PUBLIC)
    assert clearance_allows(PUBLIC, INTERNAL)
    assert clearance_allows(PUBLIC, RESTRICTED)
    assert not clearance_allows(INTERNAL, PUBLIC)
    assert clearance_allows(INTERNAL, INTERNAL)
    assert clearance_allows(INTERNAL, RESTRICTED)
    assert not clearance_allows(RESTRICTED, PUBLIC)
    assert not clearance_allows(RESTRICTED, INTERNAL)
    assert clearance_allows(RESTRICTED, RESTRICTED)


def test_knowledge_uri_roundtrip() -> None:
    uri = KnowledgeUri(authority="sources", path="kb/equity/overview.md")
    assert str(uri) == "knowledge://sources/kb/equity/overview.md"
    parsed = KnowledgeUri.parse(str(uri))
    assert parsed.authority == "sources"
    assert parsed.path == "kb/equity/overview.md"


def test_knowledge_uri_parse_rejects_wrong_scheme() -> None:
    with pytest.raises(ValueError):
        KnowledgeUri.parse("https://example.com/foo")


def test_parse_sources_config_basic(tmp_path: Path) -> None:
    yml = tmp_path / "knowledge_sources.yml"
    yml.write_text(
        'sources:\n'
        '  - name: wiki\n'
        '    path: /kb/wiki\n'
        '    access_level: internal\n'
        '    include: ["*.md"]\n'
        '    exclude: ["**/drafts/**"]\n'
        '    freshness_days: 30\n'
    )
    sources = parse_sources_config(yml)
    assert len(sources) == 1
    s = sources[0]
    assert s.name == "wiki"
    assert s.path == "/kb/wiki"
    assert s.access_level == "internal"
    assert "*.md" in s.include
    assert "**/drafts/**" in s.exclude
    assert s.freshness_days == 30


def test_list_resources_sorted_by_uri(tmp_path: Path) -> None:
    src = tmp_path / "kb"
    src.mkdir()
    (src / "z_last.md").write_text("z")
    (src / "a_first.md").write_text("a")

    sources = [SourceEntry(name="kb", path=str(src), access_level=INTERNAL, include=("*.md",))]
    metas = list_resources(sources, INTERNAL)
    uris = [m.uri for m in metas]
    assert uris == sorted(uris), "list_resources must return URIs in sorted order"


def test_resources_list_result_structure(tmp_path: Path) -> None:
    src = tmp_path / "kb"
    src.mkdir()
    (src / "doc.md").write_text("content")

    yml = _make_sources_yml(tmp_path, (
        f'  - name: kb\n    path: {src}\n    access_level: internal\n    include: ["*.md"]\n'
    ))
    resp = dispatch(_req("resources/list", {"caller_clearance": INTERNAL}),
                    sources_config_path=yml)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    resource = resp["result"]["resources"][0]
    assert "uri" in resource
    assert "name" in resource
    assert "mimeType" in resource
    assert resource["uri"].startswith("knowledge://sources/kb/")


# ---------------------------------------------------------------------------
# Spec 0056 T-003 — knowledge://market_research/... MCP namespace
# ---------------------------------------------------------------------------

import datetime as _dt


def _make_item(
    item_id: str = "item-001",
    asset_class: str = "equities",
    source_type: str = "user_note",
    confidentiality: str = "internal",
    entitlement_class: str = "public",
    status: str = "approved",
) -> MarketResearchItem:
    return MarketResearchItem(
        item_id=item_id,
        source_uri=f"file://research/{item_id}.md",
        title=f"Research note {item_id}",
        source_type=source_type,
        author_or_publisher="Analyst A",
        published_at=_dt.date(2026, 1, 15),
        ingested_at=_dt.date(2026, 1, 16),
        content_hash="abc123",
        asset_class=asset_class,
        confidentiality=confidentiality,
        entitlement_class=entitlement_class,
        status=status,
    )


def _mr_req(method: str, params: dict, req_id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "method": method, "id": req_id, "params": params}


def test_mr_list_returns_approved_items_for_internal_caller() -> None:
    catalog = InMemoryResearchCatalog()
    catalog.put(_make_item("itm-001"))
    resp = dispatch_market_research(
        _mr_req("resources/list", {"caller_clearance": INTERNAL}),
        catalog=catalog,
    )
    assert "error" not in resp
    uris = [r["uri"] for r in resp["result"]["resources"]]
    assert any("itm-001" in u for u in uris)


def test_mr_list_excludes_restricted_item_from_internal_caller() -> None:
    catalog = InMemoryResearchCatalog()
    catalog.put(_make_item("pub-001", confidentiality="internal"))
    catalog.put(_make_item("res-001", confidentiality="restricted"))
    resp = dispatch_market_research(
        _mr_req("resources/list", {"caller_clearance": INTERNAL}),
        catalog=catalog,
    )
    assert "error" not in resp
    uris = [r["uri"] for r in resp["result"]["resources"]]
    assert any("pub-001" in u for u in uris)
    assert all("res-001" not in u for u in uris)


def test_mr_list_sorted_by_uri() -> None:
    catalog = InMemoryResearchCatalog()
    catalog.put(_make_item("zzz-item"))
    catalog.put(_make_item("aaa-item"))
    resp = dispatch_market_research(
        _mr_req("resources/list", {"caller_clearance": RESTRICTED}),
        catalog=catalog,
    )
    uris = [r["uri"] for r in resp["result"]["resources"]]
    assert uris == sorted(uris)


def test_mr_read_returns_citation_for_allowed_item() -> None:
    catalog = InMemoryResearchCatalog()
    item = _make_item("r001", asset_class="equities", source_type="user_note")
    catalog.put(item)
    uri = item.knowledge_uri
    resp = dispatch_market_research(
        _mr_req("resources/read", {"caller_clearance": INTERNAL, "uri": uri}),
        catalog=catalog,
    )
    assert "error" not in resp, resp
    contents = resp["result"]["contents"]
    assert len(contents) == 1
    assert contents[0]["uri"] == uri
    assert "Research note r001" in contents[0]["text"]


def test_mr_read_access_denied_for_restricted_item_to_internal_caller() -> None:
    catalog = InMemoryResearchCatalog()
    item = _make_item("sec-001", confidentiality="restricted")
    catalog.put(item)
    resp = dispatch_market_research(
        _mr_req("resources/read", {"caller_clearance": INTERNAL, "uri": item.knowledge_uri}),
        catalog=catalog,
    )
    assert resp["error"]["code"] == ERR_ACCESS_DENIED


def test_mr_read_existence_masked_for_missing_item() -> None:
    """Non-existent item must return -32600, not -32604 (RISK-003 existence masking)."""
    catalog = InMemoryResearchCatalog()
    resp = dispatch_market_research(
        _mr_req("resources/read", {
            "caller_clearance": INTERNAL,
            "uri": "knowledge://market_research/equities/user_note/ghost-999",
        }),
        catalog=catalog,
    )
    assert resp["error"]["code"] == ERR_ACCESS_DENIED


def test_mr_missing_clearance_returns_access_denied() -> None:
    catalog = InMemoryResearchCatalog()
    resp = dispatch_market_research(
        _mr_req("resources/list", {}),
        catalog=catalog,
    )
    assert resp["error"]["code"] == ERR_ACCESS_DENIED


def test_mr_wrong_authority_returns_not_found() -> None:
    catalog = InMemoryResearchCatalog()
    resp = dispatch_market_research(
        _mr_req("resources/read", {
            "caller_clearance": INTERNAL,
            "uri": "knowledge://sources/kb/some.md",
        }),
        catalog=catalog,
    )
    assert resp["error"]["code"] == ERR_NOT_FOUND


def test_mr_quarantined_item_denied() -> None:
    catalog = InMemoryResearchCatalog()
    item = _make_item("qua-001", status="quarantined")
    catalog.put(item)
    resp = dispatch_market_research(
        _mr_req("resources/read", {"caller_clearance": RESTRICTED, "uri": item.knowledge_uri}),
        catalog=catalog,
    )
    assert resp["error"]["code"] == ERR_ACCESS_DENIED
