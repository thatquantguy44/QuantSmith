"""CLI for validating and replaying spec-0071 text-intelligence evidence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .foundation import (
    discover_manifests,
    replay_text_intelligence_manifest_file,
    validate_discovered_manifests,
    validate_text_intelligence_manifest_file,
)


def _print_findings(report) -> None:
    for finding in report.findings:
        print(
            f"[{finding.severity.upper()}] {finding.source}:{finding.field}: "
            f"{finding.message}"
        )


def _cmd_validate(args: argparse.Namespace) -> int:
    if args.discover:
        report = validate_discovered_manifests(args.discover)
        _print_findings(report)
        count = report.counts.get("manifests", 0)
        if report.ok:
            print(f"ok - validated {count} text-intelligence manifest(s)")
            return 0
        print(f"failed - {len(report.errors)} error(s) across {count} manifest(s)")
        return 1

    report = validate_text_intelligence_manifest_file(args.manifest)
    _print_findings(report)
    if report.ok:
        print(f"ok - {args.manifest}")
        return 0
    print(f"failed - {len(report.errors)} error(s): {args.manifest}")
    return 1


def _cmd_replay(args: argparse.Namespace) -> int:
    replay = replay_text_intelligence_manifest_file(
        args.manifest,
        fixture_mode=args.fixture_mode,
        allow_non_reproducible=args.allow_non_reproducible,
    )
    if args.json:
        print(replay.to_json())
    else:
        print(f"manifest_id: {replay.manifest_id}")
        print(f"run_id: {replay.orchestration.run_id}")
        print(f"status: {replay.status}")
        print(f"mode: {replay.orchestration.replay_mode}")
        print(f"gate_status: {replay.orchestration.gate_status}")
        if replay.orchestration.fixture_substitutions:
            print("fixtures:")
            for fixture in replay.orchestration.fixture_substitutions:
                print(f"  - {fixture['event_id']} -> {fixture['fixture_path']}")
        if replay.orchestration.non_reproducible_dependencies:
            print("non_reproducible_dependencies:")
            for dependency in replay.orchestration.non_reproducible_dependencies:
                print(
                    f"  - {dependency['event_id']} ({dependency['provider']}): "
                    f"{dependency['reason']}"
                )
        if replay.findings:
            print("findings:")
            for finding in replay.findings:
                print(f"  - {finding['source']}:{finding['field']}: {finding['message']}")
    return 0 if replay.status == "replayed" else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="quantsmith-text-intelligence",
        description="Validate and replay spec-0071 evidence through spec 0070.",
    )
    sub = parser.add_subparsers(dest="command")

    validate = sub.add_parser("validate", help="validate one manifest or a directory")
    validate.add_argument("--manifest", default=None)
    validate.add_argument("--discover", default=None)
    validate.set_defaults(func=_cmd_validate)

    replay = sub.add_parser("replay", help="delegate evidence replay to the 0070 engine")
    replay.add_argument("--manifest", required=True)
    replay.add_argument("--fixture-mode", action="store_true")
    replay.add_argument("--allow-non-reproducible", action="store_true")
    replay.add_argument("--json", action="store_true")
    replay.set_defaults(func=_cmd_replay)

    args = parser.parse_args(argv)
    if args.command == "validate" and not args.manifest and not args.discover:
        parser.error("validate requires --manifest or --discover")
    if args.command == "validate" and args.manifest and args.discover:
        parser.error("validate accepts only one of --manifest or --discover")
    handler = getattr(args, "func", None)
    if handler is None:
        parser.print_help()
        return 1
    if (
        args.command == "validate"
        and args.discover
        and not discover_manifests(Path(args.discover))
    ):
        print(
            f"no text-intelligence manifests found under {args.discover}",
            file=sys.stderr,
        )
        return 1
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
