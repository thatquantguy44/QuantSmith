# Mage Scheduler Adapter

## Use For

- Python/SQL/R block-based pipelines with a notebook-style development loop.
- Teams that want pipelines, triggers, and backfills managed in one UI.
- Many independent ingestion pipelines with per-pipeline concurrency control.

## Delivery Rules

- Map each workflow to a Mage pipeline and each schedule to a trigger; keep trigger
  configuration separate from block logic.
- Preserve owner, runbook, data contract, alert route, and environment metadata
  (pipeline tags and description).
- Render concurrency from the fleet declaration with `pipeline_fleet.to_mage`
  (spec `0101`) and resolve every warning — see
  `agents/tooling/dag_orchestration/profiles/mage.md`.
- Set `on_pipeline_run_limit_reached: wait` for loads that must complete.
- Stagger trigger start times; make retries and backfills idempotent.
- Keep credentials in Mage secrets or the platform secret store, never in
  `io_config.yaml` committed to Git.

## Risks

- Mage has no shared pools, cross-pipeline locks, or run priority; limits on a
  shared database must be enforced by dispatch or executor partitioning.
- Block retries hold the run's slot while retrying.
- Backfills and dynamic blocks can multiply runs and block runs past what the
  warehouse can take.
