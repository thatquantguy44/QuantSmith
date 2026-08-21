# Tasks: README Index/Runtime Sync Gate

- **Spec:** 0040-readme-sync-gate (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-11

## Definition of Done (applies to every task)

- POSIX `sh` only; no new tooling dependency.
- Advisory by default; `QF_STAGE_ENFORCE=1` makes findings blocking.
- Matches the existing `agent-catalog-check.sh`/`spec-index-check.sh`
  script shape exactly (`common.sh` sourced, `qf_stage_header`/`qf_info`/
  `qf_warn`/`qf_stage_result`).
- Degrades gracefully when either input file is missing.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Write `hooks/stages/readme-sync-check.sh`. | REQ-001, REQ-002, REQ-003, REQ-004, NFR-001, NFR-002, NFR-003 | done | Temp-file-backed loop (no piped `while read` subshell) so the finding count survives the loop. |
| T-002 | Wire `run-stage.sh`, `hooks/README.md`, root `README.md`, CI. | REQ-005 | done | `run-stage.sh`'s `ALL` list + header comment; `hooks/README.md`'s Repo Gates table; root `README.md`'s Quality Gates category table; CI's docs-integrity enforcement step (`docs-link agent-catalog spec-index readme-sync`). |
| T-003 | Run validation gates. | NFR-004 | done | `spec`, `agent-catalog`, `docs-link`, `spec-index`, `readme-sync`; full `pytest tests/ -q`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Verification | Status |
| --- | --- | --- |
| AC-001 | `sh hooks/stages/readme-sync-check.sh` against the current repo — zero findings | done |
| AC-002 | Same script against a scratch copy of root `README.md` with a runtime-bearing spec ID's row temporarily removed — one finding | done |
| AC-003 | Confirmed no finding for `—`-Runtime (agent-contract-only) spec rows in the current repo (e.g. `0033`) | done |
| AC-004 | Same script run with `specs/README.md` temporarily moved aside — clean skip, exit 0 | done |
| AC-005 | `hooks/stages/run-stage.sh` (no args) includes `readme-sync` in its output | done |
| AC-006 | Direct inspection of `.github/workflows/ci.yml`'s docs-integrity step | done |

## Follow-ups

- Extend the gate to check themed-chain prose bullets if/when they adopt
  a more structured, greppable form (carried as an open question in
  `spec.md`).
