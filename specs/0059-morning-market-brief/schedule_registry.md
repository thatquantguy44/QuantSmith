# Schedule Registry: morning-market-brief

> Provider-neutral catalog for scheduled scripts, Python jobs, QuantSmith pipelines,
> and agentic workflows. Backed by spec `0055-workflow-scheduling-operations`.
>
> A worked example for spec `0059`'s daily job — registers no new scheduling
> mechanics; `dispatch_job`'s `agentic_workflow` target type and `handlers`
> extension point (spec `0055`) already support this shape.

## Job

- **job_id:** morning-market-brief
- **owner:** quant-research
- **environment:** dev
- **runbook_uri:** docs/gate_runbook.md
- **alert_route:** morning-brief-email

## Target

- **type:** agentic_workflow
- **ref:** agents/economists/morning_brief_writer
- **args:** []
- **kwargs:** {"config_path": "morning_brief_config.yml"}

The registered handler for this target (supplied by the operator, not
QuantSmith — see `dispatch_job`'s `handlers` parameter) is expected to, in
order: read `morning_brief_config.yml`; call
`market_brief.fetch_commentary`/`top_headlines`/`sentiment_rollup`; invoke
the `morning_brief_writer` agent for the Views & Analysis text;
call `market_brief.render_morning_brief`; deliver the result via
`adapters/alert_delivery/email.deliver_email` to the `alert_route` above;
then call `market_brief.candidates_from_brief` and
`stage_research_candidates` against `research_staging.root` from the
config. QuantSmith ships each of these as a tested function; composing them
into one handler is the adopter's integration code, the same boundary
`0055`'s own docstring draws for "future agentic runners."

## Schedule

- **timezone:** America/New_York
- **calendar:** business
- **trigger type:** cron
- **trigger expression:** `0 6 * * 1-5`

## Reliability

- **retry max_attempts:** 2
- **retry backoff_seconds:** 300
- **backfill allowed:** false
- **backfill max_lookback_days:** 0

  A missed morning brief is not worth re-running hours late — "today's
  news, tomorrow" is a stale, mildly misleading document, not a useful
  backfill. Skip and let tomorrow's run be the next real one.

- **idempotency_key_template:** `{job_id}:{partition}`

## Manual Follow-Ups

| task_id | owner | due_offset_days | reminder_cadence | title |
| --- | --- | ---: | --- | --- |
| review-staged-brief | quant-research | 1 | daily | Review yesterday's `research_local/inbox/morning_brief/*.yaml` candidate and decide what, if anything, becomes durable |

## Reporting

Folded into `0055`'s existing daily operations report
(`render_daily_operations_report`) — no separate report mechanism for this
job. A failed or skipped run shows up there like any other scheduled job.
