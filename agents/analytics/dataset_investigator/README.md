# Dataset Investigator Agent

## Purpose

Investigates one tabular dataset (CSV, TSV, Parquet, or a pandas/Polars frame) on
demand: semantic column roles, a rule planner, registered deterministic tools across
six families (quality, distributions, relationships, segmentation, temporal,
anomalies), ranked findings, a bounded hypothesis-testing loop, a validator, a
fixed-order report, and an exported analysis package containing the modules that
actually ran, so every finding can be reproduced from the command line without a
language model. Spec `specs/0099-dataset-investigator/`; runtime
`src/quantsmith/dataset_investigator/`.

## Use When

- A new dataset arrives and someone needs to know what is in it, what is unusual,
  and what can be trusted before modeling or reporting on it.
- A pattern has been observed and needs testing against the alternatives that
  could explain it (denominator effects, confounding, concentration, mix shift).
- An analysis must be reproducible by someone else, from code, months later.

## Inputs

- A dataset path (CSV, TSV, Parquet); optionally the target and timestamp columns,
  role overrides, PII-flagged columns, an as-of date, and a seed.
- Optionally a time budget for the hypothesis loop (rounds, tool calls).

## Outputs

- `investigation_run/report/` — `investigation_report.md`, `findings.json`,
  `hypotheses.json`, figures.
- `investigation_run/analysis_package/` — the executed modules (`dataset_analysis/`),
  `manifest.json` with module hashes and finding → function → parameters → evidence,
  tests, `requirements.lock`, config, an example, and `dataset-investigator`
  (`analyze`, `reproduce`, `rerun`).
- `investigation_run/run_metadata.yaml` — run id, versions, seed, dataset
  fingerprint, every tool call with its parameters.

## How to run

- Deterministic, no model: `quantsmith-dataset-investigator analyze data.csv --out run`
  (needs `pip install quantsmith[investigator]`).
- With the model roles, as a saved Claude Code workflow:
  `Workflow({name: "dataset-investigator", args: {dataset: "data.csv", out: "run"}})`.

## Example Requests

- "Investigate `transactions.parquet`; the target is `is_fraud`."
- "What changed in this extract after May, and is it real or a change in mix?"
- "Reproduce finding F007 from last week's investigation against today's file."

## Required Review Themes

- Every reported number traces to a recorded tool execution and reproduces.
- Identifiers and free text are never analyzed as measures; PII values never appear.
- Rejected or merged claims never appear as findings; confidence is calibrated.
- Associations are never worded as causes.
- Sampling, skipped analyses, and capped loops are stated in the report.
