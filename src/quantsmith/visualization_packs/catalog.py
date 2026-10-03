"""Versioned, reference-only visualization recipes (spec 0093)."""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from quantsmith.pipelines import analytics_packs as analytics

SCHEMA_VERSION = "0093.1"
PACKS_DIR = Path("knowledge/visualization_packs")
INITIAL_DOMAINS = (
    "asset_management", "rates_fixed_income", "credit_risk", "finance_performance",
    "aml_financial_crime", "operations_settlement", "economics_macro",
)
VIEWS = ("level", "trend", "breakdown", "comparison", "attribution")
_ID = re.compile(r"^[a-z][a-z0-9_]*$")


class VisualizationError(ValueError):
    """An invalid contract or an unsupported evidence operation."""


def _strings(value):
    return isinstance(value, list) and bool(value) and all(isinstance(v, str) and v.strip() for v in value)


def resolve_metric(links, metric, analytics_by_id):
    matches = [(p, m) for p in links if p in analytics_by_id
               for m in analytics_by_id[p]["metrics"] if m["name"] == metric]
    if len(matches) != 1:
        raise VisualizationError(f"metric {metric!r} resolves to {len(matches)} linked definitions; clarify the reference")
    return matches[0]


def validate_pack(pack, analytics_by_id, root="."):
    """Return actionable findings, including malformed nested structures."""
    if not isinstance(pack, dict):
        return ("pack must be an object",)
    pid = pack.get("pack_id", "<unknown>")
    errors = []

    def error(message):
        errors.append(f"{pid}: {message}")

    fields = {"schema_version", "pack_id", "name", "analytics_pack_ids", "reviewer_agents", "review", "recipes"}
    if set(pack) != fields:
        error(f"fields differ: missing {sorted(fields - set(pack))}, unknown {sorted(set(pack) - fields)}")
    if pack.get("schema_version") != SCHEMA_VERSION:
        error("unsupported schema_version")
    if not isinstance(pid, str) or not _ID.fullmatch(pid):
        error("pack_id must be lower_snake_case")
    if not isinstance(pack.get("name"), str) or not pack["name"].strip():
        error("name is required")
    links = pack.get("analytics_pack_ids")
    if not _strings(links):
        error("analytics_pack_ids must be a nonempty string list")
        links = []
    elif len(set(links)) != len(links) or any(p not in analytics_by_id for p in links):
        error("duplicate or unknown analytics pack reference")
    reviewers = pack.get("reviewer_agents")
    if not _strings(reviewers):
        error("reviewer_agents must be a nonempty string list")
    else:
        for reviewer in reviewers:
            path = Path(root) / reviewer / "prompt.md"
            if not reviewer.startswith("agents/") or ".." in Path(reviewer).parts or not path.is_file():
                error(f"unknown reviewer {reviewer!r}")
    review = pack.get("review")
    if not isinstance(review, dict) or set(review) != {"status", "reviewer", "reviewed_on"}:
        error("review requires status, reviewer, reviewed_on")
    elif review["status"] not in analytics.REVIEW_STATUSES:
        error("unknown review status")
    elif review["status"] == "reviewed":
        try:
            if not isinstance(review["reviewer"], str) or not review["reviewer"].strip():
                raise ValueError()
            if date.fromisoformat(review["reviewed_on"]).isoformat() != review["reviewed_on"]:
                raise ValueError()
        except (TypeError, ValueError):
            error("reviewed requires a named reviewer and valid ISO date")
    recipes = pack.get("recipes")
    if not isinstance(recipes, list) or len(recipes) < 2:
        error("at least two recipes are required")
        return tuple(errors)
    ids, intents, signatures = set(), set(), set()
    for recipe in recipes:
        if not isinstance(recipe, dict):
            error("recipe must be an object")
            continue
        expected = {"recipe_id", "intent", "audiences", "decision", "sections", "action"}
        if set(recipe) != expected:
            error("recipe fields differ from the contract")
        for field, seen in (("recipe_id", ids), ("intent", intents)):
            value = recipe.get(field)
            if not isinstance(value, str) or not _ID.fullmatch(value) or value in seen:
                error(f"invalid or duplicate {field}")
            else:
                seen.add(value)
        if not _strings(recipe.get("audiences")) or set(recipe["audiences"]) != {"executive", "analyst"}:
            error("recipe must support executive and analyst audiences")
        for field in ("decision", "action"):
            if not isinstance(recipe.get(field), str) or not recipe[field].strip():
                error(f"recipe {field} is required")
        # These fields are prompts, never a loophole for unbound numeric claims.
        action = recipe.get("action", "")
        if not isinstance(action, str) or not action.startswith(("Review ", "Investigate ", "Compare ", "Confirm ", "Validate ")) or re.search(r"\d", action):
            error("action must be a nonnumeric investigation prompt")
        sections = recipe.get("sections")
        if not isinstance(sections, list) or not sections:
            error("recipe needs ordered sections")
            continue
        section_ids, signature = set(), []
        for section in sections:
            expected = {"section_id", "metric", "dimensions", "view", "chart_rule", "fallback_reason", "interpretation", "caveats"}
            if not isinstance(section, dict) or set(section) != expected:
                error("section fields differ from the contract (metric overrides are forbidden)")
                continue
            sid = section["section_id"]
            if not isinstance(sid, str) or not _ID.fullmatch(sid) or sid in section_ids:
                error("invalid or duplicate section_id")
            else:
                section_ids.add(sid)
            dims = section["dimensions"]
            if not isinstance(dims, list) or len(dims) > 2 or any(not isinstance(d, str) for d in dims):
                error("dimensions must be a list of at most two names")
                continue
            if len(set(dims)) != len(dims):
                error("duplicate dimension")
            try:
                aid, metric = resolve_metric(links, section["metric"], analytics_by_id)
                base = analytics_by_id[aid]
                if set(dims) - {d["name"] for d in base["dimensions"]}:
                    error("unknown dimension")
                if section["view"] == "attribution" and "contributor" in analytics.suppressed_insights(base, metric["name"]):
                    error("attribution requests a suppressed contributor insight")
            except VisualizationError as exc:
                error(str(exc))
            if section["view"] not in VIEWS:
                error("unsupported view")
            if section["view"] in ("level", "trend", "comparison") and dims:
                error("level, trend, and comparison require an ungrouped result")
            if section["view"] in ("breakdown", "attribution") and not dims:
                error("breakdown and attribution require dimensions")
            if section["chart_rule"] not in ("shape", "table"):
                error("unsupported chart_rule")
            if not isinstance(section["fallback_reason"], str) or (section["chart_rule"] == "table" and not section["fallback_reason"].strip()):
                error("table rule must explain its fallback")
            interpretation = section["interpretation"]
            if not isinstance(interpretation, str) or not interpretation.endswith("?") or re.search(r"\d", interpretation):
                error("interpretation must be a nonnumeric investigation question")
            if not isinstance(section["caveats"], list) or any(not isinstance(c, str) or not c.strip() for c in section["caveats"]):
                error("caveats must be a string list")
            signature.append((str(section["metric"]), tuple(dims), str(section["view"])))
        signature = tuple(signature)
        if signature in signatures:
            error("recipes must have distinct evidence requirements")
        signatures.add(signature)
    return tuple(errors)


@dataclass(frozen=True)
class Selection:
    status: str
    reason: str
    candidates: tuple[tuple[str, str], ...] = ()


@dataclass
class Catalog:
    packs: dict
    analytics: dict
    root: Path

    def coverage(self):
        covered = {p for pack in self.packs.values() for p in pack["analytics_pack_ids"]}
        return {p: ("covered" if p in covered else "uncovered") for p in sorted(self.analytics)}

    def select(self, domains, intent):
        bases = analytics.select_packs(sorted(set(domains)), [self.analytics[k] for k in sorted(self.analytics)])
        candidates = tuple(sorted((pid, r["recipe_id"]) for pid, p in self.packs.items()
                                  if set(p["analytics_pack_ids"]) <= set(bases.pack_ids)
                                  for r in p["recipes"] if r["intent"] == intent))
        if bases.synonym_conflicts and candidates:
            return Selection("clarification_needed", "Selected analytics packs have conflicting metric vocabulary.", candidates)
        if not candidates:
            return Selection("unavailable", "No visualization recipe supports the supplied domains and intent.")
        if len(candidates) > 1:
            return Selection("clarification_needed", "More than one recipe matches; choose a pack and recipe explicitly.", candidates)
        return Selection("selected", "Matched source domains and analytical intent.", candidates)


def load_catalog(root="."):
    root = Path(root)
    bases = analytics.load_packs(root, strict=True)
    analytics_by_id = {p["pack_id"]: p for p in bases}
    packs, errors = {}, []
    for path in sorted((root / PACKS_DIR).glob("*.json")):
        try:
            pack = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        errors.extend(validate_pack(pack, analytics_by_id, root))
        pid = pack.get("pack_id") if isinstance(pack, dict) else None
        if not isinstance(pid, str):
            continue
        if pid != path.stem or pid in packs:
            errors.append(f"{path.name}: duplicate ID or filename mismatch")
        packs[pid] = pack
    if not errors:
        covered = {p for pack in packs.values() for p in pack["analytics_pack_ids"]}
        if set(INITIAL_DOMAINS) - covered:
            errors.append("catalog missing initial domains: " + ", ".join(sorted(set(INITIAL_DOMAINS) - covered)))
        if {analytics_by_id[p]["family"] for p in covered} != set(analytics.FAMILIES):
            errors.append("catalog must represent all seven families")
    if errors:
        raise VisualizationError("\n".join(errors))
    return Catalog(copy.deepcopy(packs), analytics_by_id, root)
