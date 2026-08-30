"""CLI for the workflow-memory write path (spec 0049).

    python -m quantsmith.pipelines.workflow_memory_cli propose \\
        --workflow quant_researcher --source-run run-2026-08-21-x \\
        --scope field:close_adj --type quirk --statement "..." \\
        --confidence low --pit-scope "<= run date" \\
        --target-catalog _shared/datasets/example_prices/provenance.yaml \\
        --evidence-run run-2026-08-21-x

    python -m quantsmith.pipelines.workflow_memory_cli list-inbox [--root memory]

    python -m quantsmith.pipelines.workflow_memory_cli promote \\
        --candidate-id quant_researcher/run-2026-08-21-x/001 [--root memory] [--author ...]

    python -m quantsmith.pipelines.workflow_memory_cli discard \\
        --candidate-id quant_researcher/run-2026-08-21-x/001 [--root memory]

    python -m quantsmith.pipelines.workflow_memory_cli whoami [--root .]

Every command is a thin wrapper over ``workflow_memory``'s library functions
(T-007, REQ-013) — a human-runnable surface, not new logic. ``promote`` and
``discard`` are the only commands that ever touch the live store or the
inbox; ``propose`` (which also stages) never does (spec NFR-005).

``whoami`` (spec 0058 REQ-013) prints the pseudonymous handle this process
resolves to — the same handle ``promote`` would attribute a record to, and
the same handle a roster entry must match for enforcement to recognise this
person. It exists so someone can check what to put in ``access/roster.yml``
before editing it, rather than guessing.
"""

from __future__ import annotations

import argparse
import sys

from . import workflow_memory as wm


def _find_candidate(root: str, candidate_id: str):
    for candidate, source_file in wm.load_inbox(root=root):
        if candidate.candidate_id == candidate_id:
            return candidate, source_file
    return None, None


def _cmd_propose(args: argparse.Namespace) -> int:
    spec = wm.CandidateSpec(
        scope=args.scope, type=args.type, statement=args.statement,
        confidence=args.confidence, pit_scope=args.pit_scope,
        evidence=({"source_run": args.evidence_run},),
        target_catalog=args.target_catalog, access_level=args.access_level,
    )
    candidates = wm.propose_records([spec], workflow=args.workflow,
                                    source_run=args.source_run)
    path = wm.stage_candidates(candidates, root=args.root)
    for c in candidates:
        print(f"staged {c.candidate_id} -> {path}")
    return 0


def _cmd_list_inbox(args: argparse.Namespace) -> int:
    inbox = wm.load_inbox(root=args.root)
    if not inbox:
        print("(inbox is empty)")
        return 0
    for candidate, source_file in inbox:
        s = candidate.spec
        print(f"{candidate.candidate_id}  [{s.type}] {s.scope}  {s.confidence}")
        print(f"    {s.statement}")
        print(f"    -> {s.target_catalog}  (from {source_file})")
    return 0


def _cmd_promote(args: argparse.Namespace) -> int:
    candidate, source_file = _find_candidate(args.root, args.candidate_id)
    if candidate is None:
        print(f"no such candidate in the inbox: {args.candidate_id}", file=sys.stderr)
        return 1
    try:
        result = wm.promote(candidate, source_file=source_file, root=args.root,
                            author=args.author)
    except wm.MemoryWriteError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    print(f"promoted {args.candidate_id} -> {result.record.id} "
         f"(author={result.record.author}, target={candidate.spec.target_catalog})")
    if result.contradiction_warning:
        print(f"warning: {result.contradiction_warning}", file=sys.stderr)
    return 0


def _cmd_discard(args: argparse.Namespace) -> int:
    candidate, source_file = _find_candidate(args.root, args.candidate_id)
    if candidate is None:
        print(f"no such candidate in the inbox: {args.candidate_id}", file=sys.stderr)
        return 1
    wm.discard(candidate, source_file=source_file, root=args.root)
    print(f"discarded {args.candidate_id}")
    return 0


def _cmd_whoami(args: argparse.Namespace) -> int:
    handle = wm.resolve_author(root=args.root)
    print(handle)
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    import pathlib
    root = pathlib.Path(args.root)
    all_records = []
    for path in sorted(root.rglob("*.yaml")):
        if "inbox" in path.parts:
            continue
        try:
            all_records.extend(wm.load_records(path.read_text(), str(path)))
        except wm.MemoryParseError as exc:
            print(f"parse error: {exc}", file=sys.stderr)
            return 1
    findings = wm.validate(all_records)
    errors = 0
    for f in findings:
        loc = f"{f.file}:{f.line}" if f.file else ""
        prefix = f"[{f.severity.upper()}]"
        print(f"{prefix} {f.record_id}: {f.message}" + (f"  ({loc})" if loc else ""))
        if f.severity == "error":
            errors += 1
    if not findings:
        print(f"ok — {len(all_records)} record(s), no findings")
    return 1 if errors else 0


def _cmd_decay(args: argparse.Namespace) -> int:
    import pathlib
    root = pathlib.Path(args.root)
    manifest = wm.load_manifest(args.root)
    freshness_days = int(manifest.get("freshness_days", args.freshness_days))
    all_records = []
    for path in sorted(root.rglob("*.yaml")):
        if "inbox" in path.parts:
            continue
        try:
            all_records.extend(wm.load_records(path.read_text(), str(path)))
        except wm.MemoryParseError as exc:
            print(f"parse error: {exc}", file=sys.stderr)
            return 1
    findings = wm.check_decay(all_records, freshness_days)
    if not findings:
        print(f"ok — {len(all_records)} active record(s) all confirmed within "
              f"{freshness_days} days")
        return 0
    for f in findings:
        print(f"[STALE] {f.record_id}: {f.message}")
    return 0  # decay is advisory; never blocks


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="quantsmith.pipelines.workflow_memory_cli",
        description="Propose, stage, promote, and discard workflow-memory "
                    "candidates (spec 0049).")
    sub = parser.add_subparsers(dest="command")

    p_propose = sub.add_parser("propose", help="build and stage one candidate")
    p_propose.add_argument("--root", default="memory")
    p_propose.add_argument("--workflow", required=True)
    p_propose.add_argument("--source-run", required=True)
    p_propose.add_argument("--scope", required=True)
    p_propose.add_argument("--type", required=True, choices=wm.RECORD_TYPES)
    p_propose.add_argument("--statement", required=True)
    p_propose.add_argument("--confidence", default="low", choices=wm.CONFIDENCE_LEVELS)
    p_propose.add_argument("--pit-scope", required=True)
    p_propose.add_argument("--target-catalog", required=True)
    p_propose.add_argument("--access-level", default="internal")
    p_propose.add_argument("--evidence-run", required=True,
                           help="source_run recorded as this candidate's evidence")

    p_list = sub.add_parser("list-inbox", help="show every staged candidate")
    p_list.add_argument("--root", default="memory")

    p_promote = sub.add_parser("promote", help="accept one candidate into the live store")
    p_promote.add_argument("--root", default="memory")
    p_promote.add_argument("--candidate-id", required=True)
    p_promote.add_argument("--author", default=None,
                           help="override the resolved author handle")

    p_discard = sub.add_parser("discard", help="remove one candidate without promoting it")
    p_discard.add_argument("--root", default="memory")
    p_discard.add_argument("--candidate-id", required=True)

    p_whoami = sub.add_parser("whoami", help="print the resolved author/viewer handle")
    p_whoami.add_argument("--root", default=".",
                          help="repo root to read identity.yml from (default: cwd)")

    p_validate = sub.add_parser("validate", help="validate all records under a memory root")
    p_validate.add_argument("--root", default="memory",
                            help="memory root directory (default: memory)")

    p_decay = sub.add_parser("decay", help="report stale records under a memory root")
    p_decay.add_argument("--root", default="memory",
                         help="memory root directory (default: memory)")
    p_decay.add_argument("--freshness-days", type=int, default=90,
                         help="age threshold in days (default: 90; overridden by manifest)")

    args = parser.parse_args(argv)

    dispatch = {
        "propose": _cmd_propose,
        "list-inbox": _cmd_list_inbox,
        "promote": _cmd_promote,
        "discard": _cmd_discard,
        "whoami": _cmd_whoami,
        "validate": _cmd_validate,
        "decay": _cmd_decay,
    }
    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
