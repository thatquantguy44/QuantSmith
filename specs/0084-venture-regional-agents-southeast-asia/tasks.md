# Tasks: Venture Regional Agents — Southeast Asia & Multilingual Document NLP

- **Spec:** 0084-venture-regional-agents-southeast-asia (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-02

> Every task cites a requirement and carries a Definition of Done.

## Definition of Done (applies to every task)

- Four contract files per agent; never-boundary stated; no data or credentials.
- `agent-catalog-check.sh` passes.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Multilingual document NLP agent | REQ-001, REQ-003 | done | |
| T-002 | Three Southeast Asia agents | REQ-002, REQ-003 | done | |
| T-003 | Group README with regional roster | REQ-004 | done | |
| T-004 | Catalog section in `agents/README.md` | REQ-005 | done | |
| T-005 | Standard and dictionary section | REQ-006 | done | |
| T-006 | Run gates and review for stray data | NFR-001, NFR-002 | todo | |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | manual read of multilingual agent | todo |
| AC-002 | agent-catalog-check.sh | todo |
| AC-003 | manual read of READMEs | todo |
| AC-004 | manual read of group README | todo |
| AC-005 | agent-catalog-check.sh | todo |
| AC-006 | manual read | todo |
| AC-007 | run-stage.sh spec + agent-catalog | todo |
