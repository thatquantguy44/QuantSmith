"""Catalog, mapping, glossary, and access tools (spec ``0115`` REQ-013).

Registered into the shared registry by :func:`register`; apps and the
``semantic_mapping_steward`` loop call the same tools.

* ``catalog.snapshot`` (index) — take and store each configured profile's snapshot;
* ``catalog.describe`` (read) — tables and columns of the latest snapshot, with
  each column's redaction class and whether the caller may see its values;
* ``catalog.diff`` (read) — changes between two snapshots, classified;
* ``catalog.reconcile`` (index) — drift of indexed exemplars; writes ``drift.json``;
* ``mapping.validate`` (read) — every binding, metric source, and governed metric;
* ``metrics.list`` (read) — pack metrics and dimensions, proposed amendments,
  pack review status and caveat;
* ``glossary.lookup`` (read) — a term across the pack, the amendments, and ``0063``;
* ``mapping.amendments`` (read) — shipped proposals, which ones the mapping
  or the query repository needs, and which are already staged;
* ``mapping.propose_amendment`` (propose) — stage one proposal for the named
  pack reviewer (never edits the pack);
* ``access.describe`` (read) — the caller's clearance and withheld columns.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import access as access_mod
from . import catalog as catalog_mod
from .mapping import Vocabulary, validate_mapping
from .tools import (
    ToolContext,
    ToolError,
    ToolRegistry,
    ToolSpec,
    _index_dir,
    _obj,
    _read_jsonl,
)

__all__ = ["register"]


def _profiles(ctx: ToolContext, requested: str | None) -> list[str]:
    configured = sorted(ctx.config.data.get("catalog") or {})
    if requested:
        if requested not in {d["id"] for d in ctx.config.data["databases"]}:
            raise ToolError("E_TOOL_INPUT", f"unknown database profile {requested!r}")
        return [requested]
    return configured


def _vocab(ctx: ToolContext) -> Vocabulary:
    cached = ctx.session.get("vocabulary")
    if cached is None:
        cached = ctx.session["vocabulary"] = Vocabulary.load(ctx.config)
    return cached


def _snapshot(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    out, errors = [], []
    for profile in _profiles(ctx, args.get("profile")):
        try:
            snap = catalog_mod.snapshot_profile(ctx.config, profile, ctx.clients.get("connections"))
        except catalog_mod.CatalogError as exc:
            errors.append({"profile": profile, "code": exc.code, "message": access_mod.scrub(exc.message)})
            continue
        out.append(catalog_mod.store(_index_dir(ctx), snap, ctx.today) | {"notes": snap.get("notes", [])})
    if not out and errors:
        raise ToolError(errors[0]["code"], "; ".join(f"{e['profile']}: {e['message']}" for e in errors))
    return {"snapshots": out, "errors": errors}


def _latest(ctx: ToolContext, profile: str) -> dict[str, Any]:
    snap = catalog_mod.load_snapshot(_index_dir(ctx), profile)
    if snap is None:
        raise ToolError("E_NOT_FOUND", f"profile {profile!r} has no catalog snapshot; run catalog.snapshot")
    return snap


def _describe(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    profile = args["profile"]
    _profiles(ctx, profile)
    snap = _latest(ctx, profile)
    who = access_mod.caller(ctx.config, ctx.actor)
    reqs = access_mod.column_requirements(ctx.config)
    tables = []
    for t in snap["tables"]:
        label = catalog_mod.Resolver.label(t)
        if args.get("table") and catalog_mod.Resolver(snap).table(args["table"])[0] is not t:
            continue
        cols = []
        for c in t["columns"]:
            req = reqs.get(f"{t['name'].lower()}.{c['name'].lower()}") or reqs.get(f"{label.lower()}.{c['name'].lower()}")
            cols.append({**c, "redaction_class": req["class"] if req else None,
                         "values_visible": who.sees(req["level"]) if req else True})
        tables.append({**t, "columns": cols, "label": label})
    if args.get("table") and not tables:
        raise ToolError("E_NOT_FOUND", f"table {args['table']!r} is not in the {profile} catalog")
    return {"profile": profile, "snapshot_id": snap["snapshot_id"], "default_schema": snap.get("default_schema"),
            "tables": tables}


def _diff(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    profile = args["profile"]
    _profiles(ctx, profile)
    hist = catalog_mod.history(_index_dir(ctx), profile)
    if not hist:
        raise ToolError("E_NOT_FOUND", f"profile {profile!r} has no catalog snapshot")
    to_id = args.get("to") or hist[-1]["snapshot_id"]
    ids = [h["snapshot_id"] for h in hist]
    from_id = args.get("from") or (ids[ids.index(to_id) - 1] if to_id in ids and ids.index(to_id) > 0 else None)
    old = catalog_mod.load_snapshot(_index_dir(ctx), profile, from_id) if from_id else None
    try:
        new = catalog_mod.load_snapshot(_index_dir(ctx), profile, to_id)
    except catalog_mod.CatalogError as exc:
        raise ToolError(exc.code, exc.message) from None
    return {"profile": profile, **catalog_mod.diff(old, new)}


def _reconcile(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    index_dir = _index_dir(ctx)
    snaps = {}
    for profile in _profiles(ctx, args.get("profile")):
        snap = catalog_mod.load_snapshot(index_dir, profile)
        if snap is not None:
            snaps[profile] = snap
    if not snaps:
        raise ToolError("E_NOT_FOUND", "no catalog snapshots to reconcile against; run catalog.snapshot")
    policies = {p: (e or {}).get("drift_policy", "exclude") for p, e in (ctx.config.data.get("catalog") or {}).items()}
    repo_profiles = {r["id"]: r.get("database_profile") for r in ctx.config.data["query_repositories"]}
    report = catalog_mod.reconcile(snaps, _read_jsonl(index_dir / "exemplars.jsonl"), policies, repo_profiles)
    changed = catalog_mod.write_drift(index_dir, report)
    return {**report, "written": changed}


def _mapping_validate(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return validate_mapping(ctx.config, _index_dir(ctx), _vocab(ctx), profile=args.get("profile"))


def _metrics_list(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    v = _vocab(ctx)
    return {"pack": v.pack_summary(),
            "metrics": [{"name": n, **{k: m.get(k) for k in ("description", "unit", "additivity", "synonyms")},
                         "status": "pack"} for n, m in sorted(v.pack_metrics.items())],
            "dimensions": [{"name": d["name"], "description": d.get("description"), "status": "pack"}
                           for d in (v.pack or {}).get("dimensions", [])],
            "proposed_metrics": [{"name": n, "amendment_id": m["amendment_id"], "unit": m["unit"],
                                  "additivity": m["additivity"], "status": "proposed"}
                                 for n, m in sorted(v.amendment_metrics.items())],
            "proposed_dimensions": [{"name": n, "amendment_id": d["amendment_id"], "status": "proposed"}
                                    for n, d in sorted(v.amendment_dimensions.items())]}


def _norm(term: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", term.lower()).strip()


def _glossary(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    v = _vocab(ctx)
    term = _norm(args["term"])
    matches = []

    def hit(names: list[str]) -> bool:
        return any(_norm(n) == term for n in names if n)

    for m in (v.pack or {}).get("metrics", []):
        if hit([m["name"], *m.get("synonyms", [])]):
            matches.append({"source": "pack_metric", "name": m["name"], "unit": m["unit"],
                            "additivity": m["additivity"], "description": m["description"]})
    for d in (v.pack or {}).get("dimensions", []):
        if hit([d["name"], *d.get("synonyms", [])]):
            matches.append({"source": "pack_dimension", "name": d["name"], "description": d.get("description")})
    for m in v.amendment_metrics.values():
        if hit([m["name"], *m.get("synonyms", [])]):
            matches.append({"source": "proposed_amendment", "name": m["name"], "unit": m["unit"],
                            "additivity": m["additivity"], "description": m["description"]})
    for d in v.amendment_dimensions.values():
        if hit([d["name"], *d.get("synonyms", [])]):
            matches.append({"source": "proposed_amendment", "name": d["name"], "description": d.get("description")})
    for c in v.concepts.values():
        if hit([c["id"], c["id"].split(".", 1)[-1], c["name"], *c.get("aliases", [])]):
            matches.append({"source": "0063", "name": c["id"], "label": c["name"], "kind": c.get("kind"),
                            "definition": c.get("definition"), "review_status": c.get("review_status")})
    rules = [r for r in (v.taxonomy or {}).get("ambiguity_rules", []) if _norm(r.get("alias", "")) == term]
    governed_names = {m["name"] for m in matches if m["source"] != "0063"}
    return {"term": args["term"], "matches": matches, "ambiguity_rules": rules,
            "ambiguous": bool(rules) or len(governed_names) > 1}


def _amend_dir(ctx: ToolContext) -> Path:
    return ctx.config.resolve_path(ctx.config.data["feedback"]["inbox"]) / "pack_amendments"


def _amendments(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    v = _vocab(ctx)
    from .governed import packs as packs_mod
    used_by: dict[str, set[str]] = {}
    for prof, bindings in (ctx.config.data.get("semantic_mapping") or {}).items():
        for b in bindings or []:
            names = [b.get("concept")] + list((b.get("dimensions") or {}) if isinstance(b.get("dimensions"), dict)
                                               else b.get("dimensions") or [])
            for n in names:
                used_by.setdefault(n, set()).add(f"binding:{prof}")
    for e in _read_jsonl(_index_dir(ctx) / "exemplars.jsonl"):
        for n in e.get("concepts") or []:
            used_by.setdefault(n, set()).add(f"exemplar:{e.get('query_id') or e['exemplar_id']}")
    staged = {p.stem for p in _amend_dir(ctx).glob("*.json")} if _amend_dir(ctx).is_dir() else set()
    entries = []
    for kind, items in (("metric", v.amendment_metrics), ("dimension", v.amendment_dimensions)):
        for name, a in sorted(items.items()):
            entries.append({"amendment_id": a["amendment_id"], "kind": kind, "name": name, "status": "proposed",
                            "needed_by": sorted(used_by.get(name, set())), "staged": a["amendment_id"] in staged,
                            **({"unit": a["unit"], "additivity": a["additivity"]} if kind == "metric" else {})})
    check = packs_mod.validate_amended(v.pack or {}, v.amendments, ctx.config.data["governed_tier"].get("packs_root")) \
        if v.pack else {"errors": ["no pack selected"]}
    return {"pack_id": v.amendments.get("pack_id"), "reviewer": v.amendments.get("reviewer"),
            "review_request": v.amendments.get("review_request"), "amendments": entries,
            "validation": check}


def _propose_amendment(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    v = _vocab(ctx)
    found = next((dict(a, kind=k) for k, items in (("metric", v.amendments.get("metrics", [])),
                                                    ("dimension", v.amendments.get("dimensions", [])))
                  for a in items if a["amendment_id"] == args["amendment_id"]), None)
    if found is None:
        raise ToolError("E_NOT_FOUND", f"no shipped amendment {args['amendment_id']!r}; new concepts are added to "
                                       "data/pack_amendments.json by a person, then proposed")
    record = {"amendment": found, "pack_id": v.amendments["pack_id"], "status": "proposed",
              "reviewer": v.amendments.get("reviewer"), "proposed_by": ctx.actor, "proposed_on": ctx.today,
              "needed_by": sorted(args.get("needed_by", [])),
              "note": "Proposal only: the pack file is unchanged. The named reviewer accepts it through the 0081 "
                      "review flow (pack edit plus --mark-reviewed)."}
    target = _amend_dir(ctx) / f"{found['amendment_id']}.json"
    text = json.dumps(record, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    created = not target.exists()
    if created:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return {"proposal": json.loads(target.read_text(encoding="utf-8")), "created": created}


def _access_describe(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    who = access_mod.caller(ctx.config, ctx.actor)
    reqs = access_mod.column_requirements(ctx.config)
    return {"caller": who.as_dict(),
            "columns": [{"column": c, **r, "values_visible": who.sees(r["level"])} for c, r in sorted(reqs.items())],
            "credentials": "connections hold only secret_ref pointers; values are resolved by the host application"}


def register(reg: ToolRegistry) -> None:
    profile = {"type": "string", "maxLength": 200}
    for spec in [
        ToolSpec("catalog.snapshot", "Take and store catalog snapshots (introspection or declared file) per profile.",
                 _obj({"profile": profile}), "index", _snapshot),
        ToolSpec("catalog.describe", "Tables and columns of a profile's latest snapshot, with redaction classes.",
                 _obj({"profile": profile, "table": {"type": "string", "maxLength": 300}}, ["profile"]), "read",
                 _describe),
        ToolSpec("catalog.diff", "Changes between two catalog snapshots, classified compatible or breaking.",
                 _obj({"profile": profile, "from": {"type": "string"}, "to": {"type": "string"}}, ["profile"]),
                 "read", _diff),
        ToolSpec("catalog.reconcile", "Find exemplars that reference missing tables or columns; exclude them.",
                 _obj({"profile": profile}), "index", _reconcile),
        ToolSpec("mapping.validate", "Validate concept bindings and metric sources; account for every pack metric.",
                 _obj({"profile": profile}), "read", _mapping_validate),
        ToolSpec("metrics.list", "Pack metrics and dimensions, proposed amendments, review status and caveat.",
                 _obj({}), "read", _metrics_list),
        ToolSpec("glossary.lookup", "Look a term up in the pack, the proposed amendments, and the 0063 taxonomy.",
                 _obj({"term": {"type": "string", "maxLength": 200}}, ["term"]), "read", _glossary),
        ToolSpec("mapping.amendments", "Shipped pack-amendment proposals, what needs them, and what is staged.",
                 _obj({}), "read", _amendments),
        ToolSpec("mapping.propose_amendment", "Stage one shipped pack-amendment proposal for the named reviewer.",
                 _obj({"amendment_id": {"type": "string", "maxLength": 200},
                       "needed_by": {"type": "array", "items": {"type": "string"}}}, ["amendment_id"]),
                 "propose", _propose_amendment),
        ToolSpec("access.describe", "The caller's clearance and which classed columns' values it may see.",
                 _obj({}), "read", _access_describe),
    ]:
        reg.register(spec)
