# Adapter Catalog

Adapters are QuantSmith's boundary between agent decisions and external systems.
Agents decide what happened, what should be produced, and what policy applies.
Adapters translate an already-approved payload into a provider-specific action.

This keeps workflow logic stable while allowing teams to swap email, Slack,
Teams, schedulers, storage targets, model runtimes, or data platforms without
creating vendor-specific agents.

## Adapter Groups

| Group | Purpose |
| --- | --- |
| `alert_delivery/` | Deliver alerts, incident notices, recovery messages, and nightly workflow draft packs. |
| `schedulers/` | Run workflows on cron, GitHub Actions, Airflow, Dagster, Prefect, or cloud schedulers. |
| `artifact_delivery/` | Persist and distribute run cards, reports, draft packs, charts, and evidence bundles. |
| `dashboard_render/` | Turn a rendered dashboard payload (`0015`/`0016`) into a live artifact: an `.xlsx` workbook, a scaffolded React app, or a published report. |
| `data_access/` | Normalize access patterns for APIs, SQL, object storage, and market/vendor data sources. |
| `llm_runtime/` | Normalize model runtime selection while keeping prompts, evaluation, and policy outside provider code. |
| `model_plugin/` | Register an already-built internal optimization model so `optimization/` agents can route to and review it, without this SDK holding its logic. |

## Design Rules

- Adapters are not agents. They do not decide severity, ownership, research
  conclusions, portfolio actions, or whether a workflow is complete.
- Adapters accept structured payloads from agents and return structured delivery
  or execution results.
- Adapters never own secrets directly. Secrets are provided at runtime through
  the `secrets_management/` agents and approved environment configuration.
- Adapters must be idempotent where the provider allows it, using a stable
  `correlation_id`, deduplication key, or provider idempotency key.
- Adapters must redact credentials, MNPI, PII, restricted positions, and raw
  portfolio details unless a workflow explicitly permits the field.
- Adapters should degrade gracefully: dry run, validate-only, and no-op modes are
  first-class for testing.

## Common Adapter Result

Every adapter should return:

```yaml
adapter_name: string
provider: string
status: delivered | scheduled | stored | skipped | failed
provider_object_id: string | null
correlation_id: string
timestamp_utc: string
retryable: boolean
error_code: string | null
error_message_redacted: string | null
evidence_uri: string | null
```

## Workflow Boundary

```text
agent emits approved payload -> adapter validates provider fields
  -> adapter executes or dry-runs -> adapter returns structured result
  -> workflow records evidence and next action
```

## When To Add A New Adapter

Add an adapter when a provider or technology changes the integration boundary:
authentication, payload shape, delivery semantics, rate limits, acknowledgement,
storage behavior, or execution environment.

Do not add a new adapter only because a team uses a different naming convention
or cosmetic template. Put those differences in configuration.
