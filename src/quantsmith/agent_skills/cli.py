"""``quantsmith-agent-skills`` command line (spec 0100). Every subcommand prints JSON to stdout.

    sync    --source <dir|clone|archive> [--ref REF] [--dry-run] [--root .]
    diff    --source <dir|clone|archive> [--ref REF] [--root .]          (sync --dry-run: change summary only)
    verify  [--root .]                                                    (the checks the agent-skills gate runs)
    status  [--root .]                                                    (copy in effect, lock match, review due)
    install --scope project|user [--path MARKETPLACE_DIR] [--dry-run] [--root .]

Sources must be local: a URL is refused before any I/O. Exit status: 0 = ok / nothing to flag; 1 = findings
(verify/status) ; 2 = could not run (bad config, rejected or unreadable source, unsafe files, missing `claude`).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .config import ConfigError, load_config
from .source import SourceError, read_source
from .status import install_commands, status
from .vendor import plan_sync, verify, write_sync


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="quantsmith-agent-skills", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("sync", "diff"):
        s = sub.add_parser(name)
        s.add_argument("--source", required=True)
        s.add_argument("--ref")
        s.add_argument("--root", default=".")
        if name == "sync":
            s.add_argument("--dry-run", action="store_true")
    for name in ("verify", "status"):
        sub.add_parser(name).add_argument("--root", default=".")
    i = sub.add_parser("install")
    i.add_argument("--scope", choices=("project", "user"), required=True)
    i.add_argument("--path", type=Path)
    i.add_argument("--dry-run", action="store_true")
    i.add_argument("--root", default=".")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        cfg = load_config(args.root)
    except ConfigError as exc:
        _emit({"ok": False, "error": str(exc)})
        return 2

    if args.cmd in ("sync", "diff"):
        try:
            snap = read_source(args.source, args.ref)
        except SourceError as exc:
            _emit({"ok": False, "error": str(exc)})
            return 2
        plan = plan_sync(cfg, snap)
        dry = args.cmd == "diff" or args.dry_run
        payload = plan.summary() | {"source_kind": snap.kind, "written": False}
        if not plan.ok:
            payload["error"] = "refused: nothing written"
            _emit(payload)
            return 2
        if not dry:
            write_sync(cfg, plan)
            payload["written"] = True
        _emit(payload)
        return 0

    if args.cmd == "verify":
        findings = verify(cfg)
        _emit({"ok": not findings, "findings": findings})
        return 1 if findings else 0

    if args.cmd == "status":
        out = status(cfg)
        _emit(out)
        return 1 if out["findings"] else 0

    cmds = install_commands(cfg, args.scope, args.path)
    if args.scope == "project" and not cfg.vendor_dir.is_dir():
        _emit({"ok": False, "error": f"{cfg.raw['vendor_dir']} does not exist; sync first", "commands": cmds})
        return 2
    if args.dry_run:
        _emit({"ok": True, "dry_run": True, "commands": cmds})
        return 0
    ran = []
    for cmd in cmds:
        try:
            r = subprocess.run(cmd, cwd=cfg.root, capture_output=True, text=True, check=False)
        except FileNotFoundError:
            _emit({"ok": False, "error": "the `claude` CLI was not found on PATH; run these yourself",
                   "commands": cmds})
            return 2
        ran.append({"command": cmd, "returncode": r.returncode, "output": (r.stdout + r.stderr).strip()[-2000:]})
        if r.returncode != 0:
            _emit({"ok": False, "ran": ran})
            return 2
    _emit({"ok": True, "ran": ran})
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
