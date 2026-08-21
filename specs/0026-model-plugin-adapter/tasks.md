# Tasks: Model Plugin Adapter & Registration Agent

- **Spec:** 0026-model-plugin-adapter (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-10

## Definition of Done (applies to every task)

- The adapter group matches the existing contract-only shape
  (`README.md` + `adapter_contract.md` + profile docs).
- The agent follows the four-file convention with a `Spec-Driven Role`.
- No real model name, endpoint, import path, or formulation detail anywhere
  in this slice's files.
- The gate degrades gracefully when nothing is configured.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Add the adapter contract and invocation profiles. | REQ-001, REQ-002, NFR-001 | done | `adapters/model_plugin/{README,adapter_contract,python_callable,rest_endpoint,cli_binary}.md`. |
| T-002 | Add the registration template. | REQ-003 | done | `templates/optimization/model_plugin_manifest.yml`. |
| T-003 | Add `.gitignore` protection and the `model-plugin` gate. | REQ-003, NFR-003 | done | Anchored `/model_plugins.yml`/`.yaml`; `hooks/stages/model-plugin-check.sh`, tested in all four states (unconfigured, local-filled, force-added + enforced block, missing-field). |
| T-004 | Add the registration agent. | REQ-004, NFR-001, NFR-004 | done | `agents/optimization/model_plugin_registration/`. |
| T-005 | Add the backing standard and wire catalogs. | REQ-005 | done | `instructions/model_plugin_integration.md`; `agents/README.md`, `agents/optimization/README.md`, `adapters/README.md`, `specs/README.md`. |
| T-006 | Run validation gates. | NFR-002 | done | `spec`, `agent-catalog`, `docs-link`, `spec-index`, `secret-scan`, `model-plugin`; full `pytest tests/ -q`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | Direct inspection of `templates/optimization/model_plugin_manifest.yml` | done |
| AC-002 | `hooks/stages/model-plugin-check.sh` run against a force-added `model_plugins.yml`, advisory and `QF_STAGE_ENFORCE=1` | done |
| AC-003 | `hooks/stages/model-plugin-check.sh` run with no manifest present | done |
| AC-004 | `hooks/stages/model-plugin-check.sh` run against a manifest entry missing a required field | done |
| AC-005 | Direct inspection of `agents/optimization/model_plugin_registration/instructions.md` | done |

## Follow-ups

- An executable dispatcher under `src/quantsmith/adapters/model_plugin/`
  once a concrete invocation target exists to build and test against.
- A fourth invocation profile (async/message-queue) if a concrete workflow
  needs one.
- Consider whether `optimization_orchestrator/` needs an explicit rule
  for when to prefer a registered plugin over a built-in specialist
  formulation.
