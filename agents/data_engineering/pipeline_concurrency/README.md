# Pipeline Concurrency Agent

## Purpose

The Pipeline Concurrency Agent designs and reviews how hundreds of pipelines run at
the same time on shared infrastructure without overrunning it. It turns "we have
300 pipelines and they all fire at midnight" into a declared fleet: a global run
limit, named pools for the scarce things pipelines compete for (warehouse
connections, vendor API quota, cluster slots), mutual-exclusion keys for sinks two
pipelines must never write at once, priorities, bounded retries, staggered start
times, and a capacity plan that names the bottleneck before anything is deployed.

## Use When

- Many pipelines share a warehouse, a vendor API, or a cluster and contend for it.
- Runs are hitting connection-pool exhaustion, rate-limit bans, or lock timeouts.
- Two pipelines can write the same table or partition concurrently.
- A large job keeps missing its SLA behind a stream of small ones.
- Retries amplify load during an outage (retry storms).
- Concurrency limits need to be chosen, justified, and rendered for Dagster or Mage.

## Inputs

- The pipeline inventory: names, dependencies, owners, priorities, typical durations.
- The shared capacities and their real limits (DB `max_connections`, vendor quotas).
- Sink tables/partitions each pipeline writes (for mutual-exclusion keys).
- Retry policy and SLA expectations; the target orchestrator (Dagster, Mage, other).

## Outputs

- A `Fleet` declaration: global limit, pools with slot weights, keys, priorities, retries.
- A capacity plan from `simulate`: makespan vs. lower bound, peak and utilization
  per pool, queue wait by constraint, and the named bottleneck.
- Stagger offsets for schedules (`stagger_offsets`).
- Handoffs to `tooling/dag_orchestration` (render Dagster/Mage config),
  `pipeline_deployment`, and `pipeline_observability`.

## Example Requests

- "We run 400 vendor ingest pipelines nightly — size the warehouse and API limits."
- "Two backfills overwrote the same partition. Stop that from ever happening."
- "Our nightly window is 4 hours; will 250 pipelines fit, and what is the bottleneck?"
- "Retries during the vendor outage got our API key banned. Fix the retry design."

## Required Review Themes

- Every shared capacity is an explicit pool with a limit at or below the real one.
- Admission is all-or-nothing (no hold-and-wait); no job can need more than its pool.
- Every sink written by more than one pipeline has a mutual-exclusion key.
- Retries are bounded and re-enter admission; failures isolate their dependents.
- Start times are staggered; the capacity plan names the bottleneck.
