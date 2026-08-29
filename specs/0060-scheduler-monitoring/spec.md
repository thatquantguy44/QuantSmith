# Spec: Scheduler Monitoring

- **ID:** 0060-scheduler-monitoring
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-08-24

## Problem & Context

Spec `0055` built the control plane — a schedule registry, dispatch with an
idempotency envelope, an append-only run ledger, manual-task carry-forward,
a daily operations report, and alert-handoff payloads — but its own
`tasks.md` names three things it deliberately left open, and
`docs/handoff.md` names closing them the SDK's #2 priority after the
knowledge base: *"the scheduling layer records history without doing the
'watch it while it runs' job it exists for."*

Three gaps, precisely:

1. **`alert_handoffs()` returns payloads, nothing delivers them.**
   `workflow_scheduling.py:504`'s own docstring says so: *"Return alert
   payloads only; delivery remains the adapter layer's job."* `alerting.
   route()` (spec `0020`) already assigns an owner and channel per alert —
   that half exists — but nothing connects a `RoutedAlert` to
   `adapters/alert_delivery/`.
2. **No `workflow_scheduling_cli.py`.** The worked example
   (`examples/scheduled_daily_report/README.md`) already documents a real
   two-cron deployment whose second entry calls a module that doesn't
   exist, and says so in the file: *"There is no `workflow_scheduling_cli`
   in the SDK yet."*
3. **"Decide when schedule deployment becomes enforceable rather than
   advisory"** — a bare, undecided open question in `0055`'s own `spec.md`.

## Goals

- Add `deliver_routed_alerts` to `workflow_scheduling.py`: deliver each
  `RoutedAlert` through a caller-supplied sender for its channel, building
  the `AlertDeliveryEvent` those senders need from context already
  available at the call site.
- Add `src/quantsmith/pipelines/workflow_scheduling_cli.py`: a stdlib CLI,
  `render-report` and `alerts` subcommands, closing the gap the worked
  example names.
- Resolve the enforceable-vs-advisory open question explicitly (see Non-Goals
  and Assumptions), rather than leaving it open indefinitely.
- Update `examples/scheduled_daily_report/README.md`'s cron deployment so
  its second entry is real, not aspirational.

## Non-Goals

- **No network/delivery code.** `deliver_routed_alerts`'s `senders` are
  always caller-injected — this SDK holds no transport or credentials (P9),
  the same boundary every `adapters/alert_delivery/*.py` provider and
  `dispatch_job`'s own `handlers` parameter already draw.
- **No `dispatch` CLI subcommand.** Constructing a full `ScheduleJob`
  (nested `Target`/`Schedule`/`RetryPolicy`/`BackfillPolicy`) from flat CLI
  flags would need a registry-file format `0055` never specified — inventing
  one is new logic beyond this spec's scope, not a thin wrapper. `dispatch_job`
  remains a library call for now.
- **No manual-task CLI support.** `ManualTaskQueue` is in-memory by design
  in `0055` — there is no persisted task-file format to read from, so both
  CLI commands operate on run records only. A task-aware CLI needs that
  store built first, which is not this spec's job.
- **No real "enforced" deployment mode.** Resolved as *advisory by default*
  (see Assumptions) — no new blocking mechanism is wired into `dispatch_job`
  or the CLI; an adopter's own CI/cron step decides what a non-zero exit
  means, the same way every `hooks/stages/*.sh` gate already works.
- **No changes to `0055`'s own module surface** beyond the one addition
  above — `ScheduleJob`, `dispatch_job`, `ExecutionLedger`, `alert_handoffs`,
  `render_daily_operations_report` are unmodified.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | `deliver_routed_alerts` shall deliver each `RoutedAlert` through the sender registered for its `channel`, constructing an `AlertDeliveryEvent` from the alert, the routed owner, and caller-supplied job/correlation/route context. | must |
| REQ-002 | A `RoutedAlert` whose `channel` has no registered sender shall raise `ValueError` naming the channel and the alert, never silently dropping it. | must |
| REQ-003 | `workflow_scheduling_cli.py render-report` shall render the daily operations report from an `ExecutionLedger` file, producing output identical to calling `render_daily_operations_report` directly. | must |
| REQ-004 | `workflow_scheduling_cli.py alerts` shall preview routed alert handoffs from an `ExecutionLedger` file, never calling any delivery function. | must |
| REQ-005 | Both CLI subcommands shall degrade gracefully given a missing or empty ledger file (an empty report; `"(no alerts)"`), never raising. | must |
| REQ-006 | The enforceable-vs-advisory open question from `0055`'s Follow-ups shall be resolved and documented, not left open. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Dependency isolation | Standard library only; no new dependency. |
| NFR-002 | Determinism | The same ledger file and arguments always produce the same report/alert preview. |
| NFR-003 | No credentials in this SDK | `senders` are always caller-injected; no transport or credential lives in `workflow_scheduling.py` or the CLI (P9). |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a `RoutedAlert` and a sender registered for its channel, when `deliver_routed_alerts` runs, then the sender is called with a correctly populated `AlertDeliveryEvent` and its `DeliveryResult` is returned. | REQ-001 |
| AC-002 | Given a `RoutedAlert` whose channel has no registered sender, when `deliver_routed_alerts` runs, then it raises `ValueError` naming the channel. | REQ-002 |
| AC-003 | Given alerts routed to two different channels, when `deliver_routed_alerts` runs, then each is delivered through its own channel's sender. | REQ-001 |
| AC-004 | Given a populated ledger file, when `render-report` runs, then its stdout matches `render_daily_operations_report`'s direct output exactly. | REQ-003 |
| AC-005 | Given a ledger with a failed run, when `alerts` runs, then it prints the routed alert (owner, channel, message) and calls no delivery function. | REQ-004 |
| AC-006 | Given a missing ledger file, when either CLI command runs, then it exits 0 with an empty report or `"(no alerts)"`, not an error. | REQ-005 |
| AC-007 | Given the worked example's README, when inspected, then its second cron entry names a real, existing module and command. | REQ-003, REQ-004 |

## Data & Dependencies

- **Reads:** an `ExecutionLedger` JSONL file (already spec `0055`'s own
  format; unchanged).
- **Consumes:** `alerting.Alert`/`RoutedAlert`/`route()` (spec `0020`,
  unmodified); `adapters/alert_delivery/result.py`'s `AlertDeliveryEvent`/
  `DeliveryResult` (spec `0032`, unmodified) as the shared data contract —
  `workflow_scheduling.py` now imports these types, a one-directional
  dependency from `pipelines/` on an `adapters/` contract's plain dataclasses
  (no I/O), not the reverse.
- Standard library only.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A caller wires `deliver_routed_alerts` with a sender that itself has `dry_run=False` and live credentials, defeating the "no network code here" boundary at the integration point. | Medium — the boundary is a convention, not a technical guarantee once a caller opts in. | Documented explicitly in the function's docstring: `senders` must be pre-bound by the caller with their own `transport`/`dry_run` choice — same disclosed limit every `adapters/alert_delivery/*.py` provider already states about its own `transport` parameter. |
| RISK-002 | `job.alert_route` and `RoutedAlert.channel` look similar and could be conflated by a caller (which one selects the provider vs. the destination). | Low — a caller passes the wrong string to the wrong field, alert goes to the wrong mailbox. | Stated plainly in the function's docstring: `channel` selects *which* sender/provider; `alert_route` becomes the delivered event's destination *within* that channel. Deliberately independent fields. |

## Assumptions & Open Questions

- **Resolved:** schedule deployment stays **advisory by default**, matching
  every gate in this repo (`QF_STAGE_ENFORCE=1` convention). No new blocking
  mechanism is wired into `dispatch_job` or the CLI in this slice — an
  adopter's own CI/cron step decides what a non-zero exit means, once they
  have a concrete provider scheduler to enforce against. Revisit if/when a
  real deployment surfaces a case advisory-only cannot catch.
- Assumption: `AlertDeliveryEvent`'s required fields can be honestly
  synthesized from what `RunRecord`/`ScheduleJob`/`RoutedAlert` already
  carry (no new metadata needs to flow through `dispatch_job` to make
  delivery possible).
- Open question, carried: should manual tasks get a persisted file format
  (parallel to `ExecutionLedger`), enabling a task-aware CLI and `dispatch`
  subcommand later? Deferred until a concrete need for CLI-driven dispatch
  appears — see this spec's Non-Goals.

## Exceptions

None. This spec extends an existing, already-approved module and adds one
new CLI; it introduces no deviation from
`instructions/engineering_principles.md`.
