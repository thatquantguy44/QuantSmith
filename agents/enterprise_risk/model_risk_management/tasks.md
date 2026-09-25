# Model Risk Management Tasks

## Review

Input: the data named in this agent's `README.md` Inputs section.

Output: the findings named in this agent's `README.md` Outputs section,
following `instructions.md`'s Output Contract.

## Boundary Check

Before returning a report, confirm it does none of the following: approve, reject, or validate a model itself — that is a named validator's or committee's decision.
If the request asked for that, redirect to the accountable owner named in
this agent's `README.md` and `instructions/enterprise_risk.md`.
