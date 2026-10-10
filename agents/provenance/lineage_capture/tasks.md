# Lineage Capture Tasks

## Instrument A Pipeline For Lineage

Input: a pipeline (`0011`/`0101`) and its sources.

Output: `register_source` calls at ingestion and `record_run` calls per step with
code version, parameters, and column maps.

## Trace A Number

Input: a dataset version and column that a reviewer questions.

Output: `trace` and `trace_column` results, with every gap named and a fix.

## Plan Recompute After A Restatement

Input: a restated source version.

Output: the `impact` list and the order to recompute it.

## Cite And Verify For Publication

Input: the dataset versions behind a report.

Output: `verify` results and `cite` strings for each number's point of use.

## Export Lineage To A Catalog

Input: recorded runs and a namespace.

Output: OpenLineage-shaped events from `to_openlineage`.
