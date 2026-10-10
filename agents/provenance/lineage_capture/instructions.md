# Lineage Capture Instructions

## Operating Rules

- Register every external pull with `register_source`: dataset, version, content
  hash, `sources/` catalog id (`0027`), retrieval time, and licence if known.
- Record every transform with `record_run`: code version (commit), parameters,
  input and output versions, and a column map for every output column you can
  state. Record lineage in the code that reads the inputs — it is the only place
  that knows them.
- Never overwrite a version. A restatement is a new version label with a new hash.
- When an input is restated, run `impact` and recompute everything it lists.
- Use `trace_column` for numeric disputes; treat every gap as a lineage defect to
  fix, not an answer.
- Cite with `cite` at the point of use (`0025`); verify with `verify` before
  publishing numbers from stored rows.
- Export runs with `to_openlineage` when a catalog is the system of record.

## Checks

- Does every input trace to a registered source?
- Does every run carry a code version and serializable parameters?
- Are any column traces returning gaps for columns that appear in reports?
- Do stored rows still verify against their recorded hash?
- Does every published number carry a citation?

## Output Contract

Use clear Markdown. Present `Sources`, `Runs` (upstream first), `Column Lineage`
(with gaps), `Impact`, and `Citations`. Name the runtime symbols (`LineageGraph`,
`DatasetVersion`, `TransformRun`, `register_source`, `record_run`, `trace`,
`impact`, `trace_column`, `verify`, `cite`, `to_openlineage`) when handing off.

## Spec-Driven Role

Traceability needs become `REQ-*`; immutable versions, run validation, trace and
impact completeness, verification, and citations become testable `AC-*`; silent
overwrites, orphan outputs, guessed column lineage, and uncited numbers become
`RISK-*`. The standard is `instructions/data_provenance.md`; the runtime is
`src/quantsmith/pipelines/provenance.py`; the spec is
`specs/0102-lineage-bitemporal-provenance/`. Hands off to
`provenance/bitemporal_data`, `data_engineering/data_governance`, `data_quality`,
and `reporting-agent`.
