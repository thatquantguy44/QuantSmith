# Intelligence Brief Writer Tasks

## Review

Input: the data named in this agent's `README.md` Inputs section.

Output: the findings named in this agent's `README.md` Outputs section,
following `instructions.md`'s Output Contract.

## Boundary Check

Before returning a report, confirm it does none of the following: release or publish a brief without a named human reviewer, state a claim it cannot cite, or cite above the brief's classification — release belongs to the accountable human reviewer.
If the request asked for that, redirect to the accountable human named in
this agent's `README.md` and `instructions/venture_intelligence.md`.
