# Plan: Collateral & Margin Allocation Optimizer Contract

- **Spec:** 0067-collateral-margin-optimizer-contract (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-09-09

## Approach

Add one Markdown contract doc plus two placeholder JSON templates under
`templates/optimization/`, composing `0026`'s existing registration/
invocation envelope unchanged and grounding every collateral/margin field in
an existing `0063` taxonomy/convention/lifecycle ID. Update the
`collateral_margin_optimization` agent's `instructions.md` to point at it,
close `0067`'s optimizer-boundary open question in `0063`'s tracked Draft
Decisions, and move `0067` from reserved to written in the catalogs.

## Architecture & Components

```text
0063 taxonomy/conventions/lifecycles (concept.haircut, concept.margin_amount,
  convention.collateral.haircut_ratio, convention.collateral.margin_amount,
  lifecycle.collateral)
  -> 0067 collateral_margin_optimizer_contract.md   # problem/solution field shapes
       -> collateral_margin_problem.template.json     # placeholder problem payload
       -> collateral_margin_solution.template.json    # placeholder solution payload
            -> 0026 adapter_contract.md registration envelope (unchanged)
                 -> adopter's local model_plugins.yml entry
                      -> adopter's own optimizer (external, not in this SDK)
                           -> agents/optimization/collateral_margin_optimization/
                              (reviews the registration + output, same as any
                              other plugged-in model)
```

## Interfaces & Data Contracts

Two new JSON template shapes (problem, solution) — see the contract doc for
the full field list. Both reuse `0026`'s envelope fields verbatim
(`status`, `correlation_id`, `objective_value`, `diagnostics_uri`,
`timestamp_utc`, `retryable`, `error_code`, `error_message_redacted`) so no
new review/audit handling is needed on top of what `0026` already provides.
The domain-specific portion (`inventory`, `obligations`, `constraints`,
`objective`, `allocations`, `unmet_obligations`, `substitutions`,
`explainability`) is new, and every quantity field cites its owning `0063`
ID (`convention.collateral.haircut_ratio`, `convention.collateral.margin_amount`,
`process.collateral_margin`, `lifecycle.collateral`'s states).

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Every collateral/margin field traces to an existing `0063` ID rather than inventing parallel vocabulary that could drift from the canonical pack. |
| P5 Reversibility | yes | Docs/template-only change, isolated on a branch; no runtime behavior touched. |
| P10 Honest reporting | yes | Contract and every touched doc state explicitly that no reference optimizer ships; an optimizer's reported values remain unverified until reviewed, per `0026`'s existing rule. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `templates/optimization/collateral_margin_optimizer_contract.md` | T-001 |
| REQ-002 | Field-level `0063` ID references in the contract doc and both templates | T-001, T-002 |
| REQ-003 | `collateral_margin_problem.template.json`, `collateral_margin_solution.template.json` | T-002 |
| REQ-004 | `agents/optimization/collateral_margin_optimization/instructions.md` `Spec-Driven Role` | T-003 |
| REQ-005 | `knowledge/short_term_markets/README.md`, `specs/0063.../tasks.md` Draft Decision updates | T-004 |
| REQ-006 | `agents/README.md`, `specs/README.md`, `docs/handoff.md` | T-005 |
| NFR-001 | Envelope fields copied verbatim from `adapter_contract.md` | T-001, T-002 |
| NFR-002 | Validation gates | T-006 |
| NFR-003 | Placeholder-only templates, `secret-scan` backstop | T-002 |
| NFR-004 | Explicit "no optimizer ships" language in every touched doc | T-001, T-003, T-004 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Where the schema lives | `templates/optimization/` (beside `model_plugin_manifest.yml`) | Inside `adapters/model_plugin/` | That directory's own README Design Rule states it holds registration/invocation shape only, never domain objective/constraint content — putting a domain schema there would violate its own stated boundary. |
| Optimizer boundary | Contract-only; no reference optimizer | Ship a small reference LP as `0067`'s own optimizer | Reviewer's explicit decision: a real optimizer is being built externally and needs a stable contract to fit against, not a QuantSmith-built alternative to replace or reconcile with. |
| Envelope reuse | Copy `0026`'s invocation-output fields verbatim | Define a new collateral-specific envelope | `0026` already has working review/audit semantics (`unverified until reviewed`, redaction, retry); a second envelope shape would fork that logic for no benefit and break `optimization/model_plugin_registration/`'s ability to review it the same way as any other plugin. |
| Validator | None in this slice (Markdown/JSON contract only) | A `short_term_markets_knowledge.py`-style structural validator now | No real optimizer is registered yet to validate against; matches `0026`'s own precedent of contract-first, executable dispatcher only once a concrete invocation target exists. Carried as this spec's own open question. |

## Validation Strategy

Run `hooks/stages/run-stage.sh spec docs-link spec-index doc-counts
handoff-sync agent-catalog`, then `git diff --check`. AC-001/AC-002 are
covered by direct inspection of the contract doc and both templates
(field-by-field `0063` ID cross-check). AC-003 is covered by direct
inspection of the agent's `instructions.md`. AC-004/AC-005 are covered by
direct inspection of the updated `0063` and catalog docs. AC-006 is covered
by the gate run itself. No pytest coverage is added — this is a contracts-
only spec with no executable code, matching `0026`'s own test strategy.

## Rollout, Observability & Rollback

Rollout is a branch commit (and PR, if requested). Rollback is reverting the
single commit; `0026`'s adapter, `0063`'s pack, and the
`collateral_margin_optimization` agent's prior behavior are otherwise
unmodified — this spec only adds a new schema doc and two templates plus
pointer updates.

## Open Questions

- Once a real optimizer is registered against this contract, does `0067`
  gain a structural validator, or does the `model-plugin` gate's existing
  manifest-level checking stay sufficient?
