# Plan: Model Plugin Adapter & Registration Agent

- **Spec:** 0026-model-plugin-adapter (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-08-10

## Approach

Add one adapter group (`adapters/model_plugin/`, contract-only Markdown,
matching the `llm_runtime/`/`data_access/`/`alert_delivery/` precedent), one
new agent inside the existing `agents/optimization/` group
(`model_plugin_registration/`), and the configuration mechanism the
registration needs: a committed placeholders-only template plus a local,
gitignored manifest protected by a new gate — the exact `role_context.yml`
pattern from spec `0024`, reused rather than reinvented.

## Architecture & Components

```text
templates/optimization/model_plugin_manifest.yml   (committed, placeholders only)
  -- adopter copies to --> ./model_plugins.yml (repo root, gitignored, local)
       resolution: $QF_MODEL_PLUGINS -> ./model_plugins.yml -> none configured

adapters/model_plugin/
  adapter_contract.md   -- registration manifest schema + invocation/result schema
  python_callable.md | rest_endpoint.md | cli_binary.md   -- invocation profiles

agents/optimization/model_plugin_registration/
  ingest manifest entry -> label declared capability as claim
    -> check contract compliance -> list unverifiable claims
    -> hand off to problem_formulation | solver_diagnostics_sensitivity | risk

hooks/stages/model-plugin-check.sh
  1. deterministic: model_plugins.yml tracked/staged? -> warn/block
  2. informational: resolve and report registered-model count
  3. per-entry: required contract fields present? -> warn on gaps
```

## Interfaces & Data Contracts

`model_plugins.yml`'s `models:` list schema and the invocation Input/Output
schemas are defined in full in `adapters/model_plugin/adapter_contract.md`
(reproduced in the template's comments). No runtime schema beyond that —
this slice is contracts, docs, and a gate.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P9 Security & data | yes | Same operationalization as `0024`: gitignored by default, plus a deterministic gate check independent of `.gitignore` alone. |
| P10 Honest reporting | yes | The registration agent's core job is refusing to launder a vendor's self-reported capability into an accepted fact. |
| P4 Correct by construction | yes | A plugged-in model gets the same `solver_diagnostics_sensitivity` review a built-in solver would — no exemption for not being SDK-owned code. |
| P5 Reversibility | yes | Docs/contract/gate-only change, isolated on a branch. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `adapters/model_plugin/adapter_contract.md` | T-001 |
| REQ-002 | `adapters/model_plugin/{python_callable,rest_endpoint,cli_binary}.md` | T-001 |
| REQ-003 | `templates/optimization/model_plugin_manifest.yml`, `.gitignore`, `hooks/stages/model-plugin-check.sh` | T-002, T-003 |
| REQ-004 | `agents/optimization/model_plugin_registration/` | T-004 |
| REQ-005 | `agents/README.md`, `agents/optimization/README.md`, `adapters/README.md`, `specs/README.md`, `instructions/model_plugin_integration.md` | T-004, T-005 |
| NFR-001 | Four-file contract + adapter-group shape check | T-001, T-004 |
| NFR-002 | Validation gates | T-006 |
| NFR-003 | Placeholder-only template, gitignore, gate | T-002, T-003 |
| NFR-004 | "Claim, not fact" language required in agent instructions | T-004 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Where the new agent lives | Inside `agents/optimization/` as a 21st member | A new standalone category folder (`agents/model_plugins/`) | The agent is squarely optimization-review work (it feeds `problem_formulation`/`solver_diagnostics_sensitivity`); a new category folder for one agent would fragment the group's existing, working structure. |
| Registration safety mechanism | Reuse `role_context.yml`'s gitignore + deterministic-gate pattern | Invent a new mechanism specific to models | A registration entry is exactly as sensitive as role context (real internal specifics), so the proven pattern applies directly rather than inventing a second convention to learn. |
| Runtime scope | Contract only, no dispatcher code | Build an executable Python dispatcher now (e.g. a generic `invoke_model_plugin()`) | No concrete invocation target exists yet to build and test against honestly; a dispatcher without a real target would be untested scaffolding, the same reasoning `0022` used to defer runtime helpers. |
| Invocation profiles | Three (Python callable, REST endpoint, CLI binary) | Cover every conceivable transport (message queue, gRPC, shared file drop, …) | These three cover the realistic majority of "already-built internal model" cases; a narrow, honest set beats a speculative exhaustive one — more can be added the same way if a real workflow needs one. |

## Validation Strategy

Run `hooks/stages/model-plugin-check.sh` directly in all states (clean, a
filled local manifest, force-added, a manifest entry missing a required
field) to confirm AC-002/AC-003/AC-004, then `hooks/stages/run-stage.sh spec
agent-catalog docs-link spec-index secret-scan model-plugin`, then the full
`pytest tests/ -q` and `git diff --check`. AC-001 and AC-005 are covered by
direct inspection of the template and the agent's `instructions.md`.

## Rollout, Observability & Rollback

Rollout is a branch commit (and push, if requested). Rollback is reverting
the single commit; the gate is additive to `run-stage.sh`'s `ALL` list and
does not change any existing gate's behavior.

## Open Questions

- Should a future executable dispatcher live under
  `src/quantsmith/adapters/model_plugin/` once a concrete invocation target
  exists, following the `dashboard_render/` precedent?
- Is a fourth invocation profile (async/message-queue) needed, or do the
  three shipped here cover what adopters actually have?
