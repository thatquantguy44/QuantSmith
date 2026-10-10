# Pipeline Concurrency Instructions

## Operating Rules

- Model the fleet, not one pipeline: declare a global run limit, a pool for every
  shared scarce resource, and a mutual-exclusion key for every shared sink.
- Set pool limits from the real capacity minus headroom (other tenants, admin
  connections), never from what the orchestrator default happens to be.
- Use slot weights for heavy jobs (a job opening 4 connections holds 4 slots).
- Reserve all-or-nothing: a run starts only when every resource it needs is free.
  Never let a run hold one resource while waiting for another.
- Order by priority, let small jobs use idle capacity, and keep the starvation
  guard (`max_bypass`) on so wide jobs are not overtaken forever.
- Bound retries and route them back through admission; never retry in place
  while holding slots. Contract violations are not retried (see `0011`).
- On permanent failure, mark transitive dependents `upstream_failed`; let
  unrelated pipelines continue.
- Stagger schedules with `stagger_offsets` so the fleet does not fire on one second.
- Plan before deploy: run `simulate`, compare makespan to the lower bound, and fix
  the named bottleneck before raising the global limit.
- Record error classes, never raw error messages (they carry connection strings).

## Checks

- Is every shared resource a pool, and is every limit justified against reality?
- Can any job never be admitted (slot demand above its pool)?
- Does any sink have two writers without a shared key?
- Are retries bounded and admitted like first attempts?
- Does the plan fit the window, and which constraint dominates queue wait?
- Are start times staggered, and are they stable when pipelines are added?

## Output Contract

Use clear Markdown. Present the fleet declaration (global limit, pools, keys,
priorities, retries), then `Capacity Plan` (makespan, lower bound, efficiency,
per-pool peak/utilization, wait by constraint, bottleneck), `Failure Isolation`, and
`Orchestrator Handoff`. Name the runtime symbols (`Fleet`, `FleetJob`, `Pool`,
`FleetConfig`, `simulate`, `run_fleet`, `stagger_offsets`) when handing off to code.

## Spec-Driven Role

The fleet design becomes `REQ-*`; limits holding under load, all-or-nothing
admission, starvation freedom, retry bounding, failure isolation, and plan
determinism become testable `AC-*`; deadlock, starvation, retry storms, sink write
races, and silently lost limits become `RISK-*`. The standard is
`instructions/pipeline_engineering.md` → *Concurrency At Fleet Scale*; the runtime is
`src/quantsmith/pipelines/pipeline_fleet.py`; the spec is
`specs/0101-concurrent-pipeline-fleet/`. Hands off to `tooling/dag_orchestration`,
`data_engineering/pipeline_deployment`, and `data_engineering/pipeline_observability`.
