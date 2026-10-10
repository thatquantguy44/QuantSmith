# Ray & Dask Tasks

## Fix An Out-Of-Memory Shuffle

Input: data volume, worker memory, and key counts.

Output: `plan_partitions`, `skew_report`, and a salting or pre-aggregation plan.

## Make A Parallel Simulation Reproducible

Input: a Ray or Dask Monte Carlo or sweep.

Output: a root-seed scheme with per-task streams, verified across cluster sizes.

## Check A Pandas-To-Dask Port

Input: the original pandas code and the Dask version.

Output: `lint_determinism` findings and a sample comparison against the reference.
