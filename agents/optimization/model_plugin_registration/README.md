# Model Plugin Registration Agent

## Purpose

The Model Plugin Registration Agent ingests a registered model-plugin
manifest entry and produces a structured understanding brief: what the
model claims to do, whether its registration satisfies the adapter
contract, and — explicitly — what cannot be verified without its source.
It is the narrow first pass that lets an already-built internal
optimization model be routed to and reviewed like any other solver in the
`optimization/` group, without this SDK ever holding the model's logic.

## Use When

- A prebuilt internal optimization model needs to be registered so agents
  can route work to it.
- A registered manifest entry needs review before its `review_status`
  moves from `unreviewed` toward `approved`.
- A workflow wants to use a plugged-in model and needs to know what it can
  and cannot assume about its behavior.

## Inputs

- A `model_plugins.yml` manifest entry (local, never committed — see
  `adapters/model_plugin/adapter_contract.md`).
- Optionally, the model's declared `input_schema_uri`/`output_schema_uri`
  documents.

## Outputs

- A capability summary: objective, decision variables, constraint types, as
  declared — labeled "as declared by the owner," not independently verified.
- A contract-compliance check: which required manifest fields are present,
  which are missing.
- An explicit unverifiable-claims list: anything the model asserts
  (solver behavior, guarantees, performance) that this agent has no way to
  confirm from the manifest alone.
- A named handoff to `problem_formulation` (to scope how it fits a
  workflow), `solver_diagnostics_sensitivity` (to review its actual
  output once invoked), and `risk` (exposure from trusting an unverified
  black box).

## Example Requests

- "Ingest this model-plugin manifest entry and tell me what it claims to
  do."
- "Is this registration missing anything the adapter contract requires?"
- "What can't I assume about this plugged-in model without seeing its
  source?"

## Required Review Themes

- The manifest is treated as a claim, not a fact — every declared
  capability is labeled "as declared," and unverifiable claims are listed
  explicitly, not silently accepted.
- Contract compliance (required fields present) is checked before any
  routing recommendation.
- The model's actual objective coefficients, constraints, or weights are
  never requested, inferred, or reproduced — only the declared interface
  shape is reviewed.
- `review_status` only advances on a human decision; this agent informs
  that decision, it does not make it.
