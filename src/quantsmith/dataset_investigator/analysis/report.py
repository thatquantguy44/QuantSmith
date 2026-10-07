"""The investigation report. Spec ``0099`` (REQ-011).

Sections always appear in this order: Dataset, Executive Summary, Data
Quality, Key Findings, Anomalies, Hypotheses, Questions Worth Investigating,
Recommended Next Analysis (then an appendix listing the plan). Figures are
drawn only from recorded aggregate results — never from rows — with one
y-axis each, a legend only when two series share a chart, and labels in ink
rather than series colour.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .models import Finding, InvestigationState
from .utils import pretty_json

SECTIONS = ("Dataset", "Executive Summary", "Data Quality", "Key Findings", "Anomalies", "Hypotheses",
            "Questions Worth Investigating", "Recommended Next Analysis")

# Reference palette: two categorical slots (validated: CVD ΔE 24.7, contrast ≥ 3:1), context grey, ink.
BLUE, ORANGE, CONTEXT = "#2a78d6", "#eb6834", "#c3c2b7"
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"

TITLES = {
    "target_rate_gap": "Target-rate gap", "missingness_target": "Missingness linked to the target",
    "period_rate_window": "Time-of-day pattern", "distribution_shift": "Distribution shift",
    "trend": "Trend", "entity_concentration": "Entity concentration", "segment_gap": "Segment gap",
    "multivariate_outliers": "Multivariate outliers", "correlation": "Correlation",
    "outlier_heavy": "Heavy outliers", "skewed_distribution": "Skewed distribution",
}


def findings_payload(state: InvestigationState) -> Dict[str, Any]:
    d = state.dataset
    return {"spec_version": state.spec_version,
            "dataset": {"content_sha256": d.content_sha256, "rows": d.rows, "columns": d.columns},
            "config": state.config.model_dump(mode="json"),
            "findings": [f.model_dump(mode="json") for f in state.findings]}


def hypotheses_payload(state: InvestigationState) -> Dict[str, Any]:
    return {"spec_version": state.spec_version,
            "hypotheses": [h.model_dump(mode="json") for h in state.hypotheses],
            "questions": [q.model_dump(mode="json") for q in state.questions]}


def published(state: InvestigationState, *, quality: bool) -> List[Finding]:
    return [f for f in state.findings if f.quality == quality and f.merged_into is None and f.status == "VALIDATED"]


def key_findings(state: InvestigationState) -> List[Finding]:
    return published(state, quality=False)[: state.config.top_n]


def _fmt(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:.6g}"
    if isinstance(v, int) and not isinstance(v, bool):
        return f"{v:,}"
    return str(v)


def _ids(state: InvestigationState) -> Dict[str, str]:
    return {f.key: f.finding_id or f.key for f in state.findings}


# --- figures --------------------------------------------------------------------

def _axes(title: str, width: float = 6.4, height: float = 3.2):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(width, height), dpi=100)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=8)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title(title, color=INK, fontsize=10, loc="left")
    return plt, fig, ax


def _save(plt, fig, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE, metadata={"Software": None})
    plt.close(fig)


def figure_for(f: Finding, state: InvestigationState, path: Path) -> bool:
    """Draw a figure for one finding from its execution's aggregates; False when the kind has none."""
    res = state.results.get(f.execution_id, {})
    if f.kind == "target_rate_gap":
        groups = res.get("groups", [])
        if not groups:
            return False
        plt, fig, ax = _axes(f"`{res['target']}` rate by {res['by']}".replace("`", ""))
        labels = [g["group"] for g in groups]
        colors = [ORANGE if g == f.subject["exposed"] else BLUE if g == f.subject["reference"] else CONTEXT for g in labels]
        bars = ax.bar(range(len(groups)), [g["rate"] * 100 for g in groups], color=colors, width=0.7)
        ax.set_xticks(range(len(groups)), labels, rotation=30 if len(groups) > 4 else 0, ha="right" if len(groups) > 4 else "center")
        ax.set_ylabel("rate (%)", color=INK_2, fontsize=8)
        for b, g in zip(bars, groups):
            if g["group"] in (f.subject["exposed"], f.subject["reference"]):
                ax.annotate(f"{g['rate'] * 100:.2f}%", (b.get_x() + b.get_width() / 2, b.get_height()),
                            ha="center", va="bottom", fontsize=8, color=INK)
        _save(plt, fig, path)
        return True
    if f.kind == "period_rate_window":
        buckets = res.get("buckets", [])
        plt, fig, ax = _axes(f"{res['target']} rate by {res['part']} (window highlighted)")
        xs = [b["bucket"] for b in buckets]
        window = set(f.subject["window"])
        ax.bar(xs, [(b["rate"] or 0) * 100 for b in buckets],
               color=[ORANGE if x in window else BLUE for x in xs], width=0.7)
        ax.set_xlabel(res["part"], color=INK_2, fontsize=8)
        ax.set_ylabel("rate (%)", color=INK_2, fontsize=8)
        _save(plt, fig, path)
        return True
    if f.kind == "distribution_shift" and res.get("histogram"):
        h = res["histogram"]
        edges = h["edges"]
        mids = [(edges[i] + edges[i + 1]) / 2 for i in range(len(edges) - 1)]
        width = (edges[1] - edges[0]) * 0.42
        nb, na = sum(h["before"]) or 1, sum(h["after"]) or 1
        plt, fig, ax = _axes(f"{res['column']} before and after {res['breakpoint'][:10]}")
        ax.bar([m - width / 2 for m in mids], [c / nb * 100 for c in h["before"]], width=width, color=BLUE, label="before")
        ax.bar([m + width / 2 for m in mids], [c / na * 100 for c in h["after"]], width=width, color=ORANGE, label="after")
        ax.set_ylabel("share of rows (%)", color=INK_2, fontsize=8)
        ax.legend(frameon=False, fontsize=8, labelcolor=INK)
        _save(plt, fig, path)
        return True
    if f.kind == "trend":
        key = {"volume": "n", "metric": "metric_mean", "rate": "rate"}[f.subject["series"]]
        pts = [(i, p[key]) for i, p in enumerate(res.get("periods", [])) if p.get(key) is not None]
        if len(pts) < 2:
            return False
        plt, fig, ax = _axes(f"{f.subject['series']} per {res['freq']} period")
        ax.plot([x for x, _ in pts], [y for _, y in pts], color=BLUE, linewidth=2)
        ax.set_xlabel("period", color=INK_2, fontsize=8)
        _save(plt, fig, path)
        return True
    if f.kind == "missingness_target":
        ev = f.evidence
        plt, fig, ax = _axes(f"{f.subject['target']} rate by whether {f.subject['column']} is missing")
        vals = [ev["rate_present"] * 100, ev["rate_missing"] * 100]
        bars = ax.bar([0, 1], vals, color=[BLUE, ORANGE], width=0.6)
        ax.set_xticks([0, 1], ["present", "missing"])
        for b, v in zip(bars, vals):
            ax.annotate(f"{v:.2f}%", (b.get_x() + b.get_width() / 2, b.get_height()), ha="center", va="bottom", fontsize=8, color=INK)
        ax.set_ylabel("rate (%)", color=INK_2, fontsize=8)
        _save(plt, fig, path)
        return True
    return False


# --- markdown ---------------------------------------------------------------------

def _recommendation(state: InvestigationState, keys: List[Finding]) -> str:
    supported = [h for h in state.hypotheses if h.status == "supported"]
    if keys:
        f = keys[0]
        s = f.subject
        text = {
            "target_rate_gap": f"Segment-level investigation of `{s.get('by')}` = `{s.get('exposed')}` against `{s.get('reference')}`.",
            "missingness_target": f"Investigate why `{s.get('column')}` is missing and whether missingness is informative.",
            "period_rate_window": f"Time-of-day investigation of `{s.get('target')}` within the highlighted {s.get('part')}s.",
            "distribution_shift": f"Temporal regime investigation of `{s.get('column')}` around `{s.get('date')}`.",
            "trend": f"Investigate the `{s.get('series')}` trend over `{s.get('timestamp')}`.",
            "entity_concentration": f"Entity-level investigation of the most concentrated `{s.get('entity')}` values.",
        }.get(f.kind)
        if text:
            return text + (f" Start from {supported[0].hypothesis_id}, which the evidence supports." if supported else "")
    if state.questions:
        return f"Answer {state.questions[0].question_id}: {state.questions[0].text}"
    return "No finding met the validation bar; collect more data or supply a target or timestamp."


def render_markdown(state: InvestigationState, data_hint: str = "<dataset>", drawn: frozenset = frozenset()) -> str:
    d = state.dataset
    ids = _ids(state)
    keys = key_findings(state)
    quality = published(state, quality=True) + [f for f in state.findings if f.quality and f.status == "WEAK_EVIDENCE" and f.merged_into is None]
    rejected = [f for f in state.findings if f.status == "REJECTED"]
    not_established = [f for f in state.findings if not f.quality and f.merged_into is None and f.status in ("WEAK_EVIDENCE", "INCONCLUSIVE")]
    hs = state.hypotheses
    counts = {s: sum(1 for h in hs if h.status == s) for s in ("supported", "rejected", "inconclusive", "invalid", "untested")}
    L: List[str] = ["# Dataset Investigation", ""]

    L += ["## Dataset", "", f"`{d.source}` ({d.format}) — **{d.rows:,} rows × {d.columns} columns**", "",
          f"Content hash `{d.content_sha256[:16]}…` · run `{state.run_id}` · seed {state.config.seed}", "",
          "| Column | Role | Missing | Distinct |", "| --- | --- | --- | --- |"]
    for c in state.columns:
        L.append(f"| `{c.name}` | {c.role}{' (PII)' if c.pii else ''}{' (override)' if c.overridden else ''} | "
                 f"{c.missing_pct * 100:.1f}% | {c.n_unique:,} |")
    L.append("")

    L += ["## Executive Summary", "",
          f"- {len(keys)} key finding(s), {sum(1 for f in keys if f.confidence == 'high')} with high confidence",
          f"- {len(quality)} data-quality concern(s)",
          f"- {len(hs)} hypothesis(es) tested: {counts['supported']} supported, {counts['rejected']} rejected, "
          f"{counts['inconclusive']} inconclusive" + (f", {counts['invalid']} invalid" if counts["invalid"] else ""),
          f"- {len(state.questions)} question(s) worth investigating",
          f"- {len(rejected)} candidate claim(s) rejected by the validator (listed in `findings.json` only)", ""]
    if state.narrative:
        L += ["**Narrative** (written by the language-model writer; every number checked against the evidence):", "",
              state.narrative.strip(), ""]

    L += ["## Data Quality", ""]
    checks = {"duplicate_rows": "Duplicate rows", "duplicate_ids": "Duplicate identifiers",
              "missing_values": f"Missing values above {state.config.missing_warn * 100:.0f}%",
              "constant_column": "Constant columns", "near_constant_column": "Near-constant columns",
              "negative_values": "Impossible negative values", "mixed_types": "Mixed types",
              "high_cardinality": "High-cardinality categoricals", "timestamp_issue": "Impossible timestamps",
              "target_imbalance": "Target imbalance"}
    for kind, name in checks.items():
        hits = [f for f in quality if f.kind == kind]
        if not hits:
            L.append(f"- **PASS** — {name}: none found")
        for f in hits:
            L.append(f"- **WARNING** — {f.claim} ({f.finding_id})")
    L.append("")

    L += ["## Key Findings", ""]
    if not keys:
        L += ["No finding met the validation bar.", ""]
    for i, f in enumerate(keys, 1):
        sc = f.score
        L += [f"### {i}. {TITLES.get(f.kind, f.kind)} — {f.finding_id}", "", f.claim, "",
              f"Confidence **{(f.confidence or 'low').upper()}** · interestingness {sc.I:.2f} "
              f"(M {sc.M:.2f}, S {sc.S:.2f}, P {sc.P:.2f}, A {sc.A:.2f})"
              + (f" · p = {f.p_value:.3g}, BH-adjusted {f.p_adjusted:.3g}" if f.p_adjusted is not None else ""), "",
              "| Evidence | Value |", "| --- | --- |"]
        L += [f"| {k} | {_fmt(v)} |" for k, v in f.evidence.items()]
        L += ["", f"Method: {f.method} · Python: `{f.module}.{f.function}` · params `{json.dumps(f.params, sort_keys=True)}`", "",
              f"Reproduce: `dataset-investigator reproduce {f.finding_id} --data {data_hint}`", ""]
        if f.finding_id in drawn:
            L += [f"![{f.finding_id}](figures/{f.finding_id}.png)", ""]
    if not_established:
        L += ["### Not established", "", "Measured but not validated; do not treat as findings.", ""]
        for f in not_established:
            L.append(f"- {f.finding_id} [{f.status}] {f.claim} — {'; '.join(f.issues)}")
        L.append("")

    L += ["## Anomalies", ""]
    any_anomaly = False
    for e in state.executions:
        if e.origin != "plan" or e.tool not in ("detect_outliers", "detect_multivariate_outliers"):
            continue
        r = state.results[e.execution_id]
        any_anomaly = True
        if e.tool == "detect_outliers":
            flagged = [c for c in r["columns"] if c.get("outliers")]
            L.append(f"- Robust z-score beyond {r['threshold']}: " + (", ".join(
                f"`{c['column']}` {c['outliers']:,} ({c['outlier_pct'] * 100:.2f}%)" for c in flagged) or "none"))
        elif r.get("skipped"):
            L.append(f"- {r['method']}: skipped ({r['skipped']})")
        else:
            L.append(f"- {r['method']} over {len(r['columns'])} columns: {r['outliers']:,} rows ({r['outlier_pct'] * 100:.2f}%)"
                     + (f", sampled to {e.sampled_rows:,} rows" if e.sampled_rows else ""))
    if not any_anomaly:
        L.append("- Not run (no continuous numeric columns).")
    L.append("")

    L += ["## Hypotheses", ""]
    if not hs:
        L += ["No hypotheses were generated.", ""]
    for h in hs:
        cites = ", ".join(ids.get(k, k) for k in h.from_findings) or "—"
        L.append(f"- **{h.hypothesis_id}** [{h.status.upper()}] {h.statement}  ")
        L.append(f"  Test: `{h.tool}` · from {cites}"
                 + (f" · follow-up of {h.parent}" if h.parent else "") + f" · {h.explanation}")
    L.append("")

    L += ["## Questions Worth Investigating", ""]
    for i, q in enumerate(state.questions, 1):
        src = ", ".join([ids.get(k, k) for k in q.from_findings] + q.from_hypotheses)
        how = f"tool `{q.tool}`" if q.tool else "needs a tool the registry lacks"
        L.append(f"{i}. {q.text} ({how}; from {src})")
    L.append("")

    L += ["## Recommended Next Analysis", "", _recommendation(state, keys), ""]

    L += ["## Appendix: Plan", "", f"Planner: {state.plan.source if state.plan else 'none'}", ""]
    if state.plan:
        for pa in state.plan.analyses:
            L.append(f"- {pa.analysis}: `{pa.tool}` {json.dumps(pa.params, sort_keys=True)} — {pa.reason}")
        for sk in state.plan.skipped:
            L.append(f"- {sk.analysis}: skipped — {sk.reason}")
    for n in state.notes:
        L.append(f"- note: {n}")
    L.append("")
    return "\n".join(L)


def write_report(state: InvestigationState, out_dir: Path, *, figures: bool = True, data_hint: str = "<dataset>") -> Path:
    """Write ``report/`` (Markdown, JSON, figures) under ``out_dir``; return the report directory."""
    rep = Path(out_dir) / "report"
    (rep / "figures").mkdir(parents=True, exist_ok=True)
    drawn = set()
    if figures:
        for f in key_findings(state):
            if figure_for(f, state, rep / "figures" / f"{f.finding_id}.png"):
                drawn.add(f.finding_id)
    (rep / "investigation_report.md").write_text(render_markdown(state, data_hint, frozenset(drawn)), encoding="utf-8")
    (rep / "findings.json").write_text(pretty_json(findings_payload(state)), encoding="utf-8")
    (rep / "hypotheses.json").write_text(pretty_json(hypotheses_payload(state)), encoding="utf-8")
    return rep
