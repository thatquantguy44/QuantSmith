# Plan: Alert Delivery Executable Providers (Email, Webhook)

- **Spec:** 0032-alert-delivery-providers (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-08-10

## Approach

Mirror `adapters/dashboard_render/`'s executable-provider pattern (specs
`0017`/`0018`): a small `result.py` holding the shared result type and a
secret-shaped-value guard, one module per provider, standard-library only,
`dry_run`-capable. The one deliberate difference: dashboard providers'
whole job (write a file) is fully self-contained, but an alert delivery
provider's "real" job (send over the network with a credential) is not
something this SDK should do itself — so each provider's real work is
**payload construction, validation, and redaction**, with an injected
`transport` callable as the seam where an adopter's own send code plugs
in. `dry_run=True` is the default in both providers, so importing and
calling a provider never performs I/O unless the caller explicitly opts
in and supplies a transport.

## Architecture & Components

```text
src/quantsmith/adapters/alert_delivery/
  __init__.py         -- exports AlertDeliveryEvent, DeliveryResult,
                          deliver_email, deliver_webhook
  result.py            -- AlertDeliveryEvent (Input schema), DeliveryResult
                          (Output schema), contains_secret(), redact()
  email.py              -- build_email_payload(), deliver_email()
  webhook.py             -- build_webhook_payload(), deliver_webhook()

Call shape (both providers):
  event = AlertDeliveryEvent(...)                     # from adapter_contract.md Input
  result = deliver_email(event)                        # dry_run=True default, no I/O
  result = deliver_email(event, transport=my_sender,    # real send, adopter-owned
                          dry_run=False)
```

`AlertDeliveryEvent` mirrors `adapter_contract.md`'s Input YAML field-for-
field (a frozen dataclass, standard-library only). `DeliveryResult` mirrors
its Output YAML. `transport` is `Callable[[dict], TransportOutcome]` —
the provider builds the exact payload dict per its `*.md`'s Payload Mapping
table and hands it to `transport`; the provider never opens a socket,
imports `smtplib`, or makes an HTTP call itself.

## Interfaces & Data Contracts

`AlertDeliveryEvent` / `DeliveryResult` are the two schemas, both direct
transcriptions of `adapters/alert_delivery/adapter_contract.md`'s existing
Input/Output YAML — no new schema design, just giving the already-documented
contract a Python shape. `email.py`/`webhook.py` each additionally define
the provider-specific payload dict shape per their own `*.md`'s Payload
Mapping table (already documented, not new).

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P9 Security & data | yes | No credential ever enters this SDK; `transport` is the adopter's own authenticated client. `contains_secret` guards the constructed payload before it's ever returned. |
| P4 Correct by construction | yes | `dry_run=True` default means calling a provider can never silently send a real alert during development/testing — I/O requires an explicit, separate opt-in. |
| P10 Honest reporting | yes | A dry run returns `status="skipped"`, not `"delivered"` — the result type itself states plainly that nothing was sent, rather than a status that could be misread as success. |
| P5 Reversibility | yes | New, additive runtime module; no existing contract, agent, or gate changes behavior. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `result.py::AlertDeliveryEvent` | T-001 |
| REQ-002 | `email.py::build_email_payload`, `deliver_email` | T-002 |
| REQ-003 | `webhook.py::build_webhook_payload`, `deliver_webhook` | T-003 |
| REQ-004 | `dry_run` default + `transport` injection, both providers | T-002, T-003 |
| REQ-005 | `result.py::contains_secret`, `redact` | T-001 |
| REQ-006 | Failure classification in `deliver_email`/`deliver_webhook` | T-002, T-003 |
| REQ-007 | `adapters/alert_delivery/{README,email,webhook}.md` | T-004 |
| NFR-001 | Deterministic payload construction (no clock/random in the builder) | T-002, T-003 |
| NFR-002 | Standard-library only, no dependency added | T-002, T-003 |
| NFR-003 | `contains_secret` check before returning a payload | T-001, T-002, T-003 |
| NFR-004 | Validation gates | T-005 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Real send boundary | Injectable `transport` callable, SDK never opens a network connection | Ship a real `smtplib`/`urllib` implementation | This SDK is a scaffold copied into other repos with their own SMTP/webhook infrastructure and secrets; a hardcoded transport would either not work in a real environment or require this SDK to hold real credentials, violating P9. The same reasoning already governs `credential_access` and the `0026` model-plugin dispatcher. |
| Scope | Email + webhook only | All seven providers in one slice | `adapters/alert_delivery/README.md`'s own pre-existing Recommended Starting Set already sequences email and webhook first; matching it avoids inventing a new ordering and keeps this slice reviewable, the same reasoning `0017` used to ship two dashboard providers before `0018` added a third. |
| Result shape | Mirror the contract's existing Output YAML directly | Design a new, richer result type | The contract's Output schema was already designed and documented; transcribing it faithfully keeps the Python type and the documented contract from drifting apart. |

## Validation Strategy

`tests/test_alert_delivery_adapters.py`: payload construction for both
providers (matching each `*.md`'s Payload Mapping table), dry-run default
(no transport call, `status="skipped"`), transport injection and outcome
mapping, redaction, the secret guard, and determinism (same event twice ->
identical payload). Then `hooks/stages/run-stage.sh spec agent-catalog
docs-link spec-index`, the full `pytest tests/ -q`, and `git diff --check`.
AC-009 is covered by direct inspection of the three updated `adapters/
alert_delivery/*.md` files. AC-010 is covered by the gate run itself.

## Rollout, Observability & Rollback

Rollout is a branch commit (and push, if requested). Rollback is reverting
the single commit; `adapter_contract.md` and `agents/alerts/*` are
unmodified, so nothing downstream depends on this slice existing.

## Open Questions

- Once Slack/Teams/ticketing/PagerDuty/SMS providers are built, should
  they share a common `transport`-injection helper, or does each
  provider's payload shape differ enough that duplication stays clearer?
  Deferred to that slice.
