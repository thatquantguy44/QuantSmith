# Shape: data-pipelines

**For:** ingestion, transformation, and serving. Everything downstream inherits
this repo's mistakes.

**Not for:** modeling. This repo's product is contracts and freshness.

## Structure

```text
pipelines/    one dir per pipeline, each with a pipeline_manifest.md
contracts/    one data_contract.md per dataset produced
src/pipelines/  the implementations
config/       schedules, retries, SLA thresholds
sources/      per-source registry
```

## Why these gates

`data-contract` and `pipeline-contract` **block**.

Shipping a dataset without a declared contract is how a silent schema change
reaches a model months later, with no way to tell when it started. The contract
is what makes that detectable at the boundary instead of at the far end.

`leakage` is advisory here, not because it matters less, but because the
point-in-time discipline this repo owes downstream is expressed in the
*contract* (availability, as-of semantics, vintage handling) rather than in a
code smell.
