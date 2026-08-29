# Plan: Scheduler Monitoring

- **Spec:** 0060-scheduler-monitoring (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-08-24

## Approach

No new module for delivery — one function added to the existing
`src/quantsmith/pipelines/workflow_scheduling.py`, following the exact
composition style the rest of that file already uses (`alert_handoffs`
produces payloads, this consumes them). One new CLI file,
`workflow_scheduling_cli.py`, mirroring `workflow_memory_cli.py`'s
established shape verbatim. Neither `alerting.py` nor
`adapters/alert_delivery/` is modified — both are consumed as-is.

## Architecture & Components

```text
workflow_scheduling.py
  deliver_routed_alerts(routed, *, job_id, correlation_id, senders,
                         alert_route="") -> Tuple[DeliveryResult, ...]  REQ-001, REQ-002
      for each RoutedAlert:
        sender = senders.get(routed.channel)
        raise ValueError if sender is None                             REQ-002
        event = AlertDeliveryEvent(
            event_id=alert.dedup_key, workflow_id=job_id,
            source="quantsmith-scheduling", severity=alert.severity,
            status="triggered", owner=routed.owner, route=alert_route,
            title=f"{alert.rule_id}: {alert.metric}", summary=alert.message,
            correlation_id=correlation_id, dedupe_key=alert.dedup_key)
        results.append(sender(event))

workflow_scheduling_cli.py
  render-report --ledger PATH [--report-date YYYY-MM-DD]   REQ-003, REQ-005
      ExecutionLedger(path).records() -> render_daily_operations_report(records, (), report_date)
  alerts --ledger PATH [--as-of YYYY-MM-DD]                 REQ-004, REQ-005
      ExecutionLedger(path).records() -> alert_handoffs(records, (), as_of)
                                       -> alerting.route(alerts, Routing())
      prints each RoutedAlert; calls no delivery function
```

Both CLI commands pass `()` for manual tasks — `ManualTaskQueue` has no file
format (see Non-Goals), so there is nothing to load.

## Interfaces & Data Contracts

`AlertDeliveryEvent`/`DeliveryResult` imported from
`quantsmith.adapters.alert_delivery.result` — plain frozen dataclasses, no
I/O, so this is a one-directional type dependency (`pipelines/` reading an
`adapters/` contract), not a layering violation; confirmed no reverse import
exists (`adapters/alert_delivery/*.py` never imports `pipelines/`).

`senders: Mapping[str, Callable[[AlertDeliveryEvent], DeliveryResult]]` —
each value is a fully pre-bound callable (the caller applies its own
`transport`/`dry_run` via e.g. `functools.partial` before passing it in),
matching `dispatch_job`'s existing `handlers` parameter shape exactly.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P9 Security and data handling | yes | No transport, credential, or network call added anywhere in this SDK; `senders` are always caller-injected, same boundary every `alert_delivery` provider already draws. |
| P4 Correct by construction | yes | An unmapped channel is a raised error, not a silently dropped alert (REQ-002) — an indexing/lookup failure, not an assertion that could be removed. |
| P10 Honest reporting | yes | The CLI's `alerts` command is explicitly a preview — its own help text and docstring say "never delivers," and the test suite asserts no delivery vocabulary appears in its output. |
| P5 Reversibility | yes | Purely additive: one new function, one new file, one doc update. No existing function signature changes. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `deliver_routed_alerts` | T-001 |
| REQ-002 | `senders.get(...)` + raise | T-001 |
| REQ-003 | `render-report` subcommand | T-002 |
| REQ-004 | `alerts` subcommand | T-002 |
| REQ-005 | Both subcommands' handling of an empty `ExecutionLedger` | T-002 |
| REQ-006 | Assumptions & Open Questions resolution in `spec.md` | T-003 |
| NFR-001, NFR-002, NFR-003 | Stdlib only, pure functions, caller-injected senders | T-001, T-002 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| `dispatch` CLI subcommand | Not built | Add flat CLI flags to construct a `ScheduleJob` | Would need a new registry-file format `0055` never specified — that's new logic invented to fit a CLI, not a thin wrapper over what exists. Named explicitly as out of scope rather than half-built. |
| Enforceable-vs-advisory | Advisory by default, no new blocking mechanism | Add a `QF_SCHEDULING_ENFORCE` flag wired into `dispatch_job` | Nothing concrete to enforce *against* yet (no real provider-scheduler deployment exists in this repo) — matches this repo's own general pattern of shipping the advisory gate first and letting a real deployment motivate promoting it, rather than building enforcement plumbing speculatively. |
| Alert → event mapping | Synthesize missing `AlertDeliveryEvent` fields from `RunRecord`/`ScheduleJob`/`RoutedAlert` context at the call site | Widen `Alert`'s own dataclass to carry all 11 `AlertDeliveryEvent` fields | Would couple spec `0020`'s alerting module to spec `0032`'s delivery contract; keeping the mapping in `deliver_routed_alerts` (spec `0060`'s own new code) means neither `0020` nor `0032` needs to change. |

## Validation Strategy

`tests/test_workflow_scheduling_cli.py`, one test per acceptance criterion.
`deliver_routed_alerts` tested directly (AC-001–AC-003); the CLI tested as a
real subprocess (AC-004–AC-006), the same pattern
`test_workflow_memory_write_path.py` uses for spec `0049`'s CLI, so the
tests exercise the actual `python -m ...` entry point, not just its
internals. AC-007 is direct inspection of the updated example README. Then
the full documentation gate set, `pytest tests/ -q`, and `git diff --check`.

## Rollout, Observability & Rollback

Rollout is a branch commit and push; no migration, no existing function
signature changes. Rollback is reverting the commit. Nothing in this
repository invokes `deliver_routed_alerts` or the new CLI automatically —
an adopter wires both into their own scheduler integration when ready,
exactly as `0055`'s `dispatch_job` already expected of its `handlers`
parameter.

## Open Questions

- Carried from `spec.md`: whether manual tasks eventually get a persisted
  file format, enabling a task-aware CLI and a `dispatch` subcommand.
