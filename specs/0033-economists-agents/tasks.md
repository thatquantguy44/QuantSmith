# Tasks: Economists Agent Expansion

- **Spec:** 0033-economists-agents (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-10

## Definition of Done (applies to every task)

- Agent contracts follow the four-file convention with a `Spec-Driven Role`
  section in each `instructions.md`.
- Each agent works with no configuration and states so explicitly.
- No fabricated indicator value, policy statement, or forecast — every
  agent flags a gap instead.
- Every agent names at least one downstream handoff.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Replace the placeholder `agents/economists/README.md` with a real group README. | REQ-001 | done | Four pillars, agent table, shared principles, where-they-fit, scope-boundary note. |
| T-002 | Add seven agents. | REQ-002, REQ-005, NFR-001, NFR-003 | done | `macro_indicator_analyst/`, `monetary_policy_analyst/`, `macro_regime_classifier/`, `cross_asset_macro_linkages/`, `macro_scenario_analyst/`, `macro_backdrop_summarizer/`, `economic_outlook_report_writer/`. |
| T-003 | Write `instructions/macro_economic_analysis.md`. | REQ-003, NFR-003, NFR-004 | done | PIT/vintage discipline, real-data-first, explicit boundary vs. `macro_multi_asset`/`model_signal_monitoring`. |
| T-004 | Write `templates/docs/macro_backdrop_report.md`. | REQ-004 | done | Shared by the two reporting agents; `Cadence` field. |
| T-005 | Update catalogs and handoff docs. | REQ-006 | done | `agents/README.md`, `specs/README.md`, root `README.md`, `docs/handoff.md`, `docs/handoffs/future_features.md`, `docs/sdk_plan.md`. |
| T-006 | Run validation gates. | NFR-002 | done | `spec`, `agent-catalog`, `docs-link`, `spec-index`; `pytest tests/ -q`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | Direct inspection of `agents/economists/README.md` | done |
| AC-002 | Direct inspection of each of the seven agents' `instructions.md` | done |
| AC-003 | Direct inspection of `instructions/macro_economic_analysis.md` | done |
| AC-004 | Direct inspection of `templates/docs/macro_backdrop_report.md` | done |
| AC-005 | Direct inspection of each agent's named handoff | done |
| AC-006 | Direct inspection of `agents/README.md`, `specs/README.md`, root `README.md` | done |
| AC-007 | `hooks/stages/run-stage.sh spec agent-catalog docs-link spec-index` | done |

## Follow-ups

- A per-region policy-agent variant, if this group sees real cross-region
  use (carried as an open question in `spec.md`).
- An indicator-vintage runtime helper under `src/quantsmith/`, once a
  concrete workflow needs one (contracts-first, matching `0022`'s
  precedent).
