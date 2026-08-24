# Morning Brief Writer Agent

## Purpose

The Morning Brief Writer Agent turns the day's pulled market commentary —
real headlines and, where available, a sentiment rollup, computed by
`src/quantsmith/pipelines/market_brief.py` from NewsAPI, Alpha Vantage
`NEWS_SENTIMENT`, and Finnhub — into the "Views & Analysis" section of
`templates/docs/morning_market_brief.md` (spec `0059`). It writes the one
part of that report `market_brief.py` deliberately does not: grounded
prose interpreting what the day's headlines and sentiment actually say,
never fabricated market color.

## Use When

- The scheduled morning-brief job (spec `0055`) has already pulled and
  computed the day's headlines/sentiment rollup and needs the analysis
  section written before the report is rendered, delivered, and staged
  for review.
- A one-off ad hoc request for "what does today's watchlist news actually
  mean" over an already-pulled headline set.

## Inputs

- `market_brief.top_headlines`'s output: headlines grouped by watchlist
  topic/ticker, each with its provider, publish time, and URL.
- `market_brief.sentiment_rollup`'s output, where Alpha Vantage covered a
  topic (absent for topics it didn't — never treat that absence as
  neutral sentiment).
- Optionally, the day's `templates/docs/macro_backdrop_report.md` (from
  `macro_backdrop_summarizer`) for broader macro context to frame the
  headlines against.

## Outputs

- Markdown for the "Views & Analysis" section only — not the full report.
  `market_brief.render_morning_brief` composes this with the computed
  Headlines/Sentiment Rollup sections; this agent does not call it.
- Every claim traces to a specific supplied headline or the sentiment
  rollup, or is stated as a gap — never an unsupported assertion about
  the market.
- A watchlist topic/ticker with no material coverage today is named as
  such, not silently dropped.

## Example Requests

- "Write today's Views & Analysis from the pulled headlines and sentiment
  rollup."
- "AAPL had three headlines and mixed sentiment today — what's the read?"

## Required Review Themes

- Every claim traces to a supplied headline (by URL) or the sentiment
  rollup — nothing here should be checkable only against the model's own
  general knowledge.
- Sentiment is presented as a signal from one provider's model, never as
  a verified fact about market belief.
- This text is staged with `review_status: pending_review`
  (`market_brief.candidates_from_brief`) — it is a draft read for a human
  to review, not a promoted call. The agent's output should read that way:
  hedged where the data is thin, specific where it isn't.
- A topic with no coverage is named as a gap, not silently omitted.
