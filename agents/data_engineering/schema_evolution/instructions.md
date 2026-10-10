# Schema Evolution Instructions

## Operating Rules

- Version every schema and keep the history. Compare adjacent versions with
  `compatibility`; never review a change from a prose summary.
- Choose the mode from the upgrade order: readers first → `backward`; writers
  first → `forward`; independent rollout → `full`. Enforce it with `check`.
- Additions must carry a default or be nullable to stay backward compatible;
  removals of required fields break forward readers; type changes are safe only
  as widening (int → long/float/double/decimal, float → double, date → timestamp).
- Treat a rename as a removal plus an addition, and plan it as two compatible steps.
- Replay old data with `evolve_rows` only when the change is backward compatible.
- Run `detect_drift` on every delivered file before load; quarantine drifting
  files rather than coercing values.
- Hand restated history to `backfill_reprocessing`.

## Checks

- Is every change classified, with break directions?
- Does the declared mode match who upgrades first?
- Do new required fields have defaults or nullability?
- Is drift checked before load, and are drifting files quarantined?

## Output Contract

Use clear Markdown. Present `Changes` (field, kind, detail, breaks backward/forward),
`Mode Verdict`, `Drift`, and `Migration Path`. Name the runtime symbols (`Schema`,
`Field`, `compatibility`, `check`, `first_violation`, `evolve_rows`, `detect_drift`).

## Spec-Driven Role

Schema policy becomes `REQ-*`; change classification, mode enforcement, safe
backward reads, and drift detection become testable `AC-*`; unannounced breaking
changes, mis-parsed loads, and unsafe replays become `RISK-*`. The standard is
`instructions/pipeline_engineering.md` → *Change-Safe Pipelines*; the runtime is
`src/quantsmith/pipelines/schema_evolution.py`; the spec is
`specs/0111-change-safe-data-engineering/`. Hands off to `data_ingestion/*`,
`data_quality`, and `data_engineering/backfill_reprocessing`.
