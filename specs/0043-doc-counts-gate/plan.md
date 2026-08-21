# Plan: Documented-Count Drift Gate

- **Spec:** 0043-doc-counts-gate (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-08-12

## Approach

One new POSIX gate, `hooks/stages/doc-counts-check.sh`, in the same shape
as `readme-sync-check.sh` (`0040`) and `agent-catalog-check.sh`. It
derives three counts from the filesystem, scans three narrative documents
for stated counts, and warns on each mismatch. Wired into the four places
every repo gate is registered.

## Architecture & Components

```text
doc-counts-check.sh
  # --- derived truth (REQ-001) -------------------------------------
  agents       = find agents -type f -name prompt.md | wc -l
                 # the same definition agent-catalog-check.sh and the
                 # pre-commit hook use, so all three move together
  gates        = ls hooks/stages/*-check.sh | wc -l
  instructions = ls instructions/*.md, excluding README.md

  # --- claims scanned (REQ-002) ------------------------------------
  docs = README.md, docs/handoff.md, docs/sdk_plan.md
  for each doc (skip with an info line when absent -- REQ-005):
      for each (entity, truth, pattern) triple:
          every match of pattern -> extract its digits -> compare to truth
          mismatch -> qf_warn "<doc>: says N <entity>, actual is M"
          checked += 1

  qf_info "Checked <checked> count claim(s) across <n> document(s)."   # REQ-004
  qf_stage_result doc-counts
```

Patterns per entity — chosen to match the phrasings this repository
actually uses, listed here so a new one is added deliberately rather than
discovered by a silent miss (RISK-001):

| Entity | Patterns |
| --- | --- |
| agents | `[0-9]+ agents`, `[0-9]+ narrow, inspectable agent roles`, `Agents \([0-9]+` |
| gates | `[0-9]+ quality gates`, `Gates \([0-9]+\)` |
| instructions | `[0-9]+ instruction standards`, `Instructions \([0-9]+\)` |

Extraction is two-stage because POSIX `grep` has no capture groups: match
the whole phrase with `grep -oE`, then pull the digits out of the match
with a second `grep -oE '[0-9]+'`. Matches are space-joined into a single
token before the loop so word-splitting cannot break a multi-word phrase.

## Interfaces & Data Contracts

No new artifact and no new schema. The gate reads three existing Markdown
files and the filesystem, and writes nothing. Its interface is its exit
code and stdout findings, identical in shape to every other
`hooks/stages/*-check.sh`.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P5 Reversibility | yes | Additive: one new script plus four small registration edits. No existing gate's behaviour changes. |
| P8 No silent trade-offs | yes | RISK-001–RISK-003 name the unrecognised-phrasing gap, the false-positive mode, and the dependence on the "public agent" definition. |
| P10 Honest reporting | yes | REQ-004 makes the gate report its own coverage, so a regex that stops matching is visible rather than passing quietly — the failure mode a checker most needs to disclose about itself. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | Filesystem derivation of the three counts | T-001 |
| REQ-002 | Per-entity pattern table, per-document scan | T-001 |
| REQ-003 | Mismatch warning naming doc, stated, and true value | T-001 |
| REQ-004 | Checked-claims tally in the summary line | T-001 |
| REQ-005 | Missing-document skip | T-001 |
| REQ-006 | `run-stage.sh`, `hooks/README.md`, root `README.md`, CI | T-002 |
| NFR-001 – NFR-003 | Script shape, POSIX-only, deterministic scan | T-001 |
| NFR-004 | Validation gates | T-003 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Scope of claims | Counts derivable from the filesystem | Any documented fact | Only a derivable claim can be checked without judgement; "advisory by default" is prose no gate should adjudicate. |
| Entities covered | Agents, gates, instruction standards | Also specs and adapters | `spec-index` already guarantees spec coverage, and no narrative doc states an adapter count — a check for one would police a claim nobody makes. |
| Phrasing handling | An explicit pattern table per entity | One rigid canonical form the docs must adopt | Rewriting prose to satisfy a checker inverts the relationship; the gate should fit the writing, not the reverse. Cost: an unrecognised phrasing is a silent miss, mitigated by REQ-004's coverage tally. |
| Truth for "agent" | Reuse `find agents -type f -name prompt.md` | A separate definition local to this gate | `agent-catalog-check.sh` and `.githooks/pre-commit` already use it; a second definition could drift and have two gates disagree about what an agent is. |
| Failure mode | Advisory locally, blocking in CI | Blocking everywhere | Matches every other repo gate; a false positive (RISK-002) should not block local work. |

## Validation Strategy

No `pytest` module — the gate is a shell script, and no
`hooks/stages/*.sh` has one (`0040` set this precedent). Verified by
direct execution instead: run against the repository (expect zero
findings, AC-001); against a scratch copy with an altered agent count
(expect a warning naming stated and true values, AC-002); the same
fixture under `QF_STAGE_ENFORCE=1` (expect non-zero exit, AC-003);
confirm the coverage tally is greater than zero (AC-004); and with a
document moved aside (expect a clean skip, AC-005). Then
`hooks/stages/run-stage.sh` with no arguments (AC-006), the full
documentation-gate set, `pytest tests/ -q` (unaffected — no Python
changes), and `git diff --check`.

## Rollout, Observability & Rollback

Rollout is a branch commit and push. Rollback is reverting the single
commit; no existing gate or document changes behaviour.

## Open Questions

- Should the gate eventually cover per-group agent counts in
  `agents/README.md`'s category tables, or are whole-repo totals the
  right stopping point? (Carried from `spec.md`.)
