# Morning Brief Writer Tasks

## Write The Daily Views & Analysis

Input: `market_brief.top_headlines`'s output for today's watchlist, and
`market_brief.sentiment_rollup`'s output where available.

Output: grounded "Views & Analysis" markdown, every claim traced to a
supplied headline or the sentiment rollup.

## Frame Against The Macro Backdrop

Input: the above, plus the day's `templates/docs/macro_backdrop_report.md`
(from `macro_backdrop_summarizer`), when one exists for this cycle.

Output: the same grounded analysis, additionally noting where a headline
confirms, contradicts, or is silent on the current macro backdrop read —
never asserting a connection the headline text doesn't actually support.

## Flag A Silent Topic

Input: a watchlist topic/ticker present in the config but with an empty
headline list this run.

Output: that topic named explicitly as having no material coverage today,
not omitted from the section.
