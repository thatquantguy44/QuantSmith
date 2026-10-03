# Dual-Use Indicator Tasks

## Review

Input: the data named in this agent's `README.md` Inputs section.

Output: the findings named in this agent's `README.md` Outputs section,
following `instructions.md`'s Output Contract.

## Boundary Check

Before returning a report, confirm it does none of the following: rule on export-control classification, licence requirement, end-use legality, or whether a transfer is permitted — those belong to counsel and the responsible compliance authority (decision-path class `sovereign_adjacent`, decision_support_only).
If the request asked for that, redirect to the accountable human named in
this agent's `README.md` and `instructions/venture_intelligence.md`.
