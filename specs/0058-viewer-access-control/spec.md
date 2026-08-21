# Spec: Viewer Access Control

- **ID:** 0058-viewer-access-control
- **Status:** Approved
- **Author:** quantsmith
- **Approver:** repository owner
- **Last updated:** 2026-08-21

> WHAT and WHY only. No implementation detail — that belongs in `plan.md`.

## Problem & Context

Every record in `memory/` and every item in `research/` already carries an
`access_level` (`public` | `internal` | `restricted`). Nothing has ever
enforced it. `0048`'s own spec named this explicitly and deferred it —
*"should `access_level` filtering be enforced inside `query()` rather than
reported? Deferred until a caller exists that has a level to enforce
against"* — and at the time, no caller did: there was no front end. `0057`
built two (the reference console and the terminal), and `0056`'s reference
research store repeats the same unenforced field. The deferral's own
condition is now false: a caller — two, in fact — exists.

Today, `access_level` is decoration. It is parsed, stored, displayed as a
colored chip in both front ends, and never once consulted to decide whether
the person looking at the screen should see the record at all. A restricted
research item and a public one render identically, side by side, to whoever
is running the console — which today is safe only because it is one person
running their own local copy. It stops being safe the moment a second person
does, which is exactly the scaling step this spec exists to unblock.

This spec makes `access_level` real: a committed roster maps a resolved
viewer identity to a clearance, and every read path — `workflow_memory`'s
`query()`, and both `0057` front ends' view-model builders for *both* stores
— filters by it before a record or item ever leaves the process that read it
off disk. Filtering happens once, at the read boundary, not in the browser:
a restricted item must never appear in an API response or an embedded
snapshot that a lower-clearance viewer's client then merely declines to
render, because that is not access control, it is a UI suggestion.

## Goals

- Reuse, not duplicate, the identity resolution `0049` already built
  (env override → local config → git → OS user, hashed into a pseudonymous
  handle) as the one source of "who is running this process" for both
  write attribution and read clearance.
- A committed, reviewable roster (`access/roster.yml`) mapping a handle to a
  clearance level and a human-chosen display label — never a raw email or
  username, matching the pseudonymity guarantee `0048`/`0049` already made
  for authorship.
- Enforcement is **opt-in and fails closed**: no roster, or a roster with
  nobody in it yet, means today's unfiltered behavior is unchanged — adopting
  this spec never silently locks a solo user out of their own data. The
  moment the roster names one person, filtering activates for everyone, and
  an identity that resolves but is not listed gets the roster's declared
  (safe) default, never full access by omission.
- Enforce in exactly one place per store — `workflow_memory.query()` for
  workflow memory, the two `knowledge_console` view-model builders for
  workflow memory *and* the research store as seen through the front ends —
  so nothing downstream (rendering, the graph, the review/needed-review
  queues, an exported snapshot) can see what the read boundary already
  filtered out.
- A gate validating the roster the same way `memory-check.sh` already
  validates `memory/`: parseable, no raw identity ever committed, no unknown
  clearance value, no duplicate handle.
- An onboarding path a non-engineer can follow: resolve your own handle,
  send it to whoever maintains the roster, they add one line in a reviewed
  PR.

## Non-Goals

- **Authentication.** This does not verify that the person running a given
  local process is who their resolved identity claims. It reuses `0049`'s
  identity resolution as-is, with the same limitation `0048`'s RISK-002
  already named for it: pseudonymous, not authenticated. A person who can
  set `QF_MEMORY_AUTHOR` to any string can claim any handle. Real
  authentication is a different, much larger spec (see Assumptions) and is
  only necessary once this stops being a per-person local tool.
- **A shared, multi-tenant server.** Both front ends stay loopback-only local
  processes (per `0057`'s NFR-003 and the terminal's own design); this spec
  adds per-*process* clearance to that existing local-per-person deployment
  model. It does not stand up shared infrastructure, sessions, or network
  auth. That is the `0052`–`0054` MCP-server work named in `docs/handoff.md`
  item 17, which this spec's roster/roles are designed to be reusable by,
  not a replacement for.
- **A fourth access tier or a richer entitlement model** (per-document ACLs,
  groups, need-to-know beyond three ordered tiers, information barriers
  between two `restricted` viewers). `0048`/`0056` already fixed the
  three-tier vocabulary (`public`/`internal`/`restricted`); this spec
  enforces that vocabulary, it does not extend it.
- **Write-side authorization.** Whether a given handle is *allowed* to
  `promote`/`discard` (spec `0049`) is untouched — this spec is read-side
  only. A future spec could reuse the same roster for that; this one does not.
- **Retroactively re-classifying existing records/items.** No `access_level`
  value in `memory/` or `research/` changes. This spec enforces the field as
  it already exists.
- **Editing the roster through either front end.** The roster is edited the
  same way `memory/inbox/` candidates are reviewed: hand-edit and commit,
  reviewed via pull request. No UI writes to `access/roster.yml`.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The system shall define an explicit, ordered clearance vocabulary (`public` < `internal` < `restricted`) as the single canonical definition every enforcement point uses. | must |
| REQ-002 | The system shall determine whether an item at a given `access_level` is visible to a viewer at a given clearance using that ordering: visible iff the item's level is at or below the viewer's clearance. | must |
| REQ-003 | The system shall resolve a roster from a committed `access/roster.yml`: a list of `(handle, label, clearance)` entries plus a declared `default_clearance`, using the same dependency-free parsing discipline `0048` established (accept a small, documented subset; raise rather than guess on anything else). | must |
| REQ-004 | The system shall treat enforcement as **inactive** — every read path behaves exactly as it did before this spec — when `access/roster.yml` is absent or present with zero entries. | must |
| REQ-005 | The system shall treat enforcement as **active** the moment the roster names at least one entry, for every viewer, not only listed ones. | must |
| REQ-006 | The system shall resolve the current viewer's handle using `0049`'s existing identity-resolution chain (env override → local identity config → git → OS user), and reuse `0049`'s `derive_handle` unchanged so a person's write-attribution handle and their roster handle are always identical. | must |
| REQ-007 | The system shall assign an unlisted, resolved handle the roster's declared `default_clearance`; when a handle cannot be resolved at all, the system shall assign `default_clearance` as well, never the least-restrictive tier by default and never raise. | must |
| REQ-008 | The system shall reject a roster entry whose `handle` does not match `0049`'s author-handle pattern (i.e., looks like an email, or free text) as a validation finding, the same way `0048`'s `validate` already rejects a malformed record author. | must |
| REQ-009 | The system shall reject a roster with a duplicate `handle` or an unrecognized `clearance` value as a validation finding. | must |
| REQ-010 | `workflow_memory.query()` shall accept an optional viewer clearance and, when given, exclude any record whose `access_level` the viewer's clearance does not admit; when omitted, `query()`'s behavior shall be identical to before this spec. | must |
| REQ-011 | The `knowledge_console` view-model builders for both the workflow-memory store and the research store shall resolve the current process's viewer clearance and filter every record/item by it before deriving counts, trends, the graph, the review queue, or any other downstream field — so a filtered item never appears anywhere in the served JSON or an exported snapshot. | must |
| REQ-012 | A record/item's own display of its `access_level` (the badge/chip already shown in both front ends) shall remain visible on every item the viewer *is* shown — filtering removes invisible items, it does not hide the level of a visible one. | must |
| REQ-013 | The system shall provide a way for a person to learn their own resolved handle without reading source code, so they can be added to the roster. | must |
| REQ-014 | The system shall provide a way to preview what a given clearance (or a given handle) would see, for verifying a roster change before it merges. | should |
| REQ-015 | A gate shall validate `access/roster.yml` the run it changes: parses, no duplicate handle, no unrecognized clearance, no handle shaped like an email or free text, and the same secret/PII safety scan `memory-check.sh` already runs, applied to `access/`. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Dependencies | Python standard library only, matching `0048`/`0049`/`0057`. |
| NFR-002 | No new identity surface | Reuses `0049`'s identity resolution and handle derivation verbatim (moved, not duplicated) — one salt, one algorithm, one pattern, so a write-attribution handle and a roster handle can never silently diverge. |
| NFR-003 | Determinism | `query()`/the view-model builders' *pure* functions take clearance as a plain argument, no filesystem access — identical inputs (including clearance) always produce identical output, preserving `0048`/`0057`'s existing determinism guarantees. Only the `_from_root` I/O wrappers resolve clearance from disk. |
| NFR-004 | Backward compatibility | Every existing caller of `query()`, `build_model()`/`build_model_from_root()`, and `build_research_model()`/`build_research_model_from_root()` that does not pass/have a clearance argument sees unchanged behavior — the 290 tests existing before this spec must still pass unmodified. |
| NFR-005 | Fail closed | Any ambiguity — an unresolvable identity, an unrecognized `access_level` on an item, an unrecognized clearance value anywhere — resolves toward *less* visibility, never more. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given the three clearance tiers, when visibility is checked, then `public` is visible to all three clearances, `internal` is visible to `internal`/`restricted` only, and `restricted` is visible to `restricted` only. | REQ-001, REQ-002 |
| AC-002 | Given no `access/roster.yml`, when a store is read through `query()` or a view-model builder, then every record/item is present exactly as it would be without this spec. | REQ-004 |
| AC-003 | Given `access/roster.yml` exists with zero entries, when the store is read, then behavior is identical to AC-002 (no roster). | REQ-004 |
| AC-004 | Given a roster with one entry, when *any* viewer — listed or not — reads the store, then filtering is applied to all of them, not only the listed one. | REQ-005 |
| AC-005 | Given `QF_MEMORY_AUTHOR` set to a handle already in the roster, when clearance is resolved, then that entry's clearance is returned, with no git/OS lookup. | REQ-006 |
| AC-006 | Given a resolved handle not present in the roster, when clearance is resolved, then the roster's `default_clearance` is returned, never `restricted` by default and never an error. | REQ-007 |
| AC-007 | Given no identity resolves at all (matching `0049`'s AC-004 scenario), when clearance is resolved, then `default_clearance` is returned, not an exception. | REQ-007, NFR-005 |
| AC-008 | Given a roster entry whose `handle` is `someone@example.com`, when the roster is validated, then a finding names that entry — the same shape check `0048`'s `validate` already applies to record authorship. | REQ-008 |
| AC-009 | Given a roster with two entries sharing one `handle`, or one entry with `clearance: super-secret`, when validated, then each yields its own finding. | REQ-009 |
| AC-010 | Given three records at each clearance tier and a viewer clearance of `internal`, when `query(records, viewer_clearance="internal")` is called, then only the `public` and `internal` records are returned; when `viewer_clearance` is omitted, all three are returned. | REQ-010, NFR-004 |
| AC-011 | Given a restricted research item and a workflow-memory record, and a roster giving the current process `internal` clearance, when either front end's view-model is built, then neither the restricted item nor the restricted record appears anywhere in the JSON payload — not in `records`/`items`, not in `counts`, not in the graph, not in the review queue. | REQ-011 |
| AC-012 | Given the same setup as AC-011, when the self-contained single-file snapshot is built, then the embedded `window.__KB_MODEL__`/`window.__KB_RESEARCH__` also excludes the restricted content — a snapshot is only as visible as its builder was. | REQ-011 |
| AC-013 | Given a record the viewer *can* see, when it is rendered, then its `access_level` badge is shown exactly as before this spec. | REQ-012 |
| AC-014 | Given the CLI, when the "who am I" command runs, then it prints the same handle `resolve_author`/`resolve_viewer_clearance` would derive for the current environment — copy-pasteable into a roster PR. | REQ-013 |
| AC-015 | Given a roster change in a branch, when a preview command is run with an explicit handle or clearance override, then it reports exactly what that viewer would and would not see, without needing to actually be that person. | REQ-014 |
| AC-016 | Given a fixture roster with a duplicate handle, an email-shaped handle, and an unrecognized clearance, when the access gate runs, then it reports three findings, one per problem, naming the roster file. | REQ-015 |
| AC-017 | Given a roster file containing an embedded raw email address outside the `handle` field (e.g., in a comment), when the access gate's safety scan runs, then it is flagged the same way `memory-check.sh` flags one under `memory/`. | REQ-015 |

## Data & Dependencies

- **Reads:** `access/roster.yml` (new, committed); the same identity sources
  `0049` already reads (`QF_MEMORY_AUTHOR`, local `identity.yml`, git config,
  OS user) — never stored raw.
- **Imports/relocates:** `derive_handle`, `resolve_author`, and the author-
  handle pattern move from `quantsmith.pipelines.workflow_memory` into a new
  `quantsmith.pipelines.access_control` module; `workflow_memory` re-exports
  them unchanged for every existing caller (CLI, tests, `0049`'s `promote`).
- **Consumed by:** `workflow_memory.query()`; `knowledge_console.model`;
  `knowledge_console.research`; a new `access-check.sh` gate; a "who am I" /
  preview CLI surface.
- **Does not consume:** the write path (`propose`/`stage`/`promote`/
  `discard`) is unmodified; this spec is additive to the read side only.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | Filtering happens in the wrong place (e.g., only in the front-end React components), so a restricted item still reaches the browser and a curious viewer opens dev tools and reads it from the API response or the page source. | High — the exact failure this spec exists to prevent. | REQ-011 enforces at the Python view-model builders, before any HTTP response or embedded snapshot is produced (AC-011, AC-012) — the front ends render only what they were sent; they never receive what they should not show. |
| RISK-002 | A roster with zero entries (freshly added, not yet populated) unexpectedly locks everyone to the most restrictive tier the moment the file is committed. | Medium — an adoption cliff that punishes turning the feature on. | REQ-004: zero entries is defined as inactive, identical to no roster at all. Enforcement only turns on once a real person is listed (AC-003, AC-004). |
| RISK-003 | Someone commits a roster entry keyed by a raw email instead of a resolved handle, defeating the pseudonymity guarantee `0048`/`0049` established for authorship. | Medium — reintroduces the exact PII surface those specs closed. | REQ-008/AC-008 rejects it at validation time using the same pattern check `0048`'s `validate` already applies; REQ-015/AC-017 adds a belt-and-suspenders secret/PII scan over `access/` mirroring `memory-check.sh`. |
| RISK-004 | `default_clearance` is set to `restricted` (the most permissive read for an *unrecognized* configuration, since "restricted" sounds strict but here means "sees everything") by someone who misreads the tier name, silently granting broad access to everyone not explicitly listed. | Medium — a naming-confusion privilege escalation. | The roster template ships with `default_clearance: public` and a comment explaining the ordering explicitly; REQ-009's validation still accepts any of the three legal values (it is a legitimate deployment choice), but the shipped default and the docs make the safe choice the path of least resistance. |
| RISK-005 | Refactoring `derive_handle`/`resolve_author` out of `workflow_memory.py` breaks an existing import somewhere (the CLI, the `0049` tests) that expects them at their old location. | Low — a straightforward regression if missed. | `workflow_memory.py` re-exports both names unchanged (NFR-002); the full existing test suite (290 tests, including `0049`'s CLI subprocess tests which import by module path) is run unmodified as a regression check before this spec is considered done. |
| RISK-006 | An access-control feature gets built and nobody adopts it because onboarding a teammate requires reading source code to find their handle. | Medium — the feature exists but the scaling problem it targets persists. | REQ-013/AC-014: a one-command "who am I" that prints a roster-ready line. |

## Assumptions & Open Questions

- Assumption: "local per-person" remains the deployment model this spec
  targets — each teammate runs their own console/terminal instance against
  their own resolved identity. A shared server would need real
  authentication first (Non-Goals); this spec's roster format is designed to
  be reusable then, not rebuilt.
- Assumption: a team small enough to onboard via a roster maintained in a
  reviewed PR (tens of people, not thousands) is the right scale for this
  design. A larger org would want the roster backed by a real identity
  provider — out of scope here.
- Assumption: one clearance per person is sufficient (no per-dataset or
  per-domain entitlement distinctions within a tier). `0056`'s own
  `entitlement_class` field on research items is a separate, unenforced-by-
  this-spec concept (e.g. "vendor-licensed") that a future spec could layer
  on top of clearance, not fold into it.
- Open question: should a roster entry be able to name more than one handle
  for one person (e.g., they resolve differently on two machines)? Starting
  with one handle per entry; a person with two machines gets two roster
  lines with the same clearance if needed, which is more entries but zero
  new mechanism.
- Open question: expiring or time-boxed clearance (a contractor's access
  lapsing on a date) is not modeled. A roster edit (removing the line) is
  today's mechanism, reviewed and auditable via git history like everything
  else this repo writes.

## Exceptions

One, narrow: NFR-004 says the 290 pre-existing tests must pass unmodified.
`tests/test_workflow_memory_write_path.py::test_no_identity_resolves_to_none_without_raising_AC_004`
needed a one-line edit — it monkeypatches the private `_git_identity`/
`_os_identity` helpers by dotted path, and those helpers physically moved to
`access_control.py` under this spec's relocation (REQ-006, NFR-002). The
patch targets were updated to the new module; the test's behavior, intent,
and assertion are unchanged. This is a mechanical consequence of relocating
private implementation, not a behavior change, and no other test required
any edit.

Otherwise: none. This spec activates an enforcement point `0048` explicitly
deferred pending a caller, once `0057` supplied one; it introduces no other
deviation from `instructions/engineering_principles.md`.
