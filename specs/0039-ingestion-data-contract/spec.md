# Spec: Ingestion Data Contract Emission

- **ID:** 0039-ingestion-data-contract
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-08-11

## Problem & Context

`instructions/data_ingestion.md` (spec `0031`) states every ingestion path
"emits a data contract" (`templates/data/data_contract.md`), and
`hooks/stages/data-contract-check.sh` checks one for schema, keys,
point-in-time, and missingness content when one exists — but nothing in
the SDK has ever actually produced one from real ingested data.
`agents/data_ingestion/*` are deliberately agent-contract-only (mechanics
guidance, not a runtime service), so the gap has stood open since
`0006`'s forecast spec shipped, tracked in `docs/handoff.md`'s "More
worked examples" line as "an ingestion example that emits a data
contract."

This spec closes it with a small, dependency-free, honestly-scoped
module: given a pulled raw table (rows already fetched — this slice does
not perform the fetch itself, matching how `agents/data_ingestion/*`
never touch live APIs either) and a declared schema/key/quality contract,
it validates the actual data against that contract and renders a
populated `data_contract.md` document from the **real, computed** results
— not a filled-in-by-hand template. A duplicate key, a type violation, or
a missingness breach shows up in the rendered contract because it was
actually found in the data, never because someone wrote it down.

## Goals

- Add `src/quantsmith/pipelines/ingestion_data_contract.py`:
  `validate_ingestion` (checks rows against a declared schema, key
  uniqueness, and missingness rules, collecting every violation rather
  than stopping at the first) and `render_data_contract` (emits a
  Markdown document matching `templates/data/data_contract.md`'s section
  structure, populated with the real validation results).
- Report every schema violation with its row index and column, and every
  duplicate key — collected, not just counted, so a caller can act on
  specifics.
- Compute missingness per column and check it against caller-declared
  threshold rules, reporting the actual observed value alongside each
  rule's pass/fail — the rendered Missingness & Quality Rules table
  carries real numbers, not just the rule statement.
- Never state a data property (uniqueness, completeness) that wasn't
  actually checked against the supplied rows — an honest "not unique, N
  duplicates found" when duplicates exist, never a template default like
  "the key is unique per grain" left unexamined.
- Verify the rendered output would actually satisfy
  `hooks/stages/data-contract-check.sh`'s own keyword checks (schema,
  keys, point-in-time, missingness) — checked directly in this slice's
  tests, not assumed.

## Non-Goals

- No data fetching. Rows are supplied already-pulled (a `Sequence[Dict]`);
  this slice validates and reports, it does not call an API, database, or
  file reader — that stays `agents/data_ingestion/*`'s advisory-brief
  scope (mechanics guidance, not a runtime service) and, when a concrete
  connection is needed, the adopter's own client, matching the boundary
  already drawn for `adapters/alert_delivery/`'s `transport` seam.
- No point-in-time *computation* — `PointInTimeSpec`'s fields (availability,
  vintage policy, as-of semantics) are caller-supplied narrative, not
  derived from the data, since a raw pulled table alone doesn't carry
  publication-lag metadata to compute this from.
- No schema *inference*. The caller declares the expected schema; this
  slice checks data against it, it does not guess a schema from the rows.
- No integration with `sources/*.yml` beyond referencing a `source_id` by
  name in the rendered contract — this slice doesn't read or validate the
  catalog entry itself (`hooks/stages/source-catalog-check.sh`, spec
  `0027`, already owns that).

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | `validate_ingestion` shall check every row's values against a declared schema's types and nullability, collecting every violation (row index, column, reason) rather than stopping at the first. | must |
| REQ-002 | `validate_ingestion` shall detect duplicate primary/join key combinations across the supplied rows and report the count. | must |
| REQ-003 | `validate_ingestion` shall compute per-column missingness and check it against caller-declared quality rules, reporting the observed value and pass/fail for each rule. | must |
| REQ-004 | `render_data_contract` shall emit a Markdown document matching `templates/data/data_contract.md`'s section structure (Grain & Keys, Schema, Point-in-Time Rules, Missingness & Quality Rules, Lineage & Access, Change Policy), populated from caller-supplied metadata and the real `validate_ingestion` results. | must |
| REQ-005 | The rendered contract's Grain & Keys and Missingness sections shall state what was actually found (e.g. a duplicate-key count, a rule breach) rather than a default/unexamined statement. | must |
| REQ-006 | `specs/README.md`, `src/quantsmith/pipelines/README.md`, and root `README.md` shall list the new module and its spec. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Determinism | The same rows, schema, and rules always produce the same validation result and rendered text. |
| NFR-002 | Dependency isolation | Standard-library only (`datetime` for date-shaped validation), consistent with the rest of `pipelines/`. |
| NFR-003 | Gate compatibility | The rendered contract's text satisfies `hooks/stages/data-contract-check.sh`'s keyword checks for schema, keys, point-in-time, and missingness — verified directly in this slice's tests. |
| NFR-004 | Repository hygiene | `spec`, `agent-catalog`, `docs-link`, `spec-index` gates and the full pytest suite pass. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given rows with a type violation (e.g. a string in a declared `int` column), when `validate_ingestion` runs, then the violation is reported with its row index and column. | REQ-001 |
| AC-002 | Given rows with a `null` in a non-nullable column, when `validate_ingestion` runs, then the violation is reported. | REQ-001 |
| AC-003 | Given rows containing duplicate key-column combinations, when `validate_ingestion` runs, then `duplicate_key_count` matches the actual number of duplicate rows found. | REQ-002 |
| AC-004 | Given a missingness rule with a stated threshold and rows with a known missing fraction for that column, when `validate_ingestion` runs, then the rule's reported observed value and pass/fail match the actual computed fraction. | REQ-003 |
| AC-005 | Given fully clean, valid rows with no duplicates and no missingness breaches, when `validate_ingestion` runs, then no violations are reported and every rule passes. | REQ-001, REQ-002, REQ-003 |
| AC-006 | Given a `validate_ingestion` result and contract metadata, when `render_data_contract` runs, then the output contains all six required section headers and passes `hooks/stages/data-contract-check.sh`'s own keyword checks. | REQ-004, NFR-003 |
| AC-007 | Given a validation result with duplicate keys found, when `render_data_contract` runs, then the Grain & Keys section states the uniqueness violation and the actual count — never a default "the key is unique" statement. | REQ-005 |
| AC-008 | Given the same rows, schema, and rules, when validated and rendered twice, then the validation result and rendered text are identical both times. | NFR-001 |
| AC-009 | Given `specs/README.md`, `src/quantsmith/pipelines/README.md`, and root `README.md`, when inspected, then each lists spec `0039` and `ingestion_data_contract.py`. | REQ-006 |

## Data & Dependencies

No data dependencies (no live fetch — see Non-Goals). Standard-library
only (`datetime` for validating date-shaped string values).

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A caller passes a small or unrepresentative sample of rows and the rendered contract's claims (e.g. "no duplicates found") are read as a guarantee over the full dataset. | A data contract overstates what was actually checked. | The rendered Grain & Keys/Missingness statements are phrased explicitly as "in the validated sample" (AC-007's wording), not an unqualified guarantee. |
| RISK-002 | Point-in-time fields, being caller-supplied narrative rather than computed, could be filled in carelessly or copy-pasted from an unrelated dataset. | A contract states PIT properties that don't actually hold for this data. | Out of scope for this slice to verify mechanically (Non-Goals — no PIT computation is possible from rows alone); this is the same trust boundary `templates/data/data_contract.md` already has for any manually-authored contract, not a new gap introduced here. |
| RISK-003 | The rendered Missingness table's extra `Observed`/`Status` columns (beyond the template's three) could be mistaken for a template deviation rather than a disclosed enhancement. | A reviewer expects the table to match the template's column count exactly. | Documented explicitly in `plan.md`'s trade-offs: the template has nowhere to record actual observed results, so this slice extends the table with real computed values rather than leaving them undocumented. | 

## Assumptions & Open Questions

- Assumption: validating an already-pulled row set is the right scope,
  matching `agents/data_ingestion/*`'s own advisory-brief (not live-
  service) precedent.
- Assumption: extending the Missingness & Quality Rules table with
  `Observed`/`Status` columns is worth the deviation from the template's
  exact column count, since it's what makes the contract's claims
  checkable rather than asserted.
- Open question: should this module eventually take a `sources/<id>.yml`
  entry directly (reading its declared schema/quality fields) rather than
  a separately caller-supplied schema, once a concrete workflow wires the
  two together?

## Exceptions

None.
