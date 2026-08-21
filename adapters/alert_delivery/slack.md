# Slack Alert Delivery Adapter

## Use For

- Team-visible workflow status.
- Analyst or desk review channels.
- Incident updates that benefit from threaded discussion.
- Lightweight acknowledgements and follow-up links.

## Provider Requirements

- Workspace-approved app or bot token.
- Channel allowlist.
- User/group mapping from alert route to Slack channel, user group, or DM.
- Rate-limit and retry policy.

## Payload Mapping

| Contract field | Slack field |
| --- | --- |
| `route` | channel ID, user ID, or user group |
| `title` | message header |
| `summary` | first block |
| `body_markdown` | section blocks |
| `evidence` / `artifacts` | link blocks |
| `acknowledgement_uri` | button or link |
| `correlation_id` | metadata and footer |

## Delivery Rules

- Prefer channel messages for shared operational context and DMs only for
  explicitly routed ownership.
- Thread updates under the original message when `provider_thread_id` exists.
- Keep high-severity messages short and link to evidence/runbooks.
- Avoid posting raw tables, secrets, PII, MNPI, or restricted positions.
- Use dry-run rendering before enabling a new route.

## Result Evidence

Capture Slack channel ID, message timestamp, thread timestamp, permalink if
available, and redacted payload hash.

## Executable Provider

`src/quantsmith/adapters/alert_delivery/slack.py` (`build_slack_payload`,
`deliver_slack`) implements this mapping deterministically, applies
redaction per `privacy.redaction_level`, and guards against a credential-
shaped value ever appearing in the returned payload (spec `0037`). It
never calls the Slack API; a real send requires an injected `transport`
callable and `dry_run=False`.
