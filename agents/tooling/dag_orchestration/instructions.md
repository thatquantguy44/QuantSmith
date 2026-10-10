# DAG Orchestration Instructions

## Operating Rules

- Start from the fleet declaration (`0101`), never from hand-typed limits. Render
  with `to_dagster` / `to_mage` / `to_airflow` / `to_prefect` (`0112`); read and resolve every entry in `warnings`.
- Bound concurrency at two levels: runs across the deployment, and tasks/blocks
  inside a run. A run limit of 20 with 16-way fan-out per run is 320 tasks.
- Map each pool to a native mechanism (Dagster tag limits or op/asset pools). Where
  none exists (Mage pools, cross-pipeline keys), dispatch through `run_fleet`
  admission or split executors so the limit still holds — and say which.
- Throttle backfills apart from scheduled runs (Dagster `dagster/backfill` tag
  limit, backfill policies; Mage backfill concurrency) so history never starves
  today's load.
- Keep retries bounded; prefer retries that re-queue over retries that hold slots.
- Stagger schedules (`stagger_offsets`); make triggers idempotent (run keys).
- Keep orchestration config out of business logic; secrets in the platform's
  secret store (P9). Verify every config key against the installed version.

## Checks

- Do run-level and task-level limits multiply to something the platform can take?
- Is every pool, key, priority, and retry either native or explicitly mitigated?
- Are backfills and fan-out throttled independently of scheduled runs?
- Do the rendered limits match the fleet capacity plan?
- Was the config dry-run in a non-prod deployment before promotion?

## Consumes / Hands Off

- **Consumes:** a `Fleet` from `data_engineering/pipeline_concurrency`;
  `to_dagster` / `to_mage` output; scheduler adapter contracts in
  `adapters/schedulers/` (`dagster_prefect.md`, `mage.md`).
- **Hands off to:** `data_engineering/pipeline_deployment` (dry-run, canary,
  promote), `data_engineering/pipeline_observability` (observed durations and
  queue depth back into the plan).
- Does **not** redesign the fleet limits; it renders and enforces them.

## Output Contract

Use clear Markdown. Present the rendered config, then `Native Enforcement` (what the
orchestrator enforces), `Mitigations` (one per warning), `Backfill And Fan-Out`, and
`Version Assumptions`.

## Spec-Driven Role

Orchestrator choices become `REQ-*`; rendered limits matching the fleet plan and
every warning resolved become testable `AC-*`; silently dropped limits, unthrottled
backfills, and version-drifted config keys become `RISK-*`. The runtime is
`pipeline_fleet.to_dagster` / `to_mage`; the spec is
`specs/0101-concurrent-pipeline-fleet/`; profiles are `profiles/dagster.md` and
`profiles/mage.md`. Hands off to `pipeline_deployment` and `pipeline_observability`.
