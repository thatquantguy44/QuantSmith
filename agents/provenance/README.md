# Provenance Agents (`provenance/`)

The Provenance group answers the two questions every number in a quant artifact
must answer: **where did it come from?** and **what did we know, and when?** It
turns `0025`'s citation rule into evidence a reviewer can check.

## Agents

| Agent | Handles |
| --- | --- |
| `lineage_capture/` | Content-hashed dataset versions, source registration, transform-run lineage at dataset and column level, upstream trace, downstream impact of restatements, hash verification, citations, OpenLineage events (spec `0102`). |
| `bitemporal_data/` | Facts on valid time × knowledge time: vintages, restatements, retractions, as-of queries, revision trails, and look-ahead detection for backtests (spec `0102`). |

Planned (spec `0108`, see `docs/handoff.md` → What's Next #0):
`vendor_licensing_entitlements/`.

## Group Workflow

```text
data_ingestion/* (register sources, 0027 ids)
  -> provenance/lineage_capture   (record runs; trace / impact / cite)
  -> provenance/bitemporal_data   (as-of reads; revisions; look-ahead check)
  -> backtest_review, data_quality, data_engineering/data_governance, reporting
```

## Standard And Runtime

- Standard: `instructions/data_provenance.md` → *Lineage And Bitemporal Records*.
- Runtime: `src/quantsmith/pipelines/provenance.py`.
- Spec: `specs/0102-lineage-bitemporal-provenance/`.

## Rules

- A dataset version is immutable; restatements are new versions.
- Lineage is declared by the run that knows it; undeclared column lineage is a gap.
- Knowledge is never backdated; corrections append.
