# Credit Document Analyst Tasks

## Cited Extraction

Input: one or more documents citing a registered, disclosed source.

Output: a `0071` bundle (corpus, transforms, task results, audit ledger) and
a `0070` run envelope, with every claim resolving to a real citation span.

## Admission Bridge

Input: a real emitted task result.

Output: a `0072` admission result — `derived_evidence` or, with a named
review, `decision_input` — via `admission_input_from_bundle` and
`review_from_task_result`.

## Review Promotion Review

Input: a value proposed for promotion to `decision_input`.

Output: confirmation that reviewer, review date, and review scope are all
recorded, or a named reason promotion is refused.

## Replay Verification

Input: a previously emitted bundle.

Output: a replay report confirming identical reproduction, or a named
non-reproducible dependency if one exists.
