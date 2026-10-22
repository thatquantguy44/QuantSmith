# Spec: SFMeridian — Schema Catalog, Semantic Mapping & Access

- **ID:** 0115-sfmeridian-schema-catalog-mapping-access
- **Status:** Approved
- **Author:** Joshua Lutkemuller, CFA
- **Approver:** Joshua Lutkemuller, CFA (2026-10-22: "0115 then 0116"; named
  `0081` `securities_financing_prime` pack reviewer)
- **Last updated:** 2026-10-22

> WHAT and WHY. References to the parent spec are written `0113` R-nnn /
> A-nnn / N-nnn / K-nnn (its `REQ-`/`AC-`/`NFR-`/`RISK-` IDs) so the spec gate
> never reads them as this spec's own IDs.
>
> Phase 2 of the SFMeridian roadmap
> (`specs/0113-seclending-intelligence-plugin/roadmap.md`). This child refines,
> and may tighten but not loosen, what `0113` fixes.

## Problem & Context

`0114` taught SFMeridian the adopter's queries; it does not yet know the
adopter's *schema* or what the columns *mean*. Without a catalog, nothing can
tell that a reviewed query references a column that was dropped last week
(`0113` K-004: stale SQL laundered as knowledge) or that a generated query
names a column that never existed (`0113` K-001). Without a governed mapping,
"utilization" or "fee" is whatever the nearest query says, borrower and
lender viewpoints mix, and fee and rebate are confused (`0113` K-002). Without
access controls, counterparty identity reaches callers who may not see it
(`0113` K-006).

`0113` fixes the meaning layer as governed, not plugin-private: concepts come
from the `0081` `securities_financing_prime` pack and the `0063` taxonomy, on
`0008` metrics-semantic-layer rules, and anything the pack lacks becomes a
proposed pack amendment reviewed by the named pack reviewer (owner decision
2026-10-22: Joshua Lutkemuller, CFA). The pack itself stays `draft` until that
review happens; answers built on it carry the unreviewed-pack caveat.

## Goals

- Dated, content-addressed catalog snapshots per database profile, from
  read-only introspection (SQLite, PostgreSQL, Oracle, Databricks) or a
  declared catalog file; classified diffs; drift exclusion.
- A validated semantic mapping: every binding resolves in the catalog,
  declares viewpoint, unit, point-in-time column, and evidence, and uses only
  governed vocabulary; ratio metrics divide over the same rows.
- Metric-source bindings for the governed tier, marked available or
  unavailable with reasons (the binding half of `0113` R-024).
- Pack-amendment proposals in the `0081` format, validated by `0081`'s own
  validator and staged for the named reviewer, without editing the pack.
- Caller clearance from the `0058` roster, column redaction classes enforced
  on catalog and research outputs, and credential scrubbing everywhere.
- The `semantic_mapping_steward` loop agent (coverage row C-02).

## Non-Goals

- No SQL composition, verification, or execution of metric source queries
  (`0116` builds the `Reader` and the governed tier on these bindings).
- No edit to any `0081` pack file or review block, and no acceptance of an
  amendment: that is the named reviewer's `0081` flow.
- No secret resolution inside the plugin: connections arrive injected by the
  host application; configuration holds only `secret_ref` pointers.
- No real schemas, roster, or counterparty data; fixtures are synthetic.

## Requirements

| ID | Requirement | Traces to | Priority |
| --- | --- | --- | --- |
| REQ-001 | The plugin shall take a catalog snapshot per configured profile (`catalog.<profile>`: `source: introspect` through an injected read-only connection, or `source: file` from a declared JSON/YAML-subset catalog), recording each table or view's schema, name, kind, columns (name, type, nullability, comment), primary key, and row-count estimate where the source has one; apply the profile's schema and table allowlists; identify the snapshot by a content hash that excludes the date; keep a dated history per profile; and write nothing when the content is unchanged. | `0113` R-007, R-017 | must |
| REQ-002 | Introspection shall issue only fixed, plugin-owned `SELECT` statements against each dialect's dictionary (SQLite `sqlite_master`/`pragma_table_info`; PostgreSQL and Databricks `information_schema`; Oracle `ALL_TAB_COLUMNS`/`ALL_OBJECTS`/`ALL_CONSTRAINTS`), interpolate nothing a caller supplies, match identifiers case-insensitively, tolerate missing key privileges with a note, and report driver failures as coded errors carrying no driver text. | `0113` R-007, R-020, N-004 | must |
| REQ-003 | The plugin shall diff two snapshots and classify each change — table or column removed, column retyped, nullability relaxed (breaking); table or column added (compatible) — and hand breaking changes to `data_engineering/schema_evolution`. | `0113` R-007 | must |
| REQ-004 | The plugin shall reconcile the latest snapshot against every indexed exemplar of the profile; an exemplar referencing a missing table or column is reported with what is missing and, under `drift_policy: exclude` (default), excluded from retrieval until a reconcile finds it clean; `warn` reports without excluding. | `0113` R-007, K-004 | must |
| REQ-005 | The mapping vocabulary shall be the `0081` pack selected by `governed_tier.domain_tags` (resolved through `0081` `resolve_packs`, local overlay first), the shipped pack-amendment proposals, and `0063` concept IDs; a binding to any other concept is rejected as a private definition, with the advice to propose an amendment. | `0113` R-008, R-025 | must |
| REQ-006 | Each binding (`semantic_mapping.<profile>`) shall be validated: a single-table expression of qualified catalog columns, numbers, and arithmetic only; an aggregation that respects the pack's additivity (non-additive rates are never summed); dimensions that are pack (or proposed) dimensions on the same table; a point-in-time column on the same table; a viewpoint from `lender`, `beneficial_owner`, `agent_lender`, `borrower`; the pack's unit, or a declared `source_unit` and conversion; `quote` and `day_count` for fee and rebate concepts; an owner; no duplicate concept per profile; and evidence — a reviewed, undrifted exemplar of the same profile that reads the column, or the confirmation of a configured promoter. Evidence computing a `0063` non-interchangeable concept (fee vs rebate) is refused. | `0113` R-008, R-013, K-001, K-002 | must |
| REQ-007 | The plugin shall ship pack-amendment proposals in the `0081` metric and dimension format (rebate rate, lendable value, on-loan quantity, lendable quantity, recall quantity, collateral value, days-to-cover; the borrower `counterparty` dimension), each with a rationale; validate the pack *as amended* with `0081`'s `validate_pack`; report which proposals the mapping and the query repository need; stage a needed proposal for the named pack reviewer without editing the pack; and report the pack's review status and the unreviewed-pack caveat. | `0113` R-025, R-008 | must |
| REQ-008 | Each `governed_tier.metric_sources` entry shall be validated: the metric is a pack metric with a valid binding in the source query's profile; the query is reviewed, primary, and undrifted; `period_column` is an output or point-in-time column of the query; dimension keys are pack (or proposed) dimensions; dimension and measure columns are outputs of the query; and the measure columns are exactly the binding's base measures. Any failure makes the metric `unavailable` to the governed tier, with reasons. | `0113` R-024 | must |
| REQ-009 | Caller clearance shall come from a `0058`-shaped roster named by `access.clearance_source` (`public < internal < restricted`): no roster or an empty roster means enforcement is inactive; unknown handles get `default_clearance`; an unreadable roster fails closed to `public`. | `0113` R-017 | must |
| REQ-010 | Column redaction classes (`access.column_classes` → `access.redaction_classes` → required clearance) shall be enforced: `catalog.describe` and `access.describe` report which classed columns' values the caller may see; research treats a withheld column as sensitive (values withheld, parameters redacted, a limitation recorded) and refuses it as a segment or analysis column; result rows can be masked by class. | `0113` R-017, K-006 | must |
| REQ-011 | No credential shall appear in any trace, error, log, or artifact: connections hold only `secret_ref` pointers (resolved by the host), connection and driver errors are reduced to their type, and agent traces and tool errors are scrubbed of URI passwords, `password=`/`token=`-style pairs, and bearer tokens. | `0113` R-017, N-004 | must |
| REQ-012 | Only `sfmeridian.governed` may import `quantsmith` (`0081` pack resolution and validation, `0008` metric compilation); without the SDK it reads packs as JSON from `governed_tier.packs_root` and reports compilation unavailable. Valid measure and ratio bindings shall compile to `0008` `MetricDefinition`s whose ratio metrics divide two base measures over the same rows and refuse undeclared dimensions. | `0113` N-003, R-008 | must |
| REQ-013 | The tool registry shall add `catalog.snapshot` and `catalog.reconcile` (`index`), `catalog.describe`, `catalog.diff`, `mapping.validate`, `metrics.list`, `glossary.lookup`, `mapping.amendments`, `access.describe` (`read`), and `mapping.propose_amendment` (`propose`), all in the `0113` tool contract. | `0113` R-001, R-029 | must |
| REQ-014 | `semantic_mapping_steward` shall run as a loop agent: validate configuration → index → snapshot → diff each profile → reconcile → validate mapping → list vocabulary → check amendments → stage each needed proposal → finish; escalate on invalid configuration, no catalog, or no pack; and pass four verifiers — bound bindings resolve in this run's snapshot; bound bindings declare viewpoint and unit; no private concept and no amendment marked other than `proposed`; every governed pack metric accounted for. | `0113` R-015, R-028 | must |
| REQ-015 | The SDK shall add the `semantic_mapping_steward` agent under `agents/securities_financing/sfmeridian/` with its four contract files, a `Spec-Driven Role` section, catalog rows, and regenerated registry and skills export; coverage row C-02 becomes `built`. | `0113` R-015 | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Portability | The plugin core imports only the Python 3.11+ standard library; `quantsmith` only under `governed/`. |
| NFR-002 | Determinism | Snapshots, drift lists, validation output, and steward runs are identical for identical inputs; run IDs replay. |
| NFR-003 | Safety | Introspection is fixed `SELECT`s only; no write reaches a database; no credential in any artifact. |
| NFR-004 | Data safety | Fixtures (catalogs, roster, mapping config) are synthetic and disclosed (`0025`). |
| NFR-005 | Catalog consistency | `run-stage.sh` gates pass under `QF_STAGE_ENFORCE=1`. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given the declared fixture catalog, when snapshotted twice, then the first writes a content-addressed snapshot and a dated history entry, the second writes nothing, the snapshot carries no date, and a schema allowlist narrows it. | REQ-001 |
| AC-002 | Given the research SQLite database, when introspected, then its tables, view, and column order are recorded; given injected PostgreSQL, Databricks, and Oracle connections, then only the fixed dictionary `SELECT`s run, upper-case names resolve case-insensitively, a key-privilege failure becomes a note, and a driver failure carrying a password becomes a coded error without it. | REQ-002 |
| AC-003 | Given the v1 and v2 fixture catalogs, when diffed, then the dropped column and the retype are breaking, the added column compatible, the handoff names `schema_evolution`, and identical snapshots are `unchanged`. | REQ-003 |
| AC-004 | Given the v2 catalog, when reconciled, then the two reviewed exemplars reading the dropped column (and the deprecated legacy query) are reported and excluded from search; `warn` keeps them searchable; restoring v1 clears the exclusion. (`0113` A-007) | REQ-004 |
| AC-005 | Given the resolved pack catalog, when listed, then all five `securities_financing_prime` metrics appear with the pack's units and additivity, the pack is `draft` with the unreviewed-pack caveat and the named reviewer assigned (not recorded as reviewing), proposals are `proposed`, the amended pack passes `0081` validation, staging is idempotent and never edits the pack file, unknown proposals are refused, and the glossary applies the `0063` "special" ambiguity rule. (`0113` A-029) | REQ-005, REQ-007 |
| AC-006 | Given the fixture mapping, when validated, then all nine bindings are bound; given mutations, then unknown concept, unresolved column, multi-table and function expressions, wrong-table PIT column, unit mismatch, summed rate, wrong or missing quote and day count, unknown dimension, draft evidence, duplicate, invalid viewpoint, evidence not reading the column, non-promoter confirmation, and fee-for-rebate evidence each fail with their code. | REQ-006 |
| AC-007 | Given the bound mapping, when compiled to `0008`, then utilization is a ratio of on-loan value over lendable value sliceable by security; by day and by security its slices reconcile with the totals; a counterparty slice is refused both by `0008` and by validation (lendable value has no counterparty dimension); a viewpoint mix and a rate numerator are rejected. (`0113` A-008) | REQ-006, REQ-012 |
| AC-008 | Given the fixture metric sources, when validated, then both are available; under the v2 catalog the on-loan-value source is unavailable as drifted; draft queries, wrong outputs, unknown dimensions, non-pack metrics, and wrong measure sets are unavailable with their codes. | REQ-008 |
| AC-009 | Given the fixture roster, when callers resolve, then clearances match, unknown handles get the default, an empty roster deactivates enforcement, an unreadable roster fails closed; `access.describe` and `catalog.describe` hide classed counterparty columns from an `internal` caller and show them to a `restricted` one; rows mask by class. | REQ-009, REQ-010 |
| AC-010 | Given the research fixture with counterparty identity classed `restricted`, when an `internal` caller researches the loan book, then counterparty identifiers are withheld (category values refused, a limitation recorded, no identifier in any bundle artifact); a `restricted` caller sees them; using the column as a segment is refused with `E_ACCESS_CLEARANCE`. (`0113` A-017) | REQ-010 |
| AC-011 | Given connection errors and agent arguments carrying passwords and tokens, when the steward runs, then no credential appears in the run record, trace, or any file under the index or inbox, and scrubbing handles URI, pair, and bearer forms. (`0113` A-017 credential half) | REQ-011 |
| AC-012 | Given the registry, when listed, then the ten new tools have their declared effects, all are in the `0113` contract, the steward's manifest grants no `human_only` tool, and invalid input is refused. | REQ-013 |
| AC-013 | Given the fixtures, when the steward runs, then it completes with four of five governed metrics bound, `client_debit_balance` unbound with its missing evidence, six amendments staged, and the caveat; a fresh run replays identically; under v2 it reports the breaking change, the handoff, drift, and the unavailable source; with no pack it escalates; and the verifiers reject a forged finish. | REQ-014 |
| AC-014 | Given the agent catalog, when governance validates, then `semantic_mapping_steward` has its four files, a `Spec-Driven Role` section, catalog and registry rows, an exported skill, and three built agents with three manifests validate. | REQ-015 |
| AC-015 | Given the package source, when imports are scanned, then only `governed/` imports `quantsmith`; with the SDK unavailable, packs resolve from files and compilation reports itself unavailable. | REQ-012, NFR-001 |
| AC-016 | Given malformed `catalog`, binding, and metric-source entries, when configuration loads, then each fails with its code (a private `definition` key is unknown); the shipped template validates with placeholders. | REQ-001, REQ-006, REQ-008 |
| AC-017 | Given the full suite and gates, when run under enforcement, then all pass, the fixtures are disclosed, and two steward runs on identical inputs are identical. | NFR-002, NFR-003, NFR-004, NFR-005 |

## Data & Dependencies

- `0113` (approved), `0114` (built): configuration, index, tool registry, harness.
- `0081` analytics packs (`resolve_packs`, `validate_pack`), `0008` metrics
  semantic layer (`MetricDefinition`, `SemanticLayer`), `0063` taxonomy
  (`knowledge/short_term_markets/taxonomy.json`), `0058` roster format.
- `0121` research tools (access integration).
- Synthetic fixtures under `plugins/sfmeridian/fixtures/` with a disclosure.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A binding is syntactically valid but semantically wrong (right column, wrong meaning). | Governed numbers are wrong with a clean audit trail. | Evidence must be a reviewed exemplar reading the column or a promoter's confirmation; owners are named; the pack review and `0117` golden cases test meaning. |
| RISK-002 | Drift exclusion hides a query that is still correct (e.g. a column renamed in a view). | Fewer answers. | Exclusion is reported with what is missing; `warn` policy; a reconcile against a corrected catalog lifts it. |
| RISK-003 | The pack stays `draft` indefinitely. | Every governed answer carries a caveat; write-back stays off. | Reviewer named and review scheduled; caveat is explicit rather than silent. |
| RISK-004 | A roster misconfiguration exposes counterparty identity. | Confidentiality breach. | Unreadable roster fails closed; unknown classes require `restricted`; tests cover both clearances. |

## Assumptions & Open Questions

- Assumption: adopters can supply a declared catalog file where the plugin
  has no dictionary privileges.
- Open (not blocking): first-desk collateral margin and materiality
  thresholds (carried from `0113`); SQL Server enablement.

## Exceptions

None. Recorded tightening: `0113` A-008 asks for utilization "by day and by
counterparty". Under the agency-lender viewpoint lendable value is not
allocated to borrowers, so a by-counterparty utilization would not divide the
same rows; it is refused (by validation and by `0008`) and AC-007 tests the
by-security slice instead. On-loan value and recall quantity remain sliceable
by counterparty.
