# Meeting-to-Action Tasks

## Extract Decisions

Input: raw meeting notes or a transcript.

Output: a list of decisions made, with rationale where the notes gave one.

## Extract Open Items

Input: the same notes.

Output: a list of open items, each with an owner and date where specified,
"unclear" otherwise.

## Draft the Follow-Up

Input: the decisions and open items above, plus `role_context.yml` if
present.

Output: a draft follow-up message in the appropriate tone, clearly labeled as
a draft.
