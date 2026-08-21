# Webhook Alert Delivery Adapter

## Use For

- Universal integration fallback.
- Custom internal tools.
- Low-level integration tests.
- Downstream workflow triggers where the target system owns its own delivery.

## Provider Requirements

- Allowlisted URL.
- Secret-managed signing key or bearer token.
- Timeout, retry, and backoff configuration.
- Optional mTLS or IP allowlist for production routes.

## Payload Mapping

Webhook payloads should preserve the channel-neutral contract as JSON with
provider-specific metadata under `provider_context`.

```yaml
provider_context:
  method: POST
  content_type: application/json
  signature_header: string | null
```

## Delivery Rules

- Sign payloads when the receiving system supports signatures.
- Treat non-2xx responses as failures unless the route declares otherwise.
- Use idempotency keys from `correlation_id` and `dedupe_key`.
- Do not follow redirects in production unless explicitly allowlisted.
- Enforce a strict timeout to prevent workflow hangs.

## Result Evidence

Capture HTTP status, response correlation ID, redacted response body hash, and
retryability classification.

## Executable Provider

`src/quantsmith/adapters/alert_delivery/webhook.py` (`build_webhook_payload`,
`deliver_webhook`) implements this mapping deterministically, applies
redaction per `privacy.redaction_level`, and guards against a credential-
shaped value ever appearing in the returned payload (spec `0032`). It
never makes the HTTP call itself; a real send requires an injected
`transport` callable and `dry_run=False`.
