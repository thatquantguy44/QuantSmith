"""``quantsmith-skills`` — build, check, list, and distribute the skills export (spec 0110).

    quantsmith-skills build [--date YYYY-MM-DD]     regenerate .claude/skills/ and the registry
    quantsmith-skills check                          exit 1 when the export is stale
    quantsmith-skills list [--all]                   registry summary (active, or all incl. removed)
    quantsmith-skills pending --target claude_ai     skills to upload/delete since last publish
    quantsmith-skills mark-published --target claude_ai
    quantsmith-skills package --format plugin --out DIR
    quantsmith-skills package --format zip --out DIR [--pending-for claude_ai]
"""

from __future__ import annotations

import argparse
import json
from importlib import metadata
from pathlib import Path
from typing import List, Optional

from . import core


def _root(arg: Optional[str]) -> Path:
    if arg:
        return Path(arg).resolve()
    here = Path.cwd().resolve()
    for p in (here, *here.parents):
        if (p / "agents").is_dir() and (p / "specs").is_dir():
            return p
    return here


def _version() -> str:
    try:
        return metadata.version("quantsmith")
    except metadata.PackageNotFoundError:
        return "0.0.0"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="quantsmith-skills", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", help="repository root (default: nearest with agents/ and specs/)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="regenerate skills and registry")
    b.add_argument("--date", help="date recorded for changes (default: today)")
    sub.add_parser("check", help="exit 1 when the export is stale")
    ls = sub.add_parser("list", help="registry summary")
    ls.add_argument("--all", action="store_true", help="include removed skills")
    ls.add_argument("--json", action="store_true")
    pd = sub.add_parser("pending", help="changes since a target was last published")
    pd.add_argument("--target", required=True)
    pd.add_argument("--json", action="store_true")
    mp = sub.add_parser("mark-published", help="record a target as up to date")
    mp.add_argument("--target", required=True)
    mp.add_argument("--date")
    pk = sub.add_parser("package", help="build a plugin or per-skill zips")
    pk.add_argument("--format", choices=("plugin", "zip"), required=True)
    pk.add_argument("--out", required=True)
    pk.add_argument("--pending-for", help="zip only skills pending for this target")
    args = ap.parse_args(argv)
    root = _root(args.root)

    try:
        if args.cmd == "build":
            r = core.build(root, args.date)
            print(f"generation {r.generation}: {len(r.added)} added, {len(r.changed)} changed, "
                  f"{len(r.removed)} removed, {r.unchanged} unchanged")
            for label, names in (("+", r.added), ("~", r.changed), ("-", r.removed)):
                for n in names:
                    print(f"  {label} {n}")
            return 0
        if args.cmd == "check":
            findings = core.check(root)
            for f in findings:
                print(f)
            if not findings:
                reg = core.load_registry(root)
                active = sum(1 for e in reg["skills"] if e["status"] == "active")
                project = sum(1 for e in reg["skills"] if e.get("project"))
                print(f"skills export fresh: {active} active skills ({project} project), "
                      f"generation {reg['generation']}")
            return 1 if findings else 0
        if args.cmd == "list":
            reg = core.load_registry(root)
            rows = [e for e in reg["skills"] if args.all or e["status"] == "active"]
            if args.json:
                print(json.dumps(rows, indent=2))
            else:
                for e in rows:
                    where = "project" if e.get("project") else "package"
                    print(f"{e['name']:<60} r{e['revision']:<3} {e['status']:<8} {where:<8} "
                          f"{e['updated']}  agents/{e['agent']}/")
            return 0
        if args.cmd == "pending":
            p = core.pending(root, args.target)
            if args.json:
                print(json.dumps(p.__dict__, indent=2))
            else:
                print(f"{p.target}: published generation {p.since_generation}, "
                      f"current {p.generation}")
                print(f"  upload ({len(p.upload)}): " + ", ".join(p.upload))
                print(f"  delete ({len(p.delete)}): " + ", ".join(p.delete))
            return 0
        if args.cmd == "mark-published":
            gen = core.mark_published(root, args.target, args.date)
            print(f"{args.target} marked at generation {gen}")
            return 0
        if args.cmd == "package":
            out = Path(args.out).resolve()
            if args.format == "plugin":
                core.package_plugin(root, out, _version())
                print(f"plugin written to {out}")
                print("install it in any repo or user-wide with:")
                print(f"  claude plugin marketplace add {out}")
                print(f"  claude plugin install {core.PLUGIN_NAME}@{core.MARKETPLACE_NAME}")
                return 0
            names = None
            if args.pending_for:
                names = list(core.pending(root, args.pending_for).upload)
            written = core.package_zips(root, out, names)
            print(f"{len(written)} zip(s) written to {out}")
            return 0
    except ValueError as exc:
        print(f"error: {exc}")
        return 2
    return 2
