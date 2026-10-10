# Spark Instructions

## Operating Rules

- Size shuffle partitions with `plan_partitions` (about 128 MiB each) instead of the
  default 200; enable adaptive query execution and its skew-join handling, then
  verify skew is actually gone.
- Measure key frequencies before a large join or group-by; `skew_report` lists the
  keys no repartition can fix. Salt them (`salting_plan`) or broadcast the small side.
- For reproducible jobs, run `lint_determinism` and fix every finding:
  order windows totally (`orderBy` with a unique tiebreaker), seed `rand`/`sample`,
  replace `monotonically_increasing_id` with a deterministic key, dedup with an
  ordered window instead of `dropDuplicates`, sort `collect_list` output, put
  `orderBy` before `limit`, and pass the as-of time as a parameter.
- The lint is a line heuristic: confirm each finding, and look for ordering set
  elsewhere (e.g. a window defined on another line).
- Run under a `0101` fleet pool sized to the cluster so jobs do not oversubscribe it.

## Checks

- Is the partition count planned and the skew ratio acceptable after AQE?
- Are hot keys salted or broadcast?
- Does `lint_determinism` report nothing unexplained?
- Do two runs on the same input produce byte-identical output?

## Output Contract

Use clear Markdown. Present `Partitioning`, `Skew` (before/after, hot keys,
salting), and `Determinism` (findings and fixes). Name the runtime symbols
(`plan_partitions`, `skew_report`, `salting_plan`, `lint_determinism`).

## Spec-Driven Role

Performance and reproducibility targets become `REQ-*`; balanced partitions,
salted hot keys, and run-to-run identical output become testable `AC-*`; skewed
stragglers, spills, and non-deterministic transforms become `RISK-*`. The runtime
is `src/quantsmith/pipelines/distributed_compute.py`; the spec is
`specs/0112-data-engineering-tooling/`. Hands off to
`data_engineering/pipeline_concurrency` and `testing_validation`.
