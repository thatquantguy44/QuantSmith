# Plan: README Index/Runtime Sync Gate

- **Spec:** 0040-readme-sync-gate (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-08-11

## Approach

Add one new POSIX shell gate, `hooks/stages/readme-sync-check.sh`,
matching `agent-catalog-check.sh`/`spec-index-check.sh`'s exact shape
(source `common.sh`, `qf_stage_header`/`qf_info`/`qf_warn`/
`qf_stage_result`, advisory by default). Wire it into the four places
every existing repo gate is registered: `run-stage.sh`'s `ALL` list,
`hooks/README.md`'s Repo Gates table, root `README.md`'s Quality Gates
table, and CI's docs-integrity enforcement step.

## Architecture & Components

```text
readme-sync-check.sh
  spec_index = specs/README.md
  root_readme = README.md

  if either file missing -> qf_info "skipped", clean exit (matches
      spec-index-check.sh's own missing-file handling)

  # specs/README.md's index rows look like:
  #   | [0038-factor-risk-model] (link to its own dir) | ... | `factor_risk_model.py` | `test_factor_risk_model.py` | Approved |
  # awk -F'|' column 2 -> spec id (leading 4 digits), column 5 -> Tests
  grep matching rows -> temp file (avoids a `while read` pipe subshell,
      so the running `count`/finding total survive the loop, matching
      how leakage/backtest-style gates already collect state across a
      file-driven loop)
  for each row:
      id = leading 4 digits of column 2's [NNNN-slug] text
      tests_col = column 5 (awk field 5, since field 1 is empty before
          the row's leading "|")
      tests_col does not match *test_*.py* -> skip (no pytest module:
          agent-contract-only, catalog-only, or gate-only spec)
      else: count += 1
          grep -qF "[`id`]" root_readme || qf_warn "spec id has a
              tested runtime but is not listed in root README.md's
              runtime table"

  qf_info "Checked N spec(s) with a shipped runtime against README.md."
  qf_stage_result readme-sync
```

## Interfaces & Data Contracts

No new data contract — the gate reads two existing Markdown files
(`specs/README.md`, root `README.md`) and does not write to either. Its
only "interface" is its exit code and stdout findings, identical in
shape to every other `hooks/stages/*-check.sh` script.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P5 Reversibility | yes | Additive-only: one new script, four small edits to already-existing lists/tables. No existing gate's behavior changes. |
| P8 No silent trade-offs | yes | RISK-001/RISK-002 name the parse's exact limits (placeholder-punctuation sensitivity, presence-only not content-diff) directly in `spec.md`. |
| P10 Honest reporting | yes | Advisory by default like every other gate; never silently "fixes" a missing row, only reports it. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | Row parse: extract spec ID + Runtime column | T-001 |
| REQ-002 | Presence check against root `README.md`'s `` [`NNNN`] `` anchors | T-001 |
| REQ-003 | `qf_info "Checked N spec(s) ..."` | T-001 |
| REQ-004 | Missing-file early exit | T-001 |
| REQ-005 | `run-stage.sh`, `hooks/README.md`, root `README.md`, CI wiring | T-002 |
| NFR-001 – NFR-003 | Script shape, POSIX-only, deterministic parse | T-001 |
| NFR-004 | Validation gates | T-003 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Scope | Presence-only check (spec ID appears in root `README.md`'s table) | A full content-diff (description/filename match too) | Matches `agent-catalog-check.sh`/`spec-index-check.sh`'s own established scope; a content-diff would need to parse and compare prose, which is exactly the kind of heuristic noise `docs-link-check.sh` already avoids by checking link targets, not prose accuracy. |
| Which rows to check | Only rows whose Tests column names a real `test_*.py` module | Rows whose Runtime column is non-empty/non-`—`; every spec row regardless | The Runtime column's "not shipped" phrasing is inconsistent (`— (agent contracts)` vs `` `sources/` (catalog only, not `pipelines/`) `` vs `` `memory/` scaffold ``) and produced false positives when tried first (`0002`, `0026`, `0027`) — a spec-scratch run confirmed it. The Tests column's `test_*.py` presence matched root `README.md`'s actual inclusion set with zero discrepancies across all 39 existing specs. Checking every row regardless would flag every agent-contract-only spec (a large majority) as a false "missing" finding. |
| Loop implementation | Matched rows written to a temp file, then `while read ... < file` | `grep ... | while read ...` (pipe form) | The pipe form runs the loop body in a subshell in POSIX `sh`, so the running finding count would not survive past the loop — the same reason no other gate in this repo uses a piped `while read` for stateful counting. |

## Validation Strategy

No `pytest` test (the gate is a shell script with no Python surface,
matching every other `hooks/stages/*.sh` — none have a dedicated
`tests/test_*.py`). Verified instead by direct execution:
`sh hooks/stages/readme-sync-check.sh` against the current repo (expect
zero findings per AC-001), then against a scratch copy with a spec ID
temporarily stripped from root `README.md`'s table (expect one finding,
AC-002), then against a spec row with `—` in the Runtime column (expect
no finding, AC-003), then with `specs/README.md` temporarily moved aside
(expect a clean skip, AC-004). Then
`hooks/stages/run-stage.sh spec agent-catalog docs-link spec-index readme-sync`,
the full `pytest tests/ -q` (unaffected, confirming no regression), and
`git diff --check`.

## Rollout, Observability & Rollback

Rollout is a branch commit (and push, if requested). Rollback is
reverting the single commit; no existing gate, spec, or doc content is
modified beyond the four wiring edits.

## Open Questions

- Should a future revision extend this gate to also check the
  themed-chain prose bullets, once/if they adopt a more structured,
  greppable form? (Carried from `spec.md`.)
