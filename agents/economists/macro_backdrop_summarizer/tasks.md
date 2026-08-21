# Macro Backdrop Summarizer Tasks

## Write A Recurring Brief

Input: recent reads from the four upstream `economists/` agents (or
equivalent supplied information) and an as-of date.

Output: a populated `templates/docs/macro_backdrop_report.md` at brief
cadence.

## Refresh After A Material Change

Input: a prior brief plus what's changed (a new release, a regime shift,
a policy change).

Output: the updated brief with the change reflected and the as-of date
moved forward.

## Flag A Stale Pillar

Input: a brief cycle where one upstream pillar (e.g. policy) has no new
read.

Output: that section explicitly marked unchanged/unrefreshed since a
stated date, not silently carried over as if new.
