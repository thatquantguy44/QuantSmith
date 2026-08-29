"""CLI for spec 0055's operational surface (spec 0060): render a daily
operations report, or preview routed alert handoffs, from a run ledger
without a bespoke script per team.

    python -m quantsmith.pipelines.workflow_scheduling_cli render-report \\
        --ledger path/to/ledger.jsonl [--report-date 2026-08-24]

    python -m quantsmith.pipelines.workflow_scheduling_cli alerts \\
        --ledger path/to/ledger.jsonl [--as-of 2026-08-24]

Every command is a thin wrapper over ``workflow_scheduling``'s (and
``alerting``'s) library functions -- a human-runnable surface, not new
logic, the same discipline ``workflow_memory_cli.py`` (spec 0049) already
established.

Manual tasks have no persisted file format in this module -- ``ManualTaskQueue``
is in-memory by design (spec 0055's own scope). Both commands operate on run
records only; a task-aware CLI needs a manual-task store built first, which
is not this spec's job.

``alerts`` only renders what ``alert_handoffs``/``alerting.route`` would hand
to delivery -- it never delivers anything itself. Real delivery needs live
transport/credentials this SDK never holds (P9); compose
``workflow_scheduling.deliver_routed_alerts`` with your own
``adapters/alert_delivery/`` transport in your own scheduler integration
instead.
"""

from __future__ import annotations

import argparse
import datetime as dt

from . import alerting
from . import workflow_scheduling as ws


def _cmd_render_report(args: argparse.Namespace) -> int:
    ledger = ws.ExecutionLedger(path=args.ledger)
    report_date = dt.date.fromisoformat(args.report_date) if args.report_date else dt.date.today()
    report = ws.render_daily_operations_report(ledger.records(), (), report_date=report_date)
    print(report)
    return 0


def _cmd_alerts(args: argparse.Namespace) -> int:
    ledger = ws.ExecutionLedger(path=args.ledger)
    as_of = dt.date.fromisoformat(args.as_of) if args.as_of else dt.date.today()
    alerts = ws.alert_handoffs(ledger.records(), (), as_of=as_of)
    if not alerts:
        print("(no alerts)")
        return 0
    routed = alerting.route(list(alerts), alerting.Routing())
    for r in routed:
        escalated = "(escalated) " if r.escalated else ""
        print(
            f"[{r.alert.severity}] {r.alert.rule_id} -> owner={r.owner} "
            f"channel={r.channel} {escalated}x{r.count}: {r.alert.message}"
        )
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="quantsmith.pipelines.workflow_scheduling_cli",
        description="Render a daily operations report, or preview routed "
                    "alert handoffs, from a run ledger (spec 0055/0060).")
    sub = parser.add_subparsers(dest="command")

    p_report = sub.add_parser("render-report", help="render the daily operations report")
    p_report.add_argument("--ledger", required=True, help="path to the JSONL run ledger")
    p_report.add_argument("--report-date", default=None, help="YYYY-MM-DD (default: today)")

    p_alerts = sub.add_parser("alerts", help="preview routed alert handoffs (never delivers)")
    p_alerts.add_argument("--ledger", required=True, help="path to the JSONL run ledger")
    p_alerts.add_argument("--as-of", default=None, help="YYYY-MM-DD (default: today)")

    args = parser.parse_args(argv)

    dispatch = {
        "render-report": _cmd_render_report,
        "alerts": _cmd_alerts,
    }
    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
