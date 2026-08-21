# Build Handoff Writer Tasks

## Draft A Handoff Memo

Input: a project's goal, current state, decisions, validation status,
risks, and open questions.

Output: a populated `templates/docs/handoff_memo.md` draft, with every
unresolved item and risk stated explicitly.

## Refresh An Existing Memo

Input: an existing handoff memo plus what's changed since.

Output: the updated memo, with resolved items marked resolved and new
risks/open questions added — nothing quietly dropped.

## Pull Decisions From The Audit Trail

Input: `audit_trail_keeper`'s decision log for this project.

Output: the memo's Key Decisions table, populated from the log rather than
re-derived independently.
