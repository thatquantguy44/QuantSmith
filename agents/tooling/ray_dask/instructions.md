# Ray & Dask Instructions

## Operating Rules

- Size Dask partitions and Ray Data blocks with `plan_partitions` against worker
  memory (aim well under a quarter of worker memory per partition); repartition
  after filters that shrink data.
- Measure key frequencies before `groupby`/`merge`; salt hot keys (`salting_plan`)
  or pre-aggregate them.
- Seed parallel randomness per task from a root seed and the task's stable index
  (e.g. `numpy.random.SeedSequence(root).spawn(n)`), never from worker or
  scheduling order, so results do not depend on cluster size.
- Run `lint_determinism` on the code; `drop_duplicates`, `sample` without
  `random_state`, `head`/`limit` without a sort, and wall-clock reads are
  partition- or time-dependent.
- Compare against the single-machine (pandas/numpy) reference on a sample.
- Run under a `0101` fleet pool sized to the cluster.

## Checks

- Do partitions fit worker memory with headroom?
- Are hot keys handled?
- Is every random stream derived from a root seed and a stable task index?
- Does the distributed result match the single-machine reference?

## Output Contract

Use clear Markdown. Present `Partitioning`, `Skew`, `Randomness & Seeding`, and
`Determinism`. Name the runtime symbols (`plan_partitions`, `skew_report`,
`salting_plan`, `lint_determinism`).

## Spec-Driven Role

Scale and reproducibility targets become `REQ-*`; memory-safe partitions, salted
hot keys, cluster-size-independent seeding, and reference-matching results become
testable `AC-*`; OOMs, stragglers, and scheduling-dependent randomness become
`RISK-*`. The runtime is `src/quantsmith/pipelines/distributed_compute.py`; the
spec is `specs/0112-data-engineering-tooling/`. Hands off to
`data_engineering/pipeline_concurrency` and `testing_validation`.
