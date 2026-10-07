"""``dataset-investigator`` — the exported package's command. Spec ``0099`` (REQ-012–REQ-014).

::

    dataset-investigator analyze DATA [--target COL] [--timestamp COL] [--out DIR]
    dataset-investigator reproduce F007 --data DATA [--manifest PATH]
    dataset-investigator rerun --data DATA [--out DIR]

Exit codes: 0 reproduced (or analyzed), 2 usage error, 3 evidence mismatch, 4 wrong dataset.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from .models import Config
from .pipeline import EXIT_USAGE, investigate, reproduce, rerun

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def _config(args: argparse.Namespace) -> Config:
    if getattr(args, "config", None):
        import yaml
        data = yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) or {}
    else:
        data = {}
    for key in ("target", "timestamp", "seed", "as_of"):
        v = getattr(args, key, None)
        if v is not None:
            data[key] = v
    if getattr(args, "roles", None):
        data["roles"] = json.loads(args.roles)
    if getattr(args, "pii", None):
        data["pii"] = list(args.pii)
    return Config.model_validate(data)


def add_analyze_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("data", help="CSV, TSV, or Parquet file")
    p.add_argument("--target", help="target column (overrides inference)")
    p.add_argument("--timestamp", help="timestamp column (overrides inference)")
    p.add_argument("--roles", help='JSON object of column roles, e.g. {"zip": "categorical"}')
    p.add_argument("--pii", nargs="*", help="columns whose values must never appear in any output")
    p.add_argument("--seed", type=int)
    p.add_argument("--as-of", dest="as_of", help="as-of date for impossible-timestamp checks (YYYY-MM-DD)")
    p.add_argument("--config", help="investigation.yaml to start from")
    p.add_argument("--out", default="investigation_run", help="output directory")
    p.add_argument("--run-id")
    p.add_argument("--no-figures", action="store_true")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="dataset-investigator", description="Reproducible dataset investigation (spec 0099).")
    sub = ap.add_subparsers(dest="command", required=True)
    a = sub.add_parser("analyze", help="run the whole investigation with no language model")
    add_analyze_args(a)
    r = sub.add_parser("reproduce", help="re-execute one recorded finding and compare its evidence")
    r.add_argument("finding_id")
    r.add_argument("--data", required=True)
    r.add_argument("--manifest", default=str(PACKAGE_ROOT / "manifest.json"))
    rr = sub.add_parser("rerun", help="repeat the investigation and compare outputs with the recording")
    rr.add_argument("--data", required=True)
    rr.add_argument("--out", default="rerun_output")
    rr.add_argument("--package", default=str(PACKAGE_ROOT))
    args = ap.parse_args(argv)
    try:
        if args.command == "analyze":
            state = investigate(args.data, _config(args), args.out, run_id=args.run_id, figures=not args.no_figures)
            print(f"Investigated {state.dataset.rows:,} rows × {state.dataset.columns} columns → {args.out}/report/")
            return 0
        if args.command == "reproduce":
            m = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
            outcome = reproduce(m, args.finding_id, args.data)
        else:
            outcome = rerun(args.package, args.data, args.out)
    except (ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    print("\n".join(outcome.lines))
    return outcome.code


if __name__ == "__main__":
    raise SystemExit(main())
