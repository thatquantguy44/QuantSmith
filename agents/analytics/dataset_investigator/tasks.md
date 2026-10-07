# Dataset Investigator Agent Tasks

## Investigate A Dataset (Deterministic)

1. Run `quantsmith-dataset-investigator analyze DATA --out RUN [--target COL] [--timestamp COL] [--pii COL …] [--as-of DATE]`.
2. Read `RUN/report/investigation_report.md`; relay the key findings, quality concerns,
   hypotheses, questions, and the recommended next analysis.
3. State anything skipped, sampled, or capped (report appendix).

## Investigate A Dataset With The Model Roles

1. Run the saved workflow: `Workflow({name: "dataset-investigator", args: {dataset, out, target?, timestamp?, pii?, as_of?}})`.
2. Relay its result: report and package paths, key findings, hypothesis outcomes,
   whether the model narrative was accepted.

## Test A Specific Hypothesis

1. `quantsmith-dataset-investigator context RUN --role investigator` to see the
   findings, tools, and remaining budget.
2. Submit `{"hypotheses": [{statement, from_findings, tool, params, prediction, decision_rule}]}`
   to `quantsmith-dataset-investigator hypotheses RUN --add -`.
3. Re-run `validate`, then `report --export`.

## Reproduce A Finding

1. In the package: `dataset-investigator reproduce F007 --data DATA`
   (exit 0 reproduced, 3 evidence mismatch, 4 wrong dataset).
2. For the whole run: `dataset-investigator rerun --data DATA`.
