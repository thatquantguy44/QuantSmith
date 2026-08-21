# Model Plugin Adapter Contract

Two schemas: the **registration manifest** (what an adopter declares about a
prebuilt model, once, in `model_plugins.yml`) and the **invocation payload**
(what an agent sends/receives each time it routes work to a registered
model). The manifest is metadata and interface shape only — never the
model's actual logic, weights, coefficients, or training data.

## Registration Manifest Entry

One entry per registered model in `model_plugins.yml` (see
`templates/optimization/model_plugin_manifest.yml`):

```yaml
model_id: string                 # stable identifier, e.g. "collateral-lp-v3"
owner: string                    # team/role, not a person's name
category: lp | milp | qp | conic | nonlinear | global | stochastic |
          robust | dp | network_flow | heuristic | other
declared_capability:
  objective: string              # one line: what it optimizes for
  decision_variables: string     # shape only, e.g. "per-instrument allocation fraction"
  constraint_types:
    - string                     # e.g. "balance-sheet cap", "counterparty concentration"
  known_limitations:
    - string                     # stated by the owner, not inferred
invocation:
  type: python_callable | rest_endpoint | cli_binary
  reference: string              # placeholder in the committed template; real
                                  # endpoint/path/import path is local-only
  timeout_seconds: integer
input_schema_uri: string         # points at a schema doc, not inline proprietary detail
output_schema_uri: string
review_status: unreviewed | reviewed | approved
last_reviewed: string | null     # date, or null if unreviewed
```

## Invocation Input

```yaml
workflow_id: string
run_id: string
model_id: string                 # must match a registered manifest entry
problem_payload_uri: string      # points at the formulated problem (variables,
                                  # objective, constraints) per the model's
                                  # declared input_schema_uri
correlation_id: string
dry_run: boolean
```

## Invocation Output

```yaml
adapter_name: string
model_id: string
status: completed | infeasible | skipped | failed
solution_uri: string | null
solver_status: string | null     # as reported by the plugged-in model, unverified
objective_value: number | null
diagnostics_uri: string | null   # duals, slacks, sensitivity, if the model provides them
correlation_id: string
timestamp_utc: string
retryable: boolean
error_code: string | null
error_message_redacted: string | null
```

## Required Behavior

- Never inline the model's actual objective coefficients, constraint
  matrices, weights, or training data anywhere in the manifest or a
  committed example — schema and shape only.
- Route every invocation through `problem_payload_uri` /
  `solution_uri` (artifacts), never a raw payload embedded in a prompt or a
  tracked file.
- Treat everything the model reports (`solver_status`, `objective_value`,
  diagnostics) as **unverified until reviewed** — the adapter records what
  the model claimed, it does not confirm the model is correct.
- Support `dry_run: true` to validate a manifest entry's shape without
  invoking the real model.
- Redact `error_message_redacted` of anything that could leak the model's
  internals (stack traces referencing proprietary module paths, etc.).
