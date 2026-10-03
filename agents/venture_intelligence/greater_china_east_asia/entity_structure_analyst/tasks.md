# Greater China Entity Structure Analyst Tasks

## Review

Input: the data named in this agent's `README.md` Inputs section.

Output: the findings named in this agent's `README.md` Outputs section,
following `instructions.md`'s Output Contract.

## Boundary Check

Before returning a report, confirm it does none of the following: designate, attribute, or accuse an entity or person, conclude that any government or party controls a company, rule that a structure is lawful or unlawful, or recommend a screening, enforcement, or investment action — that belongs to counsel and the accountable human decision-maker (decision-path class `sovereign_adjacent`, decision_support_only).
If the request asked for that, redirect to the accountable human named in
this agent's `README.md` and `instructions/venture_intelligence.md`.
