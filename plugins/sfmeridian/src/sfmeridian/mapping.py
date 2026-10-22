"""Semantic mapping: governed concepts bound to physical columns, validated.

Spec ``0115`` REQ-005–REQ-008 (realizing ``0113`` REQ-008, REQ-013, REQ-024,
REQ-025). The vocabulary is never the plugin's own:

* the ``0081`` pack selected by ``governed_tier.domain_tags`` (metrics with
  units and additivity, and dimensions);
* the shipped, *proposed* pack amendments (``data/pack_amendments.json``),
  usable with a caveat until the named reviewer accepts them through the
  ``0081`` flow;
* ``0063`` concept IDs from ``knowledge/short_term_markets/taxonomy.json``.

A concept outside all three is a private definition and is rejected; the fix
is a pack amendment, not a mapping. Each binding (``semantic_mapping.<profile>``)
names its concept, a single-table expression over catalog columns, an
aggregation, the dimensions it can be sliced by, the point-in-time column,
the viewpoint, the unit (the pack's, or a declared conversion), and its
evidence: a reviewed, undrifted exemplar that reads the same column, or the
confirmation of a configured promoter. Ratio bindings divide two bound,
summable measures over dimensions both support, from one viewpoint, so
``0008``'s "ratio over the same rows" rule holds by construction.

``governed_tier.metric_sources`` bind governed metrics to the reviewed
query that supplies their base measures; a missing, unreviewed, drifted, or
mis-mapped source makes the metric *unavailable* to the governed tier.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import catalog as catalog_mod
from .governed import packs as packs_mod

__all__ = ["AMENDMENTS_PATH", "VIEWPOINTS", "Vocabulary", "validate_mapping"]

AMENDMENTS_PATH = Path(__file__).parent / "data" / "pack_amendments.json"
VIEWPOINTS = ("lender", "beneficial_owner", "agent_lender", "borrower")
AGGREGATIONS = ("sum", "count", "avg", "min", "max", "none")
QUOTES = {"concept.borrow_fee": "fee", "concept.rebate_rate": "rebate"}
_COLUMN_REF = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*){1,3}")
_ALLOWED_REST = re.compile(r"^[\s0-9.+\-*/()]*$")


def _problem(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


@dataclass
class Vocabulary:
    pack: dict[str, Any] | None
    pack_source: dict[str, Any]
    amendments: dict[str, Any]
    taxonomy: dict[str, Any] | None
    notes: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, config: Any) -> Vocabulary:
        gov = config.data.get("governed_tier", {})
        notes: list[str] = []
        try:
            packs, source = packs_mod.resolve(gov.get("packs_root"))
            pack = packs_mod.select_pack(packs, gov.get("domain_tags") or [])
            if pack is None:
                notes.append(f"no pack selected by domain_tags {gov.get('domain_tags')}")
        except (LookupError, ValueError) as exc:
            pack, source = None, {"mode": None, "error": str(exc)}
            notes.append(str(exc))
        tax = packs_mod.taxonomy(gov.get("packs_root"))
        if tax is None:
            notes.append("0063 taxonomy not found; 0063 concept IDs cannot be used")
        amendments = json.loads(AMENDMENTS_PATH.read_text(encoding="utf-8"))
        return cls(pack, source, amendments, tax, notes)

    # -- lookups ----------------------------------------------------------
    @property
    def pack_metrics(self) -> dict[str, dict[str, Any]]:
        return {m["name"]: m for m in (self.pack or {}).get("metrics", [])}

    @property
    def pack_dimensions(self) -> set[str]:
        return {d["name"] for d in (self.pack or {}).get("dimensions", [])}

    @property
    def amendment_metrics(self) -> dict[str, dict[str, Any]]:
        return {m["name"]: m for m in self.amendments.get("metrics", []) if m["name"] not in self.pack_metrics}

    @property
    def amendment_dimensions(self) -> dict[str, dict[str, Any]]:
        return {d["name"]: d for d in self.amendments.get("dimensions", []) if d["name"] not in self.pack_dimensions}

    @property
    def concepts(self) -> dict[str, dict[str, Any]]:
        return {c["id"]: c for c in (self.taxonomy or {}).get("concepts", [])}

    def kind_of(self, name: str) -> str | None:
        if name in self.pack_metrics:
            return "pack_metric"
        if name in self.amendment_metrics:
            return "amendment"
        if name in self.concepts:
            return "taxonomy"
        return None

    def metric(self, name: str) -> dict[str, Any] | None:
        return self.pack_metrics.get(name) or self.amendment_metrics.get(name)

    def concept_ref(self, name: str) -> str | None:
        if name in self.concepts:
            return name
        if name in self.amendment_metrics:
            return self.amendment_metrics[name].get("concept_ref")
        return self.amendments.get("concept_refs", {}).get(name)

    def dimension_kind(self, name: str) -> str | None:
        if name in self.pack_dimensions:
            return "pack_dimension"
        if name in self.amendment_dimensions:
            return "amendment"
        return None

    def non_interchangeable(self, a: str | None, b: str | None) -> bool:
        if not a or not b or a == b:
            return False
        return any({a, b} == set(pair) for pair in (self.taxonomy or {}).get("non_interchangeable_pairs", []))

    def pack_summary(self) -> dict[str, Any]:
        p = self.pack or {}
        review = p.get("review", {})
        reviewed = review.get("status") == "reviewed"
        return {"pack_id": p.get("pack_id"), "review_status": review.get("status"),
                "reviewer": review.get("reviewer"), "assigned_reviewer": self.amendments.get("reviewer"),
                "review_request": self.amendments.get("review_request"), "source": self.pack_source,
                "caveat": None if reviewed or not p else
                f"Pack {p.get('pack_id')} is {review.get('status')} (not reviewed by a named owner); governed "
                "numbers built on it carry the unreviewed-pack caveat.",
                "notes": list(self.notes)}


# --------------------------------------------------------------------------
# Binding validation
# --------------------------------------------------------------------------

def _exemplars(index_dir: Path) -> list[dict[str, Any]]:
    path = Path(index_dir) / "exemplars.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _find_exemplar(ref: str, exemplars: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    for e in exemplars:
        if e["exemplar_id"] == ref:
            return e
    matches = [e for e in exemplars if e.get("query_id") == ref]
    reviewed = [e for e in matches if e.get("review_status") == "reviewed"]
    return (reviewed or matches or [None])[0]


def _canon(resolver: catalog_mod.Resolver, ref: str) -> str | None:
    r = resolver.column(ref)
    return f"{r.table}.{r.column}".lower() if r.ok else None


def _check_expression(expr: Any, resolver: catalog_mod.Resolver, problems: list[dict[str, str]]
                      ) -> tuple[list[str], set[str]]:
    if not isinstance(expr, str) or not expr.strip():
        problems.append(_problem("E_MAP_EXPRESSION", "a measure needs an expression over catalog columns"))
        return [], set()
    refs = _COLUMN_REF.findall(expr)
    rest = _COLUMN_REF.sub(" ", expr)
    if not refs or not _ALLOWED_REST.match(rest):
        problems.append(_problem("E_MAP_EXPRESSION", "expressions use qualified columns, numbers, and + - * / ( ) "
                                                     "only (no functions, literals, or SQL)"))
        return [], set()
    canon, tables = [], set()
    for ref in refs:
        r = resolver.column(ref)
        if not r.ok:
            problems.append(_problem("E_MAP_UNRESOLVED", r.reason or f"{ref} does not resolve"))
            continue
        canon.append(f"{r.table}.{r.column}".lower())
        tables.add(r.table.lower())
    if len(tables) > 1:
        problems.append(_problem("E_MAP_MULTI_TABLE", f"expression spans tables {sorted(tables)}; bind each table's "
                                                      "measure separately and combine them as a ratio"))
    return canon, tables


def _validate_binding(b: Mapping[str, Any], profile: str, resolver: catalog_mod.Resolver | None, vocab: Vocabulary,
                      exemplars: Sequence[Mapping[str, Any]], excluded: Mapping[str, str], promoters: Sequence[str],
                      repo_profiles: Mapping[str, Any]) -> dict[str, Any]:
    problems: list[dict[str, str]] = []
    caveats: list[str] = []
    concept = b.get("concept")
    kind = b.get("kind", "measure")
    out: dict[str, Any] = {"profile": profile, "concept": concept, "kind": kind, "vocabulary": None,
                           "columns": [], "pit_column": None, "dimensions": {}, "viewpoint": b.get("viewpoint"),
                           "unit": b.get("unit"), "aggregation": b.get("aggregation"), "owner": b.get("owner"),
                           "evidence": {"exemplars": [], "owner_confirmation": None}}
    source = vocab.kind_of(concept) if isinstance(concept, str) else None
    out["vocabulary"] = source
    if source is None:
        problems.append(_problem("E_MAP_CONCEPT_UNKNOWN",
                                 f"{concept!r} is not a {(vocab.pack or {}).get('pack_id', '0081 pack')} metric, a "
                                 "proposed pack amendment, or a 0063 concept ID; propose a pack amendment instead "
                                 "of defining it in the mapping"))
    elif source == "amendment":
        caveats.append(f"{concept} is a proposed pack amendment awaiting review by "
                       f"{vocab.amendments.get('reviewer')}; it is not in the reviewed pack")
    if kind not in ("measure", "ratio"):
        problems.append(_problem("E_MAP_KIND", "kind is measure or ratio"))
    if resolver is None:
        problems.append(_problem("E_MAP_NO_CATALOG", f"profile {profile!r} has no catalog snapshot; run catalog.snapshot"))
    if b.get("viewpoint") not in VIEWPOINTS:
        problems.append(_problem("E_MAP_VIEWPOINT", f"viewpoint must be one of {', '.join(VIEWPOINTS)}"))
    unit = b.get("unit")
    governed = vocab.metric(concept) if isinstance(concept, str) else None
    if not isinstance(unit, str) or not unit:
        problems.append(_problem("E_MAP_UNIT", "unit is required"))
    elif governed and unit != governed["unit"]:
        problems.append(_problem("E_MAP_UNIT", f"unit {unit!r} differs from the pack's {governed['unit']!r}; bind the "
                                               "pack unit and declare source_unit and conversion"))
    if b.get("source_unit") and b.get("source_unit") != unit and not b.get("conversion"):
        problems.append(_problem("E_MAP_UNIT", f"source_unit {b['source_unit']!r} needs a declared conversion to {unit!r}"))
    if not isinstance(b.get("owner"), str) or not b.get("owner"):
        problems.append(_problem("E_MAP_OWNER", "every binding names its owner (0008: defined once, owned)"))
    ref = vocab.concept_ref(concept) if isinstance(concept, str) else None
    if ref in QUOTES:
        if b.get("quote") != QUOTES[ref]:
            problems.append(_problem("E_MAP_QUOTE", f"{concept} must declare quote: {QUOTES[ref]} (0063: fee and "
                                                    "rebate are not interchangeable)"))
        if not b.get("day_count"):
            problems.append(_problem("E_MAP_DAY_COUNT", f"{concept} must declare its day_count (0066 default ACT/360)"))

    table_cols: set[str] = set()
    if kind == "measure" and resolver is not None:
        cols, tables = _check_expression(b.get("expression"), resolver, problems)
        out["columns"] = cols
        table_cols = tables
        agg = b.get("aggregation")
        if agg not in AGGREGATIONS:
            problems.append(_problem("E_MAP_AGGREGATION", f"aggregation must be one of {', '.join(AGGREGATIONS)}"))
        elif governed and governed["additivity"] == "non_additive" and agg in ("sum", "count"):
            problems.append(_problem("E_MAP_ADDITIVITY", f"{concept} is non_additive in the pack; it cannot be summed"))
        pit = b.get("pit_column")
        if not isinstance(pit, str):
            problems.append(_problem("E_MAP_PIT", "pit_column is required (0113 REQ-010 point-in-time predicates)"))
        else:
            r = resolver.column(pit)
            if not r.ok:
                problems.append(_problem("E_MAP_PIT", r.reason or "pit_column does not resolve"))
            else:
                out["pit_column"] = f"{r.table}.{r.column}".lower()
                if table_cols and r.table.lower() not in table_cols:
                    problems.append(_problem("E_MAP_PIT", "pit_column must be on the measure's table (same rows)"))
        dims = b.get("dimensions") or {}
        if not isinstance(dims, dict):
            problems.append(_problem("E_MAP_DIMENSION", "a measure's dimensions map dimension -> column"))
            dims = {}
        for dim, col in sorted(dims.items()):
            dk = vocab.dimension_kind(dim)
            if dk is None:
                problems.append(_problem("E_MAP_DIMENSION", f"dimension {dim!r} is not a pack dimension or a proposed "
                                                            "amendment"))
            elif dk == "amendment":
                caveats.append(f"dimension {dim} is a proposed pack amendment")
            r = resolver.column(col) if isinstance(col, str) else catalog_mod.Resolved(False, reason="not a column")
            if not r.ok:
                problems.append(_problem("E_MAP_DIMENSION", f"dimension {dim}: {r.reason}"))
                continue
            if table_cols and r.table.lower() not in table_cols:
                problems.append(_problem("E_MAP_DIMENSION", f"dimension {dim} must be on the measure's table"))
            out["dimensions"][dim] = f"{r.table}.{r.column}".lower()
    elif kind == "ratio":
        for key in ("expression", "aggregation"):
            if b.get(key):
                problems.append(_problem("E_MAP_RATIO", f"a ratio binding has no {key}; it divides two bound measures"))
        dims = b.get("dimensions") or []
        if not isinstance(dims, list):
            problems.append(_problem("E_MAP_RATIO", "a ratio's dimensions are a list of dimension names"))
            dims = []
        out["dimensions"] = {d: None for d in dims}
        out["numerator"], out["denominator"] = b.get("numerator"), b.get("denominator")

    # Evidence: a reviewed, undrifted exemplar reading the column, or a configured promoter's confirmation.
    ev = b.get("evidence") or {}
    ex_refs = ev.get("exemplars") or [] if isinstance(ev, dict) else []
    confirm = ev.get("owner_confirmation") if isinstance(ev, dict) else None
    good_exemplars = []
    for ref_id in ex_refs:
        e = _find_exemplar(ref_id, exemplars)
        if e is None:
            problems.append(_problem("E_MAP_EVIDENCE", f"evidence exemplar {ref_id!r} is not in the index"))
            continue
        if e.get("review_status") != "reviewed" or e.get("eligibility") != "primary":
            problems.append(_problem("E_MAP_EVIDENCE", f"evidence exemplar {ref_id!r} is {e.get('review_status')}, "
                                                       "not reviewed"))
            continue
        if e["exemplar_id"] in excluded:
            problems.append(_problem("E_MAP_DRIFT", f"evidence exemplar {ref_id!r} is excluded ({excluded[e['exemplar_id']]})"))
            continue
        e_profile = e.get("profile") or repo_profiles.get(e.get("repo_id"))
        if e_profile != profile:
            problems.append(_problem("E_MAP_EVIDENCE", f"evidence exemplar {ref_id!r} is for profile {e_profile!r}"))
            continue
        if kind == "measure" and resolver is not None and out["columns"]:
            refs = {_canon(resolver, c) for c in catalog_mod.exemplar_references(e)[1]}
            if not refs & set(out["columns"]):
                problems.append(_problem("E_MAP_EVIDENCE", f"evidence exemplar {ref_id!r} does not read "
                                                           f"{', '.join(out['columns'])}"))
                continue
        for other in e.get("concepts") or []:
            if vocab.non_interchangeable(ref, vocab.concept_ref(other)):
                problems.append(_problem("E_MAP_NON_INTERCHANGEABLE",
                                         f"evidence exemplar {ref_id!r} computes {other}, which 0063 says is not "
                                         f"interchangeable with {concept}"))
        good_exemplars.append({"ref": ref_id, "exemplar_id": e["exemplar_id"], "query_id": e.get("query_id")})
    out["evidence"]["exemplars"] = good_exemplars
    if confirm is not None:
        if confirm in promoters:
            out["evidence"]["owner_confirmation"] = confirm
            caveats.append(f"bound on the confirmation of {confirm}, not on a reviewed exemplar")
        else:
            problems.append(_problem("E_MAP_EVIDENCE", f"owner_confirmation {confirm!r} is not a configured promoter"))
    if kind == "measure" and not good_exemplars and out["evidence"]["owner_confirmation"] is None \
            and not any(p["code"] in ("E_MAP_EVIDENCE", "E_MAP_DRIFT") for p in problems):
        problems.append(_problem("E_MAP_EVIDENCE", "no evidence: cite a reviewed exemplar that reads the column or a "
                                                   "promoter's owner_confirmation"))
    out["problems"] = problems
    out["caveats"] = caveats
    out["status"] = "invalid" if problems else "bound"
    return out


def _check_ratios(results: list[dict[str, Any]]) -> None:
    by_concept = {(r["profile"], r["concept"]): r for r in results}
    for r in results:
        if r["kind"] != "ratio":
            continue
        problems = r["problems"]
        parts = []
        for side in ("numerator", "denominator"):
            other = by_concept.get((r["profile"], r.get(side)))
            if other is None:
                problems.append(_problem("E_MAP_RATIO", f"{side} {r.get(side)!r} is not bound in profile {r['profile']}"))
                continue
            if other["kind"] != "measure" or other.get("aggregation") != "sum":
                problems.append(_problem("E_MAP_RATIO", f"{side} {other['concept']} must be a summed measure"))
            if other["status"] != "bound":
                problems.append(_problem("E_MAP_RATIO", f"{side} {other['concept']} is not validly bound"))
            parts.append(other)
        if len(parts) == 2:
            if parts[0]["viewpoint"] != parts[1]["viewpoint"] or parts[0]["viewpoint"] != r["viewpoint"]:
                problems.append(_problem("E_MAP_VIEWPOINT_MIX", "numerator, denominator, and ratio must share one "
                                                                "viewpoint (0113 REQ-013)"))
            for dim in r["dimensions"]:
                missing = [p["concept"] for p in parts if dim not in p["dimensions"]]
                if missing:
                    problems.append(_problem("E_MAP_RATIO_DIMENSION",
                                             f"{r['concept']} cannot be sliced by {dim}: {', '.join(missing)} has no "
                                             f"{dim} dimension, so the slices would not divide the same rows"))
            r["evidence"]["exemplars"] = [x for p in parts for x in p["evidence"]["exemplars"]]
            r["columns"] = [c for p in parts for c in p["columns"]]
        r["status"] = "invalid" if problems else "bound"


def _validate_sources(config: Any, results: list[dict[str, Any]], vocab: Vocabulary,
                      exemplars: Sequence[Mapping[str, Any]], excluded: Mapping[str, str],
                      repo_profiles: Mapping[str, Any]) -> list[dict[str, Any]]:
    out = []
    bound = {(r["profile"], r["concept"]): r for r in results if r["status"] == "bound"}
    for src in config.data.get("governed_tier", {}).get("metric_sources", []):
        reasons: list[dict[str, str]] = []
        metric = src.get("metric")
        if metric not in vocab.pack_metrics:
            reasons.append(_problem("E_SOURCE_METRIC", f"{metric!r} is not a metric of the selected pack"))
        e = _find_exemplar(src.get("exemplar_id", ""), exemplars)
        profile = (e.get("profile") or repo_profiles.get(e.get("repo_id"))) if e else None
        if e is None:
            reasons.append(_problem("E_SOURCE_EXEMPLAR", f"metric source {src.get('exemplar_id')!r} is not in the index"))
        else:
            if e.get("review_status") != "reviewed" or e.get("eligibility") != "primary":
                reasons.append(_problem("E_SOURCE_UNREVIEWED", f"{src['exemplar_id']} is {e.get('review_status')}"))
            if e["exemplar_id"] in excluded:
                reasons.append(_problem("E_SOURCE_DRIFTED", f"{src['exemplar_id']} is excluded ({excluded[e['exemplar_id']]})"))
            outputs = {s["name"] for s in e.get("structure", {}).get("select", [])}
            pits = {p.rsplit(".", 1)[-1] for p in e.get("pit_columns") or []}
            if src.get("period_column") not in outputs | pits:
                reasons.append(_problem("E_SOURCE_COLUMN", f"period_column {src.get('period_column')!r} is neither an "
                                                           "output nor a point-in-time column of the query"))
            for key in ("dimension_columns", "measure_columns"):
                for name, col in sorted((src.get(key) or {}).items()):
                    if col not in outputs:
                        reasons.append(_problem("E_SOURCE_COLUMN", f"{key}.{name} -> {col!r} is not an output of "
                                                                   f"{src['exemplar_id']}"))
        for dim in sorted(src.get("dimension_columns") or {}):
            if vocab.dimension_kind(dim) is None:
                reasons.append(_problem("E_SOURCE_DIMENSION", f"{dim!r} is not a pack dimension or proposed amendment"))
        binding = bound.get((profile, metric))
        if binding is None:
            reasons.append(_problem("E_SOURCE_BINDING", f"{metric!r} has no valid binding in profile {profile!r}"))
        else:
            base = {binding["numerator"], binding["denominator"]} if binding["kind"] == "ratio" else {metric}
            if set(src.get("measure_columns") or {}) != base:
                reasons.append(_problem("E_SOURCE_MEASURES", f"measure_columns must map exactly the base measures "
                                                             f"{sorted(base)}"))
        out.append({"metric": metric, "exemplar_id": src.get("exemplar_id"), "profile": profile,
                    "status": "unavailable" if reasons else "available", "reasons": reasons})
    return out


def validate_mapping(config: Any, index_dir: Path, vocab: Vocabulary, *, profile: str | None = None) -> dict[str, Any]:
    """Validate every binding and metric source; account for every governed pack metric."""
    exemplars = _exemplars(index_dir)
    excluded = catalog_mod.excluded_exemplars(index_dir)
    repo_profiles = {r["id"]: r.get("database_profile") for r in config.data["query_repositories"]}
    promoters = list(config.data.get("feedback", {}).get("promoters") or [])
    results: list[dict[str, Any]] = []
    profiles = sorted(config.data.get("semantic_mapping") or {})
    for prof in profiles:
        if profile and prof != profile:
            continue
        snap = catalog_mod.load_snapshot(index_dir, prof)
        resolver = catalog_mod.Resolver(snap) if snap else None
        seen: set[str] = set()
        for b in config.data["semantic_mapping"][prof] or []:
            r = _validate_binding(b, prof, resolver, vocab, exemplars, excluded, promoters, repo_profiles)
            if r["concept"] in seen:
                r["problems"].append(_problem("E_MAP_DUPLICATE", f"{r['concept']} is bound twice in {prof} (0008: "
                                                                 "defined once)"))
                r["status"] = "invalid"
            seen.add(r["concept"])
            r["snapshot_id"] = snap["snapshot_id"] if snap else None
            results.append(r)
    _check_ratios(results)
    sources = _validate_sources(config, results, vocab, exemplars, excluded, repo_profiles)
    governed = []
    for name, m in sorted(vocab.pack_metrics.items()):
        mine = [r for r in results if r["concept"] == name]
        ok = [r for r in mine if r["status"] == "bound"]
        if ok:
            status, missing = "bound", []
        elif mine:
            status, missing = "invalid", sorted({p["code"] for r in mine for p in r["problems"]})
        else:
            hints = sorted({e.get("query_id") or e["exemplar_id"] for e in exemplars
                            if name in (e.get("concepts") or []) and e.get("review_status") == "reviewed"})
            status = "unbound"
            missing = ([f"a binding citing reviewed exemplar(s) {', '.join(hints)}"] if hints else
                       ["a catalog column for the measure", "a reviewed exemplar or an owner confirmation"])
        governed.append({"metric": name, "unit": m["unit"], "additivity": m["additivity"], "status": status,
                         "profiles": sorted({r["profile"] for r in ok}), "missing": missing,
                         "source": next((s["status"] for s in sources if s["metric"] == name), "none")})
    used_amendments = sorted({r["concept"] for r in results if r["vocabulary"] == "amendment"}
                             | {d for r in results for d in r["dimensions"] if vocab.dimension_kind(d) == "amendment"})
    return {"bindings": results, "governed_metrics": governed, "metric_sources": sources,
            "amendments_used": used_amendments, "pack": vocab.pack_summary(),
            "counts": {"bindings": len(results), "bound": sum(r["status"] == "bound" for r in results),
                       "invalid": sum(r["status"] == "invalid" for r in results)}}
