# Spec: Quant Model Factory

- **ID:** 0061-quant-model-factory
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-09-03

## Problem & Context

Building a quant signal or model involves many competing hypotheses —
different alpha expressions, feature sets, validation windows, risk
budgets — that cannot be evaluated sequentially without introducing look-
ahead or selection bias. Today each candidate is developed by hand, in
series, and the "winner" reflects whatever the analyst examined last as
much as any genuine edge.

The Quant Model Factory spec designs an agentic system where multiple model
candidates run **in parallel**, each in its own isolated lane, then
**converge** at a shared gate that applies a uniform, pre-declared scoring
rule. The gate, not the analyst's memory, decides which candidates advance.
This is the same principle `0009-experimentation` applied to A/B test
design and `0044-backtesting` applied to backtest integrity — here applied
to the whole model development lifecycle.

Three questions motivated the design choices in this spec:

1. **How do lanes communicate without leaking decisions across them?** Each
   lane's executor is injected by the caller; lanes share only a typed
   `LaneResult` schema, never intermediate state or partially-fitted
   artefacts.

2. **What happens when some lanes finish before others?** The factory
   runtime collects results as they arrive and waits until the convergence
   mode's quorum condition is satisfied, or until a deadline passes.

3. **How is the run reproducible?** Every factory run produces an
   append-only `FactoryLedger` (JSONL, same pattern as `ResearchAuditLedger`
   in `0056`) that records every lane's inputs, outputs, gate scores, and
   the final convergence decision — enough to re-derive the winner from
   scratch.

## Goals

- Add `src/quantsmith/pipelines/quant_factory.py`: typed dataclasses for
  `FactorySpec`, `LaneSpec`, `LaneResult`, `ConvergenceGate`, and
  `FactoryLedger`; a pure `score_lane` function; a `FactoryRunner` class
  that executes lanes (via a caller-injected `lane_executor`), applies the
  convergence gate, and appends to the ledger.
- Support three convergence modes — `best_of_n` (pick the lane with the
  best gate score), `all_required` (ensemble — every lane must pass), and
  `first_to_pass` (race — first lane whose score meets the gate threshold
  wins).
- Enforce a strict lane state machine (`draft → specified → running →
  gate_pending → approved → rejected → shipped`) so status is always
  observable and transitions are explicit.
- Produce a JSONL `FactoryLedger` entry per factory run: lane inputs,
  outputs, scores, convergence decision, and elapsed time.
- Add `agents/quant_factory/`: an agent directory with the standard
  four-file contract (`README.md`, `instructions.md`, `prompt.md`,
  `tasks.md`) — no runtime code, following every other domain agent.
- Add `templates/prompts/factory_run_card.md`: a prompt template that
  structures a single factory run request (hypotheses, gate thresholds,
  convergence mode, seed).

## Non-Goals

- **No live model training or data fetching in `quant_factory.py`.**
  The `lane_executor` is caller-injected; this module never calls a
  training library or loads data directly.
- **No parallel threading or multiprocessing in the factory runtime.**
  Parallelism is the caller's responsibility; the factory runtime is a
  pure coordination layer that processes `LaneResult` objects as they are
  supplied, in the order the caller provides them. The `agents/quant_factory/`
  contract describes how an LLM orchestrator launches lanes in parallel at
  the agent layer — this module does not implement that.
- **No hyperparameter search or AutoML loop.** Each lane is a discrete,
  human-declared hypothesis; this is not a grid/random/Bayesian search
  engine.
- **No promotion into a live production registry.** `FactoryRunner.run`
  returns a `FactoryDecision` struct; what happens next (tagging a git
  commit, opening a PR, updating a registry) is the caller's responsibility.
- **No GUI, dashboard, or streaming status.** Observability is the JSONL
  ledger and the caller's stdout; a future spec can build on top.
- **No modification to `0044-backtesting` or `0009-experimentation`.**
  `quant_factory.py` imports the gate-metric types it needs from
  `backtesting.py` where they already exist; it does not change them.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | `FactorySpec` shall declare: `run_id` (str), `convergence_mode` (one of `best_of_n`, `all_required`, `first_to_pass`), `gate` (a `ConvergenceGate`), `lanes` (sequence of `LaneSpec`), `seed` (int), and `deadline_seconds` (float, default `inf`). | must |
| REQ-002 | `LaneSpec` shall declare: `lane_id` (str), `hypothesis` (str), `feature_set` (tuple of str), `model_tag` (str), `backtest_config` (dict), and `status` (initial value `draft`). | must |
| REQ-003 | `LaneResult` shall declare: `lane_id`, `status` (one of the state-machine values), `sharpe` (float or None), `max_drawdown` (float or None), `annual_return` (float or None), `gate_score` (float or None), `leakage_flags` (tuple of str), `elapsed_seconds` (float), and `error` (str or None). | must |
| REQ-004 | `ConvergenceGate` shall declare: `min_sharpe` (float), `max_drawdown` (float, negative convention), `min_annual_return` (float), `n_best` (int, used by `best_of_n`), and `pass_threshold` (float, score ≥ threshold → approved). | must |
| REQ-005 | `score_lane(result, gate)` shall return a float in [0, 1] computed from the Sharpe ratio, drawdown, and annual return components (each normalized and clipped to [0, 1]) averaged equally; a lane with any leakage flag or `error` set scores 0.0. | must |
| REQ-006 | `FactoryRunner.run(spec, lane_results)` shall: (a) reject any `LaneResult` whose `lane_id` is not in `spec.lanes`; (b) score each result; (c) apply the convergence mode to produce a `FactoryDecision`; (d) append one JSONL entry to `spec.ledger_path` before returning. | must |
| REQ-007 | `best_of_n` convergence shall rank all passing lanes by `gate_score` descending and return the top-`n_best` as `approved`; all others are `rejected`. If no lane passes the threshold, the run is `failed`. | must |
| REQ-008 | `all_required` convergence shall approve the run only when every lane's score meets `pass_threshold`; if any lane fails (score below threshold, leakage, or error), the run is `failed`. | must |
| REQ-009 | `first_to_pass` convergence shall approve the first lane (in the order supplied to `run`) whose score meets `pass_threshold`; remaining lanes are `skipped`. If no lane passes, the run is `failed`. | must |
| REQ-010 | The ledger entry shall be a JSON object with: `run_id`, `timestamp` (ISO-8601), `convergence_mode`, `gate` (gate params as dict), `lane_summaries` (list of per-lane dicts with `lane_id`, `status`, `gate_score`, `leakage_flags`, `error`, `elapsed_seconds`), `decision` (`approved`/`failed`), `approved_lanes` (list of `lane_id`), and `elapsed_seconds` (total). | must |
| REQ-011 | `FactoryRunner` shall raise `FactoryError` (a `ValueError` subclass) on: an empty `lanes` list, an unrecognised `convergence_mode`, a duplicate `lane_id` in `spec`, or a `LaneResult` with a `lane_id` not in `spec`. | must |
| REQ-012 | Add `agents/quant_factory/` with the standard four-file contract (`README.md`, `instructions.md`, `prompt.md`, `tasks.md`) and a row in `agents/README.md`. | must |
| REQ-013 | Add `templates/prompts/factory_run_card.md`: a structured template for a single factory run request, covering hypotheses, gate thresholds, convergence mode, seed, and deadline. | must |
| REQ-014 | `specs/README.md`, root `README.md`, and `agents/README.md` shall reference spec `0061`. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Dependency isolation | Standard library only (`dataclasses`, `datetime`, `pathlib`, `json`, `math`); no new dependency. |
| NFR-002 | No I/O in scoring or convergence | `score_lane` and the three convergence functions are pure; only `FactoryRunner.run`'s ledger write touches the filesystem. |
| NFR-003 | Determinism | Given the same `FactorySpec` and the same ordered list of `LaneResult` objects, `run` always produces the same `FactoryDecision` and the same ledger entry. |
| NFR-004 | Observability | Every `FactoryDecision` carries the full score and status for every lane, not just the winner, so a reviewer can audit any run from the ledger alone. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a `LaneResult` with valid Sharpe, drawdown, and return and no leakage flags, when `score_lane` runs, then the score is a float in [0, 1]. | REQ-005 |
| AC-002 | Given a `LaneResult` with a leakage flag, when `score_lane` runs, then the score is 0.0 regardless of the metric values. | REQ-005 |
| AC-003 | Given a `LaneResult` with `error` set, when `score_lane` runs, then the score is 0.0. | REQ-005 |
| AC-004 | Given two lanes and `convergence_mode=best_of_n` with `n_best=1`, when `run` is called and one lane outscores the other, then the better lane is `approved` and the other `rejected`. | REQ-007 |
| AC-005 | Given two lanes and `convergence_mode=best_of_n`, when both lanes score below `pass_threshold`, then the decision is `failed` and `approved_lanes` is empty. | REQ-007 |
| AC-006 | Given two lanes and `convergence_mode=all_required`, when both score at or above `pass_threshold`, then the decision is `approved` and both lane IDs appear in `approved_lanes`. | REQ-008 |
| AC-007 | Given two lanes and `convergence_mode=all_required`, when one lane has a leakage flag, then the decision is `failed`. | REQ-008 |
| AC-008 | Given three lanes and `convergence_mode=first_to_pass`, when the second lane passes first (in supplied order), then the decision is `approved`, the second lane is approved, and the third is `skipped`. | REQ-009 |
| AC-009 | Given three lanes and `convergence_mode=first_to_pass`, when no lane passes, then the decision is `failed` and `approved_lanes` is empty. | REQ-009 |
| AC-010 | Given a completed `run`, when the ledger file is read, then a valid JSON object is present containing `run_id`, `approved_lanes`, `decision`, and one entry per lane in `lane_summaries`. | REQ-010 |
| AC-011 | Given a `FactorySpec` with a duplicate `lane_id`, when `FactoryRunner.run` is called, then it raises `FactoryError`. | REQ-011 |
| AC-012 | Given a `LaneResult` whose `lane_id` is absent from `spec.lanes`, when `FactoryRunner.run` is called, then it raises `FactoryError`. | REQ-011 |
| AC-013 | Given the same `FactorySpec` and the same ordered `LaneResult` list, when `run` is called twice, then both `FactoryDecision` objects are equal and both ledger entries are identical (modulo timestamp). | NFR-003 |
| AC-014 | Given `agents/quant_factory/`, when the `agent-catalog` gate runs, then it is recognised as a complete public agent. | REQ-012 |
| AC-015 | Given the three catalogs/cross-references named in REQ-014, when inspected, then each references spec `0061`. | REQ-014 |

## Data & Dependencies

- **Reads:** nothing — no file reads in `score_lane` or the convergence
  functions.
- **Writes:** `<spec.ledger_path>` (JSONL, append mode) — one entry per
  `run` call.
- **Imports from this repo:** `backtesting.py` metric names are referenced
  by convention (strings), not imported types — `quant_factory.py` depends
  on nothing inside `src/quantsmith/` to stay import-cycle-free.
- Standard library only; no new dependency.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A caller supplies `LaneResult` objects out of the declared order, causing `first_to_pass` to approve a slower lane. | Medium — non-deterministic winner selection. | `run` processes results in the order they are supplied; doc-string and `factory_run_card.md` state explicitly that the caller controls ordering and that `first_to_pass` is order-sensitive. |
| RISK-002 | Ledger write fails mid-run (disk full, permission error), leaving the decision unrecorded. | Medium — a run with no audit trail. | `FactoryRunner.run` completes the `FactoryDecision` first, then attempts the ledger write; on `OSError` it raises `FactoryError` with the full decision embedded in the message so nothing is silently lost. |
| RISK-003 | Gate thresholds are set leniently (e.g. `pass_threshold=0.0`), approving every lane regardless of quality. | High — "winner" has no genuine edge. | `ConvergenceGate` validates that `pass_threshold > 0.0` at construction time; gate param values are surfaced verbatim in the ledger entry so a reviewer can see what was required. |
| RISK-004 | The `score_lane` formula is treated as a final verdict rather than a first-pass filter. | Medium — promotes a lane that is good at the formula but poor in practice. | `score_lane` is documented as a triage heuristic; `agents/quant_factory/instructions.md` requires a human-readable lane summary and backtest tear-sheet before any lane is shipped. |

## Assumptions & Open Questions

- Assumption: Three convergence modes cover the main quant use cases —
  selecting a single best model, ensembling all validated candidates, and
  racing competing implementations. A fourth mode (e.g. `pareto_front`)
  can be added without breaking the existing three.
- Assumption: Equal weighting of Sharpe, drawdown, and return in
  `score_lane` is a reasonable default; a future spec can expose a
  `weight` vector on `ConvergenceGate` without changing the rest of the
  contract.
- Open question: should `FactoryRunner` expose a streaming callback so a
  caller can log lane completions in real time, or is the ledger-on-finish
  pattern sufficient? Deferred — the callback adds complexity and the
  ledger is already written before `run` returns.
- Open question: when `all_required` is used and one lane errors, should
  the remaining lanes still be scored (for diagnostic value) or stopped
  immediately? Current design: all supplied results are scored; the gate
  then fails. This keeps the ledger informative even on a failed run.

## Exceptions

None. This spec adds a new pipeline module and an agent contract to
already-established patterns; it introduces no deviation from
`instructions/engineering_principles.md`.
