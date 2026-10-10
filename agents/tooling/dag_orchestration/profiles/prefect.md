# Prefect Profile

Concurrency, priority, retry, and scheduling guidance for running many pipelines on
Prefect. Rendered by `pipeline_fleet.to_prefect` (spec `0112`).

> **Version assumption:** Prefect 2.x/3.x (work pools and queues, global concurrency
> limits used with `prefect.concurrency.sync.concurrency(names, occupy=n)`).
> Verify against the installed version before deploying.

## Concurrency Levels

| Level | Mechanism | Bounds |
| --- | --- | --- |
| Deployment | Work-pool concurrency limit (`prefect work-pool set-concurrency-limit`) | Flow runs the pool executes at once. |
| Priority | Work queues with priority (1 is served first) | Order in which queued runs start. |
| Shared resource | Global concurrency limits (`prefect gcl create NAME --limit N`) acquired with `concurrency()` | Code holding a resource; `occupy` weights heavy work. |
| Mutual exclusion | A global limit of 1 per key | One writer per table or partition. |

## What `to_prefect` Emits

- `work_pool.concurrency_limit` = the fleet's global limit.
- Global limits `quantsmith-pool-<pool>` and `quantsmith-key-<key>` with CLI commands.
- Work queues `quantsmith-p<priority>`, ranked so the highest fleet priority is 1.
- Per flow: `work_queue`, `retries`, and `concurrency` acquisitions.

## Rules

- **Acquire all at once when you can.** When a flow holds the same slot count in
  every limit, `to_prefect` emits one `concurrency([...], occupy=n)` call, which
  holds them together.
- **Mixed slot counts.** One call per limit in name order. Every flow then acquires in
  the same global order, so there is no deadlock cycle — but holds are sequential,
  not all-or-nothing, and `to_prefect` warns. Keep that order in the flow code.
- **Retries** re-run the flow; keep the `concurrency()` block inside the flow body so
  a retry re-acquires rather than holding slots while waiting.
- **Cross-flow dependencies** are automations or `run_deployment` on upstream completion.
- **Staggering.** Offset schedules with `stagger_offsets`.

## Failure Modes To Look For

- Global limits created but never acquired in code.
- Nested `concurrency()` calls in different orders across flows.
- A work pool without a concurrency limit.
