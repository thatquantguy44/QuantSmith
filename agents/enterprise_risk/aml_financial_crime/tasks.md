# AML & Financial Crime Tasks

## Review

Input: the data named in this agent's `README.md` Inputs section.

Output: the findings named in this agent's `README.md` Outputs section,
following `instructions.md`'s Output Contract.

## Boundary Check

Before returning a report, confirm it does none of the following: determine that an alert is suspicious, file a SAR, or surface any individual-level alert, case, customer, or SAR content — determinations and filings are a named compliance officer's regulated decision, and confidentiality here is absolute.
If the request asked for that, redirect to the accountable owner named in
this agent's `README.md` and `instructions/enterprise_risk.md`.
