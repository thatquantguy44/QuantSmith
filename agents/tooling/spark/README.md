# Spark Agent

## Purpose

The Spark Agent makes Spark jobs for quant data fast enough and reproducible. It
sizes partitions, finds skew and the hot keys repartitioning cannot fix, sizes
salting for them, and flags partition- or order-dependent operations that make
results change from run to run — the kind of non-determinism that silently breaks
backtest reproducibility.

## Use When

- A Spark job stalls on a few long tasks (skew) or spills (too few partitions).
- A join or aggregation is dominated by a handful of tickers, accounts, or nulls.
- Two runs of the same job on the same data give different results.
- A PySpark job needs a reproducibility review before it feeds research.

## Inputs

- Data volume and target partition size; key frequency counts for joins/aggregations.
- The PySpark code under review.
- Cluster limits (executors, memory) and the fleet pool the job runs in (`0101`).

## Outputs

- A partition count (`plan_partitions`) and a skew report (`skew_report`).
- A salting plan for hot keys (`salting_plan`) with before/after balance.
- Determinism findings (`lint_determinism`) with fixes; handoffs to
  `data_engineering/pipeline_concurrency` and `testing_validation`.

## Example Requests

- "This join on ticker takes 40 minutes and one task does all the work."
- "Our feature job gives slightly different numbers every run — why?"
- "How many partitions for 2 TB of tick data?"
- "Review this PySpark job before it feeds the factor model."

## Required Review Themes

- Partition size is planned, not defaulted (`spark.sql.shuffle.partitions`).
- Hot keys are salted or broadcast; AQE skew handling is enabled and checked.
- No unordered windows, unseeded randomness, monotonic ids, arbitrary dedup, or
  wall-clock reads in reproducible jobs.
