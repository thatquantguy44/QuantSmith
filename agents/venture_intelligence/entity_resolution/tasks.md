# Entity Resolution Tasks

## Review

Input: the data named in this agent's `README.md` Inputs section.

Output: the findings named in this agent's `README.md` Outputs section,
following `instructions.md`'s Output Contract.

## Boundary Check

Before returning a report, confirm it does none of the following: merge records on a name alone, collapse a parent and subsidiary, or decide that two entities are the same without the evidence the rules require — a merge is the data owner's decision.
If the request asked for that, redirect to the accountable human named in
this agent's `README.md` and `instructions/venture_intelligence.md`.
