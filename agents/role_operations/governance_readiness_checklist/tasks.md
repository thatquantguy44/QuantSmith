# Governance Readiness Checklist Tasks

## Run A Readiness Pass

Input: an artifact's current state and available evidence (model card,
backtest report, dataset card, monitoring plan, owner).

Output: a populated `templates/docs/production_readiness_checklist.md`,
every item marked evidenced (cited), a gap, or not applicable.

## Re-Check After A Change

Input: a prior readiness checklist plus what's changed (new evidence, a
new result, a new dependency).

Output: the updated checklist, with items re-marked as needed and the
Blocking Gaps summary refreshed.

## Summarize Blocking Gaps

Input: a populated readiness checklist.

Output: the "Blocking Gaps" summary — every item still marked as a gap,
ordered by what would realistically need to close first.
