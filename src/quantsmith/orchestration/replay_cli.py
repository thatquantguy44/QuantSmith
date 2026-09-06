"""CLI for validating and replaying spec 0070 orchestration envelopes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .foundation import (
    discover_envelopes,
    replay_envelope_file,
    validate_discovered_envelopes,
    validate_run_envelope_file,
)


def _print_findings(report) -> None:
    for finding in report.findings:
        print(
            f"[{finding.severity.upper()}] {finding.source}:{finding.field}: "
            f"{finding.message}"
        )


def _cmd_validate(args: argparse.Namespace) -> int:
    if args.discover:
        report = validate_discovered_envelopes(args.discover)
        _print_findings(report)
        count = report.counts.get("envelopes", 0)
        if report.ok:
            print(f"ok - validated {count} orchestration envelope(s)")
            return 0
        print(f"failed - {len(report.errors)} error(s) across {count} envelope(s)")
        return 1

    report = validate_run_envelope_file(args.envelope)
    _print_findings(report)
    if report.ok:
        print(f"ok - {args.envelope}")
        return 0
    print(f"failed - {len(report.errors)} error(s): {args.envelope}")
    return 1


def _cmd_replay(args: argparse.Namespace) -> int:
    replay = replay_envelope_file(
        args.envelope,
        fixture_mode=args.fixture_mode,
        allow_non_reproducible=args.allow_non_reproducible,
    )
    if args.json:
        print(replay.to_json())
    else:
        print(f"run_id: {replay.run_id}")
        print(f"status: {replay.status}")
        print(f"mode: {replay.replay_mode}")
        print(f"gate_status: {replay.gate_status}")
        if replay.fixture_substitutions:
            print("fixtures:")
            for fixture in replay.fixture_substitutions:
                print(f"  - {fixture['event_id']} -> {fixture['fixture_path']}")
        if replay.non_reproducible_dependencies:
            print("non_reproducible_dependencies:")
            for dep in replay.non_reproducible_dependencies:
                print(f"  - {dep['event_id']} ({dep['provider']}): {dep['reason']}")
        if replay.findings:
            print("findings:")
            print(json.dumps(list(replay.findings), indent=2, sort_keys=True))
    return 0 if replay.status == "replayed" else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="quantsmith-orchestration",
        description="Validate and replay spec 0070 orchestration run envelopes.",
    )
    sub = parser.add_subparsers(dest="command")

    p_validate = sub.add_parser("validate", help="validate one envelope or a directory")
    p_validate.add_argument("--envelope", default=None, help="path to run_envelope.json")
    p_validate.add_argument(
        "--discover",
        default=None,
        help="directory or file to discover run_envelope*.json below",
    )
    p_validate.set_defaults(func=_cmd_validate)

    p_replay = sub.add_parser("replay", help="verify hashes and replay fixtureable calls")
    p_replay.add_argument("--envelope", required=True)
    p_replay.add_argument("--fixture-mode", action="store_true")
    p_replay.add_argument("--allow-non-reproducible", action="store_true")
    p_replay.add_argument("--json", action="store_true")
    p_replay.set_defaults(func=_cmd_replay)

    args = parser.parse_args(argv)
    if args.command == "validate" and not args.envelope and not args.discover:
        parser.error("validate requires --envelope or --discover")
    if args.command == "validate" and args.envelope and args.discover:
        parser.error("validate accepts only one of --envelope or --discover")
    handler = getattr(args, "func", None)
    if handler is None:
        parser.print_help()
        return 1
    if args.command == "validate" and args.discover:
        discovered = discover_envelopes(Path(args.discover))
        if not discovered:
            print(f"no orchestration envelopes found under {args.discover}", file=sys.stderr)
            return 1
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
