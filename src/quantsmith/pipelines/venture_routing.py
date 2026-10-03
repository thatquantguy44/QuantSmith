"""Request routing for the venture agent suite (spec 0096).

A deterministic router: it reads the rules in ``knowledge/venture_intelligence/routing.json`` and turns a
plain-language request into a plan, an ordered chain of the existing agents with the review gates and
decision owner attached, or into a refusal. It decides nothing about the substance of the request.

What it enforces:
* **Refusals first.** A request to recommend an investment, designate or attribute, profile a person,
  collect from non-public sources, release without review, set a mark, classify export control, or
  forecast returns is refused and pointed at the human who owns that decision; any legitimate part of
  the request is still planned.
* **Strictest class wins.** The plan's decision-path class is the strictest among its agents, and the
  caller's clearance must cover it; a caller below that clearance gets ``denied`` with no steps.
* **No guessing.** Keyword matching only. A tie or no match returns ``needs_clarification``.

A routing plan is not authorization to act, and a plan that looks complete does not make its outputs
correct.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from quantsmith.adapters.mcp_servers.contract import ACCESS_RANK, clearance_allows
from quantsmith.asian_nlp.identify import script_shares

ROUTING_FILE = "knowledge/venture_intelligence/routing.json"
LEAD, STRUCTURE = "{regional_lead}", "{regional_structure_analyst}"
NON_ENGLISH_SCRIPTS = ("han", "kana", "hangul", "thai", "cyrillic", "devanagari")


def load_routing(root: Path = Path(".")) -> Dict[str, Any]:
    return json.loads((Path(root) / ROUTING_FILE).read_text(encoding="utf-8"))


def _has(text: str, phrase: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(phrase.casefold()), text.casefold()) is not None


def detect_regions(text: str, routing: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Regions whose keywords appear in the request, in the routing file's order."""
    return [r for r in routing["regions"] if any(_has(text, k) for k in r["keywords"])]


def classify_task(text: str, routing: Mapping[str, Any]) -> List[Tuple[int, Dict[str, Any]]]:
    """Task kinds ranked by how many distinct keywords the request contains (highest first, ties by id)."""
    scored = [(sum(1 for k in t["keywords"] if _has(text, k)), t) for t in routing["task_kinds"]]
    return sorted([s for s in scored if s[0] > 0], key=lambda s: (-s[0], s[1]["id"]))


def forbidden_hits(text: str, routing: Mapping[str, Any]) -> List[Dict[str, Any]]:
    return [f for f in routing["forbidden_intents"] if any(re.search(p, text, re.IGNORECASE) for p in f["patterns"])]


def _agent_tables(pack: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {a["id"]: a for a in pack["coverage"]["agents"] if a["status"] == "built"}


def _strictest(classes: Sequence[str], order: Sequence[str]) -> str:
    present = set(classes)
    if "sovereign_adjacent" in present:
        return "sovereign_adjacent"
    if "person_adjacent" in present:
        return "person_adjacent"
    return order[0]


def plan_request(text: str, caller_clearance: Optional[str], pack: Mapping[str, Any]) -> Dict[str, Any]:
    """Route a request. ``pack`` is ``load_pack(...)`` (it must include ``routing`` and ``coverage``)."""
    if caller_clearance not in ACCESS_RANK:
        raise PermissionError("caller_clearance is required and must be public, internal, or restricted")
    routing, agents = pack["routing"], _agent_tables(pack)
    rules = routing["class_rules"]
    base: Dict[str, Any] = {"request": text, "status": "needs_clarification", "task_kind": None, "steps": [],
                            "decision_path_class": None, "required_clearance": None, "human_review": [],
                            "decision_owner": None, "refusals": [], "notes": [], "limits": routing["limits"]}
    if not text.strip():
        return {**base, "notes": ["the request is empty"]}

    refusals = [{"intent": f["id"], "refusal": f["refusal"], "decision_owner": f["decision_owner"],
                 "alternatives": f["alternatives"]} for f in forbidden_hits(text, routing)]
    ranked = classify_task(text, routing)
    regions = detect_regions(text, routing)
    built = [r for r in regions if r["status"] == "built"]
    deferred = [r for r in regions if r["status"] != "built"]
    notes: List[str] = [f"region {r['name']} has no agent yet ({r['status']})" for r in deferred]

    if not ranked:
        status = "refused" if refusals else "needs_clarification"
        why = ["no part of the request could be routed"] if refusals else ["no task kind matched; say what you want done (for example a landscape scan, a diligence memo, or a fund review)"]
        return {**base, "status": status, "refusals": refusals, "notes": notes + why}
    if len(ranked) > 1 and ranked[0][0] == ranked[1][0]:
        tied = [t["id"] for s, t in ranked if s == ranked[0][0]]
        return {**base, "status": "needs_clarification", "refusals": refusals,
                "notes": notes + [f"the request fits several task kinds equally: {', '.join(tied)}"], "candidates": tied}

    task = ranked[0][1]
    if task["id"] == "task.region_overview" and not built:
        return {**base, "status": "needs_clarification", "task_kind": task["id"], "refusals": refusals,
                "notes": notes + ["name a market (for example Singapore, India, Japan, or Kazakhstan)"]}

    steps: List[str] = []

    def add(agent_id: str) -> None:
        if agent_id not in steps:
            steps.append(agent_id)

    prefixes = {r["id"].split(".", 1)[1]: r for r in routing["regions"] if r["status"] == "built"}
    for entry in task["chain"]:
        if entry == LEAD:
            if not built:
                notes.append("no region named: the regional lead step was omitted")
            for r in built:
                add(r["lead"])
        elif entry == STRUCTURE:
            if not built:
                notes.append("no region named: the regional structure analyst step was omitted")
            for r in built:
                if r["structure_analyst"]:
                    add(r["structure_analyst"])
                else:
                    notes.append(f"{r['name']} has no structure analyst; use the shared ownership and entity agents and flag the gap")
        else:
            owner = next((reg for pre, reg in prefixes.items() if entry.startswith(pre + "_") and not entry.endswith("_lead")), None)
            if owner is not None and owner not in built:
                notes.append(f"{entry} covers {owner['name']} only and was skipped")
                continue
            add(entry)

    shares = script_shares(text)
    if any(shares.get(s, 0) > 0 for s in NON_ENGLISH_SCRIPTS) and routing["language_step"]["agent"] not in steps:
        steps.insert(0, routing["language_step"]["agent"])
        notes.append("non-English script detected: document NLP inserted first")

    missing = [s for s in steps if s not in agents]
    if missing:
        raise ValueError(f"routing refers to agents that are not built: {', '.join(missing)}")
    cls = _strictest([agents[s].get("decision_path_class", "analytic_support") for s in steps], rules["strictness_order"])
    required = rules["required_clearance"][cls]
    if not clearance_allows(required, caller_clearance):
        return {**base, "status": "denied", "task_kind": task["id"], "refusals": refusals,
                "notes": ["this class of work needs a higher clearance than the caller holds"]}
    review = list(task["review_gates"]) + ([rules["human_review"][cls]] if cls in rules["human_review"] else [])
    return {**base, "status": "planned", "task_kind": task["id"], "decision_path_class": cls,
            "required_clearance": required, "human_review": review, "decision_owner": task["decision_owner"],
            "refusals": refusals, "notes": notes,
            "steps": [{"order": i, "agent": s, "path": agents[s]["path"],
                       "class": agents[s].get("decision_path_class", "analytic_support")} for i, s in enumerate(steps, 1)]}
