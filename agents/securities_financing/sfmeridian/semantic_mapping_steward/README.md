# Semantic Mapping Steward Agent

## Purpose

The Semantic Mapping Steward keeps SFMeridian's semantic layer tied to the
adopter's real schema and to governed definitions. It snapshots each database
profile's catalog, classifies changes, excludes queries that reference
dropped objects, validates every concept binding and governed-metric source
against the catalog and the `0081`/`0063` vocabulary, and stages the pack
amendments the mapping needs for the named pack reviewer.

## Use When

- A database profile is onboarded, or its schema may have changed.
- A metric owner adds or edits a binding in `semantic_mapping`.
- A governed metric is unavailable and someone needs to know why.
- The query repository uses a concept the `0081` pack does not define.

## Inputs

- The SFMeridian configuration: `catalog`, `semantic_mapping`,
  `governed_tier.metric_sources`, `access`, and the query repositories.
- Optionally an injected read-only connection per profile (introspection), or
  a declared catalog file.

## Outputs

- Content-addressed catalog snapshots and classified diffs.
- A drift list (`drift.json`) that removes drifted exemplars from retrieval.
- A stewardship report: bindings, governed-metric coverage, metric sources,
  amendments, caveats, handoffs, and cited findings.
- Pack-amendment proposals staged for the named reviewer (the pack is unchanged).

## Example Requests

- "We dropped a column in the loan book; which queries and metrics break?"
- "Is utilization bound correctly for the warehouse profile?"
- "Which governed metrics can the governed tier serve today?"

## Required Review Themes

- Every bound binding resolves in this run's catalog snapshot.
- Viewpoint and unit are declared; fee and rebate are never interchanged.
- No plugin-private concept; amendments stay `proposed` until a person accepts them.
- Every governed pack metric is accounted for.

## Runtime

A tested loop agent (spec `0115`): `python -m sfmeridian agent run semantic_mapping_steward`,
or `sfmeridian.steward.run_steward` from Python. Manifest:
`plugins/sfmeridian/src/sfmeridian/data/agents/semantic_mapping_steward.json`.
