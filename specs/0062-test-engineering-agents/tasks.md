# Tasks: Test Engineering Agents (Python / C++ Fuzzing / JavaScript / TypeScript)

- **Spec:** 0062-test-engineering-agents (`spec.md`, `plan.md`)
- **Last updated:** 2026-09-04

## Definition of Done (applies to every task)

- Agent contracts follow the four-file convention with a `Spec-Driven Role`
  section in each `instructions.md`.
- Each agent works with no configuration and states so explicitly.
- No fabricated test pass, fuzz-run result, or coverage number — every agent
  flags an unproduced result as a gap instead.
- Every agent names at least one downstream handoff.
- `cpp_test_fuzz_engineer` states the authorized-target, sandboxed-execution
  fuzzing boundary explicitly.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Write `agents/test_engineering/README.md`. | REQ-001 | done | Roster table, routing, shared principles, non-overlap boundary vs. `testing_validation`/`quality-guard-agent`. |
| T-002 | Add five agents. | REQ-002, REQ-004, REQ-005, NFR-001, NFR-003 | done | `test_engineering_orchestrator/`, `python_test_engineer/`, `cpp_test_fuzz_engineer/`, `javascript_test_engineer/`, `typescript_test_engineer/`. |
| T-003 | Write `instructions/test_engineering.md`. | REQ-003, NFR-003, NFR-004 | done | Determinism/flakiness, meaningful-assertion discipline, mutation-testing awareness, fuzzing safety boundary, explicit boundary vs. `testing_validation`/`quality-guard-agent`. |
| T-004 | Update catalogs and handoff docs. | REQ-006 | done | `agents/README.md`, `specs/README.md`, root `README.md`, `docs/handoff.md`, `docs/sdk_plan.md`; bump agents/instruction-standards/specs counts. |
| T-005 | Run validation gates. | NFR-002 | done | `docs-link`, `agent-catalog`, `spec-index`, `doc-counts`, `handoff-sync`; `pytest tests/ -q`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | Direct inspection of `agents/test_engineering/README.md` | done |
| AC-002 | Direct inspection of each of the five agents' `instructions.md` | done |
| AC-003 | Direct inspection of `instructions/test_engineering.md` | done |
| AC-004 | Direct inspection of each agent's named handoff | done |
| AC-005 | Direct inspection of `cpp_test_fuzz_engineer/instructions.md`'s authorized-target boundary | done |
| AC-006 | Direct inspection of `agents/README.md`, `specs/README.md`, root `README.md`, `docs/handoff.md`, `docs/sdk_plan.md` and their stated counts | done |
| AC-007 | `hooks/stages/run-stage.sh docs-link agent-catalog spec-index doc-counts handoff-sync` | done |

## Follow-ups

- A per-language variant for Go, Rust, or Java, if this group sees real
  cross-language use (carried as an open question in `spec.md`).
- A runtime test-scaffolding helper under `src/quantsmith/`, once a concrete
  workflow needs one (contracts-first, matching `0033`'s precedent).
