# Plan: Ingestion Data Contract Emission

- **Spec:** 0039-ingestion-data-contract (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-08-11

## Approach

Add one new, self-contained, dependency-free module,
`src/quantsmith/pipelines/ingestion_data_contract.py`, split into two
halves: `validate_ingestion` (checks a caller-supplied row set against a
declared schema/key/quality-rule contract, collecting every violation)
and `render_data_contract` (renders `templates/data/data_contract.md`'s
section structure from real, computed results). No live fetch, no PIT
computation, no schema inference — see spec `Non-Goals`.

## Architecture & Components

```text
ingestion_data_contract.py
  ColumnSpec        -- name, type, nullable, description
  QualityRule        -- name, threshold, action_on_breach,
                         column, max_missing_fraction
  PointInTimeSpec     -- availability, use_original_vintage,
                         as_of_join_semantics (caller-supplied narrative)

  SchemaViolation     -- row_index, column, reason
  QualityRuleResult    -- rule, observed, passed
  IngestionValidationResult
      row_count, schema_violations, duplicate_key_count,
      missingness_by_column, rule_results
      .is_clean -> not schema_violations and duplicate_key_count == 0
                    and all(r.passed for r in rule_results)

  validate_ingestion(rows, schema, key_columns, missingness_rules)
      for each row, each declared column:
          type check via a type-name -> predicate table
              ("date" checked via datetime.date.fromisoformat on strings)
          nullability check
          -> SchemaViolation(row_index, column, reason) on failure
      key_columns tuple per row -> count duplicates by exact match
      per column: missing_fraction = missing_count / row_count
      each QualityRule -> QualityRuleResult(rule, observed, passed)
      returns IngestionValidationResult

  render_data_contract(dataset_name, owner, source_id, schema,
                        key_columns, grain, point_in_time,
                        missingness_rules, validation, lineage_access,
                        refresh_schedule, change_policy,
                        spec_id="", last_updated="")
      builds the six template sections as Markdown text, e.g.:
        "## Grain & Keys" ->
          states grain, key_columns, and the *actual* duplicate-key
          finding ("no duplicates found in the validated sample" or
          "NOT unique: N duplicate key combination(s) found in the
          validated sample")
        "## Schema" -> one row per ColumnSpec
        "## Point-in-Time Rules" -> point_in_time's narrative fields
        "## Missingness & Quality Rules" -> one row per QualityRule,
          extended with Observed/Status columns from rule_results
        "## Lineage & Access", "## Change Policy" -> caller-supplied text
```

## Interfaces & Data Contracts

`ColumnSpec`, `QualityRule`, `PointInTimeSpec` are caller-declared inputs
(frozen dataclasses). `SchemaViolation`, `QualityRuleResult`,
`IngestionValidationResult` are the computed-result types returned by
`validate_ingestion` and consumed by `render_data_contract`. Rows are
`Sequence[Dict[str, object]]` — plain dicts, no schema library. No new
external schema; the six rendered sections mirror
`templates/data/data_contract.md`'s own section headers exactly, so the
gate (`hooks/stages/data-contract-check.sh`) and any human reader can
compare the two directly.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Every rendered claim (duplicate count, missingness value, rule pass/fail) is read directly off `IngestionValidationResult`, never re-derived or hand-typed separately. |
| P10 Honest reporting | yes | Grain & Keys and Missingness statements are phrased as findings "in the validated sample" (RISK-001), never an unqualified guarantee over unseen data. |
| P8 No silent trade-offs | yes | RISK-001 through RISK-003 named with mitigations; the Missingness table's extra two columns are a disclosed enhancement (RISK-003), not a silent deviation from the template. |
| P5 Reversibility | yes | New, additive, self-contained module; no existing file (including the template itself) is modified. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `validate_ingestion` schema/nullability checks | T-001 |
| REQ-002 | `validate_ingestion` duplicate-key detection | T-001 |
| REQ-003 | `validate_ingestion` missingness/quality-rule checks | T-001 |
| REQ-004 | `render_data_contract` | T-001 |
| REQ-005 | Grain & Keys / Missingness section wording | T-001 |
| REQ-006 | `specs/README.md`, `src/quantsmith/pipelines/README.md`, root `README.md` | T-003 |
| NFR-001 | Pure functions of their inputs; no randomness | T-001 |
| NFR-002 | Standard-library only (`datetime`) | T-001 |
| NFR-003 | Rendered text satisfies `data-contract-check.sh`'s keyword checks | T-002 |
| NFR-004 | Validation gates | T-004 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Scope | Validate a caller-supplied row set already pulled | Fetch rows from a live source itself | Matches `agents/data_ingestion/*`'s existing advisory-brief precedent (mechanics guidance, not a runtime service) and the `transport`-injection boundary already drawn for `adapters/alert_delivery/`; this SDK doesn't hold credentials or make network calls. |
| Missingness table shape | Extend the template's 3 columns to 5 (`+Observed`, `+Status`) | Keep exactly 3 columns and leave computed results out of the rendered table | The template has nowhere to record actual findings; without the extra columns the contract would state rules but not their outcomes, undermining REQ-005's "state what was actually found." Disclosed in spec `RISK-003`, not silent. |
| Key uniqueness check | Exact-match tuple comparison over `key_columns` | A hash-based approximate/probabilistic dedup | Exact-match is deterministic (NFR-001), simple, and sufficient at the row counts this dependency-free slice is meant for; no need for approximate structures. |
| PIT fields | Caller-supplied narrative, passed through verbatim | Attempt to infer PIT properties from row timestamps | A raw pulled table alone doesn't carry publication-lag/vintage metadata; inferring it would be guessing, violating P10 honest reporting. Explicit Non-Goal. |

## Validation Strategy

`tests/test_ingestion_data_contract.py`, one test per acceptance
criterion (AC-001 through AC-009), following `0007`/`0013`/`0034`–`0038`'s
own per-AC test naming convention. AC-006's test additionally sources
`hooks/stages/data-contract-check.sh`'s own keyword regexes (or invokes
the script directly against a rendered fixture file) to verify gate
compatibility directly, not by assumption. Then
`hooks/stages/run-stage.sh spec agent-catalog docs-link spec-index`, the
full `pytest tests/ -q`, and `git diff --check`.

## Rollout, Observability & Rollback

Rollout is a branch commit (and push, if requested). Rollback is
reverting the single commit; no existing module or template is modified.

## Open Questions

- Should this module eventually take a `sources/<id>.yml` entry directly
  (reading its declared schema/quality fields) rather than a separately
  caller-supplied schema, once a concrete workflow wires the two
  together?
