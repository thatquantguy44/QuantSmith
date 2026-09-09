# Collateral & Margin Allocation Optimizer Contract

Domain-specific `input_schema_uri` / `output_schema_uri` content for a
collateral-and-margin allocation model registered through
`adapters/model_plugin/adapter_contract.md` (spec `0026`). This file supplies
the **problem framing** — objective, decision variables, and constraint
shape — that `adapters/model_plugin/` deliberately does not own (see its
`README.md`'s Design Rule). No reference optimizer ships here or anywhere in
this SDK; this is a shape an adopter's own optimizer reads and writes.

Grounded in the canonical `0063` short-term-markets pack
(`knowledge/short_term_markets/`): `process.collateral_margin`,
`concept.haircut`, `concept.margin_amount`,
`convention.collateral.haircut_ratio`, `convention.collateral.margin_amount`,
and `lifecycle.collateral`'s state model. Every field below traces to one of
those records rather than inventing new collateral vocabulary.

## Registering A Collateral Optimizer

In your local `model_plugins.yml` (see
`templates/optimization/model_plugin_manifest.yml`):

```yaml
models:
  - model_id: "{your-collateral-optimizer-id}"
    owner: "{team or role}"
    category: lp   # or milp / qp / conic / other — your optimizer's choice
    declared_capability:
      objective: "Collateral-and-margin allocation across obligations"
      decision_variables: "asset-to-obligation allocation amount"
      constraint_types:
        - "eligibility"
        - "concentration"
        - "counterparty/netting"
        - "substitution"
    invocation:
      type: python_callable   # or rest_endpoint / cli_binary
      reference: "{module.path:callable_name}"
    input_schema_uri: "templates/optimization/collateral_margin_problem.template.json"
    output_schema_uri: "templates/optimization/collateral_margin_solution.template.json"
    review_status: unreviewed
    last_reviewed: null
```

## Problem Payload (what your optimizer receives)

See `collateral_margin_problem.template.json` for the full shape. Summary:

| Section | Content |
| --- | --- |
| `inventory[]` | One row per collateral asset: market value, `product_id` (a `0063` `product.*` ID), `haircut` (`convention.collateral.haircut_ratio`), `concentration_group_ids`, `netting_set_id`, adopter-supplied `liquidity_cost_bps`. |
| `obligations[]` | One row per margin/collateral obligation: counterparty, `netting_set_id`, `required_margin_amount` (`convention.collateral.margin_amount`), `call_deadline`, and a `lifecycle_state_ref` into `lifecycle.collateral`. |
| `constraints` | Concentration limits, counterparty netting rules, and substitution rules — all adopter-declared; `0063` supplies the vocabulary, not the numbers. |
| `objective` | Adopter-declared primary objective (e.g. minimize liquidity cost, maximize HQLA retained) and optional weights for a multi-objective formulation. |

## Solution Payload (what your optimizer returns)

See `collateral_margin_solution.template.json` for the full shape. Summary:

| Section | Content |
| --- | --- |
| `allocations[]` | Asset-to-obligation allocation with haircut applied and resulting margin value. |
| `unmet_obligations[]` | Any obligation the allocation could not fully cover, with a stated shortfall and reason. |
| `substitutions[]` | Any collateral substitution made, with reason and concentration impact — mirrors `lifecycle.collateral`'s `collateral.substitution_pending` state. |
| `explainability` | Binding constraints and rejected alternatives — required so the allocation decision is reviewable, not a black-box number. |
| Envelope fields | `status`, `objective_value`, `diagnostics_uri`, `correlation_id`, `timestamp_utc`, `retryable`, `error_code`, `error_message_redacted` — identical shape to `adapter_contract.md`'s Invocation Output, so the generic adapter's review/audit handling applies unchanged. |

## Required Behavior

- Same rules as `adapter_contract.md`: never inline real objective
  coefficients, real constraint numbers, or real position/counterparty data
  in a committed example — shape only.
- Treat every optimizer output (`objective_value`, `solver_status`,
  `explainability`) as **unverified until reviewed**, per `0026`'s existing
  rule — this contract does not certify a collateral optimizer's output is
  correct, only that it is shaped correctly.
- A `haircut` or `required_margin_amount` an optimizer reports must resolve
  through `convention.collateral.haircut_ratio` /
  `convention.collateral.margin_amount`'s formula, or be flagged as a
  deviation with a stated reason.
- Point-in-time: `as_of` on the problem payload and `knowledge_pack_ref`
  pinning the `0063` pack version used must both be present, so a run is
  reproducible against the taxonomy/convention version it was framed
  against.

## Spec-Driven Role

Backed by spec `0067-collateral-margin-optimizer-contract`. Composes `0026`'s
registration/invocation envelope (unmodified) with `0063`'s taxonomy and
convention IDs for the domain-specific payload shape. No optimizer logic,
weights, or real constraint data is introduced by this contract — a
concrete optimizer remains adopter-owned and locally registered, per
`instructions/model_plugin_integration.md`.
