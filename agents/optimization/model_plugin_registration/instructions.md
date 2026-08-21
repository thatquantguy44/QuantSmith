# Model Plugin Registration Instructions

## Operating Rules

- Label every declared capability as a claim from the manifest, not a
  verified fact.
- Check the manifest against the required fields in
  `adapters/model_plugin/adapter_contract.md`; name exactly what's missing.
- Never request, infer, or reproduce the model's actual objective,
  constraints, or weights — review interface shape only.
- List unverifiable claims explicitly rather than passing them through.
- Do not advance `review_status`; recommend a status, let the human decide.
- Never write a manifest's real specifics into any file this repository
  would track — a manifest lives only in the local, gitignored
  `model_plugins.yml`.

## Checks

- Is every declared capability labeled as a claim, not treated as fact?
- Are missing required fields named specifically?
- Does the review avoid touching the model's actual logic/weights/data?
- Are unverifiable claims listed, not silently accepted?
- Does the output name a downstream handoff instead of approving the model
  itself?

## Output Contract

Use clear Markdown. Include a `Declared Capability (As Stated)` section, a
`Contract Compliance` section, an `Unverifiable Claims` section, and a
`Handoff` section.

## Spec-Driven Role

"Every claim labeled, not assumed" and "unverifiable claims listed
explicitly" trace to constitution P10 (honest reporting) and become
testable `NFR-*`; a missing contract field or an unverified claim treated as
fact becomes `RISK-*`. Backed by
`instructions/model_plugin_integration.md` and
`adapters/model_plugin/adapter_contract.md`. See
`specs/0026-model-plugin-adapter/`. Hands off to `problem_formulation`,
`solver_diagnostics_sensitivity`, and `risk`.
