"""``quantsmith-dataset-investigator`` — the Dataset Investigator command. Spec ``0099`` (REQ-016).

``analyze`` runs everything with no language model and exports the package.
The other subcommands are the steps the on-demand workflow
(``.claude/workflows/dataset-investigator.js``) drives one at a time; each reads
and writes ``RUN_DIR/state.json`` and prints JSON on stdout::

    profile DATA --out RUN_DIR [...]          load, roles, deterministic plan
    context RUN_DIR --role ROLE               what a model role may see (aggregates only)
    catalog                                   the registered tools and their parameter schemas
    plan RUN_DIR --analyses JSON|-            a model-chosen plan (validated)
    run-plan RUN_DIR [--analyses JSON|-] [--templates]   execute the plan; derive and score findings
    hypotheses RUN_DIR [--templates] [--add JSON|-]       templated loop and/or model proposals
    run-tool RUN_DIR TOOL --params JSON|-     one registered tool (exploration)
    validate RUN_DIR [--review JSON|-]        validator (+ downgrade-only model review), questions
    report RUN_DIR [--narrative TEXT|-] [--export]       report (a model narrative is grounded first)
    export RUN_DIR                            analysis package
    reproduce FID --run RUN_DIR --data DATA

Step commands accept ``--context ROLE`` to print ``{"result": ..., "context": ...}``
— the step's output plus the next role's context — so one call does one step.
That output is compact JSON and leaves the static tool catalog out of the
investigator's context (``catalog`` prints it once), so each step's output stays
small enough to pass through an executor agent intact.

Exit codes: 0 ok, 2 usage error, 3 mismatch, 4 wrong dataset, 5 narrative rejected.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

from .analysis import planner as PL
from .analysis.cli import _config, add_analyze_args
from .analysis.hypotheses import add_model_hypotheses, run_loop, tool_context
from .analysis.loading import load_dataset
from .analysis.models import InvestigationState
from .analysis.pipeline import (
    EXIT_USAGE,
    EXIT_WRONG_DATA,
    finish,
    investigate,
    load_state,
    reproduce,
    run_plan,
    save_state,
    start,
    write_bundle,
)
from .analysis.registry import ToolError, catalog, execute
from .analysis.report import key_findings
from .analysis.utils import jsonable
from .analysis.validator import (
    apply_review,
    causal_phrases,
    ground,
    report_grounding_labels,
    report_grounding_values,
)
from .context import build as build_context
from .export import build_package

EXIT_NARRATIVE = 5


def _read(value: str) -> str:
    return sys.stdin.read() if value == "-" else value


def _json_arg(value: str) -> Any:
    try:
        return json.loads(_read(value))
    except json.JSONDecodeError as exc:
        raise ValueError(f"not valid JSON: {exc}") from exc


def _emit(obj: Any, *, compact: bool = False) -> None:
    if compact:
        print(json.dumps(jsonable(obj), separators=(",", ":"), sort_keys=True))
    else:
        print(json.dumps(jsonable(obj), indent=1, sort_keys=True))


def _load(run_dir: str):
    state = load_state(Path(run_dir) / "state.json")
    if state.dataset.format in ("pandas", "polars"):
        raise ValueError("this run was started from an in-memory frame; step commands need a file")
    df, info = load_dataset(state.dataset.source)
    if info.content_sha256 != state.dataset.content_sha256:
        raise LookupError(f"{state.dataset.source} changed since the run started (content hash differs)")
    return df, state


def _save(state: InvestigationState, run_dir: str) -> None:
    save_state(state, Path(run_dir) / "state.json")


def _summary(state: InvestigationState) -> dict:
    return {"run_id": state.run_id, "rows": state.dataset.rows, "columns": state.dataset.columns,
            "executions": len(state.executions), "candidate_findings": len(state.findings),
            "key_findings": [f.finding_id for f in key_findings(state)],
            "hypotheses": {s: sum(1 for h in state.hypotheses if h.status == s)
                           for s in ("supported", "rejected", "inconclusive", "invalid", "untested")},
            "questions": len(state.questions)}


def _with_context(out: Any, state: InvestigationState, role: Optional[str]) -> Any:
    return {"result": out, "context": build_context(state, role, tools=False)} if role else out


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="quantsmith-dataset-investigator",
                                 description="Investigate a tabular dataset reproducibly (spec 0099).")
    sub = ap.add_subparsers(dest="command", required=True)
    a = sub.add_parser("analyze", help="the whole investigation, no language model, plus the analysis package")
    add_analyze_args(a)
    a.add_argument("--created-at", help="timestamp recorded in run metadata (default: none)")
    pr = sub.add_parser("profile", help="load, assign roles, plan (workflow step 1)")
    add_analyze_args(pr)
    pr.add_argument("--created-at")
    pr.add_argument("--context")
    c = sub.add_parser("context", help="the context a model role may see")
    c.add_argument("run"); c.add_argument("--role", required=True)
    sub.add_parser("catalog", help="the registered tools and their parameter schemas")
    pl = sub.add_parser("plan", help="replace the plan with a model-chosen, validated one")
    pl.add_argument("run"); pl.add_argument("--analyses", required=True)
    rp = sub.add_parser("run-plan", help="execute the plan; derive and score candidate findings")
    rp.add_argument("run"); rp.add_argument("--analyses"); rp.add_argument("--templates", action="store_true")
    hy = sub.add_parser("hypotheses", help="templated hypothesis loop and/or model proposals")
    hy.add_argument("run"); hy.add_argument("--templates", action="store_true"); hy.add_argument("--add")
    rt = sub.add_parser("run-tool", help="execute one registered tool")
    rt.add_argument("run"); rt.add_argument("tool"); rt.add_argument("--params", default="{}")
    va = sub.add_parser("validate", help="validate findings; generate questions")
    va.add_argument("run"); va.add_argument("--review")
    rep = sub.add_parser("report", help="write the report")
    rep.add_argument("run"); rep.add_argument("--narrative"); rep.add_argument("--no-figures", action="store_true")
    rep.add_argument("--export", action="store_true")
    for p in (pl, rp, hy, rt, va):
        p.add_argument("--context")
    ex = sub.add_parser("export", help="build the analysis package")
    ex.add_argument("run")
    rd = sub.add_parser("reproduce", help="reproduce one finding from a run's package")
    rd.add_argument("finding_id"); rd.add_argument("--run", required=True); rd.add_argument("--data", required=True)
    args = ap.parse_args(argv)

    try:
        cmd = args.command
        if cmd == "analyze":
            state = investigate(args.data, _config(args), args.out, run_id=args.run_id,
                                created_at=args.created_at, figures=not args.no_figures)
            pkg = build_package(state, Path(args.out))
            _emit({**_summary(state), "report": str(Path(args.out) / "report" / "investigation_report.md"),
                   "package": str(pkg)})
            return 0
        if cmd == "profile":
            df, state = start(args.data, _config(args), run_id=args.run_id, created_at=args.created_at)
            state.plan = PL.plan(df, state)
            Path(args.out).mkdir(parents=True, exist_ok=True)
            _save(state, args.out)
            _emit(_with_context({"run": args.out, **_summary(state)}, state, args.context), compact=bool(args.context))
            return 0
        if cmd == "reproduce":
            m = json.loads((Path(args.run) / "analysis_package" / "manifest.json").read_text(encoding="utf-8"))
            outcome = reproduce(m, args.finding_id, args.data)
            print("\n".join(outcome.lines))
            return outcome.code
        if cmd == "catalog":
            _emit({"tools": catalog()}, compact=True)
            return 0
        if cmd == "context":
            _emit(build_context(load_state(Path(args.run) / "state.json"), args.role))
            return 0
        df, state = _load(args.run)
        out: Any = None
        if cmd == "plan" or (cmd == "run-plan" and args.analyses):
            names = PL.validate_plan(_json_arg(args.analyses))
            state.plan = PL.plan(df, state, names, source="model")
            state.executions, state.results, state.findings, state.hypotheses = [], {}, [], []
            out = state.plan.model_dump(mode="json")
        if cmd == "run-plan":
            run_plan(state, df)
            if args.templates:
                run_loop(state, df)
            out = _summary(state)
        elif cmd == "hypotheses":
            new = []
            if args.templates:
                run_loop(state, df)
            if args.add:
                props = _json_arg(args.add)
                props = props.get("hypotheses", props) if isinstance(props, dict) else props
                new = add_model_hypotheses(state, df, list(props), ground)
            # The context lists each hypothesis in full; here only the outcome.
            out = {"tested": [{"hypothesis_id": h.hypothesis_id, "status": h.status, "explanation": h.explanation}
                              for h in new], **_summary(state)}
        elif cmd == "run-tool":
            record, result = execute(args.tool, df, _json_arg(args.params), tool_context(state),
                                     input_fingerprint=state.dataset.content_sha256, origin="model",
                                     sample_threshold=state.config.sample_threshold,
                                     expensive_sample=state.config.expensive_sample)
            if record.execution_id not in state.results:
                state.executions.append(record)
                state.results[record.execution_id] = result
            out = {"execution": record.model_dump(mode="json"), "result": result}
        elif cmd == "validate":
            finish(state, df)
            notes = []
            if args.review:
                reviews = _json_arg(args.review)
                reviews = reviews.get("reviews", reviews) if isinstance(reviews, dict) else reviews
                notes = apply_review(state, list(reviews))
            out = {**_summary(state), "review_notes": notes,
                   "statuses": {f.finding_id: f.status for f in state.findings}}
        elif cmd == "report":
            if args.narrative:
                text = _read(args.narrative).strip()
                if text.startswith('"'):
                    try:
                        decoded = json.loads(text)
                        text = decoded.strip() if isinstance(decoded, str) else text
                    except json.JSONDecodeError:
                        pass
                unbacked = ground(text, report_grounding_values(state), report_grounding_labels(state))
                causal = causal_phrases(text)
                if unbacked or causal:
                    _emit({"accepted": False, "unbacked": unbacked, "causal": causal})
                    return EXIT_NARRATIVE
                state.narrative = text
            write_bundle(state, args.run, figures=not args.no_figures, data_hint=state.dataset.source)
            out = {"accepted": True, "report": str(Path(args.run) / "report" / "investigation_report.md")}
            if args.export:
                out["package"] = str(build_package(state, Path(args.run)))
            out.update(_summary(state))
        elif cmd == "export":
            out = {"package": str(build_package(state, Path(args.run)))}
        if cmd != "export":
            _save(state, args.run)
        role = getattr(args, "context", None)
        _emit(_with_context(out, state, role), compact=bool(role))
        return 0
    except LookupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_WRONG_DATA
    except (ValueError, ToolError, FileNotFoundError, PL.PlanError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
