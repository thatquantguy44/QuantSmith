"""Deterministic tradecraft helpers for spec 0090.

Pure, standard-library functions behind the venture tradecraft and screening
agents: grade parsing, corroboration counting, likelihood-word checks, a
competing-hypotheses matrix, effective ownership through chains, a lint for
conclusion language, and a prohibited-source check for collection requirements.

What they do not do: grade a source, choose a conclusion, classify a technology,
or designate an entity. They report arithmetic and structure; people decide.
"""

from __future__ import annotations

from datetime import date
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

VAGUE_TERMS = ("may", "might", "could", "possibly", "perhaps", "potentially", "conceivably")
CONCLUSION_TERMS = ("evad", "violat", "illegal", "unlawful", "guilty", "front company",
                    "sham", "is controlled by the government", "controlled by the party",
                    "sanctions evasion", "sanctioned entity")
RATINGS = ("C", "I", "N")


# ------------------------------------------------------------------ grades
def parse_grade(grade: str, conventions: Mapping[str, Any]) -> Tuple[str, str]:
    """Split a grade like ``B2`` into (reliability, credibility), validating both axes."""
    sg = conventions["source_grade"]
    if len(grade) != 2 or grade[0] not in sg["reliability_scale"] or grade[1] not in sg["credibility_scale"]:
        raise ValueError(f"invalid grade {grade!r}; expected a letter A-F then a digit 1-6")
    return grade[0], grade[1]


def grade_without_basis() -> str:
    """The only grade allowed when no basis is stated: cannot be judged on either axis."""
    return "F6"


# ----------------------------------------------------------- corroboration
def corroboration_status(items: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Per claim: items, independent origins, channels, and a status.

    Items that share an ``origin_id`` (syndication, republication) are one origin.
    Status: ``single_source`` (one item), ``echo`` (several items, one origin),
    ``single_channel`` (several origins, one channel), ``corroborated`` (several
    origins across at least two channels).
    """
    by_claim: Dict[str, List[Mapping[str, Any]]] = {}
    for it in items:
        by_claim.setdefault(it["claim_id"], []).append(it)
    out: Dict[str, Dict[str, Any]] = {}
    for claim, rows in sorted(by_claim.items()):
        origins = {r["origin_id"] for r in rows}
        channels = {r["channel"] for r in rows}
        if len(rows) == 1:
            status = "single_source"
        elif len(origins) == 1:
            status = "echo"
        elif len(channels) == 1:
            status = "single_channel"
        else:
            status = "corroborated"
        out[claim] = {"items": len(rows), "independent_origins": len(origins),
                      "channels": len(channels), "status": status}
    return out


# ---------------------------------------------------------- likelihood words
def band_label(probability: float, conventions: Mapping[str, Any]) -> str:
    bands = conventions["confidence_language"]["bands"]
    for b in bands:
        if b["low"] <= probability < b["high"]:
            return b["label"]
    if probability == bands[-1]["high"]:
        return bands[-1]["label"]
    raise ValueError(f"probability {probability} is outside the confidence bands")


def check_statement(label: str, probability: float, conventions: Mapping[str, Any]) -> Dict[str, Any]:
    expected = band_label(probability, conventions)
    return {"ok": expected == label.strip().lower(), "stated": label, "expected": expected}


def vague_terms(text: str) -> List[Dict[str, Any]]:
    """Find hedging words that carry no probability; positions index the original text."""
    found = []
    for term in VAGUE_TERMS:
        for m in re.finditer(rf"\b{term}\b", text, flags=re.I):
            found.append({"term": m.group(0), "start": m.start(), "end": m.end()})
    return sorted(found, key=lambda f: f["start"])


# ------------------------------------------------------------------- ACH
def validate_hypotheses(hypotheses: Sequence[Mapping[str, Any]]) -> List[str]:
    errors = []
    if len(hypotheses) < 2:
        errors.append("at least two hypotheses are required")
    if not any(h.get("kind") == "deception_or_artifact" for h in hypotheses):
        errors.append("a deception_or_artifact hypothesis is required")
    return errors


def ach_matrix(hypotheses: Sequence[Mapping[str, Any]], evidence: Sequence[Mapping[str, Any]],
               ratings: Mapping[Tuple[str, str], str]) -> Dict[str, Any]:
    """Count weighted inconsistencies per hypothesis; report, never conclude.

    ``ratings[(evidence_id, hypothesis_id)]`` is ``C`` consistent, ``I`` inconsistent,
    or ``N`` neutral. Evidence rated identically across all hypotheses is
    non-diagnostic. Evidence from one origin is counted once (the largest weight).
    """
    errors = validate_hypotheses(hypotheses)
    if errors:
        raise ValueError("; ".join(errors))
    hyp_ids = [h["id"] for h in hypotheses]
    weights: Dict[str, float] = {}
    origin_best: Dict[str, Tuple[float, str]] = {}
    for e in evidence:
        w = float(e.get("weight", 1.0))
        weights[e["id"]] = w
        o = e.get("origin_id")
        if o is not None and (o not in origin_best or w > origin_best[o][0]):
            origin_best[o] = (w, e["id"])
    counted = {eid for _, eid in origin_best.values()}
    for e in evidence:
        if e.get("origin_id") is not None and e["id"] not in counted:
            weights[e["id"]] = 0.0
    inconsistency = {h: 0.0 for h in hyp_ids}
    diagnostic, non_diagnostic = [], []
    for e in evidence:
        row = []
        for h in hyp_ids:
            r = ratings.get((e["id"], h), "N")
            if r not in RATINGS:
                raise ValueError(f"invalid rating {r!r} for ({e['id']}, {h})")
            row.append(r)
            if r == "I":
                inconsistency[h] += weights[e["id"]]
        (non_diagnostic if len(set(row)) == 1 else diagnostic).append(e["id"])
    ordering = sorted(hyp_ids, key=lambda h: (inconsistency[h], h))
    return {"inconsistency": inconsistency, "ordering_by_fewest_inconsistencies": ordering,
            "diagnostic_evidence": diagnostic, "non_diagnostic_evidence": non_diagnostic,
            "note": "ordering is a matrix result, not a conclusion"}


def sensitivity(hypotheses: Sequence[Mapping[str, Any]], evidence: Sequence[Mapping[str, Any]],
                ratings: Mapping[Tuple[str, str], str]) -> List[str]:
    """Evidence IDs whose removal changes the ordering of hypotheses."""
    base = ach_matrix(hypotheses, evidence, ratings)["ordering_by_fewest_inconsistencies"]
    changed = []
    for e in evidence:
        rest = [x for x in evidence if x["id"] != e["id"]]
        if ach_matrix(hypotheses, rest, ratings)["ordering_by_fewest_inconsistencies"] != base:
            changed.append(e["id"])
    return changed


# -------------------------------------------------------------- ownership
def effective_ownership(edges: Sequence[Mapping[str, Any]], holder: str, target: str) -> Dict[str, Any]:
    """Effective ownership of ``target`` by ``holder`` through equity chains.

    Each edge: ``owner``, ``owned``, ``pct`` (fraction), ``mechanism`` (``equity`` or
    ``contract``), ``as_of``. Only equity edges are multiplied; contractual edges
    are listed as excluded, never converted into ownership. Paths are summed;
    cycles are not followed. A total above 1.0 is flagged as a data problem.
    """
    equity: Dict[str, List[Mapping[str, Any]]] = {}
    excluded = []
    for e in edges:
        if e.get("mechanism") != "equity":
            excluded.append({"owner": e["owner"], "owned": e["owned"], "mechanism": e.get("mechanism")})
            continue
        if not (0.0 <= float(e["pct"]) <= 1.0):
            raise ValueError(f"pct out of range on {e['owner']}->{e['owned']}")
        if not e.get("as_of"):
            raise ValueError(f"equity link {e['owner']}->{e['owned']} has no as_of date")
        equity.setdefault(e["owner"], []).append(e)
    paths: List[Dict[str, Any]] = []

    def walk(node: str, seen: Tuple[str, ...], product: float) -> None:
        if node == target and seen:
            paths.append({"path": list(seen), "product": product})
            return
        for e in equity.get(node, []):
            if e["owned"] in seen:
                continue
            walk(e["owned"], seen + (e["owned"],), product * float(e["pct"]))

    walk(holder, (holder,), 1.0)
    total = sum(p["product"] for p in paths)
    return {"holder": holder, "target": target, "effective": total, "paths": paths,
            "excluded_links": excluded, "exceeds_one": total > 1.0 + 1e-9}


def crosses_threshold(effective: float, threshold: float) -> Dict[str, Any]:
    """Compare to a caller-supplied threshold; the threshold is the caller's, not asserted here."""
    return {"effective": effective, "caller_threshold": threshold,
            "at_or_above": effective + 1e-12 >= threshold, "threshold_source": "caller"}


# ------------------------------------------------------ language and sources
def conclusion_language_findings(text: str) -> List[Dict[str, Any]]:
    """Lint a screening output for wording that states a conclusion rather than an indicator.

    A heuristic: it finds terms, not meaning. A clean result does not make a
    text safe, and a hit does not make it wrong; it asks a human to look.
    """
    out = []
    for term in CONCLUSION_TERMS:
        for m in re.finditer(re.escape(term), text, flags=re.I):
            out.append({"term": term, "start": m.start(), "end": m.end()})
    return sorted(out, key=lambda f: f["start"])


def candidate_channel_check(source_class: str, conventions: Mapping[str, Any]) -> str:
    """Return the class if lawful; raise for a prohibited source class."""
    if source_class in set(conventions["prohibited_source_classes"]):
        raise ValueError(f"prohibited source class {source_class!r} may not be proposed")
    return source_class


def requirement_age_days(opened: str, today: str) -> int:
    return (date.fromisoformat(today) - date.fromisoformat(opened)).days


def orphan_requirements(register: Iterable[Mapping[str, Any]]) -> List[str]:
    """Requirement IDs that link to no decision."""
    return [r["id"] for r in register if not str(r.get("decision", "")).strip()]
