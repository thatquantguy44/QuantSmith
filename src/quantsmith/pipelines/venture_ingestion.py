"""Point-in-time ingestion and entity-resolution contracts for spec 0088.

Pure functions, standard library only. They turn a raw source record into a
fact that carries ``known_at`` (spec 0083 REQ-004), build as-of views and
outcome-independent cohorts, and compare company records without ever merging
across scripts or on a name alone. No network access and no source adapter
lives here: callers supply records.
"""

from __future__ import annotations

from datetime import date, datetime
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

KNOWN_AT_POLICIES = {"filed": "filed_time", "published": "announced_time",
                     "event": "event_time", "snapshot": "retrieved_time",
                     "retrieved": "retrieved_time"}
DEFAULT_LATE_RETRIEVAL_DAYS = 30


def _day(value: Any) -> Optional[date]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def derive_known_at(raw: Mapping[str, Any], policy: str,
                    late_retrieval_days: int = DEFAULT_LATE_RETRIEVAL_DAYS) -> Dict[str, Any]:
    """Return ``{"known_at", "late_retrieval"}`` for a raw record under a policy.

    ``raw`` carries ISO dates under event_time, announced_time, filed_time and
    retrieved_time. A missing field the policy needs is an error, never a guess.
    """
    if policy not in KNOWN_AT_POLICIES:
        raise ValueError(f"unknown known_at policy {policy!r}")
    field = KNOWN_AT_POLICIES[policy]
    known = _day(raw.get(field))
    if known is None:
        raise ValueError(f"policy {policy!r} needs {field}, which is missing")
    retrieved = _day(raw.get("retrieved_time"))
    late = False
    if retrieved is not None and policy in ("filed", "published", "event"):
        late = (retrieved - known).days > late_retrieval_days
    return {"known_at": known.isoformat(), "late_retrieval": late}


def build_fact(raw: Mapping[str, Any], policy: str, source_id: str, source_grade: str,
               language: str = "en", derived: bool = False,
               confidence: str = "unrated") -> Dict[str, Any]:
    """Build a spec-0083 fact record from a raw record under a known_at policy."""
    stamp = derive_known_at(raw, policy)
    return {"entity_id": raw["entity_id"], "value": raw["value"], "unit": raw.get("unit", "count"),
            "source_id": source_id, "source_grade": source_grade,
            "event_time": raw.get("event_time"), "announced_time": raw.get("announced_time"),
            "filed_time": raw.get("filed_time"), "ingested_time": raw.get("retrieved_time"),
            "known_at": stamp["known_at"], "language": language, "derived": derived,
            "confidence": confidence, "late_retrieval": stamp["late_retrieval"],
            "field": raw.get("field", "value")}


def as_of_view(facts: Iterable[Mapping[str, Any]], as_of: str,
               exclude_late: bool = False) -> List[Mapping[str, Any]]:
    """Facts known on ``as_of``; the latest known version per (entity, field) wins."""
    cutoff = _day(as_of)
    latest: Dict[Any, Mapping[str, Any]] = {}
    for f in facts:
        if _day(f["known_at"]) > cutoff:
            continue
        if exclude_late and f.get("late_retrieval"):
            continue
        key = (f["entity_id"], f.get("field", "value"))
        if key not in latest or _day(f["known_at"]) >= _day(latest[key]["known_at"]):
            latest[key] = f
    return sorted(latest.values(), key=lambda f: (f["entity_id"], f.get("field", "value")))


def form_cohort(universe: Sequence[Mapping[str, Any]], formation_date: str) -> List[str]:
    """Entity IDs first known on or before the formation date, independent of outcome.

    Each universe row needs ``entity_id`` and ``first_known_at``. Later removal,
    failure, or success never changes membership: that is what keeps a cohort
    free of survivorship bias.
    """
    cutoff = _day(formation_date)
    return sorted(r["entity_id"] for r in universe if _day(r["first_known_at"]) <= cutoff)


def cohort_rate(cohort: Sequence[str], outcome_ids: Iterable[str]) -> Dict[str, Any]:
    """Outcome rate over the whole formed cohort, with the denominator stated."""
    hits = set(outcome_ids) & set(cohort)
    return {"numerator": len(hits), "denominator": len(cohort),
            "rate": (len(hits) / len(cohort)) if cohort else None}


# ------------------------------------------------------------ entity resolution
def _nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


# Legal-form markers are removed for *comparison only*; callers keep the
# original name and its suffix, because the legal form is itself information.
LEGAL_FORM_PREFIXES = tuple(_nfkc(x) for x in (
    "pt", "cv", "บริษัท", "công ty cổ phần", "công ty tnhh", "ctcp",
    "ооо", "тоо", "ао", "зао", "оао", "mchj"))
LEGAL_FORM_SUFFIXES = tuple(_nfkc(x) for x in (
    "股份有限公司", "有限公司", "pte ltd", "sdn bhd", "tbk", "จำกัด (มหาชน)", "จำกัด",
    "inc", "llc", "ltd", "limited", "corp", "co ltd", "gmbh", "llp", "jsc",
    "ооо", "тоо", "ао", "mchj"))


def script_of(text: str) -> str:
    """Dominant script of a name: han, thai, hangul, kana, cyrillic, latin, or other."""
    counts: Dict[str, int] = {}
    for ch in text:
        if not ch.isalpha():
            continue
        name = unicodedata.name(ch, "")
        if name.startswith("CJK UNIFIED") or name.startswith("CJK COMPATIBILITY"):
            key = "han"
        elif name.startswith("THAI"):
            key = "thai"
        elif name.startswith("HANGUL"):
            key = "hangul"
        elif name.startswith(("HIRAGANA", "KATAKANA")):
            key = "kana"
        elif name.startswith("CYRILLIC"):
            key = "cyrillic"
        elif name.startswith("LATIN"):
            key = "latin"
        else:
            key = "other"
        counts[key] = counts.get(key, 0) + 1
    return max(counts, key=counts.get) if counts else "other"


def normalize_name(name: str) -> str:
    """Case-fold, drop punctuation, and remove legal-form markers for comparison."""
    t = re.sub(r"[\.,;:()\"'`«»„“”]", " ", _nfkc(name))
    t = re.sub(r"\s+", " ", t).strip()
    suffixes = sorted(LEGAL_FORM_SUFFIXES, key=len, reverse=True)
    prefixes = sorted(LEGAL_FORM_PREFIXES, key=len, reverse=True)
    changed = True
    while changed:
        changed = False
        for suf in suffixes:
            cjk = script_of(suf) in ("han", "thai")
            if t != suf and (t.endswith(" " + suf) or (cjk and t.endswith(suf))):
                t, changed = t[: -len(suf)].strip(), True
        for pre in prefixes:
            if t.startswith(pre + " "):
                t, changed = t[len(pre):].strip(), True
    return t


def resolve_entities(a: Mapping[str, Any], b: Mapping[str, Any]) -> Dict[str, Any]:
    """Compare two company records; never merge on a name alone.

    Records may carry ``name``, ``jurisdiction``, ``registry_id``, ``lei``.
    Returns ``{"decision", "reasons"}`` with decision one of match, candidate,
    candidate_cross_script, needs_registry_id, no_match.
    """
    reasons: List[str] = []
    if a.get("lei") and a.get("lei") == b.get("lei"):
        return {"decision": "match", "reasons": ["equal LEI"]}
    same_jur = a.get("jurisdiction") and a.get("jurisdiction") == b.get("jurisdiction")
    ra, rb = a.get("registry_id"), b.get("registry_id")
    if ra and rb and same_jur:
        if ra == rb:
            return {"decision": "match", "reasons": ["equal registry identifier in one jurisdiction"]}
        return {"decision": "no_match", "reasons": ["different registry identifiers in one jurisdiction"]}
    sa, sb = script_of(a["name"]), script_of(b["name"])
    if sa != sb:
        return {"decision": "candidate_cross_script",
                "reasons": [f"names are in different scripts ({sa} vs {sb})",
                            "never merged without a registry identifier"]}
    if normalize_name(a["name"]) == normalize_name(b["name"]):
        if same_jur:
            reasons.append("normalized names equal in one script and one jurisdiction")
            return {"decision": "candidate", "reasons": reasons + ["not a merge: no registry identifier"]}
        return {"decision": "needs_registry_id",
                "reasons": ["normalized names equal but jurisdiction differs or is unknown"]}
    return {"decision": "no_match", "reasons": ["normalized names differ"]}
