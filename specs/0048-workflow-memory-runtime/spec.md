# Spec: Workflow Memory Runtime & Author Attribution

- **ID:** 0048-workflow-memory-runtime
- **Status:** Approved
- **Author:** quantsmith
- **Approver:** repository owner
- **Last updated:** 2026-08-21

> WHAT and WHY only. No implementation detail — that belongs in `plan.md`.

## Problem & Context

`specs/0002-workflow-memory/` established the persistent memory store: a record
schema, a two-axis layout (`_shared/` facts about a source, `<workflow>/` how a
workflow uses it), a lifecycle (prime → learn → confirm → curate), and
`instructions/workflow_memory.md` as its standard. `memory/` holds a worked
example, and `memory-check.sh` guards it.

**Nothing can read it.** `0002` is the only spec in this repository with no
module under `src/quantsmith/` and no test module. Every consumer named in the
standard — the `knowledge/` agents, a run card recording "the memory version a
run used" — is prose instructing a human or a model to open YAML by hand. Three
consequences follow, and all three are load-bearing:

1. **No retrieval, so no value.** The store's entire purpose is that a workflow
   "arrives already knowing the kinks of a dataset". That requires selecting the
   relevant records and putting them in front of the workflow. Nothing selects
   anything today, so the accumulated knowledge is a filing cabinet.
2. **The gate validates strings, not records.** `memory-check.sh` greps each
   catalog for the literal text `first_seen`. One occurrence anywhere in the
   file — including in a comment — satisfies it. A record missing the field
   entirely passes, as does a `last_confirmed` that precedes its `first_seen`,
   an unknown `type`, or a duplicate `id`.
3. **The freshness rule is decorative.** `manifest.yaml` declares
   `freshness_days: 90` and the standard says to "treat old records as
   hypotheses". No code compares `last_confirmed` to anything, so a record
   written once in 2026 is served with equal authority in 2030.

Separately, the store cannot say **who** learned something. Records carry
`evidence.source_run` but no author, so a finding cannot be attributed,
questioned, or credited — and an approval workflow has no one to route to. This
matters more as the store grows past one person: the difference between "the
store says X" and "X, learned by this person, from this run, corroborated three
times" is the difference between a rumour and institutional memory.

Author attribution collides with an existing guardrail: `memory-check.sh` treats
any email address in `memory/` as PII and warns. The store must therefore carry
identity that is **structurally incapable** of being an email, rather than
relying on contributors to remember not to paste one.

This spec builds the read path and attribution. It deliberately does **not**
build the write path (see Non-Goals).

## Goals

- Make the `0002` store machine-readable: parse it into typed records.
- Make retrieval real: query by scope, type, confidence, status, and
  point-in-time bound; render a token-budgeted block for prompt injection.
- Make `memory-check` validate records rather than the presence of strings.
- Make freshness enforceable: identify records past their re-validation window.
- Attribute every record to an author, resolved from the environment, expressed
  as an opaque handle that cannot be an email address.

## Non-Goals

- **Extracting records from agent conversations (the write path).** Capturing
  knowledge nobody retrieves is the failure mode this spec exists to avoid; the
  read path must demonstrate value on the existing seed records first. A later
  spec owns ingestion.
- **An approval state machine.** `status` gains no new values here. Approval
  needs a reviewer identity to route to, which is what this spec supplies;
  the workflow itself is a later spec.
- **Multi-team namespacing and impact scoring.** Organisation-scale concerns,
  deferred until a single team's store is proven. Contradiction detection is
  **not** deferred with them: two records disagreeing about one field is a
  two-record problem, detectable without any cross-team machinery, and it is the
  failure that makes a workflow act on a lie (REQ-012).
- **Semantic contradiction detection.** REQ-012 finds records that *occupy the
  same slot* (`scope` + `type`); it does not read the statements to decide
  whether they conflict. That needs a model in the loop and is a later spec.
- **Record versioning.** Reconstructing what a record said in 2020 would let a
  point-in-time query use the contemporaneous version rather than excluding the
  record outright (see AC-017). Worth doing; it changes `0002`'s storage model
  and needs its own spec.
- **A general YAML parser.** Only the documented record subset is supported
  (see `plan.md`); anything outside it is a loud failure, never a silent
  mis-parse.
- **Mapping a handle back to a person.** The handle↔person table is
  deliberately outside this repository.
- **Changing the record schema of `0002`.** Fields are added; none are
  redefined or removed.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | Parse `memory/manifest.yaml` and every `index.yaml` / `provenance.yaml` it governs into typed `Record` objects, preserving all `0002` fields. | must |
| REQ-002 | Query records by `scope`, `type`, minimum `confidence`, and `status`, returning records in a deterministic order. | must |
| REQ-003 | Filter a query by an as-of date using a rule that depends on record `type`: mechanical types (`schema`, `quirk`, `pitfall`) are timeless and always admissible; predictive types (`pattern`, `metric`, `performance`) require `last_confirmed <= as_of`; `decision` requires `first_seen <= as_of`. Applied in addition to the `pit_scope` rule (REQ-016), enforcing the point-in-time firewall (P4). | must |
| REQ-004 | Render selected records as a text block bounded by a caller-supplied budget, dropping the lowest-ranked records first and stating how many were omitted. | must |
| REQ-005 | Validate a store and return structured findings: missing required fields, unknown enum values, duplicate ids, and dates out of order. | must |
| REQ-006 | Report every record whose `last_confirmed` is older than its store's `freshness_days` as of a caller-supplied date. | must |
| REQ-007 | Resolve an author identity from, in order: an explicit environment override, a local-only identity config, git identity, then the operating-system user. | must |
| REQ-008 | Express a resolved identity as a handle matching `^[a-z0-9][a-z0-9._-]{1,31}$`, deriving a stable pseudonymous handle when the source identity is an email or OS username. | must |
| REQ-009 | Reject any `author` value containing `@` or otherwise failing REQ-008's pattern as a validation finding. | must |
| REQ-010 | Report a record with no resolvable author as a finding, without failing the parse. | should |
| REQ-011 | Expose the store's content hash so a run card can record which memory version a run used. | should |
| REQ-012 | Report any two `active` records sharing both `scope` and `type` as a contradiction candidate requiring adjudication, unless one names the other in `coexists`. | must |
| REQ-013 | Support a `superseded_by` field naming the record that replaced this one; require it when `status` is `superseded`, require it to resolve to an existing record, and reject supersession cycles. | must |
| REQ-014 | Accept `evidence` as either a single mapping (the `0002` form) or a list of mappings, and derive a corroboration count from the number of distinct `source_run` values. | must |
| REQ-015 | Report a record whose declared `corroboration_count` exceeds its derived count, or whose `confidence` is `high` on a single evidence entry, as an unsupported-confidence finding. | must |
| REQ-016 | Exclude a record from a point-in-time-bounded query when its `pit_scope` is `original vintage only` or is unrecognised, and report an unrecognised value as a validation finding. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Dependencies | Python standard library only; no PyYAML, matching every other `pipelines/` runtime. |
| NFR-002 | Determinism | Identical store + identical query ⇒ byte-identical output, including ordering and the rendered block. |
| NFR-003 | Backward compatibility | The existing `memory/` store parses and validates with **zero edits to its record files**. |
| NFR-004 | Safety | Identity resolution reads git config and the OS username but never writes them into the store in raw form; no subprocess call blocks on network or user input. |
| NFR-005 | Failure mode | An unparseable file names the file and line and raises; it never yields a partially-populated record. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given the committed `memory/` store, when it is loaded, then every record in `_shared/datasets/example_prices/provenance.yaml` and `quant_researcher/index.yaml` is returned with all `0002` fields populated and no file edits are required. | REQ-001, NFR-003 |
| AC-002 | Given a loaded store, when queried for `scope="field:volume"`, then only `MEM-0003` is returned. | REQ-002 |
| AC-003 | Given a loaded store, when queried twice with the same arguments, then the two results are identical in content and order. | REQ-002, NFR-002 |
| AC-004 | Given a record whose `pit_scope` is `"original vintage only"`, when queried with an as-of date, then it is excluded from a point-in-time-bounded query and included in an unbounded one. | REQ-016 |
| AC-005 | Given three records and a budget admitting two, when rendered, then two records appear, the omitted count is stated, and the dropped record is the lowest-ranked. | REQ-004 |
| AC-006 | Given a record missing `last_confirmed`, when the store is validated, then a finding names that record id and that field — where the current gate reports nothing. | REQ-005 |
| AC-007 | Given two records sharing an `id`, when the store is validated, then a duplicate-id finding is returned. | REQ-005 |
| AC-008 | Given a record whose `last_confirmed` precedes its `first_seen`, when the store is validated, then a date-order finding is returned. | REQ-005 |
| AC-009 | Given a record last confirmed 200 days before the as-of date and a store `freshness_days` of 90, when decay is checked, then the record is reported stale; at 30 days it is not. | REQ-006 |
| AC-010 | Given `QF_MEMORY_AUTHOR` is set, when an author is resolved, then that value is used and no git or OS lookup occurs. | REQ-007 |
| AC-011 | Given no override and no identity config, when an author is resolved from a git email, then the handle matches REQ-008's pattern, contains no `@`, and is identical across repeated resolutions of the same email. | REQ-007, REQ-008 |
| AC-012 | Given two different source identities, when both are resolved, then their handles differ. | REQ-008 |
| AC-013 | Given a record with `author: someone@example.com`, when the store is validated, then a finding is returned — and the same record trips the existing PII scan, so the two guards agree. | REQ-009 |
| AC-014 | Given a store loaded twice with no change, when its version hash is taken, then the two hashes are equal; when any record changes, they differ. | REQ-011 |
| AC-015 | Given a file containing YAML outside the supported subset, when it is loaded, then a parse error naming the file and line is raised and no records from that file are returned. | NFR-005 |
| AC-016 | Given a `quirk` record first seen in 2026, when queried as of 2020, then it is returned — a mechanical fact about the data was true before anyone wrote it down. | REQ-003 |
| AC-017 | Given a `pattern` record with `first_seen` 2018 and `last_confirmed` 2026, when queried as of 2020, then it is excluded — the record as it stands was shaped by data through 2026. | REQ-003 |
| AC-018 | Given a `decision` record made in 2026, when queried as of 2020, then it is excluded; when queried as of 2027, then it is returned. | REQ-003 |
| AC-019 | Given two `active` records sharing `scope` and `type`, when the store is validated, then a contradiction-candidate finding names both ids. | REQ-012 |
| AC-020 | Given the same pair where one names the other in `coexists`, when the store is validated, then no contradiction finding is returned; and when one is later marked `superseded`, the pair is likewise not reported. | REQ-012 |
| AC-021 | Given a record with `status: superseded` and no `superseded_by`, a record whose `superseded_by` names no existing record, and a pair of records superseding each other, when the store is validated, then each yields its own finding. | REQ-013 |
| AC-022 | Given one record using `0002`'s single-mapping `evidence` and another using a list of three entries naming two distinct runs, when both are loaded, then both parse and their derived corroboration counts are 1 and 2 respectively. | REQ-014, NFR-003 |
| AC-023 | Given the committed store, when it is validated, then `MEM-0001` (declared `corroboration_count: 4`, one evidence entry) yields an unsupported-confidence finding — the seed records claim corroboration they do not evidence, and the gate says so. | REQ-015 |

## Data & Dependencies

- **Reads:** `memory/manifest.yaml`, `memory/**/index.yaml`,
  `memory/**/provenance.yaml` — all committed, metadata-only, already
  secret/PII-scanned by `memory-check.sh`.
- **Reads (identity, never stored raw):** `QF_MEMORY_AUTHOR`, a local-only
  `identity.yml` (gitignored, following the `role_context.yml` precedent from
  `0024`), `git config user.email`, and the OS username.
- **Consumed by:** `hooks/stages/memory-check.sh` (validation and decay), the
  `agents/knowledge/*` agents (retrieval), and `templates/docs/run_card.md`
  (memory version).
- **Access:** records inherit `access_level` from the manifest; retrieval must
  not return a record above the caller's level. Enforcement of that barrier is
  in scope for validation reporting; caller-level enforcement is the retrieving
  agent's responsibility.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A hand-rolled YAML subset parser mis-reads a file that a real YAML parser would read differently, silently corrupting a record. | High — wrong memory is worse than no memory. | Support only the documented subset; raise on anything else (NFR-005, AC-015) rather than guessing. The subset is fixed by the files `0002` already commits, and those files are the parser's fixtures. |
| RISK-002 | A pseudonymous handle is treated as anonymity. It is not: the mapping table exists, and a small team is re-identifiable from the handle plus commit history. | Medium — a false privacy promise. | State plainly in the module docstring and in `instructions/workflow_memory.md` that the handle is pseudonymous, not anonymous. |
| RISK-003 | Freshness reporting is advisory, so stale records keep being served. | Medium — the exact failure `0002` named ("serving stale schema memory after the schema changed"). | Report decay as a gate finding, blocking under `QF_STAGE_ENFORCE=1`; make `last_confirmed` visible in every rendered block so a reader can discount it. |
| RISK-004 | The point-in-time filter is only as good as `pit_scope`, which is free text today (`"<= decision date"`, `"original vintage only"`). | High — a wrong filter reintroduces leakage, which P4 forbids. | Interpret only the two documented forms; treat any unrecognised `pit_scope` as **excluded** from point-in-time queries, so the failure is a missing record, never a leaked one (REQ-016). The type-based rule (REQ-003) applies independently, so a record must clear both — `pit_scope` being free text cannot on its own admit a record the type rule excludes. |
| RISK-006 | The store is itself look-ahead: knowledge recorded in 2026 did not exist in 2020, so serving it to a 2020 backtest leaks the future. | High — subtle, silent, and exactly the class P4 exists to prevent. | REQ-003's type-based rule. Mechanical facts (`schema`/`quirk`/`pitfall`) are admitted because they describe the data's construction, not an outcome; claims about what worked are bounded by `last_confirmed`, because corroboration is where the future enters a record. |
| RISK-007 | Contradiction detection (REQ-012) fires on records that legitimately coexist — a field with three distinct quirks — and a noisy gate trains people to ignore it. | Medium — a gate nobody reads is worse than no gate. | The check is self-quieting: adjudicating a pair by marking one `superseded` (REQ-013) removes it from the `active` set, so it is never reported again. `coexists` is the escape hatch for pairs that are deliberately both live, so silencing is explicit and reviewable rather than achieved by deleting a record. |
| RISK-008 | Deriving corroboration (REQ-014/REQ-015) makes the committed seed records fail validation on day one — `MEM-0001` claims 4 corroborations and evidences 1. | Low, and intended. | Loading still succeeds (AC-001); only validation reports. The finding is correct: those numbers are unsupported claims, which is the disease this spec exists to treat. Fixing the seed data means adding the runs that justify the count, or lowering the count — both honest outcomes. |
| RISK-005 | Rendering "the most relevant records" ranks by confidence and recency, which are proxies for usefulness, not measures of it. | Low-Medium — a useful record is dropped under budget. | State the ranking rule in the output; report the omitted count (AC-005) so truncation is never silent. |

## Assumptions & Open Questions

- Assumption: the record files committed under `memory/` are representative of
  the subset the parser must support. If an adopter's store uses richer YAML,
  they get a loud failure and can extend the parser.
- Assumption: `git` may be absent (a copied scaffold, a container); resolution
  falls through to the OS user without erroring.
- Open question: should `access_level` filtering be enforced *inside* `query`
  rather than reported? Deferred until a caller exists that has a level to
  enforce against.
- Open question: the salt for handle derivation — repo-constant (handles are
  comparable across clones) or per-store (handles are not correlatable between
  repositories). Starting repo-constant; the alternative is a one-line change.
- Open question: `decision` records are bound by `first_seen` (AC-018) on the
  reading that a decision is an event that existed from the moment it was made.
  The competing reading is that a decision made in 2026 encodes 2026 knowledge
  and should never inform a 2020 backtest at all. Starting with the former
  because a decision record is usually consulted for *what we chose and why*,
  not as a signal — but a workflow using decisions as inputs should override it.
- Assumption: excluding a predictive record whose `last_confirmed` postdates the
  as-of date (AC-017) is stricter than necessary in the case where the record's
  statement never changed. Without record versioning we cannot tell, so we take
  the strict reading; record versioning would replace it with the
  contemporaneous version instead.

## Exceptions

None. This spec adds a runtime and tests to a standard that already exists; it
introduces no deviation from `instructions/engineering_principles.md`.
