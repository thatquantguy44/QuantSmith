"""Worked example: the spec 0055 scheduling loop, end to end, against a real job.

    python examples/scheduled_daily_report/run_example.py

Runs the registry -> dry-run -> dispatch -> ledger -> daily-operations-report
loop against a real target (``daily_review_report.run``, not a mock), so the
scheduling runtime's guarantees are demonstrated against something a job
actually does, not a stand-in. Dispatches twice for the same partition to
show the idempotent-skip guarantee (spec 0055 AC-003) live, the same
behavior ``tests/test_workflow_scheduling.py`` checks with a mocked target.

By default this writes into ``examples/scheduled_daily_report/sample_output/``
(ledger, digest, and rendered report) -- the same files committed to the repo
as evidence of what a run produces, so the example is inspectable without
having to execute it. Pass ``--out-dir`` to write elsewhere (e.g. a scratch
directory) instead of touching the committed sample.

Deployment: this driver itself is not what cron calls. In production, cron
calls the job target directly (``daily_review_report.py``) on its own
schedule, and a second, later cron entry renders the daily operations report
from the shared ledger once the day's jobs have had a chance to run -- see
README.md's "Deploying for real" section and ``adapters/schedulers/cron.md``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from quantsmith.pipelines.workflow_scheduling import (  # noqa: E402
    BackfillPolicy,
    ExecutionLedger,
    ManualFollowup,
    ManualTaskQueue,
    RetryPolicy,
    Schedule,
    ScheduleJob,
    Target,
    Trigger,
    dry_run_schedule,
    dispatch_job,
    render_daily_operations_report,
    validate_registry,
)

UTC = dt.timezone.utc


def build_job(digest_path: str, as_of: str) -> ScheduleJob:
    """The registry entry -- mirrors ``templates/data/schedule_registry.md``.

    ``as_of`` is the digest's own view of "today" (spec 0048's point-in-time
    firewall: a job dispatched for a given date should reason about that
    date, not the wall clock it happens to run on) -- pinned to the same
    date the job was scheduled for, so a re-run against unchanged inputs
    reproduces the same digest.
    """
    return ScheduleJob(
        job_id="memory-review-digest",
        owner="quant-research-ops",
        environment="prod",
        target=Target(
            type="python_function",
            ref="examples.scheduled_daily_report.daily_review_report:run",
            kwargs={"root": str(REPO_ROOT / "memory"), "out": digest_path, "as_of": as_of},
        ),
        schedule=Schedule(
            timezone="America/New_York",
            calendar="business",
            trigger=Trigger("cron", "30 6 * * 1-5"),
        ),
        retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=30),
        backfill_policy=BackfillPolicy(allowed=True, max_lookback_days=7),
        runbook_uri="examples/scheduled_daily_report/README.md",
        alert_route="quant-research-ops-alerts",
        manual_followups=(
            ManualFollowup(
                task_id="triage-memory-review-digest",
                owner="quant-research-ops",
                due_offset_days=0,
                reminder_cadence="daily",
                title="Read today's memory review digest and action anything flagged",
            ),
        ),
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=str(Path(__file__).parent / "sample_output"))
    parser.add_argument("--now", default=None,
                        help="ISO 8601 UTC timestamp to run as, for a reproducible sample "
                             "(defaults to the real current time)")
    args = parser.parse_args(argv)

    now_utc = (dt.datetime.fromisoformat(args.now).replace(tzinfo=UTC) if args.now
              else dt.datetime.now(UTC))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    digest_path = str(out_dir / "review_digest.md")
    ledger_path = out_dir / "ledger.jsonl"
    report_path = out_dir / "daily_operations_report.md"

    job = build_job(digest_path, as_of=now_utc.date().isoformat())

    # 1. Registry validation -- what a PR touching the registry checks (AC-001).
    validation = validate_registry([job])
    print(f"registry: {'valid' if validation.is_valid else 'INVALID'} "
         f"({len(validation.findings)} finding(s))")
    if not validation.is_valid:
        for finding in validation.findings:
            print(f"  ! {finding.code}: {finding.message}")
        return 1

    # 2. Dry-run -- provider-neutral next-run evidence, nothing executes (AC-002).
    dry_run = dry_run_schedule(job, now_utc)
    print(f"dry-run: status={dry_run.status} next_run_utc={dry_run.next_run_utc} "
         f"provider_schedule_id={dry_run.provider_schedule_id}")

    # 3. Dispatch -- runs the real target, appends to a real ledger.
    ledger_path.unlink(missing_ok=True)
    ledger = ExecutionLedger(ledger_path)
    partition = now_utc.date().isoformat()
    first = dispatch_job(job, ledger, now_utc, partition=partition)
    print(f"dispatch #1: status={first.status} run_id={first.run_id} "
         f"artifacts={first.artifact_uris}")

    # 4. Dispatch again for the same partition -- proves the idempotent skip
    #    (AC-003) live, against the same real target, not a mock.
    second = dispatch_job(job, ledger, now_utc, partition=partition)
    print(f"dispatch #2: status={second.status} run_id={second.run_id} "
         f"(should be 'skipped' -- same idempotency key)")

    # 5. Manual follow-up queue -- created from the job's registry entry.
    tasks = ManualTaskQueue()
    tasks.add_for_job(job, now_utc.date())

    # 6. Daily operations report -- what a human or a downstream cron entry reads.
    report = render_daily_operations_report(
        ledger.records(), tasks.tasks(), report_date=now_utc.date())
    report_path.write_text(report, encoding="utf-8")
    print(f"wrote {report_path}")
    print(f"wrote {digest_path}")
    print(f"wrote {ledger_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
