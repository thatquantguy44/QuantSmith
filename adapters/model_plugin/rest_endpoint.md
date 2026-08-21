# REST Endpoint Profile

For a prebuilt model exposed as an internal service — common when the model
already backs a desk tool or shared platform (e.g. a Financing Hub
optimization service).

## Registration

`invocation.type: rest_endpoint`; `invocation.reference` is a URL in the
local, gitignored `model_plugins.yml`. The committed template uses a
placeholder (`https://{internal-host}/{path}`) — never a real internal
hostname or path.

## Invocation Notes

- Authentication is resolved through `agents/secrets_management/` at call
  time; a credential or token never appears in the manifest, the payload, or
  any tracked artifact.
- `timeout_seconds` from the manifest bounds the call; a timeout is reported
  as `status: failed` with `retryable: true`, not silently retried forever.
- `dry_run: true` should perform a health-check request (or be skipped
  entirely if the endpoint has no such route), not submit a real problem.

## What This Adapter Does Not Do

- Does not store request/response bodies beyond what
  `problem_payload_uri`/`solution_uri` already reference as artifacts.
- Does not assume the endpoint is idempotent; use `correlation_id` for
  dedup if the provider supports it, per the adapter design rules in
  `adapters/README.md`.
