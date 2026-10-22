"""The ``0081`` pack catalog, the ``0063`` taxonomy, and ``0008`` metric definitions.

Spec ``0115`` REQ-005, REQ-007, REQ-012. With the QuantSmith SDK installed,
packs are resolved by ``quantsmith.pipelines.analytics_packs.resolve_packs``
(local overlay first, then the bundle), amendments are checked with its
``validate_pack``, and bindings compile to ``0008`` ``MetricDefinition``\\ s in a
``SemanticLayer``. Without it, packs are read as JSON from
``<packs_root>/knowledge/analytics_packs/`` and compilation is unavailable.

The knowledge root holds ``knowledge/analytics_packs/`` and
``knowledge/short_term_markets/taxonomy.json``: ``governed_tier.packs_root``
when set, else the working directory when it has packs, else the QuantSmith
source tree.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

__all__ = [
    "compile_layer",
    "knowledge_root",
    "resolve",
    "sdk_available",
    "select_pack",
    "taxonomy",
    "validate_amended",
]

PACKS_DIR = Path("knowledge") / "analytics_packs"
TAXONOMY = Path("knowledge") / "short_term_markets" / "taxonomy.json"


def sdk_available() -> bool:
    try:
        import quantsmith.pipelines.analytics_packs  # noqa: F401
    except ImportError:
        return False
    return True


def knowledge_root(packs_root: str | Path | None) -> Path | None:
    if packs_root:
        return Path(packs_root)
    if (Path.cwd() / PACKS_DIR).is_dir():
        return Path.cwd()
    try:
        import quantsmith
    except ImportError:
        return None
    tree = Path(quantsmith.__file__).resolve().parents[2]
    return tree if (tree / PACKS_DIR).is_dir() else None


def _hash(files: Sequence[tuple[str, bytes]]) -> str:
    h = hashlib.sha256()
    for name, data in files:
        h.update(name.encode() + b"\0" + hashlib.sha256(data).hexdigest().encode() + b"\n")
    return f"sha256:{h.hexdigest()}"


def resolve(packs_root: str | Path | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """(packs, source) — ``source`` says how and from where the catalog was resolved."""
    if sdk_available():
        from quantsmith.pipelines.analytics_packs import resolve_packs
        packs, src = resolve_packs(Path(packs_root) if packs_root else None)
        return packs, {"mode": "quantsmith", "kind": src.kind, "location": src.location, "version": src.version,
                       "content_hash": src.content_hash, "pack_count": src.pack_count}
    root = knowledge_root(packs_root)
    directory = root / PACKS_DIR if root else None
    if directory is None or not directory.is_dir():
        raise LookupError("no analytics packs: install quantsmith or set governed_tier.packs_root")
    files = sorted((f.name, f.read_bytes()) for f in directory.glob("*.json"))
    return ([json.loads(b.decode("utf-8")) for _, b in files],
            {"mode": "files", "kind": "local", "location": str(directory), "version": None,
             "content_hash": _hash(files), "pack_count": len(files)})


def select_pack(packs: Sequence[Mapping[str, Any]], domain_tags: Sequence[str],
                pack_id: str = "securities_financing_prime") -> dict[str, Any] | None:
    """The pack the mapping is seeded from: ``pack_id`` if a domain tag selects it, else the first selected."""
    chosen = [p for p in packs if set(domain_tags) & set(p.get("source_domains", []))]
    for p in chosen:
        if p.get("pack_id") == pack_id:
            return dict(p)
    return dict(chosen[0]) if chosen else None


def taxonomy(packs_root: str | Path | None) -> dict[str, Any] | None:
    root = knowledge_root(packs_root)
    path = root / TAXONOMY if root else None
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def validate_amended(pack: Mapping[str, Any], amendments: Mapping[str, Any],
                     packs_root: str | Path | None) -> dict[str, Any]:
    """Validate the pack *as if* the proposed amendments were applied (the pack file is never edited)."""
    merged = copy.deepcopy(dict(pack))
    for m in amendments.get("metrics", []):
        merged["metrics"].append({k: m[k] for k in ("name", "description", "unit", "additivity", "synonyms")}
                                 | ({"additivity_rationale": m["additivity_rationale"]}
                                    if m.get("additivity_rationale") else {}))
    for d in amendments.get("dimensions", []):
        merged["dimensions"].append({k: d[k] for k in ("name", "description", "synonyms")})
    if not sdk_available():
        return {"checked_with": None, "errors": [], "note": "quantsmith not installed; 0081 validation skipped"}
    from quantsmith.pipelines.analytics_packs import validate_pack
    root = knowledge_root(packs_root) or Path.cwd()
    findings = validate_pack(merged, root)
    return {"checked_with": "quantsmith.pipelines.analytics_packs.validate_pack",
            "errors": [f.message for f in findings if f.severity == "error"]}


def compile_layer(bindings: Sequence[Mapping[str, Any]]) -> tuple[Any, list[dict[str, Any]]]:
    """Register valid measure and ratio bindings as ``0008`` metrics.

    Returns ``(SemanticLayer, compiled)``; each compiled entry names the
    metric, its kind, and its declared dimensions. Non-additive measures
    (rates) are not ``0008`` sums: they are skipped with a reason and served
    only through a metric source query (``0116``).
    """
    if not sdk_available():
        raise LookupError("0008 compilation needs the quantsmith SDK (pip install 'sfmeridian[governed]')")
    from quantsmith.pipelines.metrics_semantic_layer import (
        MetricDefinition,
        SemanticLayer,
    )
    layer = SemanticLayer()
    compiled = []
    by_concept = {b["concept"]: b for b in bindings}
    for b in sorted(bindings, key=lambda b: (b.get("kind") == "ratio", b["concept"])):
        kind = b.get("kind", "measure")
        if kind == "measure":
            if b.get("aggregation") not in ("sum", "count"):
                compiled.append({"metric": b["concept"], "kind": kind, "compiled": False,
                                 "reason": f"aggregation {b.get('aggregation')!r} is not a 0008 governed sum"})
                continue
            defn = MetricDefinition(name=b["concept"], owner=b["owner"], grain=b.get("grain") or "business_date",
                                    dimensions=tuple(sorted(b.get("dimensions") or {})), source=b["concept"],
                                    agg=b["aggregation"])
        elif kind == "ratio":
            num, den = by_concept.get(b["numerator"]), by_concept.get(b["denominator"])
            if num is None or den is None:
                compiled.append({"metric": b["concept"], "kind": kind, "compiled": False,
                                 "reason": "numerator or denominator is not bound"})
                continue
            defn = MetricDefinition(name=b["concept"], owner=b["owner"], grain=b.get("grain") or "business_date",
                                    dimensions=tuple(sorted(b.get("dimensions") or [])), numerator=b["numerator"],
                                    denominator=b["denominator"])
        else:
            continue
        layer.register(defn)
        compiled.append({"metric": b["concept"], "kind": kind, "compiled": True, "dimensions": list(defn.dimensions)})
    return layer, compiled
