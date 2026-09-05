# Spec: Test Engineering Agents (Python / C++ Fuzzing / JavaScript / TypeScript)

- **ID:** 0062-test-engineering-agents
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-09-04

## Problem & Context

`agents/testing_validation/` (lifecycle stage 4, "Verify") maps acceptance
criteria to test evidence and reviews quant-specific validity — leakage,
look-ahead, sample size, determinism. It does not own *how* to write a
pytest fixture, a libFuzzer harness, or a Vitest mock; it owns "is this `AC-*`
actually covered," not "how do you test in this language."
`agents/quality-guard-agent/` is a separate, orthogonal runtime gate —
schema/contract/policy approve-or-reject before a pipeline stage releases —
and likewise does not touch test-authoring mechanics.

Nothing in the SDK currently supplies language-specific test-engineering
expertise: idiomatic unit/integration test structure, mocking and fixture
discipline, coverage that means something versus coverage chased for its own
sake, and — for compiled/memory-unsafe code — fuzzing and sanitizer
discipline. A quant repo scaffolded from this SDK (per `CLAUDE.md`, the SDK's
own stated purpose) has research and pipeline code in Python, may have
performance-critical or memory-unsafe components in C++, and may have a
web/dashboard surface in JavaScript/TypeScript (as this repo's own `web/`
already does) — with no agent to consult for any of it.

## Goals

- Add a real `agents/test_engineering/` category folder with a group README
  and five agents:
  - **Orchestrator:** `test_engineering_orchestrator` — routes a testing
    request to the right language agent(s) by detected stack, and hands off
    results to `testing_validation` (AC mapping) and `quality-guard-agent`
    (release gate) rather than making either call itself.
  - **Python:** `python_test_engineer` — pytest: fixtures, parametrization,
    mocking discipline, property-based testing (Hypothesis), coverage
    without coverage-chasing.
  - **C++:** `cpp_test_fuzz_engineer` — GoogleTest/Catch2 unit tests plus
    fuzz harness construction (libFuzzer/AFL++), sanitizer discipline
    (ASan/UBSan/MSan/TSan), corpus and crash-triage practice, and an
    explicit authorized-target-only fuzzing boundary.
  - **JavaScript:** `javascript_test_engineer` — Jest/Vitest/Mocha unit and
    integration tests, mocking/async discipline, DOM/component testing
    patterns.
  - **TypeScript:** `typescript_test_engineer` — the same runtime tooling
    plus type-level testing (tsd/expect-type) and strict-mode discipline.
- Add `instructions/test_engineering.md`, the shared backing standard:
  determinism/no flaky tests, meaningful assertions over coverage-for-its-
  own-sake, mutation-testing awareness, the fuzzing safety boundary
  (authorized, sandboxed targets only — never production or a third-party
  system), and the group's explicit non-overlap boundary against
  `testing_validation` and `quality-guard-agent`.
- Update the agent catalog, spec index, and top-level README, `docs/handoff.md`,
  and `docs/sdk_plan.md` so the group is discoverable, routable, and every
  documented count (agents, instruction standards, specs) matches the
  filesystem, matching every other category-group spec's wiring (`0022`,
  `0024`, `0033`).

## Non-Goals

- No runtime code, executable CI job, or live test-execution service in this
  slice — agent contracts and a backing standard only, consistent with
  `0033`'s own precedent (a future implementation spec may add a runtime
  test-scaffolding helper under `src/quantsmith/` once a concrete downstream
  workflow needs one).
- No duplication of `testing_validation` (AC-to-test traceability, quant
  validation: leakage/look-ahead/significance) or `quality-guard-agent`
  (pipeline release gate: schema/contract/PII/naming policy) — this group
  hands off to both rather than replacing either.
- No language beyond the four named now. Go, Rust, and Java variants are a
  natural follow-up once this group sees real use, not a gap to fill
  pre-emptively (see Open Questions).
- No new hook/gate script. The group's outputs are agent contracts and test/
  fuzz code the requester's own CI runs; existing `agent-catalog`,
  `docs-link`, `spec-index`, `doc-counts`, and `handoff-sync` gates cover
  this slice, matching `asset_classes/` and `economists/`'s own precedent of
  no dedicated gate for a contracts-only category.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The system shall provide a `agents/test_engineering/` category folder with a group README describing the roster, scope, and routing. | must |
| REQ-002 | The system shall provide five four-file agents (`test_engineering_orchestrator`, `python_test_engineer`, `cpp_test_fuzz_engineer`, `javascript_test_engineer`, `typescript_test_engineer`), each usable with no configuration. | must |
| REQ-003 | The system shall provide `instructions/test_engineering.md`, covering determinism/flakiness, meaningful-assertion discipline, mutation-testing awareness, the fuzzing safety boundary, and explicit scope boundaries against `testing_validation` and `quality-guard-agent`. | must |
| REQ-004 | Every agent's `instructions.md` shall state a named downstream handoff (`testing_validation` and/or `quality-guard-agent`, or `test_engineering_orchestrator` for the four language agents) rather than presenting itself as the final release decision. | must |
| REQ-005 | `cpp_test_fuzz_engineer`'s `instructions.md` shall state explicitly that fuzzing targets only code the requester owns or is authorized to test, run in a sandboxed/local environment — never a production system or a third party's service. | must |
| REQ-006 | The agent catalog (`agents/README.md`), spec index (`specs/README.md`), top-level `README.md`, `docs/handoff.md`, and `docs/sdk_plan.md` shall list the new group and its agents, with every documented agent/instruction-standard/spec count matching the filesystem. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Agent contract consistency | Every new public agent has `README.md`, `prompt.md`, `instructions.md`, `tasks.md`, each with a `Spec-Driven Role` section. |
| NFR-002 | Repository hygiene | `docs-link`, `agent-catalog`, `spec-index`, `doc-counts`, `handoff-sync` gates and the full pytest suite pass. |
| NFR-003 | No fabrication | No agent claims a test passed, a fuzz run found nothing, or coverage reached a stated number without that evidence actually being supplied or produced; an unavailable result is a stated gap, per `instructions/data_provenance.md`'s real-data-first standard applied to test evidence. |
| NFR-004 | Scope boundary | Every agent's docs state explicitly what stays owned by `testing_validation` and `quality-guard-agent`, so a reader never assumes duplication. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given `agents/test_engineering/README.md`, when inspected, then it describes all five agents, their routing, and the group's non-overlap boundary. | REQ-001 |
| AC-002 | Given each of the five agents' `instructions.md`, when inspected, then each explicitly states it must work without configuration and never claims a test/fuzz/coverage result not actually produced. | REQ-002, NFR-001, NFR-003 |
| AC-003 | Given `instructions/test_engineering.md`, when inspected, then it covers determinism/flakiness, meaningful-assertion discipline, the fuzzing safety boundary, and the boundary against `testing_validation`/`quality-guard-agent`. | REQ-003 |
| AC-004 | Given each agent's `instructions.md`, when inspected, then each names at least one downstream handoff. | REQ-004 |
| AC-005 | Given `agents/test_engineering/cpp_test_fuzz_engineer/instructions.md`, when inspected, then it states fuzzing is scoped to authorized, sandboxed targets only. | REQ-005 |
| AC-006 | Given `agents/README.md`, `specs/README.md`, root `README.md`, `docs/handoff.md`, and `docs/sdk_plan.md`, when inspected, then each lists the `test_engineering/` group and its five agents, and every stated agent/instruction-standard/spec count matches the filesystem. | REQ-006 |
| AC-007 | Given the full gate suite, when run, then `docs-link`, `agent-catalog`, `spec-index`, `doc-counts`, `handoff-sync` all pass. | NFR-002 |

## Data & Dependencies

No data dependencies, no runtime code. Agents reference each requester's own
existing test tooling (pytest, GoogleTest/Catch2 + libFuzzer/AFL++, Jest/
Vitest/Mocha) and this repo's own `pyproject.toml` (`dev` extra: `pytest`)
and `web/package.json` (Vite/TypeScript) as the worked, in-repo examples a
new agent can point to.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | The new group's scope overlaps with `testing_validation` (AC-to-test mapping, quant validation) or `quality-guard-agent` (release gate), causing duplicated or conflicting guidance. | Confusing routing; two agents give inconsistent answers to the same testing question. | Each agent's `instructions.md` and the group README state the boundary explicitly and name the downstream handoff instead of making an AC-coverage or release-gate call (AC-004, NFR-004) — the same pattern already proven for `asset_classes/` against `trading_strategies/`/`securities_financing/` and for `economists/` against `trading_strategies/macro_multi_asset`/`monitoring/model_signal_monitoring`. |
| RISK-002 | `cpp_test_fuzz_engineer`'s fuzzing guidance is used against an unauthorized target (a production system or a third party's service), producing a real availability or legal incident rather than a test artifact. | Denial-of-service or unauthorized-testing incident. | `instructions/test_engineering.md` and `cpp_test_fuzz_engineer/instructions.md` both state the authorized-target-only, sandboxed-execution boundary explicitly (REQ-005, AC-005), consistent with this environment's own dual-use security-tooling policy. |
| RISK-003 | An agent reports a test passing, a fuzz run finding nothing, or a coverage number that was never actually produced. | A workflow ships on fabricated test evidence. | `instructions/test_engineering.md` and every agent's operating rules require flagging an unproduced result as a gap rather than inventing one (NFR-003), the same real-data-first standard `0033` applied to indicator/policy values. |

## Assumptions & Open Questions

- Assumption: five agents (an orchestrator plus one per named language) is
  the right first slice — enough to cover the languages actually named
  (Python, C++, JavaScript, TypeScript) without building a per-language
  agent before any of this has been used.
- Assumption: JavaScript and TypeScript warrant separate agents rather than
  one combined agent, because TypeScript's type-level testing surface
  (tsd/expect-type, strict-mode discipline) is a genuinely distinct
  responsibility from JavaScript's runtime-only testing — mirroring how this
  SDK already keeps `tooling/react` separate from other tooling agents
  rather than collapsing distinct stacks into one role.
- Open question: does a per-language variant for Go, Rust, or Java become
  worth adding once this group sees real cross-language use, versus keeping
  those out until a concrete request names them (the same open-question
  pattern `0033` carried for a per-region policy-agent variant)?

## Exceptions

None.
