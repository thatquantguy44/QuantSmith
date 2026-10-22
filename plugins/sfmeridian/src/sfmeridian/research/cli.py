"""Command line for research runs and bundle reruns (spec ``0121`` REQ-012, AC-013)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..config import ConfigError, load_config, read_file
from ..tools import ToolContext
from .policy import run_research

__all__ = ["rerun_main", "run_main"]


def _run(config_path: str, dataset: str, context: dict, today: str, out: str | None) -> int:
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        print(json.dumps({"ok": False, "issues": [i.as_dict() for i in exc.issues]}, indent=1))
        return 2
    if out:
        data = dict(config.data)
        data["research"] = {"output_dir": str(Path(out).resolve())}
        config = type(config)(data=data, hash=config.hash, source=config.source)
    run = run_research(ToolContext(config, today=today, actor="lending-data-researcher"), dataset=dataset,
                       context=context)
    s_out = run.outputs
    print(json.dumps({"status": run.status, "summary": run.summary, "run_id": run.run_id,
                      "bundle": s_out.get("bundle"), "stop_reason": s_out.get("stop_reason")}, indent=1))
    return 0 if run.status in ("completed", "escalated", "budget_exhausted") else 1


def run_main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sfmeridian research run")
    p.add_argument("--config", required=True)
    p.add_argument("--dataset", required=True)
    p.add_argument("--context", required=True, help="research context file (YAML subset or JSON)")
    p.add_argument("--out", help="bundle output directory (default: research.output_dir)")
    args = p.parse_args(argv)
    context = read_file(Path(args.context))
    return _run(args.config, args.dataset, context, context.get("as_of", ""), args.out)


def rerun_main(analysis_dir: Path, argv: list[str] | None = None) -> int:
    """Rerun from a bundle's ``analysis/`` folder with its bundled package and context."""
    p = argparse.ArgumentParser(prog="rerun.py")
    p.add_argument("--config", required=True)
    p.add_argument("--out")
    args = p.parse_args(argv)
    context = json.loads((Path(analysis_dir) / "context.json").read_text(encoding="utf-8"))
    dataset = json.loads((Path(analysis_dir) / "dataset.json").read_text(encoding="utf-8"))["id"]
    return _run(args.config, dataset, context, context.get("as_of", ""), args.out)
