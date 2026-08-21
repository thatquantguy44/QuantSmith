# Spec: README Index/Runtime Sync Gate

- **ID:** 0040-readme-sync-gate
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-08-11

## Problem & Context

Every spec in this SDK that ships a real, tested runtime under
`src/quantsmith/pipelines/` is meant to appear in two places: its own row
in `specs/README.md`'s index (with a populated Runtime column) and a
matching row in root `README.md`'s runtime table (plus, by convention, a
mention in whichever themed chain it belongs to). `hooks/stages/` already
gates two adjacent sync problems the same way — `agent-catalog-check.sh`
(every agent directory listed in `agents/README.md`) and
`spec-index-check.sh` (every spec directory listed in `specs/README.md`)
— but nothing checks the third leg: that a spec's *own* index entry and
root `README.md`'s runtime table agree with each other. `docs/handoff.md`
names this exact gap in its own Risks section: *"Docs can drift from the
code; the `docs-link`, `agent-catalog`, and `spec-index` gates help, but
narrative docs ... need periodic manual refresh."* Every spec built this
session has closed this gap by hand, as an explicit wiring task in its
own `tasks.md` — this spec makes that step self-checking instead of
relying on memory and habit.

## Goals

- Add `hooks/stages/readme-sync-check.sh`: for every spec row in
  `specs/README.md`'s index table whose Tests column names a real pytest
  module (a backtick-quoted `test_*.py` pattern — the signal that
  reliably separates a genuinely tested runtime from an agent-contract-
  only, catalog-only, or gate-only spec; verified empirically to have
  zero false positives against the current table, unlike the Runtime
  column, whose "not shipped" values are phrased inconsistently, e.g.
  `— (agent contracts)` vs `` `sources/` (catalog only, not
  `pipelines/`) ``), verify the same spec ID also appears in root
  `README.md`'s runtime table.
- Wire the new gate into `hooks/stages/run-stage.sh`'s `ALL` stage list,
  `hooks/README.md`'s Repo Gates table, root `README.md`'s Quality Gates
  category table, and CI's docs-integrity enforcement step, matching
  exactly how `agent-catalog`/`spec-index`/`docs-link` are already wired.
- Advisory by default, consistent with every other stage/gate script in
  `hooks/stages/`; `QF_STAGE_ENFORCE=1` makes findings blocking, and CI
  runs it in that mode alongside the other docs-integrity gates.

## Non-Goals

- No check of the reverse direction (a spec ID present in root
  `README.md`'s runtime table but absent from `specs/README.md`) — that
  direction can't happen by construction, since every spec's own row is
  written first as part of that spec's own wiring task, and
  `spec-index-check.sh` already guarantees every spec directory has a row
  in `specs/README.md` in the first place.
- No check of the themed-chain bullets (e.g. "Quant research: ... →
  `0038` factor risk") — those are prose, not a table, and don't have a
  single deterministic anchor to grep for the way a `[`NNNN`]` table
  entry does; a heuristic keyword match here would be noisier than
  useful, mirroring why `docs-link-check.sh` only checks structural link
  targets, not prose accuracy.
- No auto-fix. Like every other `hooks/stages/` gate, this reports a
  finding; a human or agent still writes the missing row.
- No change to any existing gate's behavior, `specs/README.md`'s or root
  `README.md`'s existing content, or any spec's own runtime code.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | `readme-sync-check.sh` shall parse `specs/README.md`'s index table and, for each row whose Tests column names a real pytest module (a backtick-quoted `test_*.py` pattern), extract the spec ID. | must |
| REQ-002 | For each extracted spec ID, the gate shall check whether that ID appears in root `README.md`'s runtime table (the same `` [`NNNN`] `` anchor form root `README.md` already uses) and warn if it does not. | must |
| REQ-003 | The gate shall report the count of runtime-bearing specs checked, matching the reporting style of `agent-catalog-check.sh`/`spec-index-check.sh`. | must |
| REQ-004 | The gate shall degrade gracefully (informational message, clean exit) when `specs/README.md` or root `README.md` is missing, matching every other `hooks/stages/` script's missing-file handling. | must |
| REQ-005 | `hooks/stages/run-stage.sh`, `hooks/README.md`, root `README.md`'s Quality Gates table, and `.github/workflows/ci.yml` shall all list/run the new `readme-sync` gate. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Consistency | Matches the existing `agent-catalog-check.sh`/`spec-index-check.sh` script shape: `common.sh` sourced, `qf_stage_header`/`qf_info`/`qf_warn`/`qf_stage_result` used, advisory by default. |
| NFR-002 | No new tooling dependency | POSIX `sh` + `grep`/`awk`/`sed` only, consistent with every other gate. |
| NFR-003 | Determinism | The same `specs/README.md`/root `README.md` content always produces the same findings. |
| NFR-004 | Repository hygiene | `spec`, `agent-catalog`, `docs-link`, `spec-index`, and the new `readme-sync` gate all pass; full pytest suite unaffected (no Python changed). |

## Acceptance Criteria

| ID | Given / When | Then | Covers |
| --- | --- | --- | --- |
| AC-001 | Given `specs/README.md`'s current index (every runtime-bearing spec through `0039` already has a matching root `README.md` row), when `readme-sync-check.sh` runs. | It reports zero findings. | REQ-001, REQ-002 |
| AC-002 | Given a `specs/README.md` row with a `test_*.py`-shaped Tests column whose spec ID is temporarily removed from root `README.md`'s runtime table (test fixture), when the gate runs. | It warns naming that spec ID. | REQ-002 |
| AC-003 | Given a `specs/README.md` row whose Tests column is a gate reference (e.g. `` `catalog/docs gates` ``, `` `source-catalog` gate ``) rather than a `test_*.py` module, when the gate runs. | That spec ID is not checked and produces no finding even though it is absent from root `README.md`'s runtime table. | REQ-001 |
| AC-004 | Given `specs/README.md` missing entirely, when the gate runs. | It reports "skipped" and exits cleanly (0), not an error. | REQ-004 |
| AC-005 | Given `hooks/stages/run-stage.sh` with no arguments, when run. | The `readme-sync` gate executes as part of the full suite. | REQ-005 |
| AC-006 | Given `.github/workflows/ci.yml`, when inspected. | The docs-integrity enforcement step includes `readme-sync` alongside `docs-link agent-catalog spec-index`. | REQ-005 |

## Data & Dependencies

No data dependencies, no runtime code, no new tooling. A POSIX shell
script consistent with every other file in `hooks/stages/`.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | The Tests-column parse (matching a backtick-quoted `test_*.py` pattern) could misfire if a future spec's Tests column names a real test module using different formatting (no backticks, a different naming convention). | A false "not synced" warning, or a missed one. | Advisory by default — a false positive is a visible, low-cost warning, not a blocked commit, matching every other heuristic gate's accepted failure mode (`leakage`, `maintenance`, etc.). Empirically verified against every existing row (zero false positives as of `0039`) before being chosen over the Runtime column, whose "not shipped" phrasing is inconsistent across rows. |
| RISK-002 | The gate only checks presence of the `` [`NNNN`] `` anchor in root `README.md`, not that the row's description or filename still matches the spec's own row. | A stale but present row would not be flagged. | Explicitly scoped as presence-only in Goals; matches `agent-catalog-check.sh`/`spec-index-check.sh`'s own scope (both are presence checks, not content-diff checks). |

## Assumptions & Open Questions

- Assumption: root `README.md`'s runtime table will keep using the
  `` [`NNNN`] `` anchor (linking to `specs/NNNN-slug/`) it already uses
  for every existing row (verified against the file as of this spec).
- Assumption: `specs/README.md`'s Tests column will keep naming a real
  `tests/test_*.py` module, backtick-quoted, for every spec that ships a
  genuinely tested runtime (the convention every spec in this SDK has
  followed to date), rather than switching to gate-only or prose-only
  phrasing for a spec that does have pytest coverage.
- Open question: should a future revision extend this gate to also check
  the themed-chain prose bullets once/if they adopt a more structured,
  greppable form?

## Exceptions

None.
