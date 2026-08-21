# Model Plugin Integration Instructions

## Purpose

Use this instruction set when an already-built internal optimization model
— a proprietary solver, an in-house allocation engine, a vendor black box —
needs to be registered so QuantSmith's `optimization/` agents can route
work to it and review its output. It is the shared standard behind
`adapters/model_plugin/` and `agents/optimization/model_plugin_registration/`.
The goal is the same as the rest of this SDK's guardrails: real capability,
honestly bounded, with nothing company-specific ever entering the
repository.

## Required Inputs

- A `model_plugins.yml` manifest entry (local, gitignored — see
  `templates/optimization/model_plugin_manifest.yml`), declaring the
  model's category, objective, decision-variable shape, constraint types,
  known limitations, and invocation profile.
- Pointers to the model's input/output schema (`input_schema_uri`/
  `output_schema_uri`) — never the schema's real contents inlined into a
  tracked file if those contents are proprietary.

## Expected Output

- A capability summary labeled as the owner's claim, not a verified fact.
- A contract-compliance check against the required manifest fields.
- An explicit list of what cannot be verified from the manifest alone.
- A routing recommendation naming the downstream agent (`problem_formulation`,
  `solver_diagnostics_sensitivity`, `risk`) — never a standalone approval.

## Standards

- **Interface, not implementation.** A registration declares what a model
  does and how to call it — never its objective coefficients, constraint
  matrices, weights, or training data. If reviewing the model requires
  seeing its logic, that review happens outside this SDK.
- **Claims are claims until reviewed.** `declared_capability` is the
  owner's self-report. Treat it as a hypothesis to check, not a fact to
  relay, until a human sets `review_status: reviewed` or `approved`.
- **Same scrutiny as a built-in solver.** A registered model's output goes
  through `solver_diagnostics_sensitivity` the same way a QP/MILP/LP
  solver's output would (specs `0007`/`0013`) — a plugin does not get a
  lighter review because QuantSmith doesn't own its internals.
- **No company data in this repository.** The manifest, its template, and
  every agent that touches it follow the same rule as
  `instructions/role_operations.md`: real model names, endpoints, import
  paths, and formulations live only in a local, gitignored
  `model_plugins.yml`.
- **Unverified stays unverified.** A solver-reported status, objective
  value, or diagnostic is recorded as what the model claimed — not
  confirmed correct — until independently checked.

## Checks

- Does the manifest entry declare every field the adapter contract
  requires?
- Is every declared capability labeled as a claim, not treated as
  established fact?
- Does the review avoid touching the model's actual logic, weights, or
  training data?
- Is `model_plugins.yml` absent from git tracking (checked by the
  `model-plugin` gate)?
- Does a registered model's output get the same diagnostic review a
  built-in solver's output would?

## Common Failure Modes

- Trusting a plugged-in model's self-reported "optimal" status without the
  same feasibility/sensitivity review a built-in solver's output gets.
- A manifest entry that inlines real objective/constraint detail because it
  was easier than writing a schema pointer.
- `model_plugins.yml` committed by accident (bypassing `.gitignore` with a
  forced add) — the `model-plugin` gate exists specifically to catch this.
- Treating an unreviewed model (`review_status: unreviewed`) as if it were
  approved because it's already "in the manifest."

## Spec-Driven Alignment

This standard backs `adapters/model_plugin/` and
`agents/optimization/model_plugin_registration/` (spec
`0026-model-plugin-adapter`). "Contract-complete registration" and "claims
labeled, not assumed" become testable `AC-*`/`NFR-*`; an unreviewed or
unverified model treated as approved is a `RISK-*`. Backed operationally by
the `model-plugin` gate (`hooks/stages/model-plugin-check.sh`). See
`instructions/optimization.md`, `instructions/role_operations.md` (the
config-safety pattern this reuses), and
`adapters/model_plugin/adapter_contract.md`.
