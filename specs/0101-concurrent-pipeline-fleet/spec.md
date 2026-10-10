# Spec: Concurrent pipeline fleet

- **ID:** 0101-concurrent-pipeline-fleet
- **Status:** Draft
- **Author:** QuantSmith
- **Approver:** (pending)
- **Last updated:** 2026-10-10

> WHAT and WHY only. Implementation lives in `plan.md`.
> Extends the **Data Engineer** chain from one pipeline (`0011`) to hundreds of
> pipelines running at once, with Dagster and Mage as first-class targets.

## Problem & Context

`0011` makes a single pipeline ordered, contract-backed, idempotent, and
retry-safe. Quant data platforms do not run one pipeline; they run hundreds — one
per vendor feed, universe, region, or table — on the same warehouse, the same
vendor API quotas, and the same sink tables. At that scale the failures are
concurrency failures, not logic failures: connection-pool exhaustion when every
pipeline fires at 00:00, vendor rate-limit bans, two pipelines writing the same
table partition at once, a retry storm that multiplies load exactly when the
system is weakest, a large job starved forever by a stream of small ones, and a
failed upstream silently leaving dozens of dependents to run on stale inputs.

The repo has scheduler adapters (`adapters/schedulers/`) and a planned
`tooling/dag_orchestration/` agent, but no tool-neutral, tested concurrency model,
and no Mage profile. Teams therefore size limits by guesswork and configure each
orchestrator by hand, so the limits in Dagster or Mage drift from what the
platform can actually take.

## Goals

- Declare a fleet of pipelines and the shared capacities they compete for (a
  global limit, named pools with slot weights, and mutual-exclusion keys).
- Admit runs so that no limit is ever exceeded, without deadlock or starvation.
- Bound retries and isolate failures so one bad pipeline does not take down or
  corrupt the rest of the fleet.
- Produce a deterministic capacity plan that names the bottleneck before anything
  is deployed.
- Spread schedule start times so hundreds of pipelines do not fire on one second.
- Render the same limits as Dagster and Mage configuration, reporting every limit
  the target cannot enforce natively.

## Non-Goals

- A distributed executor, a durable run queue, or a replacement for Dagster/Mage
  (they execute; QuantSmith declares, plans, verifies, and renders).
- Calling the Dagster or Mage APIs, or importing either package (stdlib only).
- Per-step logic inside a pipeline (owned by `0011`).
- Time-based rate limiting (requests per second); pools bound *concurrent* use.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The system shall validate a fleet at construction: unique job names, known cross-pipeline dependencies, no cycles, declared pools, and per-job slot demands that fit the pool. | must |
| REQ-002 | The system shall admit a run only if the global limit, every pool it needs (with slot weights), and its mutual-exclusion key all have capacity, reserving all or nothing. | must |
| REQ-003 | The system shall order ready runs by priority then submission order, and shall prevent starvation of a run repeatedly overtaken by smaller runs. | must |
| REQ-004 | The system shall bound retries, send each retry back through admission, and mark the transitive dependents of a permanently failed run `upstream_failed` while unrelated runs continue. | must |
| REQ-005 | The system shall produce a deterministic capacity plan with makespan, a lower bound, per-pool peak and utilization, and queue wait attributed to the constraint that caused it. | must |
| REQ-006 | The system shall compute deterministic, name-stable start offsets that spread a fleet's schedules over a window. | should |
| REQ-007 | The system shall render fleet limits as Dagster and Mage concurrency configuration and list every limit, dependency, priority, or retry semantic the target cannot enforce natively. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Safety | Observed in-use never exceeds any limit, including under retries, for a fleet of at least 300 pipelines. |
| NFR-002 | Reproducibility | The same fleet yields an identical capacity plan on every run. |
| NFR-003 | Honest reporting | No exported config silently drops a limit; lossy mappings are listed. Run manifests record error class only, never error messages (which may hold credentials). |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a fleet with a duplicate name, unknown dependency, cycle, undeclared pool, or an unfittable slot demand, when it is constructed, then it is rejected with a reason; a valid fleet is ordered topologically. | REQ-001 |
| AC-002 | Given 300 pipelines over a global limit, two pools, and shared sink keys, when the fleet runs concurrently, then measured concurrency inside the job functions never exceeds any limit, no two runs share a key at once, slot weights are honored, and real concurrency occurs. | REQ-002, NFR-001 |
| AC-003 | Given mixed priorities, when admission is serialized, then higher priority runs first; given a wide job overtaken by a stream of narrow jobs, when the guard is enabled, then it is admitted early instead of last. | REQ-003 |
| AC-004 | Given a flaky job, an always-failing job with dependents, and an unrelated job, when the fleet runs, then the flaky job succeeds within its attempts, the failing job is `failed` with its error class only, its dependents are `upstream_failed`, the unrelated job is `ok`, and retries stay within pool limits. | REQ-004, NFR-001, NFR-003 |
| AC-005 | Given the same fleet twice, when it is simulated, then the plans are identical, within limits, `makespan >= lower_bound`, and a pool-bound fleet names that pool as the bottleneck. | REQ-005, NFR-002 |
| AC-006 | Given 500 pipeline names, when offsets are computed, then they fall in the window, are deterministic, do not move when other pipelines are removed, and do not pile onto one second. | REQ-006 |
| AC-007 | Given a fleet with pools, keys, priorities, retries, and dependencies, when exported to Dagster and Mage, then the config carries the limits and every non-native semantic appears in `warnings`. | REQ-007, NFR-003 |

## Data & Dependencies

- Runtime: `src/quantsmith/pipelines/pipeline_fleet.py` (standard library only).
- Builds on `0011` (per-pipeline correctness) and `0055` (schedule registry).
- Agents: new `data_engineering/pipeline_concurrency` and
  `tooling/dag_orchestration` (Dagster and Mage profiles); existing
  `data_engineering/pipeline_orchestration`, `pipeline_deployment`,
  `pipeline_observability`.
- Adapters: `adapters/schedulers/dagster_prefect.md`, new `adapters/schedulers/mage.md`.
- Standard: `instructions/pipeline_engineering.md` → *Concurrency At Fleet Scale*.
- No private data or credentials are written to this repository.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | Partial reservations deadlock (job A holds the warehouse waiting for the API, job B the reverse). | Fleet hangs. | All-or-nothing admission; no hold-and-wait (AC-002). |
| RISK-002 | A wide job never runs because narrow jobs keep a slot busy. | Missed SLA on the most important load. | Overtake counter with queue-jump reservation (AC-003). |
| RISK-003 | Retry storm multiplies load during an outage. | Rate-limit bans, pool exhaustion. | Retries re-enter admission; bounded attempts (AC-004). |
| RISK-004 | Exported orchestrator config silently loses a limit. | Production exceeds limits the plan said were safe. | Every lossy mapping listed in `warnings` (AC-007). |
| RISK-005 | Orchestrator config keys drift across Dagster/Mage versions. | Config ignored at deploy. | Profiles state the version assumption; deployment dry-run via `pipeline_deployment` before promotion. |
| RISK-006 | Simulated durations are wrong. | Capacity plan is optimistic. | Plan is evidence, not a guarantee; feed observed durations from the run manifest / `0019` back into `est_seconds`. |

## Assumptions & Open Questions

- Assumption: pools model concurrent use (connections, slots), not request rate.
- Assumption: job durations for planning come from observed history.
- Open question: a durable queue backend and a CLI (`quantsmith-fleet plan|export`).
- Open question: Airflow (`pools`, `max_active_runs`) and Prefect (global concurrency
  limits) exporters behind the same interface.

## Exceptions

None.
