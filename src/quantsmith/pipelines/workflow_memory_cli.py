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

Every command is a thin wrapper over ``workflow_memory``'s library functions
(T-007, REQ-013) — a human-runnable surface, not new logic. ``promote`` and
``discard`` are the only commands that ever touch the live store or the
inbox; ``propose`` (which also stages) never does (spec NFR-005).
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

    args = parser.parse_args(argv)

    dispatch = {
        "propose": _cmd_propose,
        "list-inbox": _cmd_list_inbox,
        "promote": _cmd_promote,
        "discard": _cmd_discard,
    }
    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
