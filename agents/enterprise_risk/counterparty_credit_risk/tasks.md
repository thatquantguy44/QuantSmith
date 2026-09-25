# Counterparty Credit Risk Tasks

## Review

Input: the data named in this agent's `README.md` Inputs section.

Output: the findings named in this agent's `README.md` Outputs section,
following `instructions.md`'s Output Contract.

## Boundary Check

Before returning a report, confirm it does none of the following: price a derivative, set a CSA term, or compute a PFE model from scratch — pricing and legal terms are trading and legal decisions, and a supplied exposure profile is consumed, not derived, here.
If the request asked for that, redirect to the accountable owner named in
this agent's `README.md` and `instructions/enterprise_risk.md`.
