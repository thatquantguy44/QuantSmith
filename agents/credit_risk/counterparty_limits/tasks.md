# Counterparty Limits Tasks

## Facility Measurement

Input: a facility's PD, LGD, EAD inputs (or drawn balance/limit/CCF), and an
optional risk weight.

Output: EAD, expected loss (or a named basis violation), and RWA if a risk
weight was supplied.

## Counterparty Aggregation

Input: a set of facility measurements.

Output: per-counterparty total EAD and expected loss, with basis-violated
facilities named separately.

## Limit Check

Input: aggregated counterparty exposure and a limit registry.

Output: breach status and exact breach amount per counterparty; a named
finding for any counterparty with exposure and no registered limit.

## Concentration Review

Input: aggregated counterparty exposures and a stated concentration
threshold.

Output: largest counterparty share, Herfindahl index, and threshold-breach
status.
