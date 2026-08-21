"""Reference reader for the Market Research store (research/).

Backs the Research view in ``apps/knowledge-console`` (the terminal app). This
module deliberately does **not** implement ``specs/0056-market-research-
knowledge-base/`` (status: Draft) — there is no knowledge-base MCP interface, no
entitlement/information-barrier enforcement, no email connector, and no real
quarantine detection. It parses the committed, fictional-content-only reference
store at ``research/`` (see ``research/README.md``) and derives the same kind of
legible view-model ``model.py`` derives from ``memory/``, so the terminal has
real, filterable, citable data to render while ``0056`` remains unimplemented.

Standard library only, reusing ``workflow_memory``'s dependency-free YAML-subset
parser (``0048``) rather than adding a second one.
"""

from __future__ import annotations

import datetime
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from quantsmith.pipelines import access_control
from quantsmith.pipelines import workflow_memory as wm

SOURCE_TYPES = ("user_note", "firm_research", "fund_manager", "sell_side", "generated", "email_tagged")
ACCESS_LEVELS = ("public", "internal", "restricted")
REVIEW_STATUSES = (
    "draft", "pending_review", "approved", "quarantined",
    "restricted", "superseded", "deprecated", "deleted",
)
#: Statuses excluded from default (non-admin) retrieval — mirrors 0056 REQ-010/011
#: intent: a quarantined or deleted item must not surface in ordinary answers.
_HIDDEN_BY_DEFAULT = ("quarantined", "deleted")

_DEFAULT_FRESHNESS = 60


@dataclass(frozen=True)
class ResearchItem:
    id: str
    title: str
    source_type: str
    author_or_publisher: str
    asset_class: str
    access_level: str
    entitlement_class: str
    publication_date: datetime.date
    ingestion_date: datetime.date
    review_status: str
    summary: str
    citation: str
    domain: str
    freshness_days: int = _DEFAULT_FRESHNESS
    strategy_theme: str = ""
    geography: str = ""
    superseded_by: Optional[str] = None
    source_file: str = ""


@dataclass(frozen=True)
class ResearchStore:
    items: Tuple[ResearchItem, ...]
    default_freshness_days: int = _DEFAULT_FRESHNESS
    root: str = "research"


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _as_date(value, field: str, item_id: str) -> datetime.date:
    if isinstance(value, datetime.date):
        return value
    raise wm.MemoryParseError("research", 0, f"{item_id}.{field} is not a date: {value!r}")


def _manifest(root: Path) -> Dict:
    text = _read_text(root / "manifest.yaml")
    if text is None:
        return {}
    try:
        return wm.parse_memory_file(text, str(root / "manifest.yaml"))
    except wm.MemoryParseError:
        return {}


def _load_domain(path: Path, domain: str, default_freshness: int) -> List[ResearchItem]:
    text = _read_text(path)
    if text is None:
        return []
    try:
        doc = wm.parse_memory_file(text, str(path))
    except wm.MemoryParseError:
        return []
    raw_items = doc.get("items") or []
    if not isinstance(raw_items, list):
        return []
    default_access = str(doc.get("access_level", "internal"))

    items: List[ResearchItem] = []
    for raw in raw_items:
        item_id = str(raw.get("id", "")).strip()
        if not item_id:
            continue
        items.append(ResearchItem(
            id=item_id,
            title=str(raw.get("title", "")),
            source_type=str(raw.get("source_type", "")),
            author_or_publisher=str(raw.get("author_or_publisher", "")),
            asset_class=str(raw.get("asset_class", "")),
            access_level=str(raw.get("access_level", default_access)),
            entitlement_class=str(raw.get("entitlement_class", "")),
            publication_date=_as_date(raw.get("publication_date"), "publication_date", item_id),
            ingestion_date=_as_date(raw.get("ingestion_date"), "ingestion_date", item_id),
            review_status=str(raw.get("review_status", "draft")),
            summary=str(raw.get("summary", "")),
            citation=str(raw.get("citation", "")),
            domain=domain,
            freshness_days=int(raw.get("freshness_days", default_freshness) or default_freshness),
            strategy_theme=str(raw.get("strategy_theme", "")),
            geography=str(raw.get("geography", "")),
            superseded_by=(str(raw["superseded_by"]) if raw.get("superseded_by") else None),
            source_file=str(path),
        ))
    return items


def load_research_store(root: str | os.PathLike = "research") -> ResearchStore:
    """Load the whole research/ tree. Degrades to an empty store, never raises."""
    root_path = Path(root)
    if not root_path.is_dir():
        return ResearchStore(items=(), default_freshness_days=_DEFAULT_FRESHNESS, root=str(root_path))

    manifest = _manifest(root_path)
    defaults = manifest.get("defaults") or {}
    freshness = defaults.get("freshness_days", _DEFAULT_FRESHNESS)
    try:
        freshness = int(freshness)
    except (TypeError, ValueError):
        freshness = _DEFAULT_FRESHNESS

    items: List[ResearchItem] = []
    domains = manifest.get("domains") or []
    if domains:
        for d in domains:
            if not isinstance(d, dict):
                continue
            name = str(d.get("name") or "").strip()
            dpath = str(d.get("path") or name)
            if not name:
                continue
            for f in sorted((root_path / dpath).glob("*.yaml")) if (root_path / dpath).is_dir() else []:
                items.extend(_load_domain(f, name, freshness))
    else:
        # No manifest domains: walk one level and attribute by directory name.
        for sub in sorted(p for p in root_path.iterdir() if p.is_dir()):
            for f in sorted(sub.glob("*.yaml")):
                items.extend(_load_domain(f, sub.name, freshness))

    items.sort(key=lambda it: it.id)
    return ResearchStore(items=tuple(items), default_freshness_days=freshness, root=str(root_path))


def _tally(values) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for v in values:
        if not v:
            continue
        counts[v] = counts.get(v, 0) + 1
    return {k: counts[k] for k in sorted(counts)}


def _item_view(it: ResearchItem, as_of: datetime.date) -> Dict:
    days = (as_of - it.ingestion_date).days
    return {
        "id": it.id,
        "title": it.title,
        "source_type": it.source_type,
        "author_or_publisher": it.author_or_publisher,
        "asset_class": it.asset_class,
        "strategy_theme": it.strategy_theme,
        "geography": it.geography,
        "access_level": it.access_level,
        "entitlement_class": it.entitlement_class,
        "publication_date": it.publication_date.isoformat(),
        "ingestion_date": it.ingestion_date.isoformat(),
        "review_status": it.review_status,
        "summary": it.summary,
        "citation": it.citation,
        "domain": it.domain,
        "superseded_by": it.superseded_by,
        "source_file": it.source_file,
        "days_since_ingestion": days,
        "overdue": days > it.freshness_days,
        "hidden_by_default": it.review_status in _HIDDEN_BY_DEFAULT,
    }


def build_research_model(store: ResearchStore, *, as_of: Optional[datetime.date] = None,
                         generated_at: Optional[str] = None,
                         viewer_clearance: Optional[str] = None) -> Dict:
    """Deterministic JSON view-model over the research/ store.

    Mirrors the shape of ``model.build_model``: counts, item detail, and a
    visible/hidden split driven by ``review_status`` (quarantined/deleted items
    are flagged, never silently dropped from the payload — the terminal decides
    what to show, this module only tells the truth about what exists).

    ``viewer_clearance`` is ``None`` by default (see everything). When set,
    items above that clearance are dropped before counts/items are computed
    (spec 0058 REQ-011) — same pattern, same guarantee, as ``model.build_model``.
    """
    as_of = as_of or datetime.date.today()
    items = store.items
    if viewer_clearance is not None:
        items = tuple(
            it for it in items
            if access_control.access_level_allows(it.access_level, viewer_clearance)
        )
        store = ResearchStore(items=items, default_freshness_days=store.default_freshness_days,
                              root=store.root)

    items_view = [_item_view(it, as_of) for it in store.items]
    items_view.sort(key=lambda d: d["id"])

    visible = [d for d in items_view if not d["hidden_by_default"]]

    return {
        "generated_at": generated_at,
        "as_of": as_of.isoformat(),
        "default_freshness_days": store.default_freshness_days,
        "counts": {
            "total": len(store.items),
            "visible": len(visible),
            "hidden": len(store.items) - len(visible),
            "by_source_type": _tally(it.source_type for it in store.items),
            "by_asset_class": _tally(it.asset_class for it in store.items),
            "by_access_level": _tally(it.access_level for it in store.items),
            "by_review_status": _tally(it.review_status for it in store.items),
        },
        "items": items_view,
        "disclaimer": (
            "Reference implementation of specs/0056-market-research-knowledge-base "
            "(status: Draft). No MCP interface, entitlement enforcement, or email "
            "connector. Every item is fictional."
        ),
    }


def build_research_model_from_root(root: str | os.PathLike = "research", *,
                                   as_of: Optional[datetime.date] = None,
                                   generated_at: Optional[str] = None,
                                   viewer_override: Optional[str] = None) -> Dict:
    """Load the research/ tree, resolve the viewer's clearance, build its model.

    Same repo-root inference and opt-in behavior as
    ``model.build_model_from_root`` (spec 0058) — see its docstring.
    """
    store = load_research_store(root)
    root_path = Path(root)
    access_root = root_path.parent if root_path.name else root_path
    viewer_clearance = access_control.resolve_viewer_clearance(
        override=viewer_override, root=access_root)
    return build_research_model(store, as_of=as_of, generated_at=generated_at,
                                viewer_clearance=viewer_clearance)
