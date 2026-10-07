"""Hypotheses, the testing loop, and research questions. Spec ``0099`` (REQ-008, REQ-009).

A hypothesis names a registered tool, its parameters, and a declarative
decision rule — conditions on fields of the tool's result. It is
``supported`` when every *supported* condition holds, ``rejected`` when every
*rejected* condition holds, and ``inconclusive`` otherwise; a rule that refers
to a field the result does not have makes the hypothesis ``invalid``. The
same rule language is what a language-model investigator must use, so its
hypotheses are judged exactly like the templated ones.

The loop is bounded: at most ``max_rounds`` rounds and ``max_tool_calls``
new tool executions. Round 1 tests templates for the top findings; later
rounds test follow-ups chosen by earlier outcomes (e.g. when "positives rise
in the window" is rejected, test the denominator effect).
"""

from __future__ import annotations

import operator
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

from .findings import pct, ranked
from .models import (
    Condition,
    DecisionRule,
    Finding,
    Hypothesis,
    InvestigationState,
    Question,
)
from .registry import (
    ToolContext,
    ToolError,
    execute,
    planned_execution_id,
    spec,
    validate_params,
)
from .utils import sha256_json

OPS: Dict[str, Callable[[Any, Any], bool]] = {
    ">=": operator.ge, ">": operator.gt, "<=": operator.le, "<": operator.lt, "==": operator.eq, "!=": operator.ne,
}
_MISSING = object()


def resolve(result: Dict[str, Any], path: str) -> Any:
    cur: Any = result
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return _MISSING
    return cur


def evaluate(rule: DecisionRule, result: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    """Apply a decision rule to a tool result: (status, explanation, evidence)."""
    evidence: Dict[str, Any] = {}
    paths = [c.path for c in rule.supported + rule.rejected]
    for path in paths:
        v = resolve(result, path)
        if v is _MISSING:
            return "invalid", f"the result has no field `{path}`", evidence
        evidence[path] = v
    def holds(c: Condition) -> Optional[bool]:
        v = evidence[c.path]
        if v is None:
            return None
        try:
            return bool(OPS[c.op](v, c.value))
        except TypeError:
            return None
    def describe(c: Condition) -> str:
        v = evidence[c.path]
        shown = f"{v:.4g}" if isinstance(v, float) else str(v)
        return f"{c.path} = {shown} {c.op} {c.value}"
    sup = [holds(c) for c in rule.supported]
    rej = [holds(c) for c in rule.rejected]
    if sup and all(s is True for s in sup):
        return "supported", "; ".join(describe(c) for c in rule.supported), evidence
    if rej and all(r is True for r in rej):
        return "rejected", "; ".join(describe(c) for c in rule.rejected), evidence
    missing = [c.path for c, h in zip(rule.supported + rule.rejected, sup + rej) if h is None]
    why = f"no value for {', '.join(missing)}" if missing else "neither the supported nor the rejected conditions all hold"
    return "inconclusive", why, evidence


def rule(supported: List[Tuple[str, str, Any]], rejected: List[Tuple[str, str, Any]]) -> DecisionRule:
    return DecisionRule(supported=[Condition(path=p, op=o, value=v) for p, o, v in supported],
                        rejected=[Condition(path=p, op=o, value=v) for p, o, v in rejected])


# --- templates ---------------------------------------------------------------

def _first(state: InvestigationState, roles: Tuple[str, ...], exclude: Tuple[str, ...] = (), max_unique: int = 0) -> Optional[str]:
    for c in state.columns:
        if c.role in roles and not c.pii and c.name not in exclude and (not max_unique or c.n_unique <= max_unique):
            return c.name
    return None


def _entity(state: InvestigationState) -> Optional[str]:
    return next((c.name for c in state.columns if c.role == "entity_identifier"), None)


def _role(state: InvestigationState, col: str) -> Optional[str]:
    return next((c.role for c in state.columns if c.name == col), None)


Template = Dict[str, Any]


def _t_gap(f: Finding, st: InvestigationState) -> List[Template]:
    s, a = f.subject, st.config.alpha
    out = []
    strata = _first(st, ("continuous_numeric",), exclude=(s["by"], s["target"])) or \
        _first(st, ("categorical", "boolean"), exclude=(s["by"], s["target"]), max_unique=50)
    if strata:
        out.append({"template": "gap_stratified",
                    "statement": f"The `{s['by']}` = `{s['exposed']}` vs `{s['reference']}` gap in `{s['target']}` rate persists within bands of `{strata}`.",
                    "tool": "stratified_target_rates",
                    "params": {"target": s["target"], "by": s["by"], "strata": strata,
                               "exposed": s["exposed"], "reference": s["reference"]},
                    "prediction": "The Mantel–Haenszel rate ratio stays at or above 1.5.",
                    "rule": rule([("mh_rate_ratio", ">=", 1.5), ("cmh_p_value", "<", a)], [("mh_rate_ratio", "<", 1.2)])})
    ent = _entity(st)
    if ent and _role(st, s["by"]) in ("categorical", "boolean"):
        out.append({"template": "gap_entity",
                    "statement": f"`{s['target']}` positives in `{s['by']}` = `{s['exposed']}` are concentrated in a few `{ent}` values.",
                    "tool": "analyze_entity_concentration",
                    "params": {"entity": ent, "target": s["target"], "subset_column": s["by"], "subset_value": s["exposed"]},
                    "prediction": "The top 1% of entities hold at least half of the positives.",
                    "rule": rule([("top1pct_positive_share", ">=", 0.5)], [("top1pct_positive_share", "<", 0.2)])})
    return out


def _t_missing(f: Finding, st: InvestigationState) -> List[Template]:
    s, a = f.subject, st.config.alpha
    strata = _first(st, ("continuous_numeric",), exclude=(s["column"], s["target"])) or \
        _first(st, ("categorical", "boolean"), exclude=(s["column"], s["target"]), max_unique=50)
    if not strata:
        return []
    return [{"template": "missing_stratified",
             "statement": f"The higher `{s['target']}` rate where `{s['column']}` is missing persists within bands of `{strata}`.",
             "tool": "stratified_target_rates",
             "params": {"target": s["target"], "by": s["column"], "strata": strata, "missing_indicator": True},
             "prediction": "The Mantel–Haenszel rate ratio stays at or above 1.5.",
             "rule": rule([("mh_rate_ratio", ">=", 1.5), ("cmh_p_value", "<", a)], [("mh_rate_ratio", "<", 1.2)])}]


def _t_window(f: Finding, st: InvestigationState) -> List[Template]:
    s, a = f.subject, st.config.alpha
    w = s["window"]
    base = {"timestamp": s["timestamp"], "target": s["target"], "part": s["part"], "window": w}
    out = [{"template": "window_volume",
            "statement": f"More `{s['target']}` events happen per {s['part']} during {s['part']}s {w[0]} to {w[-1]} than in the rest.",
            "tool": "compare_window_counts", "params": base,
            "prediction": "Positives per bucket are at least 1.2× higher inside the window.",
            "rule": rule([("positives_ratio", ">=", 1.2), ("p_positives", "<", a)], [("positives_ratio", "<", 1.2)])}]
    by = _first(st, ("categorical",), exclude=(s["target"],), max_unique=50)
    if by:
        out.append({"template": "window_composition",
                    "statement": f"The mix of `{by}` during {s['part']}s {w[0]} to {w[-1]} differs from the rest.",
                    "tool": "compare_window_composition",
                    "params": {"timestamp": s["timestamp"], "by": by, "part": s["part"], "window": w},
                    "prediction": "The population stability index between window and rest is at least 0.1.",
                    "rule": rule([("psi", ">=", 0.1), ("p_value", "<", a)], [("psi", "<", 0.05)])})
    return out


def _t_shift(f: Finding, st: InvestigationState) -> List[Template]:
    s, a = f.subject, st.config.alpha
    out = []
    target = next((c.name for c in st.columns if c.role == "binary_target"), None)
    if target and target != s["column"]:
        out.append({"template": "shift_target",
                    "statement": f"The `{target}` rate changed at the same breakpoint as `{s['column']}` (`{s['date']}`).",
                    "tool": "detect_target_shift",
                    "params": {"target": target, "timestamp": s["timestamp"], "split": s["breakpoint"]},
                    "prediction": "The target rate after the breakpoint differs from before by at least 20%.",
                    "rule": rule([("rate_change_abs", ">=", 0.2), ("p_value", "<", a)], [("rate_change_abs", "<", 0.1)])})
    by = _first(st, ("categorical",), exclude=(s["column"],), max_unique=50)
    if by:
        out.append({"template": "shift_mix",
                    "statement": f"The `{s['column']}` shift coincides with a change in the mix of `{by}` at `{s['date']}`.",
                    "tool": "compare_period_composition",
                    "params": {"timestamp": s["timestamp"], "by": by, "split": s["breakpoint"]},
                    "prediction": "The population stability index of the mix before and after is at least 0.1.",
                    "rule": rule([("psi", ">=", 0.1), ("p_value", "<", a)], [("psi", "<", 0.05)])})
    return out


def _t_corr(f: Finding, st: InvestigationState) -> List[Template]:
    s, a = f.subject, st.config.alpha
    control = _first(st, ("continuous_numeric", "discrete_numeric"), exclude=(s["a"], s["b"]))
    if not control:
        return []
    return [{"template": "corr_partial",
             "statement": f"The `{s['a']}`–`{s['b']}` correlation remains after controlling for `{control}`.",
             "tool": "partial_correlation", "params": {"x": s["a"], "y": s["b"], "control": control},
             "prediction": "The absolute partial correlation is at least 0.3.",
             "rule": rule([("abs_partial", ">=", 0.3), ("p_value", "<", a)], [("abs_partial", "<", 0.1)])}]


TEMPLATES: Dict[str, Callable[[Finding, InvestigationState], List[Template]]] = {
    "target_rate_gap": _t_gap, "missingness_target": _t_missing, "period_rate_window": _t_window,
    "distribution_shift": _t_shift, "correlation": _t_corr,
}


def _f_denominator(h: Hypothesis, st: InvestigationState) -> List[Template]:
    p = h.params
    return [{"template": "window_denominator",
             "statement": (f"The higher `{p['target']}` rate during {p['part']}s {p['window'][0]} to {p['window'][-1]} is a "
                           f"denominator effect: total volume is lower there while `{p['target']}` volume is not higher."),
             "tool": "compare_window_counts", "params": p,
             "prediction": "Volume per bucket is at least 20% lower inside the window, and positives per bucket within ±20%.",
             "rule": rule([("volume_ratio", "<=", 0.8), ("positives_ratio", "<", 1.2), ("positives_ratio", ">=", 0.8)],
                          [("volume_ratio", ">", 0.9)])}]


FOLLOW_UPS: Dict[Tuple[str, str], Callable[[Hypothesis, InvestigationState], List[Template]]] = {
    ("window_volume", "rejected"): _f_denominator,
}


# --- the loop ----------------------------------------------------------------

def tool_context(state: InvestigationState) -> ToolContext:
    c = state.config
    return ToolContext(roles=state.roles(), pii=frozenset(state.pii()), min_cell=c.min_cell, min_n=c.min_n,
                       alpha=c.alpha, seed=c.seed, as_of=c.as_of, positive=c.positive,
                       near_constant=c.near_constant, max_numeric_columns=c.max_numeric_columns)


def _next_id(state: InvestigationState) -> str:
    return f"H{len(state.hypotheses) + 1:03d}"


def _new_calls(state: InvestigationState) -> int:
    return sum(1 for e in state.executions if e.origin in ("hypothesis", "model"))


def test_hypothesis(state: InvestigationState, df: pd.DataFrame, h: Hypothesis) -> Hypothesis:
    """Execute a hypothesis's tool (once per identical call) and apply its decision rule."""
    ctx = tool_context(state)
    try:
        validate_params(h.tool, h.params, ctx)
    except ToolError as exc:
        h.status, h.explanation = "invalid", str(exc)
        return h
    cfg = state.config
    eid = planned_execution_id(h.tool, df, h.params, ctx, input_fingerprint=state.dataset.content_sha256,
                               sample_threshold=cfg.sample_threshold, expensive_sample=cfg.expensive_sample)
    if eid not in state.results:
        if _new_calls(state) >= cfg.max_tool_calls:
            h.status, h.explanation = "untested", "tool-call cap reached"
            return h
        record, result = execute(h.tool, df, h.params, ctx, input_fingerprint=state.dataset.content_sha256,
                                 origin="model" if h.origin == "model" else "hypothesis",
                                 sample_threshold=cfg.sample_threshold, expensive_sample=cfg.expensive_sample)
        state.executions.append(record)
        state.results[record.execution_id] = result
    h.execution_id = eid
    h.status, h.explanation, h.evidence = evaluate(h.decision_rule, state.results[eid])
    return h


def _add(state: InvestigationState, t: Template, round_: int, from_findings: List[str], parent: Optional[str]) -> Optional[Hypothesis]:
    key = sha256_json({"t": t["template"], "tool": t["tool"], "params": t["params"]})
    if any(sha256_json({"t": h.template, "tool": h.tool, "params": h.params}) == key for h in state.hypotheses):
        return None
    h = Hypothesis(hypothesis_id=_next_id(state), round=round_, template=t["template"], from_findings=from_findings,
                   parent=parent, statement=t["statement"], tool=t["tool"], params=t["params"],
                   prediction=t["prediction"], decision_rule=t["rule"], origin="template")
    state.hypotheses.append(h)
    return h


def candidates_for_hypotheses(state: InvestigationState) -> List[Finding]:
    reportable = [f for f in state.findings if not f.quality and f.status != "REJECTED" and f.merged_into is None]
    return ranked(reportable)[: state.config.top_n]


def run_loop(state: InvestigationState, df: pd.DataFrame) -> None:
    """Rounds of templated hypotheses and follow-ups, within the caps (REQ-008, NFR-003)."""
    cfg = state.config
    round_ = 1
    pending: List[Hypothesis] = []
    for f in candidates_for_hypotheses(state):
        for t in TEMPLATES.get(f.kind, lambda *_: [])(f, state):
            h = _add(state, t, round_, [f.key], None)
            if h:
                pending.append(h)
    while pending and round_ <= cfg.max_rounds:
        for h in pending:
            test_hypothesis(state, df, h)
        round_ += 1
        nxt: List[Hypothesis] = []
        if round_ <= cfg.max_rounds:
            for h in pending:
                for t in FOLLOW_UPS.get((h.template or "", h.status), lambda *_: [])(h, state):
                    child = _add(state, t, round_, h.from_findings, h.hypothesis_id)
                    if child:
                        nxt.append(child)
        pending = nxt
    for h in pending:
        h.explanation = h.explanation or "round cap reached"
        state.notes.append(f"{h.hypothesis_id} not tested: round cap reached")
    capped = [h for h in state.hypotheses if h.status == "untested"]
    if capped:
        state.notes.append(f"{len(capped)} hypothesis(es) left untested by the round or tool-call cap")


def add_model_hypotheses(state: InvestigationState, df: pd.DataFrame, proposals: List[Dict[str, Any]],
                         grounder: Callable[[str, List[Any], List[str]], List[str]]) -> List[Hypothesis]:
    """Validate and test hypotheses a language-model investigator proposed (REQ-008, REQ-017).

    Each proposal needs ``statement``, ``from_findings`` (finding keys or ids), ``tool``, ``params``,
    ``prediction``, and ``decision_rule``. The statement may only state numbers found in the evidence
    of the findings it cites or in its own parameters (``grounder`` returns the unbacked ones).
    """
    known = {f.key: f for f in state.findings} | {f.finding_id: f for f in state.findings if f.finding_id}
    round_ = max((h.round for h in state.hypotheses), default=0) + 1
    out = []
    for prop in proposals:
        hid = _next_id(state)
        try:
            cites = [known[k].key for k in prop.get("from_findings", [])]
            rule_ = DecisionRule.model_validate(prop["decision_rule"])
            h = Hypothesis(hypothesis_id=hid, round=round_, template=None, from_findings=cites, parent=None,
                           statement=str(prop["statement"]), tool=str(prop["tool"]), params=dict(prop["params"]),
                           prediction=str(prop.get("prediction", "")), decision_rule=rule_, origin="model")
        except (KeyError, TypeError, ValueError) as exc:
            bad = Hypothesis(hypothesis_id=hid, round=round_, statement=str(prop.get("statement", ""))[:500],
                             tool=str(prop.get("tool", "")), params={}, prediction="",
                             decision_rule=DecisionRule(supported=[], rejected=[]), origin="model",
                             status="invalid", explanation=f"malformed proposal: {exc}")
            state.hypotheses.append(bad)
            out.append(bad)
            continue
        state.hypotheses.append(h)
        try:
            spec(h.tool)
        except ToolError as exc:
            h.status, h.explanation = "invalid", str(exc)
            out.append(h)
            continue
        values = [known[k].evidence for k in h.from_findings] + [h.params]
        labels = [str(v) for v in h.params.values()] + [str(v) for k in h.from_findings for v in known[k].subject.values()]
        unbacked = grounder(h.statement, values, labels)
        if unbacked:
            h.status, h.explanation = "invalid", f"statement states unbacked values: {unbacked}"
            out.append(h)
            continue
        out.append(test_hypothesis(state, df, h))
    return out


# --- research questions ---------------------------------------------------------

def questions(state: InvestigationState) -> List[Question]:
    """5–10 follow-up questions, each tied to the findings or hypotheses behind it (REQ-009)."""
    qs: List[Question] = []
    ent = _entity(state)
    by_key = {f.key: f for f in state.findings}

    def add(text: str, findings: List[str], hyps: List[str], tool: Optional[str]) -> None:
        if len(qs) >= 10 or any(q.text == text for q in qs):
            return
        qs.append(Question(question_id=f"Q{len(qs) + 1:02d}", text=text, from_findings=findings,
                           from_hypotheses=hyps, tool=tool, needs_new_tool=tool is None))

    for h in state.hypotheses:
        p, src = h.params, h.from_findings
        if h.template == "gap_stratified" and h.status == "supported":
            add(f"What sets `{p['by']}` = `{p['exposed']}` apart, given that its higher `{p['target']}` rate holds within `{p['strata']}` bands?",
                src, [h.hypothesis_id], "analyze_entity_concentration" if ent else None)
        elif h.template == "gap_stratified" and h.status == "rejected":
            add(f"How much of the `{p['by']}` gap does `{p['strata']}` account for, band by band?",
                src, [h.hypothesis_id], "compare_target_rates")
        elif h.template == "window_denominator" and h.status == "supported":
            add(f"What lowers total volume during {p['part']}s {p['window'][0]} to {p['window'][-1]}, and do the "
                f"`{p['target']}` events there come from a few `{ent or 'entity'}` values?",
                src, [h.hypothesis_id], "analyze_entity_concentration" if ent else None)
        elif h.template == "shift_target" and h.status == "supported":
            add(f"Did the process generating `{p['target']}` change at the breakpoint, and in which segments?",
                src, [h.hypothesis_id], None)
        elif h.status == "inconclusive":
            add(f"Does this hold with more data or a longer window: {h.statement}", src, [h.hypothesis_id], h.tool)
    for f in ranked([f for f in state.findings if f.merged_into is None and f.status != "REJECTED"]):
        s = f.subject
        if f.kind == "correlation":
            cat = _first(state, ("categorical",), max_unique=50)
            add(f"Does the `{s['a']}`–`{s['b']}` relationship hold within `{cat}` groups?" if cat else
                f"Is the `{s['a']}`–`{s['b']}` relationship stable over time?", [f.key], [],
                "compare_segments" if cat else None)
        elif f.kind == "trend":
            what = {"volume": "row volume", "metric": f"`{s.get('column')}`", "rate": f"`{s.get('column')}` rate"}[s["series"]]
            add(f"What explains the {what} trend over `{s['timestamp']}`?", [f.key], [], None)
        elif f.kind == "missing_values":
            target = next((c.name for c in state.columns if c.role == "binary_target"), None)
            add(f"Why is `{s['column']}` missing in {pct(f.evidence['missing_pct'])} of rows, and is it missing at random?",
                [f.key], [], "compare_target_rates_by_missingness" if target else None)
        elif f.kind == "entity_concentration":
            add(f"Are anomalies concentrated among a few `{s['entity']}` values?", [f.key], [], None)
        elif f.kind in ("multivariate_outliers", "outlier_heavy"):
            add("Do the outlying rows share a segment or period?", [f.key], [], "compare_segments")
        elif f.kind == "distribution_shift":
            add(f"Was the `{s['column']}` shift at `{s['date']}` a change in the data or in how it was recorded?", [f.key], [], None)
        elif f.kind == "target_rate_gap" and ent:
            add(f"Are `{s['target']}` positives in `{s['by']}` = `{s['exposed']}` concentrated among a few `{ent}` values?",
                [f.key], [], "analyze_entity_concentration")
    if len(qs) < 5:
        anchor = [f.key for f in ranked(list(by_key.values()))[:1]]
        target = next((c.name for c in state.columns if c.role == "binary_target"), None)
        ts = next((c.name for c in state.columns if c.role == "timestamp"), None)
        for c in state.columns:
            if len(qs) >= 5 or not anchor:
                break
            if c.role == "continuous_numeric" and ts:
                add(f"Is the distribution of `{c.name}` stable over `{ts}`?", anchor, [], "detect_distribution_shift")
            elif c.role in ("categorical", "boolean") and target and not c.pii:
                add(f"Does the `{target}` rate differ across `{c.name}` once other columns are held fixed?",
                    anchor, [], "stratified_target_rates")
    return qs
