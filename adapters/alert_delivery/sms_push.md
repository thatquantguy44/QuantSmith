# SMS And Push Alert Delivery Adapter

## Use For

- Critical, time-sensitive notifications where chat/email latency is unacceptable.
- Human acknowledgement prompts for production incidents.
- Narrow escalation paths approved by policy.

## Provider Requirements

- Explicit recipient opt-in and route allowlist.
- Approved SMS, push, or mobile notification provider.
- Quiet-hours and escalation policy.
- Strict payload redaction.

## Payload Mapping

| Contract field | SMS/push field |
| --- | --- |
| `route` | phone group, device group, or push topic |
| `severity` | urgency |
| `title` | short title |
| `summary` | short body |
| `acknowledgement_uri` | short link |
| `correlation_id` | metadata |

## Delivery Rules

- Restrict to `critical` alerts by default.
- Never include raw data tables, account identifiers, credentials, PII, MNPI, or
  restricted positions.
- Use short links only from approved domains.
- Prefer "acknowledge in system" links over direct reply semantics.
- Respect quiet-hours policy unless the escalation policy explicitly overrides it.

## Result Evidence

Capture provider message ID, route group, timestamp, delivery status, and
acknowledgement URI if supported.

## Executable Provider

`src/quantsmith/adapters/alert_delivery/sms_push.py`
(`build_sms_push_payload`, `deliver_sms_push`) implements this mapping
deterministically and enforces two of this file's own delivery rules
structurally rather than narratively (spec `0037`): it raises unless the
event's severity is `critical`, unless `allow_all_severities=True` is
passed; and it truncates an oversized title/body to a short-message
length cap (`TITLE_MAX_LEN`/`BODY_MAX_LEN`) with a visible marker rather
than sending it oversized. It also applies redaction and the
credential-shaped-value guard. It never calls an SMS/push gateway; a real
send requires an injected `transport` callable and `dry_run=False`.
