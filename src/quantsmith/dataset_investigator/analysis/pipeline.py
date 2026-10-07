"""The deterministic investigation, finding reproduction, and full reruns.
Spec ``0099`` (REQ-012, REQ-013, REQ-014).

:func:`investigate` is the whole run with no language model: load → roles →
plan → tools → candidate findings → hypothesis loop → validation → questions
→ report. The same code runs inside an exported package, where
:func:`reproduce` re-executes one recorded finding and :func:`rerun` repeats
the investigation and compares its outputs byte for byte with the recorded ones.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from . import findings as F
from . import hypotheses as H
from . import planner as P
from .loading import Source, load_dataset
from .metadata import NON_DETERMINISTIC_FIELDS, write_run_metadata
from .models import (
    Config,
    InvestigationState,
    ToolExecution,
)
from .registry import execute
from .report import write_report
from .roles import infer_columns
from .validator import validate

EXIT_OK, EXIT_USAGE, EXIT_MISMATCH, EXIT_WRONG_DATA = 0, 2, 3, 4
TOLERANCE = {"rel": 1e-6, "abs": 1e-9}


def start(source: Source, config: Optional[Config] = None, *, run_id: Optional[str] = None,
          created_at: Optional[str] = None) -> tuple:
    """Load and profile ``source``; return ``(df, state)`` with roles assigned (REQ-001, REQ-002)."""
    config = config or Config()
    df, info = load_dataset(source)
    missing = [c for c in [config.target, config.timestamp, *config.roles, *config.pii] if c and c not in df.columns]
    if missing:
        raise ValueError(f"configured column(s) not in the dataset: {missing}")
    columns = infer_columns(df, config)
    state = InvestigationState(run_id=run_id or f"investigation_{info.content_sha256[:12]}", created_at=created_at,
                               config=config, dataset=info, columns=columns)
    return df, state


def run_plan(state: InvestigationState, df: pd.DataFrame) -> None:
    """Execute every planned tool call once, derive candidate findings, and score them."""
    ctx = H.tool_context(state)
    cfg = state.config
    for pa in state.plan.analyses:
        record, result = execute(pa.tool, df, pa.params, ctx, input_fingerprint=state.dataset.content_sha256,
                                 origin="plan", sample_threshold=cfg.sample_threshold, expensive_sample=cfg.expensive_sample)
        if record.execution_id not in state.results:
            state.executions.append(record)
            state.results[record.execution_id] = result
    state.findings = F.derive_all(state)
    F.score(state)


def finish(state: InvestigationState, df: pd.DataFrame) -> None:
    """Validate every finding and generate the research questions."""
    validate(state, df)
    state.questions = H.questions(state)


def investigate(source: Source, config: Optional[Config] = None, out_dir: Union[str, Path, None] = None, *,
                run_id: Optional[str] = None, created_at: Optional[str] = None, figures: bool = True,
                data_hint: Optional[str] = None) -> InvestigationState:
    """Run a whole investigation with no language model (REQ-014); write the bundle if ``out_dir`` is set."""
    df, state = start(source, config, run_id=run_id, created_at=created_at)
    state.plan = P.plan(df, state)
    run_plan(state, df)
    H.run_loop(state, df)
    finish(state, df)
    if out_dir is not None:
        write_bundle(state, out_dir, figures=figures,
                     data_hint=data_hint or (str(source) if isinstance(source, (str, Path)) else "<dataset>"))
    return state


def write_bundle(state: InvestigationState, out_dir: Union[str, Path], *, figures: bool = True,
                 data_hint: str = "<dataset>") -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_report(state, out, figures=figures, data_hint=data_hint)
    write_run_metadata(state, out / "run_metadata.yaml")
    save_state(state, out / "state.json")
    return out


def save_state(state: InvestigationState, path: Union[str, Path]) -> None:
    Path(path).write_text(state.model_dump_json(indent=1) + "\n", encoding="utf-8")


def load_state(path: Union[str, Path]) -> InvestigationState:
    return InvestigationState.model_validate_json(Path(path).read_text(encoding="utf-8"))


# --- manifest, reproduction, rerun --------------------------------------------------

def manifest(state: InvestigationState, module_hashes: Dict[str, str]) -> Dict[str, Any]:
    """The analysis manifest: every finding → module, function, parameters, expected evidence (REQ-012)."""
    d = state.dataset
    entries = {}
    for f in state.findings:
        if f.merged_into is not None:
            continue
        ex = state.execution(f.execution_id)
        entries[f.finding_id] = {
            "key": f.key, "kind": f.kind, "claim": f.claim, "status": f.status,
            "module": f.module, "function": f.function, "tool": f.tool, "version": f.version,
            "params": f.params, "execution_id": f.execution_id, "sampled_rows": ex.sampled_rows,
            "result_sha256": ex.result_sha256, "evidence": f.evidence, "tolerance": TOLERANCE,
        }
    return {
        "spec_version": state.spec_version, "run_id": state.run_id,
        "dataset": {"source": d.source, "format": d.format, "sha256": d.file_sha256,
                    "content_sha256": d.content_sha256, "rows": d.rows, "columns": d.columns},
        "config": state.config.model_dump(mode="json"),
        "roles": {c.name: c.role for c in state.columns},
        "modules": dict(sorted(module_hashes.items())),
        "non_deterministic_fields": list(NON_DETERMINISTIC_FIELDS),
        "findings": entries,
    }


@dataclass
class Outcome:
    code: int
    lines: List[str] = field(default_factory=list)


def _same_dataset(m: Dict[str, Any], data: Union[str, Path]) -> tuple:
    df, info = load_dataset(data)
    recorded = m["dataset"]
    ok = (recorded.get("sha256") and info.file_sha256 == recorded["sha256"]) or info.content_sha256 == recorded["content_sha256"]
    return bool(ok), df, info


def reproduce(m: Dict[str, Any], finding_id: str, data: Union[str, Path]) -> Outcome:
    """Re-execute one recorded finding on ``data`` and compare it with the recorded evidence (REQ-013)."""
    entry = m["findings"].get(finding_id)
    if entry is None:
        return Outcome(EXIT_USAGE, [f"No finding {finding_id} in the manifest; known: {', '.join(sorted(m['findings']))}"])
    out = Outcome(EXIT_OK, [f"Reproducing Finding {finding_id}...", entry["claim"]])
    ok, df, info = _same_dataset(m, data)
    if not ok:
        out.code = EXIT_WRONG_DATA
        out.lines.append(f"Wrong dataset: content hash {info.content_sha256[:16]}… does not match the recorded "
                         f"{m['dataset']['content_sha256'][:16]}…")
        return out
    config = Config.model_validate(m["config"])
    columns = infer_columns(df, config)
    state = InvestigationState(run_id=m["run_id"], config=config, dataset=info, columns=columns)
    ctx = H.tool_context(state)
    record, result = execute(entry["tool"], df, entry["params"], ctx, input_fingerprint=info.content_sha256,
                             origin="validation", sample_threshold=config.sample_threshold,
                             expensive_sample=config.expensive_sample)
    ex = ToolExecution(**{**record.model_dump(), "execution_id": entry["execution_id"]})
    again = [g for g in F.derive(ex, result, state) if g.key == entry["key"]]
    if not again:
        out.code = EXIT_MISMATCH
        out.lines.append("The finding no longer arises from the recorded call.")
        return out
    expected, actual = entry["evidence"], again[0].evidence
    tol = entry.get("tolerance", TOLERANCE)
    width = max(len(k) for k in expected) if expected else 0
    for k in expected:
        a = actual.get(k)
        shown_a = f"{a:.6g}" if isinstance(a, float) else str(a)
        out.lines.append(f"{k + ':':<{width + 1}}  {shown_a}")
    if all(_close(expected[k], actual.get(k), tol) for k in expected) and expected.keys() == actual.keys():
        out.lines.append("Finding successfully reproduced.")
    else:
        out.code = EXIT_MISMATCH
        diffs = [k for k in expected if not _close(expected[k], actual.get(k), tol)]
        out.lines.append(f"Evidence does not match the recorded values: {', '.join(diffs) or 'fields differ'}")
    return out


def _close(e: Any, a: Any, tol: Dict[str, float]) -> bool:
    import math
    if isinstance(e, (int, float)) and isinstance(a, (int, float)) and not isinstance(e, bool):
        return math.isclose(float(e), float(a), rel_tol=tol["rel"], abs_tol=tol["abs"])
    if isinstance(e, dict) and isinstance(a, dict):
        return e.keys() == a.keys() and all(_close(e[k], a[k], tol) for k in e)
    if isinstance(e, list) and isinstance(a, list):
        return len(e) == len(a) and all(_close(x, y, tol) for x, y in zip(e, a))
    return e == a


def rerun(package_root: Union[str, Path], data: Union[str, Path], out_dir: Union[str, Path]) -> Outcome:
    """Repeat the whole investigation from the package and compare outputs with the recorded ones (REQ-014)."""
    root = Path(package_root)
    m = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    ok, _, info = _same_dataset(m, data)
    if not ok:
        return Outcome(EXIT_WRONG_DATA, [f"Wrong dataset: content hash {info.content_sha256[:16]}… does not match the recording."])
    config = Config.model_validate(m["config"])
    state = investigate(data, config, out_dir, run_id=m["run_id"], data_hint=str(data))
    out = Outcome(EXIT_OK, [f"Re-ran {len(state.executions)} tool executions; {len(state.findings)} candidate findings."])
    for name in ("findings.json", "hypotheses.json"):
        recorded = (root / "expected" / name).read_bytes()
        produced = (Path(out_dir) / "report" / name).read_bytes()
        same = recorded == produced
        out.lines.append(f"{name}: {'identical' if same else 'DIFFERS'}")
        if not same:
            out.code = EXIT_MISMATCH
    out.lines.append("Investigation reproduced." if out.code == EXIT_OK else "Investigation did not reproduce.")
    return out
