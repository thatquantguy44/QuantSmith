# Alert Triage Tasks

## Triage A Batch

Input: a batch of already-routed alerts from `alert_router`, plus optional
personal context (what's already being worked, known issues).

Output: a priority-ordered annotation with a stated reason per alert; no
change to any alert's lifecycle state.

## Flag A Suspected Duplicate

Input: two or more alerts that look related.

Output: a flagged note for human confirmation — never an automatic
merge, dedupe, or suppression.

## Re-Triage Mid-Incident

Input: a new alert arriving while another is already being actively
worked.

Output: a priority call on where the new alert fits relative to current
work, with reasoning — still no suppression, escalation, or resolution
performed.
