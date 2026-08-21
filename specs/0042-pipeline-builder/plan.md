# Plan: Pipeline Builder — Intent Compiler, Readiness Review, Manifest Emission

- **Spec:** 0042-pipeline-builder (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-08-12

## Approach

One new module, `src/quantsmith/pipelines/pipeline_builder.py`, importing
`DataContract`, `Pipeline`, `Step`, and `StepFn` from `data_pipeline.py`
(`0011`) and adding the design-time layer that runs *before* step
implementations exist. `data_pipeline.py` is imported, never modified.

## Architecture & Components

```text
pipeline_builder.py
  StepIntent      -- name, kind (source|transform|sink), deps,
                     contract (0011's DataContract), dataset, connection,
                     max_attempts, tested
  PipelineIntent  -- name, owner, steps, classification, schedule,
                     partitioning, retry_policy, backfill_policy,
                     idempotency_key, freshness_sla, runbook, escalation,
                     deployment_note

  ReadinessFinding -- code, severity ("blocking"|"advisory"), subject, message
  CompiledPipeline -- intent, dag_order, findings
                       .blocking_findings / .advisory_findings
                       .is_shippable = bool(dag_order) and no blocking findings

  review_readiness(intent) -> List[ReadinessFinding]
      # encodes instructions/pipeline_engineering.md's checklist
      pipeline-level blocking: no steps, no owner, no schedule,
          no retry_policy, no backfill_policy, no idempotency_key, no runbook
      pipeline-level advisory: no/invalid classification, no partitioning,
          no freshness_sla, no escalation, no deployment_note
      step-level blocking:  no output contract; invalid kind;
          source declaring dependencies; max_attempts < 1
      step-level advisory:  not tested; source/sink with no connection;
          no dataset name; transform or sink with no upstream
      # every check runs; findings accumulate in a stable, documented order

  compile_intent(intent) -> CompiledPipeline
      findings = review_readiness(intent)
      try:
          Pipeline([Step(s.name, _placeholder, s.deps, s.contract, ...)])
          dag_order = tuple(that pipeline.order)
      except ValueError as exc:            # 0011 raises for cycle,
          findings += blocking("invalid-dag", str(exc))   # unknown dep,
          dag_order = ()                                  # duplicate name
      # the placeholder Pipeline is local to validation and never returned

  render_pipeline_manifest(intent, compiled, spec_id="", last_updated="") -> str
      # templates/data/pipeline_manifest.md's six sections, plus Readiness:
      #   Ownership | Schedule | Inputs & Outputs | Reliability
      #   Observability & Runbook | DAG | Readiness
      # DAG section renders each step with its real dependencies and the
      # execution order -- not a chain implying edges that do not exist
      # Reliability/Readiness state declared-not-verified (REQ-004)

  to_pipeline(intent, step_fns) -> Pipeline
      refuse if not compile_intent(intent).is_shippable
      refuse if any step has no implementation in step_fns
      return Pipeline([Step(s.name, step_fns[s.name], s.deps, s.contract, ...)])
      # the only function that yields a runnable object
```

## Interfaces & Data Contracts

No new persisted schema. `StepIntent.contract` is `0011`'s own
`DataContract`, so a contract declared at design time is the identical
object enforced at run time — no translation layer, no drift. The
rendered manifest's shape is `templates/data/pipeline_manifest.md`, which
`hooks/stages/pipeline-contract-check.sh` already validates.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | DAG validity is decided by `0011`'s own toposort, not a second implementation that could disagree with it. |
| P10 Honest reporting | yes | Declared properties are labelled declared-not-verified (REQ-004, RISK-001); the manifest lists outstanding findings instead of presenting an unreviewed pipeline as ready. |
| P5 Reversibility | yes | Additive: one new module, one new example artifact, doc wiring. `data_pipeline.py` is imported, never edited. |
| P8 No silent trade-offs | yes | RISK-001–RISK-004 name the declared-vs-verified boundary, the placeholder trick, the cost of committing an example, and the severity-split judgement call. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `compile_intent`, placeholder-`Pipeline` validation | T-001 |
| REQ-002 | `review_readiness`, `ReadinessFinding` | T-001 |
| REQ-003 | `render_pipeline_manifest` | T-001 |
| REQ-004 | Declared-not-verified wording, Readiness section | T-001 |
| REQ-005 | `to_pipeline` | T-001 |
| REQ-006 | Generated `specs/0042-pipeline-builder/pipeline_manifest.md` | T-003 |
| REQ-007 | `specs/README.md`, `pipelines/README.md`, root `README.md` | T-004 |
| NFR-001 | Pure functions; stable finding order | T-001 |
| NFR-002 | Imports only stdlib + `data_pipeline` | T-001 |
| NFR-003 | Gate-regex test | T-002 |
| NFR-004 | Validation gates | T-005 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| DAG validation | Construct a throwaway `0011` `Pipeline` with placeholder step functions | Write a toposort inside this module | A second implementation could drift from `0011`'s and disagree about what is a valid pipeline — the one thing a build-time checker must never do. Cost: the placeholder trick needs explaining (RISK-002). |
| Graph errors | Returned as blocking findings | Allowed to raise `ValueError` out of `compile_intent` | A design review wants *all* problems at once; raising on the first structural error would hide the readiness findings behind it. `to_pipeline` still raises, because there the caller asked for a runnable object. |
| Manifest sections | Template's six, plus a disclosed seventh (`Readiness`) | Exactly six sections | The template has nowhere to record review findings; omitting them would make the manifest look clean regardless of its actual state. Disclosed, as `0039` disclosed its extra Missingness columns. |
| DAG rendering | Per-step dependency lines plus an execution-order line | The template's `a -> b -> c` chain | A topological order joined by arrows implies edges that may not exist; rendering real per-step dependencies is the honest form of the same information. |
| Example manifest | Committed at `specs/0042-pipeline-builder/pipeline_manifest.md` | Verified in tests only (`0039`'s precedent) | The `pipeline-contract` gate has never validated anything; committing a generated example makes it live. Approved explicitly for this spec; the cost is recorded as RISK-003. |

## Validation Strategy

`tests/test_pipeline_builder.py`, one test per acceptance criterion
(AC-001 – AC-010), following the per-AC naming convention used since
`0007`. AC-006 checks the rendered text against
`pipeline-contract-check.sh`'s own six regexes rather than assuming
compatibility, as `0039` did for `data-contract-check.sh`. AC-008 proves
the handoff end to end by running the bound pipeline through
`data_pipeline.run` and asserting `RunManifest.ok()`. AC-011 is verified
by running the gate itself against the committed example. Then
`hooks/stages/run-stage.sh spec agent-catalog docs-link spec-index
readme-sync pipeline-contract`, the full `pytest tests/ -q`, and
`git diff --check`.

## Rollout, Observability & Rollback

Rollout is a branch commit and push. Rollback is reverting the single
commit; removing the example manifest returns the `pipeline-contract`
gate to its previous dormant state. No existing module changes behaviour.

## Open Questions

- Should a future revision consume a `sources/<id>.yml` entry (`0027`) to
  populate a source step's connection metadata instead of taking a
  caller-supplied string? (Carried from `spec.md`.)
