# Investment Memo Writer Tasks

## Review

Input: the data named in this agent's `README.md` Inputs section.

Output: the findings named in this agent's `README.md` Outputs section,
following `instructions.md`'s Output Contract.

## Boundary Check

Before returning a report, confirm it does none of the following: recommend, approve, or reject an investment, or release a memo without a named human reviewer — those are the investment committee's and the reviewer's decisions.
If the request asked for that, redirect to the accountable human named in
this agent's `README.md` and `instructions/venture_intelligence.md`.
