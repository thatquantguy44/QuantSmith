# Plan: Quant Model Factory

- **Spec:** 0061-quant-model-factory (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-09-03

## Approach

One new module, `src/quantsmith/pipelines/quant_factory.py`, standard
library only. Pure dataclasses for the inputs/outputs; a stateless
`score_lane` function; a `FactoryRunner` class whose only side effect is
a JSONL ledger append. The caller injects a `lane_executor` callable, so
the factory runtime has no opinions about training frameworks, data
loaders, or model types. The three convergence modes are three small pure
functions inside `FactoryRunner.run`; no inheritance or plugin registry.

This pattern mirrors `market_brief.py` (caller-injected fetch functions,
no network in the module) and `ingestion_data_contract.py` (candidates
proposed, never promoted). The factory proposes a decision; the caller
ships it.

## Architecture & Components

```text
quant_factory.py
  FactorySpec
    run_id          str
    convergence_mode  "best_of_n" | "all_required" | "first_to_pass"
    gate            ConvergenceGate
    lanes           tuple[LaneSpec, ...]
    seed            int
    deadline_seconds  float  (default inf)
    ledger_path     Path

  LaneSpec
    lane_id         str
    hypothesis      str
    feature_set     tuple[str, ...]
    model_tag       str
    backtest_config dict
    status          LaneStatus (initial: "draft")

  LaneResult
    lane_id         str
    status          LaneStatus
    sharpe          float | None
    max_drawdown    float | None   (negative convention)
    annual_return   float | None
    gate_score      float | None   (set by runner after scoring)
    leakage_flags   tuple[str, ...]
    elapsed_seconds float
    error           str | None

  ConvergenceGate
    min_sharpe        float
    max_drawdown      float   (negative, e.g. -0.15)
    min_annual_return float
    n_best            int     (best_of_n only)
    pass_threshold    float   (> 0.0, validated at construction)

  FactoryDecision
    run_id           str
    decision         "approved" | "failed"
    approved_lanes   tuple[str, ...]
    lane_results     tuple[LaneResult, ...]
    elapsed_seconds  float

  FactoryError(ValueError)

  score_lane(result: LaneResult, gate: ConvergenceGate) -> float
    # Three components:
    #   sharpe_score  = clip((sharpe - 0) / (gate.min_sharpe * 2), 0, 1)
    #   dd_score      = clip((drawdown - gate.max_drawdown) / abs(gate.max_drawdown), 0, 1)
    #   return_score  = clip((ret - gate.min_annual_return) / gate.min_annual_return, 0, 1)
    #   final         = mean(sharpe_score, dd_score, return_score)
    # 0.0 on any leakage_flag or error, or any metric being None.

  FactoryRunner
    run(spec: FactorySpec,
        lane_results: Sequence[LaneResult]) -> FactoryDecision
      1. Validate spec (unique lane_ids, valid convergence_mode, non-empty lanes)
      2. Validate results (all lane_ids in spec)
      3. Score each result via score_lane
      4. Apply convergence mode → FactoryDecision
      5. Append JSONL entry to spec.ledger_path
      6. Return FactoryDecision

  _converge_best_of_n(results, gate) -> FactoryDecision
  _converge_all_required(results, gate) -> FactoryDecision
  _converge_first_to_pass(results, gate) -> FactoryDecision

  _append_ledger(path, spec, decision, start_time)
```

### Agent directory (`agents/quant_factory/`)

```text
agents/quant_factory/
  README.md       -- purpose, inputs, outputs, when to use
  instructions.md -- spec-driven role, lane state machine, gate usage,
                     human-review requirement before shipping
  prompt.md       -- system prompt for the factory orchestrator
  tasks.md        -- per-run task checklist (hypothesis → spec → run → review → ship)
```

### Prompt template

```text
templates/prompts/factory_run_card.md
  -- Structured template for one factory run request:
     run_id, hypotheses (one per lane), gate thresholds, convergence_mode,
     seed, deadline_seconds, expected deliverables
```

## Interfaces & Data Contracts

### `score_lane` formula (REQ-005)

All three metric components are normalized against the gate's own minimum
values so the gate author's declared standards define "good". Each
component is clipped to [0, 1] before averaging:

```
sharpe_component  = clip((sharpe - 0)              / max(gate.min_sharpe * 2, ε), 0, 1)
dd_component      = clip((drawdown - gate.max_dd)  / max(abs(gate.max_dd), ε),   0, 1)
return_component  = clip((ret - gate.min_ret)      / max(gate.min_ret, ε),        0, 1)
score             = mean(sharpe_component, dd_component, return_component)
```

Where ε = 1e-9 (prevents division by zero when gate min equals 0).
A lane with any `leakage_flags`, `error` set, or any metric `None` → 0.0.

### Lane state machine

```
draft → specified → running → gate_pending → approved
                                           → rejected
                             skipped       (first_to_pass only)
```

The factory runtime sets status on `LaneResult` objects it returns in the
`FactoryDecision`; it does not mutate the caller's `LaneSpec` objects.

### JSONL ledger entry (REQ-010)

```json
{
  "run_id": "...",
  "timestamp": "2026-09-03T12:00:00Z",
  "convergence_mode": "best_of_n",
  "gate": {"min_sharpe": 0.8, "max_drawdown": -0.15, "min_annual_return": 0.05,
           "n_best": 1, "pass_threshold": 0.6},
  "lane_summaries": [
    {"lane_id": "lane_a", "status": "approved", "gate_score": 0.74,
     "leakage_flags": [], "error": null, "elapsed_seconds": 42.1}
  ],
  "decision": "approved",
  "approved_lanes": ["lane_a"],
  "elapsed_seconds": 42.1
}
```

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | `score_lane` is pure; the three convergence functions are pure; ledger write is the only side effect; duplicate `lane_id` raises before any work. |
| P5 Reversibility | yes | `FactoryRunner.run` appends to the ledger (never overwrites); the caller decides what to ship; no model weights or registry entries are mutated by this module. |
| P6 Observability | yes | Full per-lane score and status in every `FactoryDecision` and every ledger entry; `FactoryError` on write failure embeds the full decision so nothing is silently lost. |
| P9 Security & data | yes | No network, no credentials; `ledger_path` is caller-specified; no credential-shaped content; no data loaded. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `FactorySpec` dataclass | T-001 |
| REQ-002 | `LaneSpec` dataclass | T-001 |
| REQ-003 | `LaneResult` dataclass | T-001 |
| REQ-004 | `ConvergenceGate` dataclass | T-001 |
| REQ-005 | `score_lane` function | T-001 |
| REQ-006 | `FactoryRunner.run` | T-001 |
| REQ-007 | `_converge_best_of_n` | T-001 |
| REQ-008 | `_converge_all_required` | T-001 |
| REQ-009 | `_converge_first_to_pass` | T-001 |
| REQ-010 | `_append_ledger` | T-001 |
| REQ-011 | Validation in `FactoryRunner.run` | T-001 |
| REQ-012 | `agents/quant_factory/` four-file contract | T-003 |
| REQ-013 | `templates/prompts/factory_run_card.md` | T-003 |
| REQ-014 | Cross-references in `specs/README.md`, `README.md`, `agents/README.md` | T-004 |
| NFR-001 | stdlib only, no imports from `src/quantsmith/` | T-001 |
| NFR-002 | `score_lane`, `_converge_*` are pure; only `_append_ledger` writes | T-001 |
| NFR-003 | Deterministic: same inputs → same output | T-001 |
| NFR-004 | Full lane summaries in `FactoryDecision` and ledger | T-001 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Pure factory runtime, parallel execution is caller's responsibility | Caller injects ordered `LaneResult` list | `asyncio`/`ThreadPoolExecutor` inside the factory | Keeps the module stdlib-only and import-cycle-free; parallelism at the agent layer (the prompt describes how to launch lanes concurrently) is more flexible than hard-wiring a thread model. |
| Equal-weight score formula | `mean(sharpe, dd, return)` | Weighted sum with caller-supplied weights | Equal weights are correct by default and the formula is simple enough to audit; weights can be added to `ConvergenceGate` in a follow-up without breaking the interface. |
| Three discrete convergence modes | `best_of_n`, `all_required`, `first_to_pass` | Single generic `ConvFunc` callback | Three named modes are auditable and ledger-readable; a callback is opaque to the ledger and harder to reason about in a review. |
| Append-only JSONL ledger | `_append_ledger` opens in `"a"` mode | Database, structured log sink | JSONL is stdlib, human-readable, and easily grep-able; the same pattern `ResearchAuditLedger` in `0056` uses. |
| `FactoryError` embeds decision on ledger write failure | Raise with full decision JSON | Silently return decision if write fails | RISK-002 mitigation: a run with no audit trail is not safe to proceed silently; the caller can choose to log the error and continue, but the default is loud. |

## Validation Strategy

One test per AC (AC-001 through AC-013) in `tests/test_quant_factory.py`.
All tests use in-memory `LaneResult` fixtures; no file system access
except AC-010/AC-013 (ledger write via `tmp_path` pytest fixture or
`tempfile.TemporaryDirectory`). No mocking — the module is pure enough
that injected fixtures cover everything.

## Rollout, Observability & Rollback

- New module; no existing code changed. Rollback = delete the file.
- Ledger is append-only; a bad run entry can be annotated manually.
- The `agents/quant_factory/instructions.md` gate requires human review
  before any `approved` lane is shipped; the module itself never triggers
  a deployment.

## Open Questions

- Should `score_lane` expose a `weights` parameter on `ConvergenceGate`?
  Deferred — equal weights first, extend in a follow-up.
- Should the ledger support a `notes` freeform field for the human
  reviewer's comments? Deferred — the ledger format is append-only JSON;
  a follow-up can add a separate annotations file.
