"""Market Research Knowledge Base (spec 0056).

Slices 1, 3, and 4 — schema, ingestion, governance, PIT filtering, citation,
audit, curation, and scheduling-integration logic. Standard library only.

**Not implemented here** (deferred):
- MCP surface (Slice 2) — blocked on spec 0052.
- Email connector (Slice 5) — blocked on provider choice (spec.md Open Questions).

**What is here:**
- T-001  MarketResearchItem schema and core taxonomy.
- T-002  Ingestion normalization with quarantine heuristics.
- T-004  ResearchCatalog storage adapter contract + InMemoryResearchCatalog.
- T-005  Classification and freshness helpers.
- T-006  Governance policy: clearance, entitlement, status checks.
- T-007  Access-tiered filter (filter before search, not after — RISK-002).
- T-008  Point-in-time filter across publication, effective, and ingestion dates.
- T-009  Citation rendering and unsupported-gap reporting.
- T-010  Lifecycle state management and allowed transitions.
- T-011  ResearchAuditLedger (append-only JSONL, same pattern as 0055).
- T-013  Curation: conflict detection and canonical-source selection.
- T-014  Scheduling integration: propose_knowledge_candidate for review handoff.
- T-016  Synthetic benchmark fixture generator.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

from quantsmith.pipelines import access_control

# ---------------------------------------------------------------------------
# Vocabulary (T-001, T-005)
# ---------------------------------------------------------------------------

SOURCE_TYPES: Tuple[str, ...] = (
    "user_note", "generated_report", "firm_research",
    "fund_manager", "sell_side", "email_market_color",
    "transcript", "meeting_note", "other",
)

ASSET_CLASSES: Tuple[str, ...] = (
    "equities", "credit", "rates", "fx", "commodities",
    "digital_assets", "macro", "multi_asset", "other",
)

#: Reuses 0058's ACCESS_LEVELS: ("public", "internal", "restricted").
CONFIDENTIALITY_LEVELS: Tuple[str, ...] = access_control.ACCESS_LEVELS

STATUSES: Tuple[str, ...] = (
    "draft", "pending_review", "approved", "quarantined",
    "restricted", "superseded", "deprecated", "deleted",
)

#: Statuses excluded from default retrieval — existence must not leak (NFR-001).
_HIDDEN_BY_DEFAULT: frozenset = frozenset(("quarantined", "deleted"))

#: Statuses eligible for current-context retrieval.
_RETRIEVABLE: frozenset = frozenset(("approved", "restricted"))

#: Allowed lifecycle state transitions (T-010). Terminal states have empty tuples.
VALID_TRANSITIONS: Dict[str, Tuple[str, ...]] = {
    "draft":          ("pending_review", "quarantined", "deleted"),
    "pending_review": ("approved", "restricted", "quarantined", "deleted"),
    "approved":       ("superseded", "deprecated", "quarantined", "deleted"),
    "restricted":     ("approved", "deprecated", "quarantined", "deleted"),
    "quarantined":    ("pending_review", "deleted"),
    "superseded":     ("deleted",),
    "deprecated":     ("deleted",),
    "deleted":        (),
}

DEFAULT_FRESHNESS_DAYS = 60

# ---------------------------------------------------------------------------
# Core schema (T-001)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MarketResearchItem:
    """A single governed market-research item. Immutable once ingested.

    Confidentiality reuses 0058's ACCESS_LEVELS — not reinvented here
    (plan.md Dependency status). MNPI/secret/PII detection sets
    status=quarantined, not a fourth confidentiality tier.
    """

    item_id: str
    source_uri: str
    title: str
    source_type: str
    author_or_publisher: str
    published_at: datetime.date
    ingested_at: datetime.date
    content_hash: str
    asset_class: str
    confidentiality: str
    entitlement_class: str
    status: str
    effective_at: Optional[datetime.date] = None
    entities: Tuple[str, ...] = ()
    themes: Tuple[str, ...] = ()
    freshness_days: Optional[int] = None
    superseded_by: Optional[str] = None
    canonical_of: Optional[str] = None

    @property
    def knowledge_uri(self) -> str:
        """Canonical MCP knowledge URI (plan.md §Knowledge URI)."""
        return (
            f"knowledge://market_research"
            f"/{self.asset_class}/{self.source_type}/{self.item_id}"
        )

    @property
    def effective_freshness_days(self) -> int:
        return self.freshness_days if self.freshness_days is not None else DEFAULT_FRESHNESS_DAYS


# ---------------------------------------------------------------------------
# Field validation (supports T-015 tests)
# ---------------------------------------------------------------------------


def validate_item(item: MarketResearchItem) -> List[str]:
    """Return a list of validation error messages for a MarketResearchItem."""
    errors: List[str] = []
    if not item.item_id:
        errors.append("item_id is required")
    if not item.source_uri:
        errors.append("source_uri is required")
    if not item.title:
        errors.append("title is required")
    if not item.author_or_publisher:
        errors.append("author_or_publisher is required")
    if not item.content_hash:
        errors.append("content_hash is required")
    if item.source_type not in SOURCE_TYPES:
        errors.append(f"source_type {item.source_type!r} not in allowed values")
    if item.asset_class not in ASSET_CLASSES:
        errors.append(f"asset_class {item.asset_class!r} not in allowed values")
    if item.confidentiality not in CONFIDENTIALITY_LEVELS:
        errors.append(f"confidentiality {item.confidentiality!r} not in allowed values")
    if item.status not in STATUSES:
        errors.append(f"status {item.status!r} not in allowed values")
    if item.superseded_by is not None and item.status != "superseded":
        errors.append("superseded_by is set but status is not 'superseded'")
    return errors


# ---------------------------------------------------------------------------
# Quarantine heuristics (T-002, REQ-011, AC-006)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QuarantineFlag:
    """Evidence of a quarantine-triggering pattern found during ingestion."""

    category: str   # "secret" | "pii" | "mnpi" | "license"
    matched: str    # the pattern label that matched (never the raw content value)
    detail: str     # human-readable explanation for the reviewer


# Secret-like patterns — heuristic, not exhaustive.
_SECRET_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(
        r"(?:api[_-]?key|api[_-]?secret|secret[_-]?key|access[_-]?key"
        r"|bearer[_-]?token|auth[_-]?token|password|passwd"
        r"|private[_-]?key|client[_-]?secret)[=:\s]+\S+",
        re.IGNORECASE,
    ), "api-key-like"),
    (re.compile(r"-----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+|DSA\s+)?PRIVATE\s+KEY-----"),
     "private-key-block"),
]

# PII-like patterns.
_PII_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), "email-address"),
    (re.compile(r"\b(?:\+?1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}\b"), "phone-number"),
    (re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"), "ssn-like"),
]

# MNPI indicators.
_MNPI_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bmaterial\s+non[- ]public\b", re.IGNORECASE),
    re.compile(r"\bMNPI\b"),
    re.compile(r"\binsider\s+(?:information|trading|knowledge)\b", re.IGNORECASE),
    re.compile(r"\bnot\s+yet\s+publicly\s+(?:disclosed|announced|released)\b", re.IGNORECASE),
    re.compile(r"\bpending\s+(?:public\s+)?(?:announcement|disclosure|merger|acquisition)\b",
               re.IGNORECASE),
]

# License-restriction indicators.
_LICENSE_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bnot\s+for\s+(?:redistribution|distribution|reproduction)\b", re.IGNORECASE),
    re.compile(r"\bproprietary\s+(?:and\s+)?confidential\b", re.IGNORECASE),
    re.compile(r"\bdo\s+not\s+(?:distribute|reproduce|forward)\b", re.IGNORECASE),
    re.compile(r"\bclient[- ]confidential\b", re.IGNORECASE),
    re.compile(r"\blicensed\s+(?:content|material|research|data)\b", re.IGNORECASE),
]


def _scan_quarantine(text: str) -> List[QuarantineFlag]:
    """Run heuristic quarantine checks over ``text``. Pure function (AC-006)."""
    flags: List[QuarantineFlag] = []
    for pattern, label in _SECRET_PATTERNS:
        if pattern.search(text):
            flags.append(QuarantineFlag(
                "secret", label,
                f"possible secret detected ({label}); review required before indexing",
            ))
    for pattern, label in _PII_PATTERNS:
        if pattern.search(text):
            flags.append(QuarantineFlag(
                "pii", label,
                f"possible PII detected ({label}); review required before indexing",
            ))
    for pattern in _MNPI_PATTERNS:
        m = pattern.search(text)
        if m:
            flags.append(QuarantineFlag(
                "mnpi", m.group(0),
                "possible MNPI indicator; compliance review required before indexing",
            ))
            break  # one MNPI flag is enough
    for pattern in _LICENSE_PATTERNS:
        m = pattern.search(text)
        if m:
            flags.append(QuarantineFlag(
                "license", m.group(0),
                "possible license restriction; entitlement review required before indexing",
            ))
            break
    return flags


# ---------------------------------------------------------------------------
# Ingestion normalization (T-002)
# ---------------------------------------------------------------------------


def ingest_item(
    *,
    item_id: str,
    source_uri: str,
    title: str,
    source_type: str,
    author_or_publisher: str,
    published_at: datetime.date,
    asset_class: str,
    confidentiality: str,
    entitlement_class: str,
    ingested_at: Optional[datetime.date] = None,
    content_hash: Optional[str] = None,
    effective_at: Optional[datetime.date] = None,
    entities: Tuple[str, ...] = (),
    themes: Tuple[str, ...] = (),
    freshness_days: Optional[int] = None,
    superseded_by: Optional[str] = None,
    canonical_of: Optional[str] = None,
    raw_content: str = "",
    initial_status: str = "pending_review",
) -> Tuple[MarketResearchItem, List[QuarantineFlag]]:
    """Normalize a raw ingestion payload into a governed MarketResearchItem.

    Returns the item and any quarantine flags. When flags are present the
    item's status is forced to ``quarantined`` regardless of initial_status —
    quarantined items are excluded from indexes until reviewed (AC-006,
    RISK-006). The caller supplies ``raw_content`` for the fields they want
    scanned; an empty string skips scanning (for items whose content lives
    in an external store that has already been scanned at ingest time).
    """
    if ingested_at is None:
        ingested_at = datetime.date.today()
    if content_hash is None:
        content_hash = hashlib.sha256(
            f"{source_uri}:{title}:{published_at.isoformat()}".encode("utf-8")
        ).hexdigest()[:16]

    flags = _scan_quarantine(raw_content) if raw_content else []
    status = "quarantined" if flags else initial_status

    return MarketResearchItem(
        item_id=item_id,
        source_uri=source_uri,
        title=title,
        source_type=source_type,
        author_or_publisher=author_or_publisher,
        published_at=published_at,
        ingested_at=ingested_at,
        content_hash=content_hash,
        asset_class=asset_class,
        confidentiality=confidentiality,
        entitlement_class=entitlement_class,
        status=status,
        effective_at=effective_at,
        entities=entities,
        themes=themes,
        freshness_days=freshness_days,
        superseded_by=superseded_by,
        canonical_of=canonical_of,
    ), flags


# ---------------------------------------------------------------------------
# Storage adapter contract (T-004, NFR-004)
# ---------------------------------------------------------------------------


class ResearchCatalog:
    """Contract for market-research catalog storage adapters (T-004, NFR-004).

    Concrete adapters satisfy this contract against document stores, object
    storage, relational metadata catalogs, vector/search indexes, and
    enterprise drives without changing the agent-facing interface. The SDK
    carries only the in-memory reference adapter below.
    """

    def get(self, item_id: str) -> Optional[MarketResearchItem]:
        raise NotImplementedError

    def search(
        self,
        *,
        asset_class: Optional[str] = None,
        source_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[MarketResearchItem]:
        raise NotImplementedError

    def put(self, item: MarketResearchItem) -> None:
        raise NotImplementedError

    def delete(self, item_id: str) -> None:
        raise NotImplementedError


class InMemoryResearchCatalog(ResearchCatalog):
    """Reference catalog adapter backed by a plain dict. Tests and local use."""

    def __init__(self) -> None:
        self._store: Dict[str, MarketResearchItem] = {}

    def get(self, item_id: str) -> Optional[MarketResearchItem]:
        return self._store.get(item_id)

    def search(
        self,
        *,
        asset_class: Optional[str] = None,
        source_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[MarketResearchItem]:
        items = list(self._store.values())
        if asset_class is not None:
            items = [i for i in items if i.asset_class == asset_class]
        if source_type is not None:
            items = [i for i in items if i.source_type == source_type]
        if status is not None:
            items = [i for i in items if i.status == status]
        return sorted(items, key=lambda i: i.item_id)

    def put(self, item: MarketResearchItem) -> None:
        self._store[item.item_id] = item

    def delete(self, item_id: str) -> None:
        self._store.pop(item_id, None)

    def __len__(self) -> int:
        return len(self._store)


# ---------------------------------------------------------------------------
# Classification and freshness (T-005, REQ-005, REQ-009, NFR-009)
# ---------------------------------------------------------------------------


def is_stale(
    item: MarketResearchItem, as_of: Optional[datetime.date] = None
) -> bool:
    """Whether the item is older than its freshness window as of ``as_of``."""
    as_of = as_of or datetime.date.today()
    anchor = item.effective_at if item.effective_at is not None else item.published_at
    return (as_of - anchor).days > item.effective_freshness_days


def classify_item(
    item: MarketResearchItem, as_of: Optional[datetime.date] = None
) -> str:
    """Return a retrieval classification for the item (T-005, REQ-009).

    Returns one of: ``"current"``, ``"stale"``, ``"superseded"``, ``"hidden"``.
    ``"hidden"`` means the item must not surface in default results.
    """
    if item.status in _HIDDEN_BY_DEFAULT:
        return "hidden"
    if item.status == "superseded":
        return "superseded"
    if item.status == "deprecated":
        return "stale"
    if is_stale(item, as_of):
        return "stale"
    return "current"


# ---------------------------------------------------------------------------
# Governance policy (T-006, REQ-006, NFR-001, NFR-008)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GovernanceDecision:
    """Result of a governance check for one item (T-006, AC-003, AC-008)."""

    item_id: str
    allowed: bool
    denial_class: Optional[str] = None  # "clearance" | "entitlement" | "status"
    # Never includes restricted content details — NFR-001 requires existence non-disclosure.


def check_governance(
    item: MarketResearchItem,
    caller_clearance: str,
    entitlements: Tuple[str, ...] = (),
) -> GovernanceDecision:
    """Apply clearance, entitlement, and status governance before retrieval.

    Clearance check delegates to ``access_control.access_level_allows()``
    (built, tested, fail-closed). Entitlement check is net-new: the caller
    must hold the item's entitlement_class unless it is empty or 'public'.
    Status check: quarantined and deleted items are never retrievable (AC-006).

    Denial responses carry ``denial_class`` only — never the restricted item's
    title, existence, or content (NFR-001, RISK-001, RISK-002).
    """
    if item.status in _HIDDEN_BY_DEFAULT:
        return GovernanceDecision(item.item_id, allowed=False, denial_class="status")

    if not access_control.access_level_allows(item.confidentiality, caller_clearance):
        return GovernanceDecision(item.item_id, allowed=False, denial_class="clearance")

    # Entitlement: empty or "public" class needs no license.
    if item.entitlement_class and item.entitlement_class not in ("public", ""):
        if item.entitlement_class not in entitlements:
            return GovernanceDecision(item.item_id, allowed=False, denial_class="entitlement")

    return GovernanceDecision(item.item_id, allowed=True)


# ---------------------------------------------------------------------------
# Access-tiered search (T-007, REQ-006, NFR-001)
# ---------------------------------------------------------------------------


def filter_by_access_tier(
    items: Iterable[MarketResearchItem],
    caller_clearance: str,
    entitlements: Tuple[str, ...] = (),
) -> List[MarketResearchItem]:
    """Filter before search — access-tiered index selection (T-007).

    Pre-search filtering prevents post-retrieval leakage of restricted
    document existence through ranking behavior (RISK-002, NFR-001).
    Only items the caller may see enter the search space.
    """
    return [
        item for item in items
        if check_governance(item, caller_clearance, entitlements).allowed
    ]


# ---------------------------------------------------------------------------
# Point-in-time filter (T-008, REQ-007, NFR-003)
# ---------------------------------------------------------------------------


def point_in_time_filter(
    items: Iterable[MarketResearchItem],
    as_of: datetime.date,
    *,
    include_superseded: bool = False,
    include_stale: bool = True,
) -> List[MarketResearchItem]:
    """Exclude items whose knowledge was not available at ``as_of`` (AC-004).

    Exclusion conditions (any one is sufficient):
    - published_at > as_of
    - effective_at > as_of (when set — the date the content *describes*)
    - ingested_at > as_of (the item hadn't been ingested yet)
    - status in _HIDDEN_BY_DEFAULT
    - status == 'superseded' and include_superseded is False

    ``include_stale`` keeps stale items when True (the default for historical
    queries); callers requesting current context should filter further with
    ``classify_item``.
    """
    result: List[MarketResearchItem] = []
    for item in items:
        if item.published_at > as_of:
            continue
        if item.effective_at is not None and item.effective_at > as_of:
            continue
        if item.ingested_at > as_of:
            continue
        if item.status in _HIDDEN_BY_DEFAULT:
            continue
        if item.status == "superseded" and not include_superseded:
            continue
        result.append(item)
    return result


# ---------------------------------------------------------------------------
# Citation rendering (T-009, REQ-008, REQ-009, NFR-002)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CitationResult:
    """A cited passage or item summary with full provenance (AC-005, NFR-002)."""

    item_id: str
    knowledge_uri: str
    citation_text: str       # the specific claim or summary passage
    source_type: str
    author_or_publisher: str
    published_at: str        # ISO date string
    classification: str      # "current" | "stale" | "superseded"


@dataclass(frozen=True)
class UnsupportedGap:
    """A claim or sub-question with no accessible citation (NFR-002, AC-005)."""

    query: str
    reason: str              # "no_source" | "clearance_denied" | "all_stale"


def render_citation(
    item: MarketResearchItem,
    passage: str = "",
    as_of: Optional[datetime.date] = None,
) -> CitationResult:
    """Render a citation for a retrieval result (T-009, AC-005)."""
    return CitationResult(
        item_id=item.item_id,
        knowledge_uri=item.knowledge_uri,
        citation_text=passage or item.title,
        source_type=item.source_type,
        author_or_publisher=item.author_or_publisher,
        published_at=item.published_at.isoformat(),
        classification=classify_item(item, as_of),
    )


def render_unsupported_gap(
    query: str,
    reason: str = "no_source",
) -> UnsupportedGap:
    """Render an unsupported-gap record for a query with no accessible source."""
    return UnsupportedGap(query=query, reason=reason)


# ---------------------------------------------------------------------------
# Lifecycle management (T-010, REQ-010, NFR-010)
# ---------------------------------------------------------------------------


def validate_lifecycle_transition(current_status: str, new_status: str) -> bool:
    """Whether transitioning current_status → new_status is allowed (T-010)."""
    return new_status in VALID_TRANSITIONS.get(current_status, ())


def transition_status(
    item: MarketResearchItem, new_status: str
) -> MarketResearchItem:
    """Return a new item with updated status, or raise ValueError if disallowed."""
    if not validate_lifecycle_transition(item.status, new_status):
        raise ValueError(
            f"lifecycle transition {item.status!r} → {new_status!r} "
            f"is not allowed (item {item.item_id})"
        )
    return MarketResearchItem(
        item_id=item.item_id,
        source_uri=item.source_uri,
        title=item.title,
        source_type=item.source_type,
        author_or_publisher=item.author_or_publisher,
        published_at=item.published_at,
        ingested_at=item.ingested_at,
        content_hash=item.content_hash,
        asset_class=item.asset_class,
        confidentiality=item.confidentiality,
        entitlement_class=item.entitlement_class,
        status=new_status,
        effective_at=item.effective_at,
        entities=item.entities,
        themes=item.themes,
        freshness_days=item.freshness_days,
        superseded_by=item.superseded_by if new_status == "superseded" else item.superseded_by,
        canonical_of=item.canonical_of,
    )


# ---------------------------------------------------------------------------
# Audit ledger (T-011, REQ-012, NFR-007)
# ---------------------------------------------------------------------------


class ResearchAuditLedger:
    """Append-only JSONL audit ledger (T-011, AC-008, NFR-007).

    Same pattern as 0055's ExecutionLedger: immutable records, one JSON object
    per line, preserves history for compliance reconstruction. Never logs
    restricted content (NFR-007 requires reconstruction, not content storage).
    """

    def __init__(self, path: os.PathLike | str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, record: Dict) -> None:
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")

    def record_ingestion(
        self,
        item: MarketResearchItem,
        flags: List[QuarantineFlag],
        *,
        actor: str = "",
    ) -> None:
        self._append({
            "event_type": "ingestion",
            "item_id": item.item_id,
            "asset_class": item.asset_class,
            "source_type": item.source_type,
            "status": item.status,
            "quarantine_flag_categories": [f.category for f in flags],
            "actor": actor,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })

    def record_retrieval(
        self,
        *,
        caller_clearance: str,
        item_ids: Tuple[str, ...],
        audit_id: str,
        as_of: Optional[str] = None,
        query_intent: str = "",
    ) -> None:
        self._append({
            "event_type": "retrieval",
            "audit_id": audit_id,
            "caller_clearance": caller_clearance,
            "as_of": as_of,
            "item_ids": list(item_ids),
            "query_intent_length": len(query_intent),  # never the query text — may be sensitive
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })

    def record_denial(
        self,
        *,
        item_id: str,
        caller_clearance: str,
        denial_class: str,
        audit_id: str,
    ) -> None:
        """Log a denial without revealing the restricted item's content (NFR-001)."""
        self._append({
            "event_type": "denial",
            "audit_id": audit_id,
            "caller_clearance": caller_clearance,
            "denial_class": denial_class,  # "clearance" | "entitlement" | "status" — not content
            "item_id": item_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })

    def record_lifecycle(
        self,
        item: MarketResearchItem,
        old_status: str,
        *,
        actor: str = "",
    ) -> None:
        self._append({
            "event_type": "lifecycle",
            "item_id": item.item_id,
            "from_status": old_status,
            "to_status": item.status,
            "actor": actor,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })

    def record_citation(
        self,
        citation: CitationResult,
        audit_id: str,
    ) -> None:
        self._append({
            "event_type": "citation",
            "audit_id": audit_id,
            "item_id": citation.item_id,
            "knowledge_uri": citation.knowledge_uri,
            "source_type": citation.source_type,
            "classification": citation.classification,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })

    def read_all(self) -> List[Dict]:
        """Read all records. Returns empty list when the ledger doesn't exist yet."""
        if not self._path.exists():
            return []
        records = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                records.append(json.loads(line))
        return records


# ---------------------------------------------------------------------------
# Curation (T-013, REQ-014, AC-007)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConflictGroup:
    """Two or more approved items with potentially conflicting signals (T-013)."""

    items: Tuple[MarketResearchItem, ...]
    basis: str                          # why these items were flagged as conflicting
    canonical_id: Optional[str] = None  # set when a human has selected a canonical source


def find_conflicts(
    items: Iterable[MarketResearchItem],
) -> List[ConflictGroup]:
    """Find approved items that share asset_class + themes and may conflict (AC-007).

    Conflict candidates: both approved/restricted, same asset_class, at least
    one shared theme, neither supersedes the other. Human review and
    canonical-source selection determine whether a true conflict exists.
    """
    approved = [
        i for i in items if i.status in ("approved", "restricted")
    ]
    groups: List[ConflictGroup] = []
    seen_pairs: set = set()

    for idx, a in enumerate(approved):
        for b in approved[idx + 1:]:
            if a.asset_class != b.asset_class:
                continue
            if a.superseded_by == b.item_id or b.superseded_by == a.item_id:
                continue
            shared = set(a.themes) & set(b.themes)
            if not shared:
                continue
            pair = tuple(sorted((a.item_id, b.item_id)))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            groups.append(ConflictGroup(
                items=(a, b),
                basis=(
                    f"same asset_class={a.asset_class!r} and "
                    f"shared themes {sorted(shared)!r}"
                ),
            ))
    return groups


def select_canonical(
    group: ConflictGroup,
    canonical_id: str,
) -> ConflictGroup:
    """Record a canonical-source selection for a conflict group (AC-007)."""
    ids = {i.item_id for i in group.items}
    if canonical_id not in ids:
        raise ValueError(
            f"canonical_id {canonical_id!r} not in conflict group items {ids!r}"
        )
    return ConflictGroup(
        items=group.items,
        basis=group.basis,
        canonical_id=canonical_id,
    )


# ---------------------------------------------------------------------------
# Scheduling integration (T-014, REQ-015, AC-010)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KnowledgeCandidate:
    """A research candidate proposed from a scheduled report (T-014, AC-010).

    Always enters pending_review — never auto-promoted. Carries citations
    from the source document so provenance is traceable before review.
    """

    candidate_id: str
    source_item_id: str             # the scheduled report that produced this
    draft_item: MarketResearchItem  # status is always "pending_review"
    citations: Tuple[CitationResult, ...]
    proposed_at: datetime.date


def propose_knowledge_candidate(
    *,
    source_item_id: str,
    title: str,
    asset_class: str,
    author_or_publisher: str,
    published_at: datetime.date,
    citations: Tuple[CitationResult, ...],
    source_type: str = "generated_report",
    confidentiality: str = "internal",
    entitlement_class: str = "public",
    themes: Tuple[str, ...] = (),
    entities: Tuple[str, ...] = (),
    proposed_at: Optional[datetime.date] = None,
) -> KnowledgeCandidate:
    """Propose a knowledge candidate from a scheduled report (T-014).

    The draft item always has status=pending_review — AC-010 requires that
    candidates enter review, never auto-promotion (NFR-010 reversibility).
    The candidate_id is deterministic from source_item_id + title so that
    re-running a scheduled report is idempotent at the proposal level.
    """
    candidate_id = (
        "candidate-"
        + hashlib.sha256(
            f"{source_item_id}:{title}:{published_at.isoformat()}".encode("utf-8")
        ).hexdigest()[:8]
    )
    today = proposed_at or datetime.date.today()
    draft, _ = ingest_item(
        item_id=candidate_id,
        source_uri=(
            f"knowledge://market_research/{asset_class}/{source_type}/{candidate_id}"
        ),
        title=title,
        source_type=source_type,
        author_or_publisher=author_or_publisher,
        published_at=published_at,
        ingested_at=today,
        asset_class=asset_class,
        confidentiality=confidentiality,
        entitlement_class=entitlement_class,
        themes=themes,
        entities=entities,
        initial_status="pending_review",
    )
    return KnowledgeCandidate(
        candidate_id=candidate_id,
        source_item_id=source_item_id,
        draft_item=draft,
        citations=citations,
        proposed_at=today,
    )


# ---------------------------------------------------------------------------
# Benchmark fixtures (T-016, NFR-005, NFR-006)
# ---------------------------------------------------------------------------


def generate_synthetic_catalog(
    n: int = 1_000_000,
    *,
    seed: int = 42,
    start_date: datetime.date = datetime.date(2020, 1, 1),
) -> Iterator[MarketResearchItem]:
    """Yield ``n`` deterministic synthetic MarketResearchItems (T-016, NFR-005).

    Purely synthetic — no real research content, no external calls.
    Deterministic given ``seed``. For capacity and latency benchmark fixtures.
    The pseudonymous-not-anonymous limit stated in spec 0048 NFR-004 also
    applies here: synthetic items carry no real author identifiers.
    """
    # Linear congruential generator — standard library only.
    state = seed

    def _lcg() -> int:
        nonlocal state
        state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
        return state

    asset_classes_list = list(ASSET_CLASSES)
    source_types_list = list(SOURCE_TYPES)
    conf_list = list(CONFIDENTIALITY_LEVELS)

    for i in range(n):
        asset_class = asset_classes_list[_lcg() % len(asset_classes_list)]
        source_type = source_types_list[_lcg() % len(source_types_list)]
        conf = conf_list[_lcg() % len(conf_list)]
        days_offset = _lcg() % (365 * 5)
        pub_date = start_date + datetime.timedelta(days=int(days_offset))
        item_id = f"SYN-{i:09d}"
        content_hash = f"{_lcg():08x}{_lcg():08x}"
        yield MarketResearchItem(
            item_id=item_id,
            source_uri=f"synthetic://catalog/{item_id}",
            title=f"Synthetic item {i} ({asset_class})",
            source_type=source_type,
            author_or_publisher="synthetic-generator",
            published_at=pub_date,
            ingested_at=pub_date,
            content_hash=content_hash,
            asset_class=asset_class,
            confidentiality=conf,
            entitlement_class="public",
            status="approved",
        )
