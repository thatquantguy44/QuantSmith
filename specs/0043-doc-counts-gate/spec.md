# Spec: Documented-Count Drift Gate

- **ID:** 0043-doc-counts-gate
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-08-12

## Problem & Context

The narrative docs state headline counts — how many agents, quality
gates, and instruction standards the SDK has. Every one of them had
drifted from reality, in four separate places and by wide margins: agents
were documented as 131 (`docs/handoff.md`, `docs/sdk_plan.md`) and 122
(root `README.md`) against a real 161; gates as 23 and 21 against a real
26; instruction standards as 26 against a real 33. `docs/handoff.md`'s
gate listing named only 22 of the 26 gates, silently omitting four.

The drift is structural, not careless. `agent-catalog` (`0019`-era),
`spec-index`, and `readme-sync` (`0040`) each check that an *entity* is
listed somewhere — a spec row, an agent path, a table entry — but none
can check a number written in prose. `docs/handoff.md`'s own Risks
section names the general problem ("narrative docs ... need periodic
manual refresh"), and the counts are the part of it that is mechanically
checkable: the truth is a `find` away.

This spec adds the gate that closes it, so adding the twenty-seventh gate
or the hundred-and-sixty-second agent surfaces the stale number instead
of quietly widening the gap.

## Goals

- Add `hooks/stages/doc-counts-check.sh`: derive the true count of
  agents, gates, and instruction standards from the filesystem, then scan
  the narrative docs for stated counts and report every mismatch.
- Recognise the phrasings actually used in this repository — `**161
  agents**`, `161 narrow, inspectable agent roles`, `**Gates (26)**`,
  `**26 quality gates**`, `**Instructions (33)**` — rather than requiring
  a single rigid form.
- Report the document, the stated number, and the true number for each
  mismatch, so the fix is mechanical.
- Advisory by default like every other gate; blocking under
  `QF_STAGE_ENFORCE=1`, and enforced in CI alongside the other
  documentation-integrity gates.

## Non-Goals

- **No auto-fix.** Like every other `hooks/stages/` gate, this reports; a
  human or agent edits the document.
- **No general prose-fact checking.** Only counts whose truth is
  derivable from the filesystem are in scope. A claim like "advisory by
  default" is prose this gate cannot and should not adjudicate.
- **No new counted entities beyond the three.** Specs and adapters are
  deliberately excluded: `spec-index` already guarantees spec coverage,
  and no narrative doc currently states an adapter count, so a check for
  one would police a claim nobody makes.
- **No change to any existing gate**, or to the counts themselves — those
  were corrected before this spec (commit `0be442a`); this gate keeps them
  correct.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The gate shall derive the true count of public agents (directories containing `prompt.md` under `agents/`), quality gates (`hooks/stages/*-check.sh`), and instruction standards (`instructions/*.md` excluding `README.md`) from the filesystem. | must |
| REQ-002 | The gate shall scan the narrative docs (root `README.md`, `docs/handoff.md`, `docs/sdk_plan.md`) for stated counts of those three entities, recognising both the `N <noun>` and `<Noun> (N)` phrasings used in this repository. | must |
| REQ-003 | For each stated count that disagrees with the derived truth, the gate shall warn, naming the document, the stated number, and the true number. | must |
| REQ-004 | The gate shall report how many count claims it checked, so a silent zero-match regex cannot masquerade as a pass. | must |
| REQ-005 | The gate shall degrade gracefully: a missing document is skipped with an informational message, not an error. | must |
| REQ-006 | `hooks/stages/run-stage.sh`, `hooks/README.md`, root `README.md`'s gate table, and `.github/workflows/ci.yml` shall list and run the new `doc-counts` gate. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Consistency | Matches the existing repo-gate script shape: `common.sh` sourced, `qf_stage_header`/`qf_info`/`qf_warn`/`qf_stage_result`, advisory by default. |
| NFR-002 | No new tooling dependency | POSIX `sh` plus `grep`/`find`/`ls`, consistent with every other gate. |
| NFR-003 | Determinism | The same working tree always produces the same findings. |
| NFR-004 | Repository hygiene | `spec`, `agent-catalog`, `docs-link`, `spec-index`, `readme-sync`, `doc-counts` gates and the full pytest suite pass. |

## Acceptance Criteria

| ID | Given / When | Then | Covers |
| --- | --- | --- | --- |
| AC-001 | Given the repository with its counts corrected, when `doc-counts-check.sh` runs. | It reports zero findings. | REQ-001, REQ-002, REQ-003 |
| AC-002 | Given a scratch copy of a narrative doc whose agent count is altered to a wrong number, when the gate runs against it. | It warns, naming the document, the stated number, and the true number. | REQ-003 |
| AC-003 | Given the same scratch fixture, when the gate runs under `QF_STAGE_ENFORCE=1`. | It exits non-zero. | REQ-003, NFR-001 |
| AC-004 | Given the repository, when the gate runs. | It reports the number of count claims checked, and that number is greater than zero. | REQ-004 |
| AC-005 | Given a narrative document that does not exist, when the gate runs. | It reports the document as skipped and exits cleanly. | REQ-005 |
| AC-006 | Given `hooks/stages/run-stage.sh` with no arguments, when run. | The `doc-counts` gate executes as part of the full suite. | REQ-006 |
| AC-007 | Given `.github/workflows/ci.yml`, when inspected. | The documentation-integrity step includes `doc-counts`. | REQ-006 |

## Data & Dependencies

No data dependencies and no runtime code. A POSIX shell script consistent
with the rest of `hooks/stages/`.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A future document states a count in a phrasing the regexes do not recognise, and the gate passes while the number is wrong. | False confidence — the gate appears to cover a claim it never saw. | REQ-004: the gate reports how many claims it checked, so a drop to zero (or an implausibly low number) is visible rather than silent. The recognised phrasings are documented in `plan.md` so a new one can be added deliberately. |
| RISK-002 | A number that happens to precede a counted noun in unrelated prose is read as a count claim (e.g. a sentence about "3 agents" in an example). | A false positive warning. | Advisory by default, so a false positive is a visible warning rather than a blocked commit — the same accepted failure mode as `leakage` and the other heuristic gates. The scan is limited to three known narrative documents, not the whole repository. |
| RISK-003 | The derived truth itself could be wrong if the definition of a "public agent" changes (e.g. a new marker file replaces `prompt.md`). | The gate would enforce a stale definition. | The derivation reuses the exact definition `agent-catalog-check.sh` and the pre-commit hook already use (`find agents -type f -name prompt.md`), so all three move together rather than diverging. |

## Assumptions & Open Questions

- Assumption: the three narrative documents (`README.md`,
  `docs/handoff.md`, `docs/sdk_plan.md`) are where headline counts
  appear; `agentic_dictionary.md` and the per-group READMEs state
  membership rather than totals.
- Open question: should the gate eventually cover per-group agent counts
  (e.g. `agents/README.md`'s category tables), or is whole-repo totals
  the right stopping point?

## Exceptions

None.
