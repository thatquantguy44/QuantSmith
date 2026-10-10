# Pipeline Concurrency Tasks

## Declare A Fleet

Input: the pipeline inventory, shared resources and their real limits, sinks.

Output: a `Fleet` declaration — global limit, pools with slot weights, mutual-exclusion
keys, priorities, retries — that constructs without error.

## Plan Capacity For A Window

Input: a fleet declaration with observed durations and a time window.

Output: a `simulate` capacity plan — makespan vs. lower bound, utilization, wait by
constraint, bottleneck — and the change that would most shorten the makespan.

## Diagnose Contention

Input: symptoms (pool exhaustion, rate-limit bans, lock timeouts, missed SLAs).

Output: the missing pool, key, weight, or stagger that causes it, and the fix.

## Harden Retries And Failure Isolation

Input: the current retry policy and an incident (retry storm, stale dependents).

Output: bounded retries through admission, `upstream_failed` isolation, and the
`AC-*` that proves it.

## Hand Off To An Orchestrator

Input: an approved fleet and the target (Dagster, Mage).

Output: a handoff to `tooling/dag_orchestration` to render config with
`to_dagster` / `to_mage`, including every warning the target raises.
