"""Baseline-versus-model comparison for spec 0094.

Takes the deterministic baseline extractions and extractions supplied from outside (a
model run; this package never calls a model), reports agreement per language, and keeps
the baseline value wherever the two disagree. Model items are labelled ``derived: true``
and ``method: "llm"`` and are *never* decision-ready until they carry provenance
(model, prompt manifest, and a ``0070`` envelope reference) and a named bilingual human
reviewer.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Dict, Iterable, List, Mapping, Sequence

REQUIRED_PROVENANCE = ("model", "prompt_manifest", "envelope_ref")


def validate_model_item(item: Mapping[str, Any]) -> List[str]:
    errors = []
    for f in ("type", "span", "start", "end"):
        if f not in item:
            errors.append(f"model item missing {f}")
    prov = item.get("provenance") or {}
    for f in REQUIRED_PROVENANCE:
        val = prov.get(f)
        if not (isinstance(val, str) and val.strip()):
            errors.append(f"model item provenance lacks {f}")
    return errors


def decision_ready(item: Mapping[str, Any]) -> bool:
    """A model-derived item is decision-ready only with provenance and a named reviewer."""
    if not item.get("derived"):
        return item.get("method") == "rule" and not item.get("ambiguous")
    if validate_model_item(item):
        return False
    reviewer = (item.get("provenance") or {}).get("reviewer")
    return isinstance(reviewer, str) and bool(reviewer.strip())


def _same_span(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    return a["type"] == b["type"] and a["start"] == b["start"] and a["end"] == b["end"]


def compare(baseline: Sequence[Mapping[str, Any]], model: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Compare by (type, start, end). The baseline is returned unchanged inside ``merged``."""
    base = copy.deepcopy(list(baseline))
    errors = [e for m in model for e in validate_model_item(m)]
    if errors:
        raise ValueError("; ".join(errors))
    marked = []
    for m in model:
        d = copy.deepcopy(dict(m))
        d["derived"] = True
        d["method"] = "llm"
        d.setdefault("provenance", {}).setdefault("reviewer", None)
        marked.append(d)
    agree: List[Dict[str, Any]] = []
    disagree: List[Dict[str, Any]] = []
    model_only: List[Dict[str, Any]] = []
    matched_base = set()
    for m in marked:
        hit = next((i for i, b in enumerate(base) if _same_span(b, m)), None)
        if hit is None:
            model_only.append(m)
            continue
        matched_base.add(hit)
        b = base[hit]
        same = json.dumps(b.get("value"), sort_keys=True) == json.dumps(m.get("value"), sort_keys=True) \
            and b.get("currency") == m.get("currency")
        (agree if same else disagree).append({"baseline": b, "model": m})
    baseline_only = [b for i, b in enumerate(base) if i not in matched_base]
    merged = copy.deepcopy(base) + copy.deepcopy(model_only)   # baseline values are never replaced
    return {"agree": agree, "disagree": disagree, "model_only": model_only, "baseline_only": baseline_only,
            "merged": merged, "baseline_unchanged": base == list(baseline)}


def agreement_by_language(results: Iterable[Mapping[str, Any]], languages: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    """Per-language agreement counts from parallel ``compare`` results and language tags."""
    out: Dict[str, Dict[str, Any]] = {}
    for res, lang in zip(results, languages):
        c = out.setdefault(lang, {"agree": 0, "disagree": 0, "model_only": 0, "baseline_only": 0})
        for k in c:
            c[k] += len(res[k])
    for c in out.values():
        both = c["agree"] + c["disagree"]
        c["agreement_rate"] = (c["agree"] / both) if both else None
    return out
