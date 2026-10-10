# Backfill & Reprocessing Instructions

## Operating Rules

- Register the restated version as a new source version (`0102`); never overwrite
  the old one.
- Plan with `plan_reprocessing`; do not hand-pick tables. If lineage is missing for
  a step, fix the lineage first.
- Execute with `execute_plan` under the fleet's pools (`0101`) so a backfill cannot
  starve scheduled pipelines; use a tag that names the restatement.
- Persist each new output as it is produced (`persist`) so dependent re-runs read it.
- Compare every reprocessed dataset with `compare` on its business key; set a gate
  per dataset (e.g. `max_changed_fraction`) and justify it.
- Publish with `swap`; it moves every superseded pointer or none. Keep
  `SwapOutcome.previous` as the rollback target and record the decision.
- A blocked swap is a finding to investigate, not a reason to swap piecemeal.
- Follow `docs/restatement_runbook.md` for the operational steps.

## Checks

- Was the plan derived from lineage, and does it exclude unrelated branches?
- Are outputs new versions, with lineage tracing to the restated source?
- Did execution respect pool limits, and are failures isolated?
- Does every published dataset have a diff and a passing gate?
- Is the rollback target recorded?

## Output Contract

Use clear Markdown. Present `Plan` (runs in order), `Execution` (manifest, new
versions), `Diffs`, `Publication` (swapped or blocked, with reasons), and
`Rollback`. Name the runtime symbols (`Restatement`, `plan_reprocessing`,
`execute_plan`, `compare`, `max_changed_fraction`, `swap`).

## Spec-Driven Role

Restatement handling becomes `REQ-*`; lineage-exact planning, immutable re-runs
under limits, failure isolation, and atomic gated publication become testable
`AC-*`; stale downstream tables, over-broad recompute, and mixed old/new states
become `RISK-*`. The standard is `instructions/pipeline_engineering.md` →
*Change-Safe Pipelines*; the runtime is `src/quantsmith/pipelines/reprocessing.py`;
the spec is `specs/0111-change-safe-data-engineering/`. Hands off to
`data_engineering/pipeline_observability`, `data_quality`, and
`provenance/lineage_capture`.
