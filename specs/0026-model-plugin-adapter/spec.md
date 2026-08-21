# Spec: Model Plugin Adapter & Registration Agent

- **ID:** 0026-model-plugin-adapter
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-08-10

## Problem & Context

`agents/optimization/` gives a workflow a rich set of built-in specialist
formulations (LP, MILP, QP, conic, nonlinear, global, stochastic, robust,
DP, network flow, and application layers on top) and a solver-diagnostics
review step. It has no way to route work to a model an adopter has *already
built* internally — a proprietary allocation engine, a vendor black box, an
existing desk tool — without either reimplementing it inside this SDK (which
would require the SDK to hold proprietary logic it should never hold) or
bypassing the review discipline entirely (which would let a plugged-in model
skip the scrutiny a built-in solver gets). `adapters/` already has the right
shape for this — a boundary where an agent decides, and an adapter
translates to a provider-specific action without owning that provider's
internals — but no group existed for "provider = an already-built
optimization model."

## Goals

- Add `adapters/model_plugin/`: a registration-manifest contract plus
  invocation/result schemas, with three invocation profiles (Python
  callable, REST endpoint, CLI binary) covering the realistic ways an
  internal model is already exposed.
- Add a registration mechanism that keeps real model specifics out of this
  repository, reusing the pattern proven in spec `0024`
  (`role_context.yml`): a committed, placeholders-only template
  (`templates/optimization/model_plugin_manifest.yml`) and a local,
  gitignored `model_plugins.yml` at the repo root, protected by a
  deterministic gate.
- Add `agents/optimization/model_plugin_registration/`: the agent that
  ingests a manifest entry and produces a structured, honestly-bounded
  understanding brief — labeling every declared capability as a claim, not
  a fact, and listing what can't be verified.
- Add the backing standard `instructions/model_plugin_integration.md` and
  wire the group into `agents/optimization/`, the adapter catalog, and the
  spec index.

## Non-Goals

- No actual invocation runtime in this slice; the adapter is a contract
  (Markdown), matching the existing precedent for `llm_runtime/`,
  `data_access/`, and `alert_delivery/` (none of which have executable code
  either — only `dashboard_render/` does, because it renders to concrete,
  SDK-owned output formats). A future spec may add an executable dispatcher
  under `src/quantsmith/adapters/model_plugin/` once a concrete invocation
  target exists to build and test against.
- No behavior verification of a registered model; this agent reviews the
  *registration*, not the model's actual solving correctness — that
  remains `solver_diagnostics_sensitivity`'s job once the model is invoked
  in a real workflow.
- No automatic detection of proprietary logic accidentally pasted into a
  manifest (e.g., real objective coefficients); unlike the tracked-file
  check, which is deterministic, this would require semantic understanding
  of arbitrary YAML content. Documentation and human review are the
  safeguard here, the same posture `0025` took for its own heuristic limits.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The system shall provide a registration-manifest contract (`adapters/model_plugin/adapter_contract.md`) declaring the required fields for a plugged-in optimization model, plus invocation/result schemas. | must |
| REQ-002 | The system shall provide three invocation-shape profiles (Python callable, REST endpoint, CLI binary) documenting what each needs from a registration. | must |
| REQ-003 | The system shall provide a configuration template and local-only resolution mechanism for the registration manifest, protected by a gate that deterministically flags a tracked or staged `model_plugins.yml` (blocking under `QF_STAGE_ENFORCE=1`). | must |
| REQ-004 | The system shall provide `agents/optimization/model_plugin_registration/` on the four-file contract, which labels every declared capability as a claim, checks contract compliance, and lists unverifiable claims. | must |
| REQ-005 | The agent catalog, adapter catalog, spec index, and `instructions/optimization.md`-adjacent standard shall document the group and its no-company-data guarantee. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Agent/adapter contract consistency | Every new public agent has the four-file contract with a `Spec-Driven Role`; the adapter group has `README.md` + `adapter_contract.md` + profile docs, matching the existing adapter-group shape. |
| NFR-002 | Repository hygiene | `spec`, `agent-catalog`, `docs-link`, `spec-index`, `secret-scan`, `model-plugin` gates and the full pytest suite pass. |
| NFR-003 | Data safety | No real model name, endpoint, import path, or formulation detail anywhere in the template or docs; `model_plugins.yml` is gitignored by default. |
| NFR-004 | Honest review | The registration agent labels declared capability as a claim in every default output, never asserting it as verified fact. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given `templates/optimization/model_plugin_manifest.yml`, when inspected, then every value is an evident placeholder and no real model/endpoint/path appears. | REQ-003, NFR-003 |
| AC-002 | Given a `model_plugins.yml` staged or force-added at the repo root, when the `model-plugin` gate runs, then it is flagged, and blocks under `QF_STAGE_ENFORCE=1`. | REQ-003, NFR-003 |
| AC-003 | Given no `model_plugins.yml` present, when the gate runs, then it reports "not configured" and exits cleanly. | REQ-003, NFR-002 |
| AC-004 | Given a manifest with a registered entry missing a required field (e.g. no `review_status`), when the gate runs, then that specific missing field is reported. | REQ-003 |
| AC-005 | Given `agents/optimization/model_plugin_registration/instructions.md`, when inspected, then it requires every declared capability to be labeled a claim and every unverifiable assertion to be listed explicitly. | REQ-004, NFR-004 |

## Data & Dependencies

No data dependencies, no runtime code. The gate is a POSIX shell script
consistent with `hooks/stages/`, adding no new tooling dependency.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | An adopter inlines real objective/constraint detail into `model_plugins.yml` because a schema pointer feels like extra work. | Proprietary formulation logic sits in a local file that could later be committed by accident. | `instructions/model_plugin_integration.md` states "interface, not implementation" as a Standard; the gate's deterministic tracked-file check is the backstop even if the manifest content itself isn't policed. |
| RISK-002 | A plugged-in model's self-reported status is trusted without the diagnostic review a built-in solver gets. | An infeasible or wrong solution is acted on as if verified. | The registration agent's instructions require every claim labeled and unverifiable assertions listed; the adapter contract records solver-reported status as "unverified" by field name (`solver_status: string | null # ... unverified`). |
| RISK-003 | No executable dispatcher exists yet, so "plug in a model" is still a manual integration step for the adopter. | The feature is a contract, not a turnkey integration. | Explicitly scoped as a Non-Goal; a future spec can add `src/quantsmith/adapters/model_plugin/` once a concrete invocation target exists to build and test against, following the `dashboard_render/` precedent. |

## Assumptions & Open Questions

- Assumption: the three invocation profiles (Python callable, REST
  endpoint, CLI binary) cover the realistic shapes an already-built
  internal model takes; a fourth profile (e.g., a message-queue/async job)
  can be added the same way if a concrete workflow needs it.
- Assumption: reusing the `role_context.yml` gitignore-plus-gate pattern is
  the right level of protection for a registration manifest, consistent
  with how `0024` treated similarly sensitive local configuration.
- Open question: should a future executable dispatcher live under
  `src/quantsmith/adapters/model_plugin/`, or should invocation stay
  entirely the adopter's own integration code that merely conforms to this
  contract?

## Exceptions

None.
