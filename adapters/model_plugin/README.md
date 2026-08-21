# Model Plugin Adapters

Model plugin adapters let an adopter register an already-built internal
optimization model (a proprietary solver, an in-house allocation engine, a
vendor black box) so QuantSmith's `optimization/` agents can route work to it
and review its output — without this SDK ever holding the model's logic,
weights, or proprietary formulation.

## Files

| File | Purpose |
| --- | --- |
| `adapter_contract.md` | Provider-neutral registration manifest, invocation, and result schema. |
| `python_callable.md` | Profile for a model exposed as a local Python function/class. |
| `rest_endpoint.md` | Profile for a model exposed via an internal REST API. |
| `cli_binary.md` | Profile for a model exposed via a CLI or batch job. |

## Design Rule

Agents own problem framing, review, and the decision to trust an output.
Model plugin adapters own *only* the registration contract and invocation
shape — they never contain the model's actual objective, constraints,
weights, or proprietary logic. A registered model is treated as a reviewed
black box: its declared capability is checked against the contract, its
output is reviewed the same way a built-in solver's output would be
(`solver_diagnostics_sensitivity`), and anything it claims but cannot be
verified from its declared schema is flagged, not trusted.

## Configuration & Data Safety

The registration manifest (`model_plugins.yml`, at the repo root) is
**local-only and gitignored by default** — the same pattern as
`role_context.yml` (see `agents/role_operations/`) — because a real
manifest entry is likely to name a real internal model, its real objective/
constraint shape, and a real invocation endpoint, all of which are
company-specific. This repository ships only the template
(`templates/optimization/model_plugin_manifest.yml`, placeholders only) and
the `model-plugin` gate, which deterministically flags a tracked or staged
`model_plugins.yml`. See `instructions/model_plugin_integration.md`.
