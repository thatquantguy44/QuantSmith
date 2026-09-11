# Counterparty Limits Agent

## Purpose

The Counterparty Limits Agent aggregates credit exposure by counterparty
across facilities, checks it against a registered limit, and flags
concentration — the exposure-management half of wholesale credit review that
needs no institution-specific rating or PD model to do correctly.

## Use When

- Facility-level exposures need rolling up to a counterparty (or group) view.
- A counterparty's aggregated exposure needs checking against its approved
  limit, with breach and utilization reported explicitly.
- A portfolio's concentration — the largest single counterparty's share, or
  its overall Herfindahl index — needs measuring against a stated threshold.
- A facility's expected loss could not be computed (a PD/LGD basis mismatch)
  and that gap needs surfacing at the counterparty level, not hiding inside
  an aggregate total.

## Inputs

- Facility-level measurements: EAD, expected loss (or a named basis
  violation), counterparty ID.
- A limit registry: one limit per counterparty with exposure. An
  unregistered counterparty with exposure is a defect to report, not a case
  to skip.
- A concentration threshold — always supplied by the caller; this agent
  never assumes one.

## Outputs

- Per-counterparty aggregated exposure and expected loss, with any
  basis-violated facility named separately.
- A limit-check result per counterparty: `within_limit` or `breached`, with
  the exact breach amount.
- A concentration report: largest counterparty share, Herfindahl index, and
  whether the supplied threshold is breached.

## Example Requests

- "Aggregate this quarter's facility measurements by counterparty and flag
  any limit breaches."
- "What's this portfolio's concentration, and does it breach our 40% single-
  counterparty threshold?"
- "Which counterparties have exposure with no facility-level expected loss
  computed, and why?"

## Required Review Themes

- No counterparty with exposure is left unchecked against a limit — an
  unregistered limit is a defect, not an implicit pass.
- A missing expected-loss figure (basis violation) is named at the
  counterparty level, never silently treated as zero.
- The concentration threshold is stated explicitly in every report; this
  agent never infers or defaults one.
- Rating and PD/LGD estimation are out of scope — this agent consumes those
  values, it does not produce them.

## Runtime

A tested, runnable pipeline exists (spec
`0073-wholesale-credit-measurement`):
`src/quantsmith/pipelines/wholesale_credit_measurement.py` —
`measure_facility` (EL/EAD/RWA given supplied PD/LGD/risk-weight),
`aggregate_counterparty_exposure`, `check_counterparty_limits`,
`compute_concentration`, and `run_counterparty_limit_review` composing all
four. Every arithmetic primitive is imported from `0072`'s
`credit_risk_knowledge.py`, not reimplemented.

**What this agent does not do:** assign a rating or estimate a PD or LGD.
`workflow.wholesale_obligor_review`'s rating/PD step remains an adopter's own
model registered through `0026` — this agent and its runtime only consume
that model's output, never produce it.
