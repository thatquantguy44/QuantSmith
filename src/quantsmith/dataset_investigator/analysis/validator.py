"""The validator: no claim is published until it survives these checks.
Spec ``0099`` (REQ-010, REQ-017).

For every candidate finding, in rank order:

1. it has numerical evidence;
2. every number in the claim is in the evidence (to the precision written,
   allowing a percent to stand for a share), and every backticked name or label
   is a column, group, or other label from the evidence — the same approach as
   ``0080``'s grounding check, reimplemented so this package stays standalone;
3. it uses no causal wording (findings are associations);
4. the function fits the columns' roles;
5. re-executing the recorded call gives the same result hash and re-deriving
   the finding gives the same evidence;
6. the sample is large enough;
7. it is significant after Benjamini–Hochberg adjustment over every test in the
   run, and its effect is not negligible;
8. it is not a duplicate of a higher-ranked finding (merged into it);
9. its confidence is calibrated to the evidence.

Statuses, worst wins: ``REJECTED`` > ``INCONCLUSIVE`` > ``WEAK_EVIDENCE`` >
``VALIDATED``. Rejected and merged findings never appear as findings.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, Iterable, List, Sequence, Set

import pandas as pd

from .findings import derive, ranked, score
from .hypotheses import tool_context
from .models import Finding, InvestigationState
from .registry import ToolError, execute, validate_params

CAUSAL_PHRASES = ("because", "caused by", "causes", "causing", "due to", "leads to", "led to", "results in",
                  "resulted in", "results from", "driven by", "drives", "drove", "is responsible for", "explains why")
_CAUSAL = re.compile(r"\b(" + "|".join(re.escape(p) for p in CAUSAL_PHRASES) + r")\b", re.IGNORECASE)
_NUMBER = re.compile(r"(?<![\w.])[-+−]?\d[\d,]*(?:\.\d+)?%?")
_BACKTICK = re.compile(r"`([^`]*)`")
SEVERITY = {"VALIDATED": 0, "WEAK_EVIDENCE": 1, "INCONCLUSIVE": 2, "REJECTED": 3}
CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}
MIN_POSITIVES = 5
MIN_MAGNITUDE = 0.1
REL_TOL, ABS_TOL = 1e-9, 1e-12


def numbers_in(values: Iterable[Any]) -> List[float]:
    out: List[float] = []

    def walk(v: Any) -> None:
        if isinstance(v, bool) or v is None:
            return
        if isinstance(v, (int, float)):
            if math.isfinite(float(v)):
                out.append(float(v))
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x)
    for v in values:
        walk(v)
    return out


def labels_in(values: Iterable[Any]) -> Set[str]:
    out: Set[str] = set()

    def walk(v: Any) -> None:
        if isinstance(v, str):
            out.add(v)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x)
    for v in values:
        walk(v)
    return out


def ground(text: str, values: Sequence[Any], labels: Sequence[str] = ()) -> List[str]:
    """The numbers and backticked labels in ``text`` not backed by ``values`` / ``labels``."""
    allowed_labels = set(labels) | labels_in(values)
    unbacked = [f"`{span}`" for span in _BACKTICK.findall(text) if span not in allowed_labels]
    stripped = _BACKTICK.sub(" ", text)
    nums = numbers_in(values)
    for tok in _NUMBER.findall(stripped):
        t = tok.replace("−", "-").replace(",", "").lstrip("+")
        is_pct = t.endswith("%")
        t = t.rstrip("%")
        try:
            v = abs(float(t))
        except ValueError:
            continue
        decimals = len(t.split(".")[1]) if "." in t else 0
        tol = 0.5 * 10 ** (-decimals) + 1e-9 * v
        candidates = [abs(x) for x in nums] + ([abs(x) * 100 for x in nums] if is_pct else [])
        if not any(abs(v - c) <= tol for c in candidates):
            unbacked.append(tok)
    return unbacked


def causal_phrases(text: str) -> List[str]:
    return sorted({m.group(1).lower() for m in _CAUSAL.finditer(text)})


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool) or a is None or b is None:
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(float(a), float(b), rel_tol=REL_TOL, abs_tol=ABS_TOL)
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return a == b


def evidence_matches(expected: Dict[str, Any], actual: Dict[str, Any]) -> bool:
    return _same(expected, actual)


def dedupe_key(f: Finding) -> str:
    cols = sorted(str(v) for v in labels_in([f.subject]))
    return f"{f.kind}|{'|'.join(cols)}"


def finding_labels(f: Finding, state: InvestigationState) -> List[str]:
    return sorted(labels_in([f.subject])) + [c.name for c in state.columns]


def _calibrated(status: str, f: Finding) -> str:
    if status != "VALIDATED":
        return "low"
    strong = (f.p_adjusted is not None and f.p_adjusted < 0.001) or (f.test is None and f.n >= 1000)
    return "high" if strong and f.n >= 200 else "medium"


def validate(state: InvestigationState, df: pd.DataFrame) -> None:
    """Validate every candidate finding in place, then assign stable ids (REQ-010)."""
    cfg = state.config
    ctx = tool_context(state)
    score(state)
    fresh: Dict[str, tuple] = {}
    seen: Dict[str, str] = {}
    for f in ranked(state.findings):
        verdicts: List[tuple] = []

        def worse(s: str, why: str, verdicts: List[tuple] = verdicts) -> None:
            verdicts.append((s, why))

        f.merged_into = None
        if not f.evidence or not numbers_in([f.evidence]):
            worse("REJECTED", "no numerical evidence")
        unbacked = ground(f.claim, [f.evidence], finding_labels(f, state))
        if unbacked:
            worse("REJECTED", f"claim states values not in its evidence: {', '.join(unbacked)}")
        causal = causal_phrases(f.claim)
        if causal:
            worse("REJECTED", f"causal wording: {', '.join(causal)}")
        try:
            validate_params(f.tool, f.params, ctx)
        except ToolError as exc:
            worse("REJECTED", f"function does not fit the columns: {exc}")
        else:
            try:
                original = state.execution(f.execution_id)
            except KeyError:
                worse("REJECTED", "no recorded execution")
            else:
                if f.execution_id not in fresh:
                    fresh[f.execution_id] = execute(
                        original.tool, df, original.params, ctx, input_fingerprint=state.dataset.content_sha256,
                        origin="validation", sample_threshold=cfg.sample_threshold, expensive_sample=cfg.expensive_sample)
                record, result = fresh[f.execution_id]
                if record.result_sha256 != original.result_sha256:
                    worse("REJECTED", "re-executing the recorded call gave a different result")
                again = [g for g in derive(original, result, state) if g.key == f.key]
                if not again or not evidence_matches(f.evidence, again[0].evidence):
                    worse("REJECTED", "the evidence does not reproduce from the recorded call")
        if f.n < cfg.min_n:
            worse("WEAK_EVIDENCE", f"sample of {f.n} is below the minimum of {cfg.min_n}")
        low_pos = [k for k, v in f.evidence.items() if k.startswith("positives_") and isinstance(v, (int, float)) and v < MIN_POSITIVES]
        if low_pos:
            worse("WEAK_EVIDENCE", f"fewer than {MIN_POSITIVES} positives in a compared group ({', '.join(sorted(low_pos))})")
        if f.test and (f.p_adjusted is None or f.p_adjusted >= cfg.alpha):
            shown = "none" if f.p_adjusted is None else f"{f.p_adjusted:.3g}"
            worse("INCONCLUSIVE", f"not significant after BH adjustment (p = {shown})")
        if f.magnitude < MIN_MAGNITUDE:
            worse("WEAK_EVIDENCE", "effect size is negligible")
        issues = [why for _, why in verdicts]
        status = max((s for s, _ in verdicts), key=SEVERITY.__getitem__, default="VALIDATED")
        dk = dedupe_key(f)
        if status != "REJECTED" and dk in seen:
            f.merged_into = seen[dk]
            issues.append(f"duplicate of {seen[dk]}")
        elif status != "REJECTED":
            seen[dk] = f.key
        computed = _calibrated(status, f)
        if f.confidence and CONFIDENCE_RANK[f.confidence] > CONFIDENCE_RANK[computed]:
            issues.append(f"confidence lowered from {f.confidence} to {computed}")
        f.confidence = computed
        f.status = status
        f.issues = issues
    _assign_ids(state)


def _assign_ids(state: InvestigationState) -> None:
    def order(fs: List[Finding]) -> List[Finding]:
        return sorted(fs, key=lambda f: (f.merged_into is not None, SEVERITY.get(f.status or "REJECTED", 3),
                                         -(f.score.I if f.score else 0), f.key))
    keymap: Dict[str, str] = {}
    for prefix, group in (("F", [f for f in state.findings if not f.quality]), ("Q", [f for f in state.findings if f.quality])):
        for i, f in enumerate(order(group), 1):
            f.finding_id = f"{prefix}{i:03d}"
            keymap[f.key] = f.finding_id
    for f in state.findings:
        if f.merged_into:
            f.merged_into = keymap.get(f.merged_into, f.merged_into)
    state.findings.sort(key=lambda f: (f.finding_id[0] != "F", f.finding_id))


def apply_review(state: InvestigationState, reviews: List[Dict[str, Any]]) -> List[str]:
    """Apply a model reviewer's verdicts. Only downgrades are accepted (REQ-017)."""
    by_id = {f.finding_id: f for f in state.findings} | {f.key: f for f in state.findings}
    notes = []
    for r in reviews:
        f = by_id.get(str(r.get("finding")))
        if f is None:
            notes.append(f"unknown finding {r.get('finding')!r}")
            continue
        new_status = r.get("status")
        if new_status in SEVERITY and SEVERITY[new_status] > SEVERITY[f.status or "VALIDATED"]:
            f.status = new_status
            f.issues.append(f"reviewer: {str(r.get('note', '')).strip()[:300] or 'downgraded'}")
            f.confidence = "low"
        elif new_status not in (None, f.status):
            notes.append(f"{f.finding_id}: reviewer may only downgrade (asked {new_status}, kept {f.status})")
        new_conf = r.get("confidence")
        if new_conf in CONFIDENCE_RANK and CONFIDENCE_RANK[new_conf] < CONFIDENCE_RANK[f.confidence or "low"]:
            f.confidence = new_conf
            f.issues.append(f"reviewer lowered confidence to {new_conf}")
    return notes


def report_grounding_values(state: InvestigationState) -> List[Any]:
    """What a model-written narrative may cite: published evidence, hypothesis evidence, and dataset size."""
    published = [f for f in state.findings if f.merged_into is None and f.status in ("VALIDATED", "WEAK_EVIDENCE")]
    vals: List[Any] = [f.evidence for f in published]
    vals += [h.evidence for h in state.hypotheses if h.status in ("supported", "rejected", "inconclusive")]
    vals.append({"rows": state.dataset.rows, "columns": state.dataset.columns,
                 "n_findings": sum(1 for f in published if not f.quality),
                 "n_quality": sum(1 for f in published if f.quality),
                 "n_hypotheses": len(state.hypotheses), "n_questions": len(state.questions)})
    return vals


def report_grounding_labels(state: InvestigationState) -> List[str]:
    labs = [c.name for c in state.columns] + [f.finding_id for f in state.findings if f.finding_id]
    labs += [h.hypothesis_id for h in state.hypotheses] + [q.question_id for q in state.questions]
    for f in state.findings:
        labs += sorted(labels_in([f.subject]))
    return labs
