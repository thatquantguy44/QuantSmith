# Plan: Test Engineering Agents (Python / C++ Fuzzing / JavaScript / TypeScript)

- **Spec:** 0062-test-engineering-agents (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-09-04

## Approach

Add `agents/test_engineering/` as a new category folder with a group README
plus five four-file public agents: one orchestrator and one specialist per
named language (Python, C++, JavaScript, TypeScript). Add the backing
instruction standard `instructions/test_engineering.md`. Update the agent
catalog, spec index, top-level README, `docs/handoff.md`, and
`docs/sdk_plan.md` so the group is discoverable, routable, and every
documented count matches the filesystem — following the same wiring
`0033-economists-agents` used.

## Architecture & Components

```text
requester's codebase (Python / C++ / JavaScript / TypeScript)
  -> test_engineering/test_engineering_orchestrator   # detects stack, routes
       -> test_engineering/python_test_engineer          # pytest, Hypothesis
       -> test_engineering/cpp_test_fuzz_engineer         # GoogleTest/Catch2 + libFuzzer/AFL++
       -> test_engineering/javascript_test_engineer        # Jest/Vitest/Mocha
       -> test_engineering/typescript_test_engineer          # + type-level tests
            -> testing_validation      # AC-to-test traceability, quant validation
            -> quality-guard-agent     # release gate (schema/contract/policy)

Explicit non-duplication:
  test_engineering/*        != testing_validation
    (how to write/run a test in this language   vs. is this AC actually covered)
  test_engineering/*        != quality-guard-agent
    (test authoring                             vs. release approve/reject decision)
```

## Interfaces & Data Contracts

No new schema. All five agents produce free-form Markdown plus test/fuzz
code, consistent with `asset_classes/`'s own precedent (no shared report
template) — the two-report-template pattern from `economists/` doesn't apply
here because these agents don't produce a recurring structured report, they
produce code and a short results summary.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Scope boundaries against `testing_validation` and `quality-guard-agent` prevent the group from making an unreviewed AC-coverage or release-gate call. |
| P10 Honest reporting | yes | Every agent flags an unproduced test/fuzz/coverage result as a gap rather than inventing one, per `instructions/test_engineering.md`. |
| P5 Reversibility | yes | Docs/contracts-only change, isolated on a branch. |
| — dual-use tooling policy | yes | `cpp_test_fuzz_engineer` states the authorized-target, sandboxed-execution boundary explicitly (RISK-002 in `spec.md`), consistent with this environment's security-tooling policy for fuzzing/dual-use tools. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `agents/test_engineering/README.md` | T-001 |
| REQ-002 | `agents/test_engineering/{test_engineering_orchestrator,python_test_engineer,cpp_test_fuzz_engineer,javascript_test_engineer,typescript_test_engineer}/` | T-002 |
| REQ-003 | `instructions/test_engineering.md` | T-003 |
| REQ-004 | Named handoff in each agent's `instructions.md` | T-002 |
| REQ-005 | Authorized-target boundary in `cpp_test_fuzz_engineer/instructions.md` | T-002 |
| REQ-006 | `agents/README.md`, `specs/README.md`, root `README.md`, `docs/handoff.md`, `docs/sdk_plan.md` | T-004 |
| NFR-001 | Four-file contract + `Spec-Driven Role` per agent | T-002 |
| NFR-002 | Validation gates | T-005 |
| NFR-003 | "Never invent, flag as gap" operating rule per agent | T-002, T-003 |
| NFR-004 | Explicit boundary language against `testing_validation`/`quality-guard-agent` | T-001, T-002, T-003 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| New category vs. expand `testing_validation` | New sibling category `agents/test_engineering/` | Turn `testing_validation` into a category folder with these as sub-agents | Category folders carry no `prompt.md` of their own; converting `testing_validation` would strip it of its identity as the stage-4 lifecycle agent directly referenced in the Lifecycle Agents table — a bigger, riskier structural change than adding a sibling group, and not what was asked. |
| Roster size | Five agents (orchestrator + Python + C++ fuzzing + JavaScript + TypeScript) | Four (drop the orchestrator) or fewer (combine JS/TS into one agent) | An orchestrator matches this SDK's existing pattern for a multi-specialist domain (`optimization_orchestrator`, `ml_orchestrator`, `dl_orchestrator`, `pm_orchestrator`); JavaScript and TypeScript stay separate because type-level testing (tsd/expect-type, strict-mode discipline) is a genuinely distinct responsibility from runtime-only JS testing. |
| Runtime scope | Contracts and standard only | Build a runtime test-scaffolding helper now | No concrete downstream workflow yet needs one; matches `0033`'s own precedent of contracts-first, runtime only once a driving use case exists. |
| Report template | None — free-form Markdown + code | A shared `templates/docs/test_engineering_report.md` | These agents' primary output is test/fuzz code, not a recurring structured report; a template would be an abstraction with no current shared structure to enforce, unlike `economists/`'s two report-writer agents which genuinely share one shape. |

## Validation Strategy

Run `hooks/stages/run-stage.sh docs-link agent-catalog spec-index doc-counts
handoff-sync`, then the full `pytest tests/ -q` (expected unaffected — no
runtime code in this slice) and `git diff --check`. AC-001 is covered by
direct inspection of the group README. AC-002/AC-004/AC-005 are covered by
direct inspection of each agent's `instructions.md`. AC-003 is covered by
direct inspection of the new standard. AC-006 is covered by
`agent-catalog`/`spec-index`/`doc-counts`/`handoff-sync` plus direct
inspection of the updated counts. AC-007 is covered by the gate run itself.

## Rollout, Observability & Rollback

Rollout is a branch commit (and push, if requested). Rollback is reverting
the single commit; no existing agent, gate, or template changes behavior —
`testing_validation` and `quality-guard-agent` are unmodified. A future
runtime spec can add a test-scaffolding helper under `src/quantsmith/` once a
concrete workflow needs one, following the `0006`/`0007` pattern of
promoting a contract-only group into a tested runtime.

## Open Questions

- Does a per-language variant for Go, Rust, or Java become worth adding once
  this group sees real cross-language use, versus keeping those out until a
  concrete request names them?
