# Quant Factory Agent — Per-Run Task Checklist

This checklist covers one factory run from hypothesis to ship decision.
Copy it into your run notes and check off each item.

## Phase 1: Hypothesis → Spec

- [ ] Fill in `templates/prompts/factory_run_card.md` (one row per lane:
      `lane_id`, `hypothesis`, `feature_set`, `model_tag`,
      `backtest_config`, convergence mode, gate thresholds, `seed`).
- [ ] Confirm `pass_threshold > 0.0`.
- [ ] Confirm `convergence_mode` is one of `best_of_n`, `all_required`,
      `first_to_pass`; document the rationale.
- [ ] For `first_to_pass`: declare the priority ordering of lanes in the
      run card — this ordering is order-sensitive and must be reproducible.
- [ ] Construct `FactorySpec`; verify no duplicate `lane_id`.

## Phase 2: Lane Execution

- [ ] Launch all lanes (in parallel where possible); note start time.
- [ ] For each lane, record when it transitions to `running`.
- [ ] Collect `LaneResult` from each lane as it completes (or errors).
- [ ] Confirm no `LaneResult.lane_id` is missing from the spec.

## Phase 3: Convergence Gate

- [ ] Call `FactoryRunner.run(spec, lane_results)`.
- [ ] Read the returned `FactoryDecision`: `decision`, `approved_lanes`,
      per-lane `gate_score` and `status`.
- [ ] Confirm the ledger entry was appended at `spec.ledger_path`.
- [ ] Emit the human-readable summary (see `instructions.md`).

## Phase 4: Review

- [ ] For every approved lane:
  - [ ] Read the full backtest tear-sheet (not just the headline metrics).
  - [ ] Confirm `leakage_flags` is empty.
  - [ ] Run `hooks/stages/run-stage.sh leakage` on the lane's feature set.
  - [ ] Check that the lane's `backtest_config` matches what was declared
        in the run card (no silent config drift).
- [ ] Share the summary and ledger entry with the analyst; wait for
      explicit approval.

## Phase 5: Ship Decision

- [ ] Analyst approves in writing (PR comment, meeting note, or chat log).
- [ ] Tag the approved lane's model artefact (git tag, registry entry,
      or equivalent) as `approved-<run_id>`.
- [ ] Update the run card with `decision: approved`, the approved lane IDs,
      and the date.
- [ ] Do NOT mark any lane `shipped` until the analyst explicitly says so.
