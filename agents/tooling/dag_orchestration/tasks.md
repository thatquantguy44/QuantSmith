# DAG Orchestration Tasks

## Render A Fleet To Dagster

Input: an approved `Fleet` declaration (`0101`).

Output: `to_dagster` config (`concurrency.runs`, tag limits, run tags) with every
warning resolved, per `profiles/dagster.md`.

## Render A Fleet To Mage

Input: an approved `Fleet` declaration (`0101`).

Output: `to_mage` config (`queue_config`, per-pipeline `concurrency_config`,
retries) with a mitigation for every warning, per `profiles/mage.md`.

## Review An Orchestrator Deployment

Input: an existing Dagster or Mage deployment and its symptoms.

Output: a review of run/task concurrency, backfill throttling, retries, and
scheduling, with concrete config changes.

## Throttle Backfills And Fan-Out

Input: a backfill or dynamic fan-out that floods the queue.

Output: separate limits and policies so history and fan-out cannot starve
scheduled runs.

## Compare Orchestrators

Input: a workload (pipeline count, shared resources, team skills).

Output: a Dagster-vs-Mage comparison on concurrency control, using the profiles'
capability tables.
