"""Run bundle: reports, coverage, recommendations, charts, code, manifest.

Spec ``0121`` REQ-012 (POC §10, AC-11, AC-13). One directory per run holds
everything needed to review and rerun it:

* ``report.md`` / ``report.json`` — findings, evidence, scope, limitations;
* ``coverage.json`` — every family with status and reason;
* ``recommendations.json`` — the §9 contract;
* ``charts/*.vl.json`` — Vega-Lite specs;
* ``analysis/`` — a copy of the ``sfmeridian`` package that produced the run,
  every rendered SQL template (``queries/``), the research context, the
  dataset declaration, and ``rerun.py``;
* ``dataset_contract_proposal.json`` — proposed rules, marked *proposed*;
* ``run_manifest.json`` — written last by the runner: config hash, versions,
  tool calls, stop reason, artifact hashes, and (unhashed) timings.

Artifacts other than the manifest contain no timing or wall-clock value, so
frozen inputs reproduce their hashes. Original data is never copied in;
for file datasets the POC loader (``load_dataset.py``) verifies the source
bytes by SHA-256.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from .. import __version__
from .evidence import ResearchSession, canonical
from .intake import loader_source

__all__ = ["PACKAGE_DIR", "artifact_hashes", "write_bundle"]

PACKAGE_DIR = Path(__file__).resolve().parents[1]


def _dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, sort_keys=True, ensure_ascii=False, default=str) + "\n",
                    encoding="utf-8")


def artifact_hashes(bundle: Path) -> dict[str, str]:
    out = {}
    for p in sorted(bundle.rglob("*")):
        if p.is_file() and p.name != "run_manifest.json" and "__pycache__" not in p.parts:
            out[p.relative_to(bundle).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def _markdown(s: ResearchSession, report: dict[str, Any]) -> str:
    lines = [f"# Dataset research: {s.dataset.id}", "",
             f"- Objective: {s.context.objective}", f"- Dataset kind: `{s.context.dataset_kind}`",
             f"- Object: `{s.dataset.obj}` ({s.dataset.source}, {s.dataset.dialect})",
             f"- As-of: {s.context.as_of}" + (f" ({s.context.timezone})" if s.context.timezone else ""),
             f"- Stop reason: **{s.stop_reason}**", f"- Rows in the filtered population: {s.facts.get('rows')}",
             "", "## Findings", ""]
    for f in report["findings"]:
        lines.append(f"- **{f['finding_id']} · {f['severity']} · {f['kind']}** — {f['observation']} "
                     f"[scope: {f['scope']}; evidence: {', '.join(f['evidence_ids'])}]")
        if f.get("hypothesis"):
            lines.append(f"  - Hypothesis (not established): {f['hypothesis']}")
    if not report["findings"]:
        lines.append("- No findings from the families that ran.")
    lines += ["", "## Recommendations", ""]
    for r in report["recommendations"]:
        nxt = r["next_diagnostic"]
        lines.append(f"- **{r['recommendation_id']} · {r['priority']}** — {r['action']} "
                     f"(evidence {', '.join(r['evidence_ids'])}; verify: {r['verification']})")
        lines.append(f"  - Next: {'rendered query `' + nxt['template'] + '`' if nxt['type'] == 'query' else nxt['text']}")
    lines += ["", "## Coverage", "", "| Family | Status | Reason |", "| --- | --- | --- |"]
    for c in report["coverage"]:
        lines.append(f"| {c['family']} | {c['status']} | {c['reason'] or ''} |")
    lines += ["", "## Limitations", ""] + [f"- {x}" for x in report["limitations"]]
    lines += ["", "## Interpretation", "",
              ("Findings are observations with stated scope. Pushed-down results are exact for the declared "
               "filtered population; extract results describe the returned rows only. Outliers are flags, "
               "correlations are descriptive, nothing was repaired, and passing checks does not establish "
               "business correctness or point-in-time availability.")]
    return "\n".join(lines) + "\n"


def _contract_proposal(s: ResearchSession) -> dict[str, Any]:
    summaries = s.facts.get("summaries", {})
    types = s.facts.get("types", {})
    return {
        "status": "proposed — not accepted; review before adopting any rule",
        "dataset": s.dataset.id, "as_of": s.context.as_of,
        "columns": {c: {"inferred_type": types.get(c), "observed_null_rate": v.get("null_rate"),
                        "observed_min": v.get("min"), "observed_max": v.get("max")} for c, v in summaries.items()},
        "grain": {"configured": list(s.context.business_grain), "result": s.facts.get("grain"),
                  "candidate_single_column_keys": s.facts.get("candidate_keys", [])},
        "domain_rules": [{"rule_id": r["rule_id"], "status": r.get("status"), "violations": r.get("violations")}
                         for r in s.facts.get("rules", []) if "rule_id" in r],
    }


def write_bundle(s: ResearchSession, root: Path) -> Path:
    key = hashlib.sha256(canonical({"dataset": s.dataset.describe(), "context": s.context.raw,
                                    "config": s.config_hash, "version": __version__}).encode()).hexdigest()[:16]
    bundle = Path(root) / f"{s.dataset.id}-{key}"
    if bundle.exists():
        shutil.rmtree(bundle)
    (bundle / "charts").mkdir(parents=True)
    report = {
        "dataset": s.dataset.describe(), "context": s.context.raw, "config_hash": s.config_hash,
        "stop_reason": s.stop_reason, "rows": s.facts.get("rows"),
        "findings": [f.as_dict() for f in s.findings], "recommendations": s.recommendations,
        "coverage": s.ledger.as_list(), "limitations": s.limitations, "evidence": s.evidence.as_list(),
        "budgets": {"limits": s.context.budgets, "used": s.budget.used()},
        "connector_capabilities": s.executor.capabilities,
    }
    _dump(bundle / "report.json", report)
    (bundle / "report.md").write_text(_markdown(s, report), encoding="utf-8")
    _dump(bundle / "coverage.json", s.ledger.as_list())
    _dump(bundle / "recommendations.json", s.recommendations)
    for chart in s.charts:
        _dump(bundle / "charts" / f"{chart['usermeta']['sfmeridian']['chart_id']}.vl.json", chart)
    _dump(bundle / "dataset_contract_proposal.json", _contract_proposal(s))
    analysis = bundle / "analysis"
    shutil.copytree(PACKAGE_DIR, analysis / "sfmeridian", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for q in s.executor.log:
        (analysis / "queries").mkdir(parents=True, exist_ok=True)
        (analysis / "queries" / f"{q['query_id']}.sql").write_text(
            f"-- template: {q['template']} v{q['template_version']}\n-- parameters (redacted): "
            f"{json.dumps(q['parameters'], default=str)}\n{q['sql']}\n", encoding="utf-8")
    _dump(analysis / "context.json", s.context.raw)
    _dump(analysis / "dataset.json", s.dataset.describe())
    (analysis / "rerun.py").write_text(
        "\"\"\"Rerun this research with the bundled sfmeridian package.\n\n"
        "Usage: python analysis/rerun.py --config <sfmeridian config> [--out <dir>]\n"
        "The config supplies the dataset declaration and connection pointer; credentials are never bundled.\n\"\"\"\n"
        "import json, sys\nfrom pathlib import Path\n\n"
        "HERE = Path(__file__).resolve().parent\nsys.path.insert(0, str(HERE))\n\n"
        "from sfmeridian.research.cli import rerun_main  # noqa: E402\n\n"
        "if __name__ == '__main__':\n    raise SystemExit(rerun_main(HERE, sys.argv[1:]))\n", encoding="utf-8")
    if s.dataset.source == "file" and s.dataset.file_bytes is not None:
        (analysis / "load_dataset.py").write_text(
            loader_source(hashlib.sha256(s.dataset.file_bytes).hexdigest(), s.dataset.path.suffix.lower()),
            encoding="utf-8")
    return bundle


def write_manifest(bundle: Path, manifest: dict[str, Any], timings: dict[str, Any]) -> dict[str, Any]:
    full = {**manifest, "artifact_hashes": artifact_hashes(bundle), "timings_unhashed": timings}
    _dump(bundle / "run_manifest.json", full)
    return full
