"""The scheduled job itself: a workflow-memory review digest.

Real, small, and useful on its own -- scans ``memory/`` for anything the
knowledge console's review queue would flag (freshness decay, validation
findings, unsupported confidence, thin corroboration) and writes a short
Markdown digest. It reuses ``0048``'s ``validate`` and ``0057``'s
``build_review_queue`` rather than reimplementing either.

This is the *target* the scheduling worked example (spec 0055) dispatches --
see ``examples/scheduled_daily_report/README.md`` for the registry entry and
cron deployment that schedule it, and ``run_example.py`` for the driver that
proves the registry -> dry-run -> dispatch -> ledger -> report loop against
it end to end.
"""

from __future__ import annotations

import argparse
import datetime
from pathlib import Path
from typing import Optional

from quantsmith.knowledge_console import model as m
from quantsmith.pipelines import workflow_memory as wm


def build_digest(root: str, as_of: datetime.date) -> str:
    """Render the digest text. Pure -- takes a root and a date, returns text."""
    store = m.load_store(root)
    plain = [lr.record for lr in store.records]
    findings = wm.validate(plain)
    queue = m.build_review_queue(store, as_of, findings)

    lines = [f"# Workflow Memory Review Digest -- {as_of.isoformat()}", ""]
    if not queue:
        lines.append("Nothing needs review today.")
    else:
        lines.append(f"{len(queue)} record(s) need review:")
        lines.append("")
        for item in queue:
            reason = item["reasons"][0]["detail"]
            lines.append(f"- [{item['severity']}] {item['record_id']} "
                         f"({item['scope']}, {item['workflow']}): {reason}")
    return "\n".join(lines) + "\n"


def run(*, root: str = "memory", out: str = "review_digest.md",
       as_of: Optional[str] = None) -> str:
    """Build the digest and write it to ``out``. Returns the artifact path.

    This is the entry point the scheduling runtime's ``python_function``
    target type calls (``_invoke_target`` imports this module and calls
    ``run(**kwargs)``) -- its return value becomes the dispatched run's
    ``artifact_uris`` (spec 0055 REQ-004).
    """
    resolved_as_of = (datetime.date.fromisoformat(as_of) if as_of
                      else datetime.datetime.now(datetime.timezone.utc).date())
    digest = build_digest(root, resolved_as_of)

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(digest, encoding="utf-8")
    return f"file://{out_path}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="memory")
    parser.add_argument("--out", default="review_digest.md")
    parser.add_argument("--as-of", default=None, help="ISO date; defaults to today (UTC)")
    args = parser.parse_args(argv)
    artifact = run(root=args.root, out=args.out, as_of=args.as_of)
    print(artifact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
