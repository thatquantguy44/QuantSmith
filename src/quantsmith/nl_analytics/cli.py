"""Command-line interface for spec ``0080``'s natural-language analytics.
REQ-009, REQ-012, T-018.

::

    quantsmith-nl-analytics ask "<question>" --registry registry.json \\
        --data data.json --today 3 [--as-of N] [--window N] \\
        [--viewer-clearance public] [--envelope-dir DIR --run-id ID] \\
        [--publish --approve --contract PATH --db PATH]

``--registry`` and ``--data`` are local JSON files the caller supplies (see
``examples/nl_analytics/`` for the worked shapes); this module never reads a
network location, a database connection string, or a credential — every I/O
call is a local file the caller named on the command line, matching the
package's own stdlib-only, injected-I/O contract (NFR-003).

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from quantsmith.pipelines.metrics_semantic_layer import Fact, SemanticLayer

from .interpret import InterpretContext
from .respond import AnswerContext, ChatResponse, ResponseError, WriteBackRequest, answer
from .writeback import default_contract, load_contract, prior_insights
from .writeback_sqlite import open_writer


def _load_registry(path: str) -> SemanticLayer:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    layer = SemanticLayer()
    for metric in data.get("metrics", []):
        layer.define(**metric)
    return layer


def _load_data(path: str) -> List[Fact]:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        Fact(period=row["period"], dims=row.get("dims", {}), measures=row.get("measures", {}))
        for row in rows
    ]


def _response_to_dict(response: ChatResponse) -> Dict[str, Any]:
    return {
        "status": response.status,
        "reason": response.reason,
        "headline": response.headline,
        "insights": [
            {"kind": i.kind, "statement": i.statement, "values": i.values} for i in response.insights
        ],
        "chart": None if response.chart is None else {
            "chart_type": response.chart.chart_type,
            "title": response.chart.title,
            "metric": response.chart.metric,
            "dimensions": list(response.chart.dimensions),
            "data": list(response.chart.data),
        },
        "markdown_table": response.markdown_table,
        "plan_echo": response.plan_echo,
        "caveats": list(response.caveats),
        "citations": list(response.citations),
        "run_id": response.run_id,
        "envelope_uri": response.envelope_uri,
        "writeback": None if response.writeback is None else {
            "status": response.writeback.status,
            "written_count": response.writeback.written_count,
            "run_id": response.writeback.run_id,
        },
    }


def _print_human(response: ChatResponse) -> None:
    print(f"status: {response.status}")
    if response.status != "answered":
        print(f"reason: {response.reason}")
        return
    print(f"headline: {response.headline}")
    print(f"plan: {response.plan_echo}")
    for insight in response.insights:
        print(f"  - [{insight.kind}] {insight.statement}")
    if response.caveats:
        print("caveats:")
        for caveat in response.caveats:
            print(f"  - {caveat}")
    print("citations:")
    for citation in response.citations:
        print(f"  - {citation}")
    if response.markdown_table:
        print()
        print(response.markdown_table)
    if response.envelope_uri:
        print(f"\nenvelope: {response.envelope_uri}")
    if response.writeback is not None:
        wb = response.writeback
        print(f"\nwrite-back: {wb.status} ({wb.written_count} record(s), run_id={wb.run_id})")


def _cmd_ask(args: argparse.Namespace) -> int:
    layer = _load_registry(args.registry)
    rows = _load_data(args.data)
    as_of = args.as_of if args.as_of is not None else args.today

    contract = None
    writer = None
    if args.db:
        contract = load_contract(args.contract) if args.contract else default_contract(
            args.contract_name, auto_approve=args.approve
        )
        writer = open_writer(args.db, contract)

    writeback = None
    if args.publish:
        if not args.run_id:
            print("error: --publish requires --run-id", file=sys.stderr)
            return 2
        writeback = WriteBackRequest(
            contract=contract, writer=writer, author_handle=args.author,
            dry_run=args.dry_run, approved=args.approve,
        )

    # Pointing at a store always lets a "since yesterday" / "vs last week's
    # answer" question read what is already persisted there — reading is
    # never a side effect, unlike --publish, so no extra flag gates it.
    prior_insight_lookup = None
    if writer is not None:
        def prior_insight_lookup(key: str, lookup_as_of: int, _writer=writer):
            return prior_insights(_writer.read, key, lookup_as_of)

    context = AnswerContext(
        layer=layer, reader=lambda plan: rows, as_of=as_of,
        interpret_context=InterpretContext(today_period=args.today, default_window_periods=args.window),
        viewer_clearance=args.viewer_clearance,
        envelope_dir=args.envelope_dir, run_id=args.run_id,
        envelope_actor_clearance=args.viewer_clearance,
        prior_insight_lookup=prior_insight_lookup,
        writeback=writeback,
    )

    try:
        response = answer(args.question, context)
    except ResponseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(_response_to_dict(response), indent=2, sort_keys=True))
    else:
        _print_human(response)
    return 0 if response.status == "answered" else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="quantsmith-nl-analytics",
        description="Ask a natural-language data question against a governed metric registry.",
    )
    sub = parser.add_subparsers(dest="command")

    p_ask = sub.add_parser("ask", help="answer one natural-language question")
    p_ask.add_argument("question", help="the question, in plain language")
    p_ask.add_argument("--registry", required=True, help="path to a metric registry JSON file")
    p_ask.add_argument("--data", required=True, help="path to a fact-rows JSON file")
    p_ask.add_argument("--today", type=int, required=True, help="today's period key")
    p_ask.add_argument("--as-of", type=int, default=None, help="as-of period bound (default: --today)")
    p_ask.add_argument("--window", type=int, default=7, help="default window size in periods")
    p_ask.add_argument("--viewer-clearance", default="public")
    p_ask.add_argument("--json", action="store_true", help="print the response as JSON")
    p_ask.add_argument("--envelope-dir", default=None, help="emit a 0070 audit envelope here")
    p_ask.add_argument("--run-id", default=None, help="caller-assigned run id (required for --envelope-dir/--publish)")
    p_ask.add_argument("--publish", action="store_true", help="build and publish a write-back record")
    p_ask.add_argument("--approve", action="store_true", help="approve the commit (see --dry-run)")
    p_ask.add_argument(
        "--dry-run", dest="dry_run", action="store_true", default=True,
        help="preview the write-back without committing (default)",
    )
    p_ask.add_argument("--commit", dest="dry_run", action="store_false", help="actually commit the write-back")
    p_ask.add_argument("--contract", default=None, help="path to a filled-in writeback_contract.md")
    p_ask.add_argument("--contract-name", default="cli_default", help="target name when --contract is omitted")
    p_ask.add_argument("--db", default=None, help="SQLite file for the write-back target")
    p_ask.add_argument("--author", default="cli", help="author_handle recorded on write-back records")
    p_ask.set_defaults(func=_cmd_ask)

    args = parser.parse_args(argv)
    if args.command == "ask" and args.publish and not args.db:
        parser.error("--publish requires --db")
    handler = getattr(args, "func", None)
    if handler is None:
        parser.print_help()
        return 1
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
