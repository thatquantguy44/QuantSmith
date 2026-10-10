# Spark Tasks

## Fix A Skewed Job

Input: key frequency counts and the slow stage.

Output: a `skew_report`, a `salting_plan` or broadcast choice, and the before/after balance.

## Size Partitions

Input: data volume and cluster size.

Output: `plan_partitions` result and the shuffle/AQE settings.

## Make A Job Reproducible

Input: PySpark code that gives different results between runs.

Output: `lint_determinism` findings, confirmed and fixed.
