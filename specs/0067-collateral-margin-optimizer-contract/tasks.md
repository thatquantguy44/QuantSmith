# Tasks: Collateral & Margin Allocation Optimizer Contract

- **Spec:** 0067-collateral-margin-optimizer-contract (`spec.md`, `plan.md`)
- **Last updated:** 2026-09-09

## Definition of Done (applies to every task)

- Every collateral/margin field cites an existing `0063` `concept.*`/
  `convention.*`/`lifecycle.*` ID rather than new vocabulary.
- No real objective coefficient, constraint number, counterparty ID, or
  position appears anywhere committed — placeholders only.
- Every doc states plainly that no reference optimizer ships in this SDK.
- Envelope fields match `adapter_contract.md`'s Invocation Output verbatim.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Write `templates/optimization/collateral_margin_optimizer_contract.md`. | REQ-001, REQ-002, NFR-001, NFR-004 | done | Registration example, problem/solution field tables, required-behavior section. |
| T-002 | Write the problem and solution JSON templates. | REQ-002, REQ-003, NFR-001, NFR-003 | done | `collateral_margin_problem.template.json`, `collateral_margin_solution.template.json`. |
| T-003 | Update `agents/optimization/collateral_margin_optimization/instructions.md`. | REQ-004, NFR-004 | done | Added `Spec-Driven Role` section naming `0067` and the `0026` registration path. |
| T-004 | Resolve `0067`'s optimizer-boundary decision in `0063`'s tracked Draft Decisions. | REQ-005 | done | `knowledge/short_term_markets/README.md`, `specs/0063.../tasks.md` — reviewer, date, and resolution recorded. |
| T-005 | Update catalogs. | REQ-006 | done | `agents/README.md` (optimization row), `specs/README.md` (index row), `docs/handoff.md` (move `0067` out of the reserved table; roadmap item). |
| T-006 | Run validation gates. | NFR-002 | done | `spec`, `docs-link`, `spec-index`, `doc-counts`, `handoff-sync`, `agent-catalog`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | Direct inspection of `collateral_margin_optimizer_contract.md` | done |
| AC-002 | Direct inspection of both JSON templates against `0063` IDs | done |
| AC-003 | Direct inspection of `collateral_margin_optimization/instructions.md` | done |
| AC-004 | Direct inspection of `knowledge/short_term_markets/README.md` and `specs/0063.../tasks.md` | done |
| AC-005 | Direct inspection of `agents/README.md`, `specs/README.md`, `docs/handoff.md` | done |
| AC-006 | `hooks/stages/run-stage.sh spec docs-link spec-index doc-counts handoff-sync agent-catalog` | done |

## Follow-ups

- A structural JSON-Schema validator for the problem/solution payloads, once
  a real optimizer is registered against this contract (carried as this
  spec's own open question).
- `0064`/`0065`/`0066`, once each is individually approved and activated —
  none of them are a dependency of this contract.
