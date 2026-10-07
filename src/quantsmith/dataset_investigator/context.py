"""What each language-model role is shown. Spec ``0099`` (REQ-017, NFR-002).

A role sees the profile, the column roles, and recorded *aggregate* evidence —
never rows. Tools never output identifier or free-text values, and refuse to
report the values of PII-flagged columns, so the evidence itself carries none;
this module only selects and shapes it per role.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .analysis.findings import ranked
from .analysis.models import InvestigationState
from .analysis.planner import ANALYSES
from .analysis.registry import catalog

ROLES = ("planner", "investigator", "validator", "writer")
INVESTIGATOR_FINDINGS = 20  # the highest-ranked candidates; keeps each step's output small

ANALYSIS_DESCRIPTIONS = {
    "profile": "shape, roles, missingness, cardinality",
    "data_quality": "missingness, duplicates, impossible values, mixed types, cardinality",
    "target_balance": "class balance of the target",
    "numeric_distributions": "summary statistics, skew, tails of numeric columns",
    "categorical_distributions": "category frequencies and concentration",
    "correlations": "Pearson and Spearman between numeric columns",
    "target_relationships": "target rate by every grouping column; mutual information",
    "missingness_relationships": "target rate where a column is missing vs present",
    "segments": "numeric metrics by categorical groups",
    "temporal_trends": "volume, metric and target-rate trends over time",
    "temporal_drift": "distribution shift (KS, PSI) with a breakpoint",
    "period_patterns": "target rate by hour of day and weekday",
    "entity_concentration": "how concentrated rows and positives are among entities",
    "anomaly_detection": "robust z-scores; Mahalanobis, Isolation Forest, LOF",
}

DECISION_RULES = (
    "A hypothesis names a registered tool, its params, and a decision_rule "
    '{"supported": [{"path": "<result field>", "op": ">=|>|<=|<|==|!=", "value": <number>}], '
    '"rejected": [...]}. It is supported when every supported condition holds, rejected when every '
    "rejected condition holds, otherwise inconclusive; a path the result lacks makes it invalid. "
    "Paths are dotted keys of the tool's result (e.g. mh_rate_ratio, extreme.rate)."
)
NUMBERS_RULE = ("State only numbers that appear in the evidence shown to you (rounding is fine; a percent may "
                "stand for a share). Put column names, group labels and dates in backticks. Describe associations, "
                "never causes: no 'because', 'due to', 'caused by', 'drives', 'leads to'.")


def _round(v: Any) -> Any:
    """Floats to 6 significant digits: what a role reads, without 16-digit noise (grounding allows rounding)."""
    if isinstance(v, float):
        return float(f"{v:.6g}")
    if isinstance(v, dict):
        return {k: _round(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_round(x) for x in v]
    return v


def _columns(state: InvestigationState) -> List[Dict[str, Any]]:
    return [{"name": c.name, "role": c.role, "dtype": c.dtype, "missing_pct": round(c.missing_pct, 6),
             "n_unique": c.n_unique, "pii": c.pii} for c in state.columns]


def _set(d: Dict[str, Any]) -> Dict[str, Any]:
    """Only the fields that carry something: a missing key reads as null, empty, or false."""
    return {k: v for k, v in d.items() if v not in (None, [], {}, False)}


def _finding(f) -> Dict[str, Any]:
    return _set({"id": f.finding_id, "key": f.key, "kind": f.kind, "claim": f.claim, "subject": f.subject,
            "evidence": f.evidence, "status": f.status, "confidence": f.confidence, "issues": f.issues,
            "interestingness": f.score.I if f.score else None, "p_adjusted": f.p_adjusted, "n": f.n,
            "quality": f.quality, "merged_into": f.merged_into})


def _hypothesis(h) -> Dict[str, Any]:
    return _set({"id": h.hypothesis_id, "round": h.round, "statement": h.statement, "tool": h.tool, "params": h.params,
            "status": h.status, "explanation": h.explanation, "evidence": h.evidence, "from_findings": h.from_findings,
            "origin": h.origin})


def build(state: InvestigationState, role: str, *, tools: bool = True) -> Dict[str, Any]:
    """The context for ``role`` — aggregates and evidence only (REQ-017).

    ``tools=False`` leaves the (static) tool catalog out of the investigator's
    context, for a caller that already holds it from an earlier step.
    """
    if role not in ROLES:
        raise ValueError(f"unknown role {role!r}; use one of {ROLES}")
    return _round(_build(state, role, tools))


def _build(state: InvestigationState, role: str, tools: bool) -> Dict[str, Any]:
    base = {"role": role, "run_id": state.run_id, "omitted_fields": "null, empty, or false",
            "dataset": {"rows": state.dataset.rows, "columns": state.dataset.columns, "format": state.dataset.format},
            "columns": _columns(state)}
    if role == "planner":
        return {**base,
                "analyses": [{"name": a, "description": ANALYSIS_DESCRIPTIONS[a]} for a in ANALYSES],
                "deterministic_plan": state.plan.model_dump(mode="json") if state.plan else None,
                "instructions": "Choose and order analyses by name from `analyses`; you cannot add tools or parameters."}
    live = [f for f in state.findings if f.merged_into is None]
    if role == "investigator":
        used = sum(1 for e in state.executions if e.origin in ("hypothesis", "model"))
        candidates = ranked([f for f in live if not f.quality])
        out = {**base, "findings": [_finding(f) for f in candidates[:INVESTIGATOR_FINDINGS]],
               "findings_not_shown": max(0, len(candidates) - INVESTIGATOR_FINDINGS),
               "hypotheses": [_hypothesis(h) for h in state.hypotheses],
               "tools": catalog(), "decision_rules": DECISION_RULES, "numbers": NUMBERS_RULE,
                "budget": {"tool_calls_left": max(0, state.config.max_tool_calls - used),
                           "rounds_used": max((h.round for h in state.hypotheses), default=0),
                           "max_rounds": state.config.max_rounds}}
        if not tools:
            del out["tools"]
        return out
    if role == "validator":
        return {**base, "findings": [_finding(f) for f in live],
                "instructions": ("Check each claim against its evidence. You may only downgrade: return "
                                 "{finding, status, confidence, note} with a worse status or lower confidence.")}
    published = [f for f in live if f.status == "VALIDATED"]
    return {**base, "key_findings": [_finding(f) for f in published if not f.quality][: state.config.top_n],
            "quality": [_finding(f) for f in published if f.quality],
            "not_established": [_finding(f) for f in live if f.status in ("WEAK_EVIDENCE", "INCONCLUSIVE")],
            "hypotheses": [_hypothesis(h) for h in state.hypotheses],
            "questions": [q.model_dump(mode="json") for q in state.questions],
            "numbers": NUMBERS_RULE,
            "instructions": "Write a short executive narrative (at most 250 words) of what is established and what is not."}
