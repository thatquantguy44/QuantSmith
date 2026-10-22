"""``python -m sfmeridian`` — command line over the tool registry (spec ``0114`` REQ-011).

Every command prints one JSON document and exits 0 on success, 1 when the
result reports a failure, and 2 on invalid configuration or arguments. The
CLI is the only place a wall-clock date is read (``--today`` overrides it);
tools and agents receive the date as an input.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import CONTRACT_VERSION, __version__
from .config import ConfigError, load_config
from .librarian import run_librarian
from .tools import ToolContext, default_registry


def _print(value: Any) -> None:
    print(json.dumps(value, indent=1, sort_keys=True, ensure_ascii=False))


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sfmeridian", description="SFMeridian securities finance intelligence plugin")
    p.add_argument("--config", help="config file (default: $SFMERIDIAN_CONFIG)")
    p.add_argument("--today", help="ISO date to stamp proposals and runs (default: today)")
    p.add_argument("--actor", default="sfmeridian-cli", help="pseudonymous handle of the caller")
    p.add_argument("--agents-root", default="agents", help="the agents/ directory for governance checks")
    p.add_argument("--version", action="version", version=f"sfmeridian {__version__} (contract {CONTRACT_VERSION})")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("config", help="configuration").add_subparsers(dest="action", required=True)
    v = c.add_parser("validate")
    v.add_argument("--allow-placeholders", action="store_true", help="accept <placeholder> values (templates)")

    t = sub.add_parser("tool", help="the tool registry").add_subparsers(dest="action", required=True)
    t.add_parser("list")
    call = t.add_parser("call")
    call.add_argument("name")
    call.add_argument("--args", default="{}", help="JSON object of tool arguments")

    i = sub.add_parser("index", help="fetch and index query repositories")
    i.add_argument("--repo", action="append", dest="repo_ids")
    i.add_argument("--force", action="store_true")
    sub.add_parser("status", help="index status per repository")
    s = sub.add_parser("search", help="search indexed exemplars")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=5)
    s.add_argument("--no-hints", action="store_true")

    f = sub.add_parser("feedback", help="the reviewed inbox").add_subparsers(dest="action", required=True)
    fp = f.add_parser("propose")
    fp.add_argument("--kind", required=True, choices=["exemplar", "correction"])
    fp.add_argument("--payload", required=True, help="JSON object or @file.json")
    fl = f.add_parser("list")
    fl.add_argument("--status", choices=["staged", "promoted", "discarded"])
    fpr = f.add_parser("promote")
    fpr.add_argument("candidate_id")
    fpr.add_argument("--note")
    fd = f.add_parser("discard")
    fd.add_argument("candidate_id")
    fd.add_argument("--reason", required=True)

    g = sub.add_parser("governance", help="catalog checks").add_subparsers(dest="action", required=True)
    gv = g.add_parser("validate")
    gv.add_argument("--strict", action="store_true")

    a = sub.add_parser("agent", help="run a loop agent").add_subparsers(dest="action", required=True)
    ar = a.add_parser("run")
    ar.add_argument("name", choices=["query_librarian"])
    ar.add_argument("--repo", action="append", dest="repo_ids")
    ar.add_argument("--save", action="store_true", help="write the run record under <index.dir>/runs/")
    return p


def _payload(text: str) -> Dict[str, Any]:
    if text.startswith("@"):
        text = Path(text[1:]).read_text(encoding="utf-8")
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("payload must be a JSON object")
    return value


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    today = args.today or datetime.date.today().isoformat()
    try:
        config = load_config(args.config, allow_placeholders=getattr(args, "allow_placeholders", False))
    except ConfigError as exc:
        _print({"ok": False, "issues": [i.as_dict() for i in exc.issues]})
        return 2
    if args.command == "config":
        _print({"ok": True, "config_hash": config.hash, "source": config.source})
        return 0
    ctx = ToolContext(config=config, today=today, actor=args.actor, agents_root=Path(args.agents_root))
    registry = default_registry()

    if args.command == "agent":
        inputs = {"repo_ids": args.repo_ids} if args.repo_ids else {}
        run = run_librarian(ctx, registry=registry, inputs=inputs)
        record = run.as_dict()
        if args.save:
            runs = config.resolve_path(config.data["index"]["dir"]) / "runs"
            runs.mkdir(parents=True, exist_ok=True)
            (runs / f"{run.run_id}.json").write_text(json.dumps(record, indent=1, sort_keys=True) + "\n",
                                                     encoding="utf-8")
        _print(record)
        return 0 if run.status in ("completed", "escalated") else 1

    if args.command == "tool" and args.action == "list":
        _print({"contract_version": CONTRACT_VERSION, "tools": registry.describe()})
        return 0
    try:
        name, tool_args = {
            ("tool", "call"): lambda: (args.name, _payload(args.args)),
            ("index", None): lambda: ("repos.index", {k: v for k, v in
                                                      {"repo_ids": args.repo_ids, "force": args.force or None}.items() if v}),
            ("status", None): lambda: ("repos.status", {}),
            ("search", None): lambda: ("queries.search", {"query": args.query, "limit": args.limit,
                                                          "include_hints": not args.no_hints}),
            ("feedback", "propose"): lambda: ("feedback.propose", {"kind": args.kind, "payload": _payload(args.payload)}),
            ("feedback", "list"): lambda: ("feedback.list", {"status": args.status} if args.status else {}),
            ("feedback", "promote"): lambda: ("feedback.promote", {k: v for k, v in
                                                                  {"candidate_id": args.candidate_id, "note": args.note}.items() if v}),
            ("feedback", "discard"): lambda: ("feedback.discard", {"candidate_id": args.candidate_id, "reason": args.reason}),
            ("governance", "validate"): lambda: ("governance.validate", {"strict": args.strict}),
        }[(args.command, getattr(args, "action", None))]()
    except (ValueError, json.JSONDecodeError) as exc:
        _print({"ok": False, "error": str(exc)})
        return 2
    result = registry.call(name, tool_args, ctx)
    _print(result.as_dict())
    if not result.ok:
        return 1
    if name == "repos.index" and not result.output.get("ok", True):
        return 1
    if name == "governance.validate" and not result.output.get("ok", True):
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
