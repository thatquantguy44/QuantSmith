# Source Reliability Grader Tasks

## Review

Input: the data named in this agent's `README.md` Inputs section.

Output: the findings named in this agent's `README.md` Outputs section,
following `instructions.md`'s Output Contract.

## Boundary Check

Before returning a report, confirm it does none of the following: override or replace a human analyst's grade, or grade on reputation or familiarity alone — a proposed grade is advice and the analyst decides.
If the request asked for that, redirect to the accountable human named in
this agent's `README.md` and `instructions/venture_intelligence.md`.
