# Plan: Data Provenance & Synthetic-Data Disclosure Guardrail

- **Spec:** 0025-data-provenance-guardrail (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-08-09

## Approach

Add one instruction standard, one template, and one gate — the same
three-part shape as `alerting` (`0020`)/`monitoring` (`0021`) — then wire
`agents/role_operations/` (the group that prompted this) and add a one-line
cross-reference to the two existing groups that already handle governed
data/visuals (`dashboard_design`, `data_storytelling`) rather than
duplicating their logic.

## Architecture & Components

```text
instructions/data_provenance.md        (priority stack + disclosure standard)
templates/docs/synthetic_data_disclosure.md   (the disclosure report itself)
hooks/stages/data-provenance-check.sh
  1. deterministic-ish: disclosure artifact's required fields present?
  2. advisory heuristic: docs/**/*.md, examples/**/*.md (scaffold dirs
     excluded) mentioning synthetic/simulated/mock/fabricated/placeholder
     data, with no matching disclosure anywhere -> flag

agents/role_operations/README.md            -- Shared Principles: new bullet
agents/role_operations/rapid_scaffolder/*   -- explicit disclosure requirement
instructions/data_storytelling.md           -- one-line cross-reference
agents/analytics/dashboard_design/instructions.md -- one-line cross-reference
```

## Interfaces & Data Contracts

`synthetic_data_disclosure.md`'s required fields (validated by the gate via
grep, same idiom as `alert-contract-check.sh`): disclosed location
(section/chart), reason real data wasn't used, generation method, reviewer
sign-off. The Disclosure Table itself (one row per occurrence) is a human
authoring convention, not machine-validated row-by-row in this slice — the
gate checks the artifact declares the required *field types*, not that every
real occurrence has a row (that remains a human review responsibility, per
the constitution's stance that heuristic gates point a reviewer at
something, they don't replace review).

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P10 Honest reporting | yes | This spec exists specifically to operationalize P10 for data/visual content: no silent synthetic-data defaults, complete disclosure over a representative caveat. |
| P4 Correct by construction | yes | The priority stack makes "prefer real data" the default path, not an afterthought applied after synthetic data was already chosen for convenience. |
| P9 Security & data | consistent | Distinct from P9 (secrets/PII) but the same family of concern: what enters a decision-facing artifact must be honestly labeled, the way P9 requires secrets never enter it at all. |
| P5 Reversibility | yes | Docs/template/gate-only change, isolated on a branch. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `instructions/data_provenance.md` (Priority Stack section) | T-001 |
| REQ-002 | `templates/docs/synthetic_data_disclosure.md` | T-002 |
| REQ-003 | `hooks/stages/data-provenance-check.sh` | T-003 |
| REQ-004 | `agents/role_operations/README.md`, `rapid_scaffolder/{instructions,README}.md` | T-004 |
| NFR-001 | Gate tested in all three states (clean, flagged, resolved) | T-003 |
| NFR-002 | Validation gates | T-005 |
| NFR-003 | Heuristic-limitation language in gate header + spec Non-Goals/NFR-003 | T-003 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Scope of adoption | `role_operations` fully wired, `dashboard_design`/`data_storytelling` get a cross-reference line | Rework all three groups fully in this slice | The two existing groups already enforce "numbers from a governed source"; a full rework risks re-litigating logic that already works, when a pointer to the new standard is enough for now. |
| Row-level disclosure validation | Not machine-validated (human review responsibility) | Parse the Disclosure Table and cross-check every synthetic marker in the artifact | Reliable table-row-to-content matching would need artifact-format-specific parsing (Markdown table vs. HTML vs. dashboard payload) with no shared schema today; the field-presence check is honest about what a shell gate can actually verify. |
| Where to scope the heuristic scan | `docs/**` and `examples/**`, scaffold dirs excluded | Every `*.md` in the repo | Scanning `agents/`/`instructions/`/`templates/` would flag this SDK's own guidance text about synthetic data as if it were an undisclosed use — the same false-positive risk `secret-scan` already solved by excluding scaffold directories. |

## Validation Strategy

Run `hooks/stages/data-provenance-check.sh` directly in the three states
(clean, a docs/*.md mentioning synthetic data with no disclosure, the same
file after adding a disclosure) to confirm AC-002/AC-003/AC-004, then
`hooks/stages/run-stage.sh spec agent-catalog docs-link spec-index
secret-scan role-context data-provenance`, then `git diff --check`. AC-001
is covered by running the gate against a fully-filled disclosure template.
AC-005 is covered by direct inspection of `rapid_scaffolder/instructions.md`.

## Rollout, Observability & Rollback

Rollout is a branch commit (and push, if requested). Rollback is reverting
the single commit; the gate is additive to `run-stage.sh`'s `ALL` list and
does not change any existing gate's behavior.

## Open Questions

- Should disclosure requirements extend to runtime demo/test fixtures that
  use synthetic data by design, or is their existing docstring/README
  labeling sufficient given they aren't decision-facing content?
