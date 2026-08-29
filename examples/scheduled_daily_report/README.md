# Worked Example: A Cron-Scheduled Daily Report

A concrete, low-risk demonstration of `specs/0055-workflow-scheduling-operations/`
(the follow-up its own `tasks.md` named). It runs the runtime's full loop --
**registry validation → dry-run → dispatch → execution ledger → daily
operations report** -- against a real target, not a mock: a job that scans
`memory/` for anything the knowledge console's review queue would flag and
writes a short digest.

## What's here

| File | Role |
| --- | --- |
| `daily_review_report.py` | **The job.** Real and useful on its own: reuses `0048`'s `validate` and `0057`'s `build_review_queue` to write a Markdown digest of what needs review. Runnable standalone: `python examples/scheduled_daily_report/daily_review_report.py --root memory --out digest.md`. |
| `run_example.py` | **The driver.** Builds the job's registry entry, validates it, dry-runs it, dispatches it twice against a real `ExecutionLedger` (proving the idempotent-skip guarantee, AC-003, live), and renders the daily operations report. |
| `sample_output/` | Committed evidence of one run (`review_digest.md`, `ledger.jsonl`, `daily_operations_report.md`), generated with `--now 2027-06-01T10:30:00+00:00` for a reproducible digest. Wall-clock fields (`started_at_utc`/`ended_at_utc`) reflect whenever the sample was actually generated -- re-run it yourself for fresh ones. |

## Run it yourself

```sh
python examples/scheduled_daily_report/run_example.py
# or, for the exact committed sample_output/ (deterministic as_of):
python examples/scheduled_daily_report/run_example.py --now 2027-06-01T10:30:00+00:00
```

Pass `--out-dir` to write elsewhere instead of touching the committed sample.

## The registry entry

`run_example.py`'s `build_job()` is the code form of what
`templates/data/schedule_registry.md` describes in prose:

- **job_id:** `memory-review-digest` · **owner:** `quant-research-ops` · **environment:** `prod`
- **target:** `python_function` → `examples.scheduled_daily_report.daily_review_report:run`
- **schedule:** `cron` `30 6 * * 1-5`, `America/New_York`, `business` calendar
- **retry:** 2 attempts, 30s backoff · **backfill:** allowed, 7-day lookback
- **runbook_uri:** this file · **alert_route:** `quant-research-ops-alerts`
- **manual follow-up:** `triage-memory-review-digest` -- someone reads the digest and actions anything flagged

## Deploying for real

`run_example.py` itself is **not** what cron would call -- it is the local
proof that the loop works, run by a person or a test. A real deployment
splits the job and the reporting into two separate cron entries, per
`adapters/schedulers/cron.md`'s delivery rules (source-controlled schedule,
explicit timezone, logs to a known directory, paired alert route):

```cron
# 06:30 America/New_York, business days -- the job itself
30 6 * * 1-5 cd /path/to/repo && /usr/bin/env python3 \
  examples/scheduled_daily_report/daily_review_report.py \
  --root memory --out /var/quantsmith/reports/review_digest.md \
  >> /var/log/quantsmith/memory-review-digest.log 2>&1

# 07:30 America/New_York -- after the day's jobs have had a chance to run,
# render the operations report from the shared ledger
30 7 * * 1-5 cd /path/to/repo && /usr/bin/env python3 \
  -m quantsmith.pipelines.workflow_scheduling_cli render-report \
  --ledger /var/quantsmith/ledger.jsonl \
  >> /var/log/quantsmith/daily-operations-report.log 2>&1
```

`workflow_scheduling_cli` now exists (spec `0060`) -- `render-report` wraps
`ExecutionLedger`/`render_daily_operations_report` exactly as `run_example.py`
calls them, so the second cron entry above is real, not aspirational. An
`alerts` subcommand previews (never delivers) the routed alert handoffs
`alert_handoffs`/`alerting.route` would produce for the same ledger; wiring
real delivery is `workflow_scheduling.deliver_routed_alerts` composed with
your own `adapters/alert_delivery/` transport, in your own scheduler
integration -- this SDK holds no transport/credentials (P9). See
`specs/0060-scheduler-monitoring/`.

## What this proves, and what it doesn't

Proves: the registry/dry-run/dispatch/ledger/report loop composes correctly
against a real target, dispatch is idempotent per (`job_id`, partition), and
the resulting report accurately rolls up what happened. Does **not** prove:
an actual cron daemon invoking this on a schedule (`adapters/schedulers/cron.md`
remains a contract, not executable deploy code -- see `docs/handoff.md`),
alert delivery (spec 0055's `alert_handoffs` returns payloads only; wiring
them to a real `adapters/alert_delivery/` provider is a separate step), or
promoting the digest's findings into `memory/` (that's spec 0049's
`propose`/`promote`, a human decision this job does not make for you).
