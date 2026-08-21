# Tasks: Documented-Count Drift Gate

- **Spec:** 0043-doc-counts-gate (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-12

## Definition of Done (applies to every task)

- POSIX `sh` only; no new tooling dependency.
- Advisory by default; `QF_STAGE_ENFORCE=1` makes findings blocking.
- Matches the existing repo-gate script shape (`common.sh` sourced,
  `qf_stage_header`/`qf_info`/`qf_warn`/`qf_stage_result`).
- Reports its own coverage, so a regex that stops matching is visible.
- Degrades gracefully when a scanned document is absent.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Write `hooks/stages/doc-counts-check.sh`. | REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, NFR-001, NFR-002, NFR-003 | done | Filesystem-derived truth reusing `agent-catalog-check.sh`'s own "public agent" definition; per-entity pattern table; two-stage digit extraction (POSIX `grep` has no capture groups). |
| T-002 | Wire `run-stage.sh`, `hooks/README.md`, root `README.md`, CI. | REQ-006 | done | `ALL` list + header comment; Repo Gates table; Quality Gates category table; CI's documentation-integrity step alongside `docs-link agent-catalog spec-index readme-sync`. |
| T-003 | Run validation gates. | NFR-004 | done | `spec`, `agent-catalog`, `docs-link`, `spec-index`, `readme-sync`, `doc-counts`; `pytest tests/ -q`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Verification | Status |
| --- | --- | --- |
| AC-001 | `sh hooks/stages/doc-counts-check.sh` against the repository — zero findings | done |
| AC-002 | Scratch copy with an altered agent count — warns, naming stated and true values | done |
| AC-003 | Same fixture under `QF_STAGE_ENFORCE=1` — exits non-zero | done |
| AC-004 | Coverage tally reported and greater than zero | done |
| AC-005 | A scanned document moved aside — reported as skipped, clean exit | done |
| AC-006 | `hooks/stages/run-stage.sh` (no args) includes `doc-counts` | done |
| AC-007 | Direct inspection of `.github/workflows/ci.yml` | done |

## Follow-ups

- Extend to per-group agent counts in `agents/README.md`'s category
  tables, if whole-repo totals prove too coarse (carried as an open
  question in `spec.md`).
- Consider a companion check for the `specs/README.md` "next free spec
  number" line, which is the same class of manually-maintained fact.
