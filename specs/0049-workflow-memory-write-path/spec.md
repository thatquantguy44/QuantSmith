# Spec: Workflow Memory Write Path

- **ID:** 0049-workflow-memory-write-path
- **Status:** Approved
- **Author:** quantsmith
- **Approver:** repository owner
- **Last updated:** 2026-08-21

> WHAT and WHY only. No implementation detail — that belongs in `plan.md`.

## Problem & Context

`specs/0002-workflow-memory/` defined the store; `specs/0048-workflow-memory-
runtime/` made it machine-readable — a parser, typed `Record`s, point-in-time-
aware `query`, `validate`, and freshness. `specs/0057-knowledge-console/` made
it legible to a human. Every one of these is a **reader**. Nothing writes.

The only way a new record enters `memory/` today is a person hand-editing
YAML. That is the exact failure `0048`'s own problem statement named for the
read path — "the accumulated knowledge is a filing cabinet" — and it applies
with more force to writing: a workflow that learns something has no way to
say so, so nothing gets learned unless someone remembers to transcribe it by
hand, in the right shape, days after the run that produced it.

Several runtimes already produce exactly the kind of structured finding a
memory record should be built from — they just have nowhere to send it.
`validate_ingestion` (`0039`) returns `SchemaViolation`s and
`QualityRuleResult`s naming a real column and a real rule, not prose.
`walk_forward` (`0046`) reports a real fold-distribution `performance`.
`fred_point_in_time` (`0045`) knows a real vintage `quirk`. `factor_risk_model`
(`0038`) computes a real `metric`. Capture belongs at this **runtime
boundary** — where a real row, fold, or vintage was actually examined — not at
the gate boundary, where a gate finding names a source file
("negative `.shift()`") with no dataset scope to attach a memory record to.

A second gap blocks writing specifically: `0048` defined `Record.author` and a
validator that rejects an author shaped like an email address (REQ-009), but
never built the function that *resolves* an author in the first place
(`0048`'s own handoff notes list "author handles" as outstanding). A write
path that stamps authorship on every accepted record needs that resolution to
exist. This spec builds it — closing `0048`'s REQ-007/REQ-008 — because
`promote` cannot ship without it, not as separate, deferred work.

The store's own standard (`instructions/workflow_memory.md`) already names the
lifecycle this spec implements: *"Learn (write): after a run, append new
observations as candidate records with provenance and low confidence."* This
spec is what makes that sentence executable.

## Goals

- Let a pipeline propose one or more candidate records at the moment it
  actually observes something, from a small, generic input shape any runtime
  can construct — without importing that runtime's domain types into the
  memory module.
- Stage proposals into a **committed** location, separate from the live
  store, so nothing is silently promoted and a proposal survives to be
  reviewed in a normal pull request.
- Make review real: a pull request touching `memory/inbox/` *is* the approval
  workflow — reviewable in a diff, mergeable or not, with git's own history as
  the audit trail. No separate approval database or state machine.
- Provide one deliberate, human-invoked action — `promote` — that turns an
  accepted candidate into a real record: assigns its id, stamps its author and
  `first_seen`, and appends it to the live catalog it belongs to.
- Provide the matching negative action — `discard` — that removes a candidate
  without promoting it, leaving the removal commit as the record of that
  decision.
- Finish `0048`'s outstanding author-resolution requirements (REQ-007,
  REQ-008): resolve an identity from environment, local config, or git/OS,
  expressed as a handle structurally incapable of being an email address.
- Prove the whole path works against a real runtime, not a synthetic example:
  one producer integration, from `0039`'s `validate_ingestion` findings to
  staged candidates.

## Non-Goals

- **Automatic promotion.** No candidate is ever promoted by a script running
  unattended, regardless of confidence, corroboration, or how clean the
  proposing run was. Promotion is always a deliberate call — a human running
  `promote` locally, or merging the PR that already contains it (see
  Assumptions). Removing the human is a different, much riskier spec.
- **A reviewer/approver identity or RBAC system.** `resolve_author` records
  *who proposed* a candidate; it says nothing about who is authorized to
  accept one. Today that authority is "whoever can run `promote` or merge to
  `main`" — the same authority the repository's git permissions already grant
  and gate. A first-class reviewer role is a later spec, if adoption shows the
  gap matters.
- **Automatic contradiction resolution.** `0048`'s `validate` already detects
  two `active` records sharing `scope`+`type` (REQ-012). `promote` surfaces
  that as a warning when it would create such a pair; it does not choose a
  winner, mark one `superseded`, or block the promotion. A human decides.
- **Wiring every candidate producer.** `0039` is this spec's one worked
  integration, chosen because its findings already carry a column and a rule —
  the clearest case that a memory record and a validation finding are the
  same fact in two shapes. `0046`, `0045`, and `0038` are named in the
  Problem & Context as the next-obvious producers; wiring them is follow-up
  work per producer, not blocked on anything here (REQ-009's contract is
  generic precisely so they can each add a thin translator later).
- **A console/UI for the inbox.** `0057`'s knowledge console is deliberately
  read-only (its own NFR-003); this spec does not add a write surface there.
  Reviewing a proposal happens in its pull request, or via this spec's CLI.
- **Changing `0048`'s record schema, enums, or point-in-time rules.** No new
  `status` value, no new `type`. A candidate becomes a `Record` at promotion
  using exactly `0048`'s existing shape; "proposed" is a *location*
  (`memory/inbox/`), never a new lifecycle state on the record itself.
- **External or non-git-committed staging.** The inbox is committed, matching
  `memory/`'s own default (`manifest.yaml`'s `persistence: committed`). A
  workflow using `persistence: external` memory is out of scope for staging
  too; its write path is a variant this spec does not design.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | Resolve an author identity from, in order: an explicit environment override, a local-only identity config, git identity, then the operating-system user; never block, prompt, or raise when none resolve. (Completes `0048` REQ-007.) | must |
| REQ-002 | Express a resolved identity as a handle matching `0048`'s author pattern (`^[a-z0-9][a-z0-9._-]{1,63}$`), deriving a stable pseudonymous handle when the source identity is an email or OS username; the same source identity always derives the same handle. (Completes `0048` REQ-008.) | must |
| REQ-003 | Accept a candidate as a generic input — `scope`, `type`, `statement`, `confidence`, `pit_scope`, one or more evidence entries, and the target catalog file it belongs to — constructible by any pipeline without that pipeline importing pipeline-specific types into the memory module. | must |
| REQ-004 | Build one or more candidates from a batch of such inputs, tagged with the proposing `workflow` and a `source_run`, without writing anything to disk. | must |
| REQ-005 | Serialize a batch of candidates deterministically to a committed file under `memory/inbox/<workflow>/<source_run>.yaml`, in the same YAML subset `0048`'s parser already reads. | must |
| REQ-006 | Load every staged candidate under `memory/inbox/`, tagged with its source file, without ever merging them into a live-store query or point-in-time result. | must |
| REQ-007 | Promote one staged candidate into the live store: assign a unique id (checked against the live store and every other already-promoted id in this run), resolve and stamp `author` unless the caller supplies one explicitly, stamp `first_seen` and `last_confirmed` to the promotion date unless the caller supplies one explicitly, and append the resulting record to its declared target catalog file without disturbing any other record already in that file. | must |
| REQ-008 | Remove a promoted candidate from the inbox file it came from as part of promotion; leave every other candidate in that file untouched. | must |
| REQ-009 | Refuse to promote a candidate that would fail `0048`'s `validate` once built into a record (missing/invalid field, bad date order, malformed author), or whose assigned id would collide with an existing one; report why, promote nothing. | must |
| REQ-010 | Warn, without refusing, when promoting a candidate would create two `active` records sharing `scope` and `type` (a `0048` REQ-012 contradiction candidate) — the decision is the human's, not the tool's. | must |
| REQ-011 | Discard one staged candidate from the inbox without promoting it, leaving every other candidate in that file untouched. | must |
| REQ-012 | Provide one worked producer integration: translate `0039`'s `IngestionValidationResult` (schema violations and failed quality-rule results) into this spec's generic candidate-input shape, scoped to a caller-supplied dataset. | must |
| REQ-013 | Provide a standard-library CLI exposing propose+stage, list-inbox, promote, and discard as human-runnable commands. | must |
| REQ-014 | `templates/docs/run_card.md` records which candidates a run proposed, alongside its existing "memory version used" field. | should |
| REQ-015 | The memory gate reports a staged candidate file that fails to parse or is missing a required candidate field, the same way it already reports a malformed live record. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Dependencies | Python standard library only, matching `0048`/`0057`. |
| NFR-002 | No network, no external state | `propose`, `stage`, `promote`, and `discard` only ever read/write files already inside the repository's `memory/` tree; no database, no network call, no credential. |
| NFR-003 | Determinism | Identical candidates staged twice, or promoted against an identical store, produce byte-identical YAML — a reviewer's PR diff is exactly the new content, never incidental reformatting. |
| NFR-004 | Non-destructive writes | Promoting or discarding one candidate never changes the field values of, drops, or duplicates an unrelated record already present in a live catalog or another inbox file — the catalog file is re-serialized deterministically, so its bytes may change, but every other record's parsed content does not. |
| NFR-005 | Irreversibility boundary | `propose` and `stage` never mutate the live store. Only `promote` does, and only when explicitly invoked — never as a side effect of proposing, staging, validating, or running the gate. |
| NFR-006 | Failure mode | An unparseable inbox file, or one missing a required candidate field, is reported by id/file/reason; it never silently promotes partial or wrong data. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given `QF_MEMORY_AUTHOR` is set, when an author is resolved, then that value is used and no git or OS lookup occurs. | REQ-001 |
| AC-002 | Given no override and no identity config, when an author is resolved from a git email, then the handle matches REQ-002's pattern, contains no `@`, and is identical across repeated resolutions of the same email. | REQ-001, REQ-002 |
| AC-003 | Given two different source identities, when both are resolved, then their handles differ. | REQ-002 |
| AC-004 | Given no git and no OS-resolvable identity, when an author is resolved, then the call returns `None` rather than raising or blocking. | REQ-001 |
| AC-005 | Given three candidate inputs sharing one `source_run` and `workflow`, when they are proposed, then three candidates are built in memory and no file under `memory/` changes. | REQ-003, REQ-004, NFR-005 |
| AC-006 | Given a proposed batch, when it is staged, then `memory/inbox/<workflow>/<source_run>.yaml` is created (or appended to) containing exactly those candidates, parseable by `0048`'s existing YAML-subset parser. | REQ-005 |
| AC-007 | Given the same batch staged twice, when the two files are compared, then they are byte-identical. | REQ-005, NFR-003 |
| AC-008 | Given two staged inbox files across two workflows, when the inbox is loaded, then candidates from both are returned, each tagged with its source file, and neither appears in a `0048` `query`/`point_in_time_filter` result over the live store. | REQ-006 |
| AC-009 | Given a valid staged candidate, when it is promoted, then the returned record has a unique id, a resolved author, `first_seen`/`last_confirmed` set to the promotion date, and is present in its declared target catalog file; every record already in that file parses back with identical field values to before the promotion (the file's bytes may change — re-serialization is deterministic, not byte-preserving — but no existing record's content does). | REQ-007, NFR-004 |
| AC-010 | Given a promotion, when the target inbox file is inspected afterward, then the promoted candidate is gone and every other candidate in that file is untouched. | REQ-008 |
| AC-011 | Given a candidate missing a required field, when promotion is attempted, then it is refused, nothing is written to the live store or the inbox, and the reason names the missing field. | REQ-009, NFR-006 |
| AC-012 | Given a candidate whose caller-supplied id already exists in the target catalog, when promotion is attempted, then it is refused with a collision reason. | REQ-009 |
| AC-013 | Given an `active` record already in the store with the same `scope` and `type` as a candidate being promoted, when promotion runs, then the record is still promoted and a contradiction warning is returned alongside it. | REQ-010 |
| AC-014 | Given a staged candidate, when it is discarded, then it is removed from its inbox file, every other candidate in that file is untouched, and nothing is added to the live store. | REQ-011 |
| AC-015 | Given a real `IngestionValidationResult` with one schema violation and one failed quality rule, when candidates are built from it for a named dataset, then two candidate inputs are produced, each with a `scope` naming the violating column/rule and a `source_run` traceable back to the validation call. | REQ-012 |
| AC-016 | Given the CLI, when `propose`, `list-inbox`, `promote`, and `discard` are each invoked against a scratch `memory/` tree, then each performs exactly the corresponding library action and prints a result a human can read without opening YAML by hand. | REQ-013 |
| AC-017 | Given a run that staged two candidates, when its run card is rendered from the template, then a "Memory proposed" entry lists them, next to the existing "Memory version used" field. | REQ-014 |
| AC-018 | Given an inbox file with a record missing `pit_scope`, when the memory gate runs, then it reports that file and field the same way it reports a malformed live record — not silently, not only at promotion time. | REQ-015, NFR-006 |

## Data & Dependencies

- **Reads/writes:** `memory/inbox/<workflow>/<source_run>.yaml` (new, committed);
  `memory/<workflow>/index.yaml` and `memory/_shared/datasets/<ds>/
  provenance.yaml` (existing live catalogs, appended to only by `promote`).
- **Reads (identity, never stored raw):** `QF_MEMORY_AUTHOR`, a local-only
  `identity.yml` (gitignored, following the `role_context.yml` precedent from
  `0024`), `git config user.email`, the OS username.
- **Imports:** `quantsmith.pipelines.workflow_memory` (this spec extends it —
  `Record`, `validate`, `rank_key`, the YAML-subset parser); consumed by
  `quantsmith.pipelines.ingestion_data_contract` (the worked producer) and a
  new CLI entry point.
- **Consumed by:** a human reviewer (via the CLI or a pull-request diff of
  `memory/inbox/`); `templates/docs/run_card.md`; future producer
  integrations named in Non-Goals.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A future caller wires `promote` into an unattended job, and memory starts accepting itself without review. | High — defeats the entire reason staging exists. | `promote` is a library call with no scheduled/automatic caller anywhere in this spec, and NFR-005 makes "never a side effect" a tested property, not a convention. The CLI requires an explicit human-typed command; nothing here proposes a cron job. |
| RISK-002 | Auto-assigned ids collide under concurrent promotion (two branches promoting around the same time). | Medium — a broken store on merge. | `promote` checks collision against the live store at call time (REQ-009/AC-012); because staging and promotion both happen through normal git history, a real collision surfaces as an ordinary merge conflict on the catalog file, which git already handles and a human already resolves. |
| RISK-003 | `resolve_author` is mistaken for identity verification rather than convenience attribution. | Low-Medium — over-trusting a self-reported handle. | Same caveat `0048`'s RISK-002 already states for the handle: pseudonymous, not anonymous, not authenticated. This spec inherits that limitation rather than silently expanding its meaning; the CLI accepts an explicit `--author` override precisely because self-resolution is a default, not a guarantee. |
| RISK-004 | A producer integration (REQ-012) turns *every* validation finding into a memory record, flooding the store with noise no one reviews. | Medium — the "filing cabinet" failure, inverted into a firehose. | `candidates_from_validation` proposes candidates; it does not stage or promote them automatically (Non-Goals). Whether to stage a given run's candidates is a decision `ingestion_data_contract`'s caller makes, not something this spec forces on every validation call. |
| RISK-005 | A malformed or half-written inbox file is merged and silently ignored until someone runs `promote` and gets a confusing error. | Medium — a silent gap between "looks committed" and "actually stageable". | REQ-015/AC-018: the memory gate validates inbox files the same run it validates live ones, so a broken candidate file is a gate finding on the PR that introduced it, not a surprise later. |
| RISK-006 | `first_seen` set to the promotion date (not the observation date) understates how long a fact has actually been true, for a `decision`-type candidate whose `0048` REQ-003 admissibility rule keys on `first_seen`. | Low — conservative, not a leakage risk. | Deliberate: per `0048`'s P4 firewall reasoning, a record's claim to be "known" starts when someone vetted it, not when a script guessed it. This can only make a candidate *inadmissible* to an earlier `as_of` query than a "true" observation date would, never the reverse — the same safe-direction asymmetry `0048` chose for `pit_scope` (RISK-004 there). | 

## Assumptions & Open Questions

- Assumption: this repository's normal pull-request review is the approval
  workflow. A team without PR review as a practice would need a different
  gate before `memory/inbox/` merges reach `main` — not something this spec
  can enforce from inside the repo.
- Assumption: `promote`/`discard` run locally, against a checkout the operator
  can already commit to. Neither needs new credentials beyond what committing
  to the repo already requires.
- Assumption: one candidate names exactly one target catalog file at proposal
  time (via `REQ-003`'s explicit `target_catalog`), rather than the write path
  inferring which file a `scope` belongs to. Inference is guessable wrong in a
  way that silently misfiles a record; the proposer already knows where it
  belongs.
- Open question: should `promote` support promoting a whole inbox file in one
  call, versus one candidate at a time? Starting with one-at-a-time (simpler
  to reason about per AC-009/AC-010); a batch convenience wrapper is a small
  addition later if reviewing one-by-one proves tedious.
- Open question: today's contradiction warning (REQ-010) is advisory text
  returned to the caller. Should the CLI refuse-by-default and require an
  explicit `--force` past a contradiction warning? Left open; starting
  permissive (warn, don't block) so a legitimate `coexists` pair is never
  blocked by construction, matching `0048`'s own RISK-007 reasoning.
- Open question: `identity.yml`'s exact schema (beyond "carries an identity
  QF_MEMORY_AUTHOR can also express") is left to implementation; it follows
  `role_context.yml`'s precedent of a gitignored, locally-filled template.

## Exceptions

None. This spec builds a write path and finishes two requirements
(`0048` REQ-007/REQ-008) that spec already approved but left unimplemented; it
introduces no deviation from `instructions/engineering_principles.md`.
