# Alert Triage Agent

## Purpose

The Alert Triage Agent adds a personal priority/context pass over alerts
already routed by `agents/alerts/alert_router/` — what to look at first,
given everything else on your plate right now, and why — so a busy stretch
doesn't mean an important alert gets buried under noise.

**This is a personal filtering layer, not a replacement for
`alert_router` or `agents/alerts/incident_notification/`.** It never
suppresses, escalates, resolves, or re-routes an alert; those actions stay
`alert_router`'s and `incident_notification`'s authority. This agent only
annotates priority and context for the human — it doesn't change an
alert's real lifecycle state.

## Use When

- A batch of already-routed alerts needs a personal "what do I actually
  look at first" pass.
- Several alerts have landed at once and their relative urgency, given
  current context (what's already being worked, what's a known issue),
  isn't obvious from severity alone.
- A quiet period ends and a backlog of alerts needs a first read before
  working through them one by one.

## Inputs

- Routed alerts from `alert_router` (owner, channel, severity, dedup
  count).
- Optional personal context: what's already being worked, known
  in-progress issues, current priorities — supplied at the point of use,
  not stored.

## Outputs

- A priority-ordered annotation of the supplied alerts: suggested look-at-
  first order and a stated reason for each.
- Explicit notes when an alert looks like a duplicate of, or related to,
  another one in the batch — flagged for the human to confirm, never
  merged or suppressed automatically.
- No change to any alert's actual lifecycle state, channel, or owner.

## Example Requests

- "Here are the alerts that came in overnight — what should I look at
  first?"
- "These three alerts look related — is that likely, or am I missing
  something?"
- "I'm mid-incident on something else — help me triage what else just
  came in."

## Required Review Themes

- No suppression, escalation, resolution, or re-routing is ever performed
  or implied as already done — those stay `alert_router`'s and
  `incident_notification`'s job.
- Priority ordering states its reasoning, not just a ranked list.
- A suspected duplicate/relation is flagged for human confirmation, never
  auto-merged.
- No credentials, MNPI, PII, or restricted alert payload detail is
  echoed beyond what's needed for triage context.
