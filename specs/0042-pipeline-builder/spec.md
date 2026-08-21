# Spec: Pipeline Builder — Intent Compiler, Readiness Review, Manifest Emission

- **ID:** 0042-pipeline-builder
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-08-12

## Problem & Context

`agents/data_engineering/pipeline_builder/` has shipped as an agent
contract since the `0019` group build-out — "compile a
source→transform→sink intent into a reviewable DAG with contracts,
schedules, retries, tests, ownership, and a deployment plan" — but has
no runtime. It is one of three remaining `P1` backlog items and the one
that composes most cleanly with work already shipped.

There is a second, sharper reason to build it now.
`hooks/stages/pipeline-contract-check.sh` validates a pipeline manifest
against six required themes (owner, schedule, inputs/outputs,
retry/backfill, idempotency, runbook) whenever one exists — but **no
manifest artifact exists anywhere in this repository**, so the gate has
never validated anything; every run reports "No pipeline manifest
artifact detected." That is precisely the gap spec `0039` closed for
data contracts, and this spec closes it here.

The work is deliberately *not* a second pipeline runtime.
`specs/0011-data-pipeline-orchestration/` (`data_pipeline.py`) already
owns execution — `Pipeline`, `Step`, `DataContract`, `run`, `backfill`,
`RunManifest`, and a topological sort that rejects cycles, unknown
dependencies, and duplicate step names at construction. This spec adds
the *design-time* layer that runs before implementations exist:
compile an intent, review it against `instructions/pipeline_engineering.md`'s
checklist, render a reviewable manifest, and hand off a bound `Pipeline`
to `0011` when the code is ready.

## Goals

- Add `src/quantsmith/pipelines/pipeline_builder.py` with four public
  functions: `compile_intent`, `review_readiness`,
  `render_pipeline_manifest`, and `to_pipeline`.
- Validate the DAG **by constructing an `0011` `Pipeline`** with
  placeholder step functions, inheriting its cycle / unknown-dependency /
  duplicate-name rejection rather than reimplementing graph logic —
  composition-not-reimplementation, matching `0034`–`0036` on `0013` and
  `0041` on `0006`.
- Encode `instructions/pipeline_engineering.md`'s existing eight-item
  checklist as structured, severity-tagged findings, collecting **every**
  violation rather than stopping at the first (the `0039` discipline).
- Render a `templates/data/pipeline_manifest.md`-shaped Markdown document
  populated from the real compiled DAG and the real findings — and commit
  a rendered example at `specs/0042-pipeline-builder/pipeline_manifest.md`
  so the `pipeline-contract` gate validates real content for the first
  time.
- State every intent-declared property (idempotency, tested, retry
  policy) as **declared, not verified** — this module reviews a
  declaration, never an implementation.

## Non-Goals

- **No execution.** `0011` owns running pipelines; `to_pipeline` hands
  off to it and stops there.
- **No code generation** of step implementations. Scaffolding is
  `role_operations/rapid_scaffolder`'s concern.
- **No schedule semantics.** A schedule string's *presence* is checked;
  parsing or validating cron expressions would be false precision about a
  field this module cannot execute.
- **No deployment logic.** Deployment is captured as declared metadata
  with an explicit handoff to `agents/data_engineering/pipeline_deployment/`,
  a separate `P1` backlog item.
- **No row-level contract validation.** Checking actual data against a
  contract is `0011`'s `DataContract.validate` and `0039`'s
  `validate_ingestion`; this slice checks only that a contract is
  *declared* for each step's output.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | `compile_intent` shall validate the step graph by constructing an `0011` `Pipeline`, and shall surface a cycle, an unknown dependency, or a duplicate step name as a blocking finding rather than raising. | must |
| REQ-002 | `review_readiness` shall check an intent against `instructions/pipeline_engineering.md`'s checklist, returning every finding (not only the first), each tagged `blocking` or `advisory`. | must |
| REQ-003 | `render_pipeline_manifest` shall emit Markdown matching `templates/data/pipeline_manifest.md`'s section structure, populated from the compiled DAG order, the real per-step dependencies, and the real findings. | must |
| REQ-004 | The rendered manifest shall label intent-declared properties as declared-not-verified, and shall list outstanding findings rather than presenting an unreviewed pipeline as ready. | must |
| REQ-005 | `to_pipeline` shall bind caller-supplied step implementations into a runnable `0011` `Pipeline`, and shall refuse an intent that is not shippable or that is missing an implementation. | must |
| REQ-006 | A rendered example manifest shall be committed at `specs/0042-pipeline-builder/pipeline_manifest.md` and shall satisfy `hooks/stages/pipeline-contract-check.sh`'s six checks. | must |
| REQ-007 | `specs/README.md`, `src/quantsmith/pipelines/README.md`, and root `README.md` shall list the new module and its spec. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Determinism | The same intent always produces the same compiled order, findings (in a stable order), and rendered text. |
| NFR-002 | Dependency isolation | Standard library plus `data_pipeline` only; no third-party dependency. |
| NFR-003 | Gate compatibility | The rendered manifest satisfies `pipeline-contract-check.sh`'s six keyword checks — verified directly in tests, not assumed. |
| NFR-004 | Repository hygiene | `spec`, `agent-catalog`, `docs-link`, `spec-index`, `readme-sync`, `pipeline-contract` gates and the full pytest suite pass. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a valid multi-step intent, when `compile_intent` runs, then `dag_order` lists every step with each step appearing after all of its dependencies. | REQ-001 |
| AC-002 | Given an intent whose steps form a cycle, when `compile_intent` runs, then a blocking finding is returned, `dag_order` is empty, `is_shippable` is `False`, and no exception escapes. | REQ-001 |
| AC-003 | Given a step depending on a name not in the intent, when `compile_intent` runs, then a blocking finding naming the problem is returned. | REQ-001 |
| AC-004 | Given a step with no declared output contract, when `review_readiness` runs, then a blocking finding naming that step is returned. | REQ-002 |
| AC-005 | Given an intent with several independent defects (missing owner, missing runbook, two steps lacking contracts), when `review_readiness` runs, then a finding is returned for each — not just the first. | REQ-002 |
| AC-006 | Given a compiled intent, when `render_pipeline_manifest` runs, then the output contains all six template section headers and satisfies `pipeline-contract-check.sh`'s six keyword regexes. | REQ-003, NFR-003 |
| AC-007 | Given a compiled intent carrying findings, when the manifest is rendered, then it states the declarations are declared-not-verified and lists the outstanding findings. | REQ-004 |
| AC-008 | Given a shippable intent and a step-function map, when `to_pipeline` runs, then it returns an `0011` `Pipeline` that executes via `data_pipeline.run` and yields a `RunManifest` reporting `ok()`. | REQ-005 |
| AC-009 | Given a non-shippable intent, or a shippable one missing an implementation, when `to_pipeline` runs, then it raises `ValueError` naming the reason. | REQ-005 |
| AC-010 | Given the same intent, when compiled and rendered twice, then the findings and the rendered text are identical both times. | NFR-001 |
| AC-011 | Given `specs/0042-pipeline-builder/pipeline_manifest.md`, when `hooks/stages/run-stage.sh pipeline-contract` runs, then it reports the manifest and returns no findings. | REQ-006 |
| AC-012 | Given `specs/README.md`, `src/quantsmith/pipelines/README.md`, and root `README.md`, when inspected, then each lists spec `0042` and `pipeline_builder.py`. | REQ-007 |

## Data & Dependencies

No data dependencies. Standard library plus
`src/quantsmith/pipelines/data_pipeline.py` (`0011`).

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A reader takes the rendered manifest's "Idempotency" or "tested" entries as verified facts, when they are only what the intent declared. | A pipeline is reviewed as safe on the strength of an unverified claim. | REQ-004: the manifest states declared-not-verified explicitly and lists outstanding findings; the same posture `0026` takes for a registered model's declared capability. |
| RISK-002 | The placeholder-function trick inside `compile_intent` could be mistaken for the module being able to *run* a pipeline without implementations. | Confusion about where execution actually lives. | Documented in the module docstring and `plan.md`; the placeholder `Pipeline` is local to validation and never returned — `to_pipeline` is the only function that yields a runnable object, and it requires real implementations. |
| RISK-003 | Committing an example manifest makes the previously dormant `pipeline-contract` gate scan a file forever; if the template or the gate's regexes later change, that file becomes a standing finding. | Repository noise from a stale example. | AC-011 verifies the committed example passes today; the example is generated by `render_pipeline_manifest`, so regenerating it after a template change is a one-line reproduction, not a hand edit. |
| RISK-004 | The readiness checklist's blocking/advisory split is a judgement call; a team could disagree about which items should block. | Findings are ignored, or block work the team considers ready. | The split is documented in `plan.md`'s trade-offs; severities are data on each finding, so a caller can apply its own policy without the module changing. |

## Assumptions & Open Questions

- Assumption: reviewing a *declared* intent is the right scope, matching
  how `agents/data_engineering/pipeline_builder/` describes its own role
  (design and review, not orchestration).
- Assumption: `templates/data/pipeline_manifest.md`'s six sections are
  the right output shape; the rendered manifest adds a seventh
  (`Readiness`) to carry real findings, disclosed rather than silent —
  the same disclosed-extension choice `0039` made for its Missingness
  table.
- Open question: should a future revision consume a `sources/<id>.yml`
  entry (`0027`) to populate a source step's connection metadata, rather
  than taking it as a caller-supplied string?

## Exceptions

None.
