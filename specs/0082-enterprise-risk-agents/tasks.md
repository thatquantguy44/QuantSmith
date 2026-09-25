# Tasks: Enterprise Risk Agents

- **Spec:** 0082-enterprise-risk-agents (`spec.md`, `plan.md`)
- **Last updated:** 2026-09-25

> Ordered, testable units of work. Every task cites the requirement(s) it advances
> and carries a Definition of Done. No task without a requirement.

## Definition of Done (applies to every task)

- Every agent has all four contract files (`README.md`, `instructions.md`,
  `tasks.md`, `prompt.md`).
- Every `instructions.md` has a `Spec-Driven Role` section.
- No company data, credentials, or personal data anywhere.
- `hooks/stages/agent-catalog-check.sh` and
  `PYTHONPATH=src python3 -m pytest tests/test_analytics_packs.py -q` pass.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Create `agents/enterprise_risk/` with six agents (`operational_risk`, `model_risk_management`, `counterparty_credit_risk`, `aml_financial_crime`, `liquidity_treasury_risk`, `climate_esg_risk`), each with all four contract files and a stated "never does this" boundary. | REQ-001, REQ-003, NFR-003 | done | |
| T-002 | Write `instructions/enterprise_risk.md`: the shared measure/never-decide rule and per-agent never-table. | REQ-002, NFR-003 | done | |
| T-003 | Re-point `reviewer_agents` in the 7 named `0081` packs to the matching new agent; leave every other pack, and `agents/risk/` itself, unmodified; regenerate `knowledge/analytics_packs/README.md`'s catalog table. | REQ-004, REQ-006 | done | `builds_on` on the 7 packs also gained `instructions/enterprise_risk.md`. |
| T-004 | Add the `Enterprise Risk Agents` section to `agents/README.md`. | REQ-005 | done | |
| T-005 | Run `agent-catalog-check.sh`, the `analytics_packs` validator and test suite, and the full repository test suite; fix any finding. | NFR-001, NFR-002 | done | |
| T-006 | Update `docs/handoff.md` and `docs/handoffs/future_features.md`; register the spec in `specs/README.md`; bump the next unreserved spec number. | REQ-005 | done | |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `agent-catalog-check.sh` (structural: four files per agent) | done |
| AC-002 | Manual read of `instructions/enterprise_risk.md` | done |
| AC-003 | Manual read of each agent's `README.md` | done |
| AC-004 | `test_analytics_packs.py::test_ac008_reviewer_and_builds_on_must_exist` (existence) + manual diff of the 7 JSON files | done |
| AC-005 | Manual read of `agents/README.md`'s new section | done |
| AC-006 | `git diff --stat knowledge/analytics_packs/` shows exactly 7 files + `README.md` | done |
| AC-007 | `hooks/stages/agent-catalog-check.sh` | done |
| AC-008 | `PYTHONPATH=src python3 -m quantsmith.pipelines.analytics_packs` | done |

## Follow-ups

Tracked work intentionally deferred (no silent "temporary" shortcuts — P8).

- A runtime for any of the six agents, once a real caller-supplied data
  model exists for one of them.
- A knowledge pack for any of the six, if a runtime is built and needs the
  same coverage-gap/golden-case apparatus `0072`/`0063` have.
