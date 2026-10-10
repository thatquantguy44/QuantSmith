# Ray & Dask Agent

## Purpose

The Ray & Dask Agent brings partitioning, skew, memory, and reproducibility
discipline to Python-native distributed compute — Dask DataFrames and Ray (Ray
Data, Ray Tasks) — used for feature generation, simulation, and parameter sweeps.
It sizes partitions and blocks, finds hot keys, sizes salting, and flags
order- or partition-dependent operations and unseeded randomness.

## Use When

- A Dask or Ray Data pipeline runs out of memory or crawls on a few big partitions.
- A Monte Carlo or parameter sweep must be reproducible across runs and cluster sizes.
- A `groupby`/`merge` is dominated by a few keys.
- Pandas code is being scaled out and must give the same answer as before.

## Inputs

- Data volume, target partition/block size, and worker memory.
- Key frequency counts for shuffles; the Dask/Ray code under review.
- Seeds and the random-number strategy for simulations.

## Outputs

- A partition count (`plan_partitions`) and a skew report with hot keys.
- A salting plan for hot keys; determinism findings (`lint_determinism`) with fixes.
- A reproducible seeding scheme for parallel randomness; handoffs to
  `data_engineering/pipeline_concurrency` and `testing_validation`.

## Example Requests

- "Our Dask feature job OOMs on the groupby by ticker."
- "Make this Ray Monte Carlo reproducible regardless of worker count."
- "We moved pandas code to Dask and the numbers changed slightly — why?"

## Required Review Themes

- Partitions sized for worker memory; hot keys salted.
- Parallel randomness seeded per task from a root seed, independent of scheduling.
- No partition-dependent dedup, ordering, or sampling without a seed.
- Results match the single-machine reference on a sample.
