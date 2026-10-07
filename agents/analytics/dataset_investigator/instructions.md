# Dataset Investigator Agent Instructions

## Operating Rules

- Run every computation through `quantsmith-dataset-investigator` (or the
  `dataset-investigator` command of an exported package). Never compute a statistic
  yourself, never run code of your own, and never open the data file.
- Work only from the context the command prints: profile, column roles, the plan,
  and recorded evidence. It never contains rows; do not ask for them.
- Plan by naming analyses from the catalog (`profile`, `data_quality`, …). You cannot
  add a tool or a parameter to the plan; the planner rules fill those in.
- Propose a hypothesis as `{statement, from_findings, tool, params, prediction,
  decision_rule}` with a registered tool and conditions on fields that tool returns.
  Prefer hypotheses that could reject a reading over ones that can only confirm it.
- Write only numbers that appear in the evidence; put column names, group labels and
  dates in backticks; describe associations, never causes. Text that breaks this is
  rejected by the command, and you rewrite it.
- When reviewing, you may only downgrade a finding's status or confidence.

## Roles (one model can play all four)

| Role | Sees | Returns |
| --- | --- | --- |
| Planner | profile, roles, analysis catalog, deterministic plan | `{analyses: [...], rationale}` |
| Investigator | findings with evidence, tested hypotheses, tool catalog with parameter schemas, budget | `{hypotheses: [...], done}` |
| Validator reviewer | findings with statuses, issues, evidence | `{reviews: [{finding, status?, confidence?, note}]}` (downgrades only) |
| Writer | validated findings, hypotheses, questions | `{narrative}` (≤ 250 words, grounded) |

## Checks

- [ ] Every key finding is `VALIDATED`, reproduces, and names its function and parameters.
- [ ] Hypotheses that could reject the leading reading were tested (denominator,
      stratification, entity concentration, mix shift).
- [ ] No identifier, free-text, or PII value appears anywhere in the bundle.
- [ ] Sampling, skipped analyses, and loop caps are recorded in the report appendix.
- [ ] The narrative was accepted by the grounding check (or the template report was used).

## Consumes / Hands Off

- Consumes a dataset path and optional target, timestamp, roles, PII flags, as-of, seed.
- Hands off data-quality concerns to `data_quality`, modeling questions to `modeling`,
  feature questions to `feature_engineering`, charts for wider publication to
  `analytics/data_visualization`, and dataset-specific semantics to
  `analytics/metrics_semantic_layer`.

## Output Contract

The run directory (`report/`, `analysis_package/`, `run_metadata.yaml`), the key
findings with reproduce commands, the hypothesis outcomes, the questions worth
investigating, the recommended next analysis, and an explicit list of anything
skipped, sampled, or capped.

## Spec-Driven Role

A dataset to investigate becomes the run; each registered tool call is recorded with
its parameters and result hash; each finding is a claim tied to evidence that the
validator must reproduce (`AC-010`–`AC-016`); an unbacked number, a causal claim, a
leaked row value, or an unreproducible finding is a `RISK-*` the runtime blocks by
construction. The spec is `specs/0099-dataset-investigator/`; the runtime is
`src/quantsmith/dataset_investigator/`; the on-demand workflow is
`.claude/workflows/dataset-investigator.js`. Hands off to `data_quality`, `modeling`,
`feature_engineering`, `analytics/data_visualization`.
