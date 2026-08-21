# Alert Delivery Adapters

Alert delivery adapters send validated notification payloads to humans or
systems. They sit behind the alert agents:

```text
monitoring event -> alert_policy -> alert_router -> alert_delivery adapter
  -> incident_notification -> acknowledgement or recovery record
```

The alert agents own detection, severity, routing, deduplication, and escalation.
The adapter owns provider translation, delivery, retry semantics, and provider
result capture.

## Files

| File | Purpose |
| --- | --- |
| `adapter_contract.md` | Channel-neutral alert delivery schema and required behavior. |
| `email.md` | Email delivery for reports, alerts, and scheduled draft packs. |
| `slack.md` | Slack channel, DM, thread, and acknowledgement delivery. |
| `teams.md` | Microsoft Teams channel/card delivery for enterprise workflows. |
| `webhook.md` | Generic HTTP delivery for custom workflow integrations. |
| `pagerduty_opsgenie.md` | Incident-management delivery and escalation integrations. |
| `ticketing.md` | Jira, ServiceNow, Linear, and other ticket creation/update flows. |
| `sms_push.md` | SMS and push notification delivery for high-urgency use cases. |

## Recommended Starting Set

Implement in this order:

1. `email.md` for nightly draft packs and default alert delivery.
2. `webhook.md` as the universal integration fallback.
3. `slack.md` and `teams.md` for team workflows.
4. `ticketing.md` for operational handoff.
5. `pagerduty_opsgenie.md` and `sms_push.md` only after escalation policy is stable.

## Executable Providers

All seven providers above are shipped as executable modules under
`src/quantsmith/adapters/alert_delivery/` — email and webhook (spec
`0032`), then Slack, Teams, ticketing, PagerDuty/Opsgenie, and SMS/push
(spec `0037`), completing the Recommended Starting Set end to end. Every
provider constructs the exact contract-shaped payload deterministically
and validates/redacts it — none opens a network connection itself. Real
delivery requires an adopter-supplied `transport` callable and
`dry_run=False`; the default (`dry_run=True`) never performs I/O, matching
`adapters/dashboard_render/`'s own dry-run-first pattern.

Two providers additionally enforce their own stated delivery rules
structurally, not just narratively: `pagerduty_opsgenie` and `sms_push`
raise by default unless the event's severity meets their routing bar
(`high`/`critical` and `critical` respectively — pass
`allow_all_severities=True` to override), and `sms_push` truncates an
oversized title/body to a short-message length cap with a visible marker
rather than sending it oversized.
