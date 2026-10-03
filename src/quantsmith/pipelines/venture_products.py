"""Intelligence-product validation and rendering for spec 0092.

The ``intelligence_brief_writer`` and ``investment_memo_writer`` agents draft briefs and memos. This
module is the teeth behind their contracts: ``validate_product`` refuses a draft that has an uncited
claim, cites something the product's classification or date does not allow, blurs evidence with
judgement, states a likelihood that does not match its probability, claims high confidence without
independent corroboration, leans only on unreviewed translated or model-produced evidence, uses
conclusion language, or (for a memo) recommends, approves, or rejects an investment.

It validates structure and wording. It cannot tell whether a cited passage truly supports a claim,
and a clean result does not make a product correct; a named human reviewer still releases it.
Rules live in ``knowledge/venture_intelligence/conventions.json`` (``product_rules``).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional, Tuple

from quantsmith.adapters.mcp_servers.contract import ACCESS_RANK
from quantsmith.asian_nlp.extract import load_conventions

from .venture_tradecraft import (check_statement, conclusion_language_findings, corroboration_status,
                                 parse_grade, vague_terms)

SECTION_KEYS = ("evidence", "assumptions", "judgements", "open_gaps")


def _named(value: Any) -> bool:
    """True only for a non-empty string; ``None`` and non-strings are never a name."""
    return isinstance(value, str) and bool(value.strip())


def index_passages(*results: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Merge retrieval results into ``{citation_id: passage}``."""
    out: Dict[str, Dict[str, Any]] = {}
    for r in results:
        for p in r.get("passages", []):
            out[p["citation_id"]] = dict(p)
    return out


def _texts(product: Mapping[str, Any]) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    if product.get("bluf"):
        out.append(("bluf", str(product["bluf"])))
    for key in SECTION_KEYS:
        for item in product.get(key, []) or []:
            out.append((str(item.get("id", key)), str(item.get("text", ""))))
            if item.get("basis"):
                out.append((str(item.get("id", key)), str(item["basis"])))
    return out


def validate_product(product: Mapping[str, Any], index: Mapping[str, Mapping[str, Any]],
                     conventions: Optional[Mapping[str, Any]] = None) -> List[str]:
    """Errors as ``"<item>: <code>: detail"``; empty when the draft meets the rules."""
    conv = conventions or load_conventions()
    rules = conv["product_rules"]
    errors: List[str] = []
    kind = product.get("kind")
    if kind not in rules["kinds"]:
        return [f"product: invalid_kind: {kind!r}"]
    spec = rules["kinds"][kind]
    as_of = str(product.get("as_of", ""))
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", as_of):
        errors.append("product: invalid_as_of: an ISO date is required")
    level = product.get("access_level")
    if level not in ACCESS_RANK:
        errors.append("product: invalid_access_level: public, internal, or restricted")
        level = "restricted"
    for section in spec["required_sections"]:
        value = product.get(section)
        if not value:
            errors.append(f"product: missing_section: {section} is required and may not be empty")
    for field in spec.get("required_fields", []):
        if not _named(product.get(field)):
            errors.append(f"product: missing_field: {field}")
    if kind == "intelligence_brief" and len(str(product.get("bluf", ""))) > spec["bluf_max_chars"]:
        errors.append(f"bluf: bluf_too_long: more than {spec['bluf_max_chars']} characters")

    ids: List[str] = []
    for key in SECTION_KEYS:
        ids += [str(i.get("id")) for i in product.get(key, []) or []]
    for dup in {i for i in ids if ids.count(i) > 1}:
        errors.append(f"{dup}: duplicate_id: ids must be unique across sections")

    evidence = {str(e["id"]): e for e in product.get("evidence", []) or []}
    assumptions = {str(a["id"]): a for a in product.get("assumptions", []) or []}
    for eid, e in evidence.items():
        cites = e.get("citations") or []
        if not cites:
            errors.append(f"{eid}: uncited_claim: every evidence item cites at least one retrieved passage")
        for cid in cites:
            p = index.get(cid)
            if p is None:
                errors.append(f"{eid}: unresolvable_citation: {cid}")
                continue
            if as_of and str(p.get("known_at", "9999")) > as_of:
                errors.append(f"{eid}: cites_future_information: {cid} known {p.get('known_at')} after {as_of}")
            if ACCESS_RANK.get(p.get("access_level"), 99) > ACCESS_RANK[level]:
                errors.append(f"{eid}: cites_above_classification: {cid} is {p.get('access_level')}, product is {level}")
        try:
            parse_grade(str(e.get("source_grade", "")), conv)
        except ValueError:
            errors.append(f"{eid}: invalid_source_grade: {e.get('source_grade')!r}")
    for aid, a in assumptions.items():
        if not _named(a.get("basis")):
            errors.append(f"{aid}: assumption_without_basis: state why the assumption is made")

    claim_items = [{"claim_id": e.get("claim_id", eid), "origin_id": e.get("origin_id", eid),
                    "channel": e.get("channel", "unknown")} for eid, e in evidence.items()]
    status = corroboration_status(claim_items) if claim_items else {}
    levels = rules["evidence_confidence_levels"]
    for j in product.get("judgements", []) or []:
        jid = str(j.get("id"))
        supports = [r for r in j.get("rests_on", []) or [] if r in evidence]
        unknown = [r for r in j.get("rests_on", []) or [] if r not in evidence and r not in assumptions]
        for r in unknown:
            errors.append(f"{jid}: unknown_support: {r}")
        if not supports:
            errors.append(f"{jid}: judgement_without_evidence: rests_on must name at least one evidence item")
        try:
            chk = check_statement(str(j.get("likelihood", "")), float(j.get("probability")), conv)
            if not chk["ok"]:
                errors.append(f"{jid}: likelihood_mismatch: stated {chk['stated']!r}, probability implies {chk['expected']!r}")
        except (TypeError, ValueError):
            errors.append(f"{jid}: likelihood_unverifiable: a likelihood word and a probability in [0.01, 0.99] are required")
        if j.get("evidence_confidence") not in levels:
            errors.append(f"{jid}: invalid_evidence_confidence: one of {', '.join(levels)}")
        if vague_terms(str(j.get("text", ""))):
            errors.append(f"{jid}: vague_wording: hedging without a probability")
        if supports and all(evidence[s].get("derived") and not _named(evidence[s].get("reviewer")) for s in supports):
            errors.append(f"{jid}: rests_only_on_unreviewed_derived_evidence: translated or model-produced evidence needs a named reviewer")
        if j.get("evidence_confidence") == "high":
            weak = [s for s in supports if status.get(str(evidence[s].get("claim_id", s)), {}).get("status") != "corroborated"]
            if weak:
                errors.append(f"{jid}: high_confidence_without_corroboration: {', '.join(weak)} lack independent origins across channels")

    for owner, text in _texts(product):
        for f in conclusion_language_findings(text):
            errors.append(f"{owner}: conclusion_language: {f['term']!r} states a conclusion, not an indicator")
        if kind == "investment_memo":
            for pat in rules["recommendation_terms"]:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    errors.append(f"{owner}: recommendation_language: {m.group(0)!r}; the investment committee decides")
    if product.get("status") not in rules["draft_statuses"] and not _named(product.get("reviewer")):
        errors.append("product: premature_final_status: only a named human reviewer releases a product")
    return errors


def releasable(product: Mapping[str, Any], index: Mapping[str, Mapping[str, Any]],
               conventions: Optional[Mapping[str, Any]] = None) -> Tuple[bool, List[str]]:
    """Releasable only when the draft validates and a named human reviewer is recorded."""
    reasons = validate_product(product, index, conventions)
    if not _named(product.get("reviewer")):
        reasons = reasons + ["product: no_named_reviewer: a human must review and release"]
    return (not reasons, reasons)


def render_markdown(product: Mapping[str, Any], index: Mapping[str, Mapping[str, Any]]) -> str:
    """Deterministic Markdown. A product with no named reviewer carries a DRAFT banner."""
    reviewer = product.get("reviewer")
    lines = [f"# {product.get('title', '')}", "",
             f"- **Kind:** {product.get('kind')}  **As of:** {product.get('as_of')}  "
             f"**Classification:** {product.get('access_level')}"]
    if product.get("decision_owner"):
        lines.append(f"- **Decision owner:** {product['decision_owner']}")
    lines.append(f"- **Reviewer:** {reviewer}" if reviewer else
                 "- **DRAFT - not reviewed.** A named human must review and release this product.")
    lines.append("")
    if product.get("bluf"):
        lines += ["## Bottom line up front", "", str(product["bluf"]), ""]
    lines += ["## Evidence", ""]
    for e in product.get("evidence", []) or []:
        tag = " (translated or model-derived)" if e.get("derived") else ""
        lines.append(f"- **{e['id']}** [{e.get('source_grade')}]{tag}: {e.get('text')} "
                     f"[{', '.join(e.get('citations') or [])}]")
    lines += ["", "## Assumptions", ""]
    lines += [f"- **{a['id']}**: {a.get('text')} (basis: {a.get('basis')})" for a in product.get("assumptions", []) or []]
    lines += ["", "## Judgement", ""]
    for j in product.get("judgements", []) or []:
        lines.append(f"- **{j['id']}**: {j.get('text')} - {j.get('likelihood')} (p={j.get('probability')}); "
                     f"evidence confidence {j.get('evidence_confidence')}; rests on {', '.join(j.get('rests_on') or [])}")
    lines += ["", "## Open gaps", ""]
    lines += [f"- **{g['id']}**: {g.get('text')}" for g in product.get("open_gaps", []) or []]
    cited = sorted({c for e in product.get("evidence", []) or [] for c in e.get("citations") or []})
    lines += ["", "## Sources", ""]
    for cid in cited:
        p = index.get(cid, {})
        lines.append(f"- `{cid}` {p.get('source_id', '?')} [{p.get('source_grade', '?')}] known {p.get('known_at', '?')} "
                     f"{p.get('access_level', '?')} hash {str(p.get('content_hash', ''))[:12]}")
    return "\n".join(lines) + "\n"
