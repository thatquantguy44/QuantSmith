# NL Analytics Agent

## Purpose

The NL Analytics Agent turns a user's natural-language data question into a governed
answer: a validated `QueryPlan` (never free-form SQL), a chart, and grounded
insights, delivered as a chat response and/or an approved, reversible database
write-back. It owns the orchestration — interpret, validate, authorize, execute,
choose a chart, compute insights, narrate, gate, and (optionally) write back and emit
an audit envelope — and hands each step's real work to the agent that already owns
it, rather than duplicating it.

Runtime: `src/quantsmith/nl_analytics/` (`plan.py`, `interpret.py`, `authorize.py`,
`execute.py`, `chart.py`, `insights.py`, `narrate.py`, `respond.py`, `writeback.py`,
`writeback_sqlite.py`, `envelope.py`), spec `specs/0080-nl-analytics-insights/`
(Draft, ranked #1 priority by the owner 2026-09-24).

## Use When

- A user asks a data question in plain language ("what was our funding cost last
  week", "which desk's P&L changed the most since yesterday") and needs an answer
  grounded in governed metrics, not a hand-written query or number.
- An answer needs to be published back to a database as a reversible, approved
  insight record, not just returned in chat.
- A question is ambiguous or references an unknown/restricted metric or dimension
  and needs a clarification rather than a wrong or leaked answer.

## Inputs

- A natural-language question, plus enough context to interpret it: the semantic
  layer (`0008`), the viewer's access clearance (`0058`), an as-of period, and
  (optionally) a prior interpretation or persisted insight to compare against.
- For write-back: a filled-in `writeback_contract.md` (target, deny-list, approval
  mode) and an approval decision when the contract requires one.

## Outputs

- A typed chat response: an answer (chart, insights, narrative, citations), a
  clarification request, a masked/empty/stale result, or a write-rejected status —
  never a silent wrong answer.
- Optionally, an append-only, idempotent, reversible write-back record.
- Optionally, a `0070` audit envelope (prompt/context manifests, assumption ledger,
  audit events, replay-checkable hashes) for the run.

## Example Requests

- "What was total financing cost by desk last week?"
- "Has funding cost changed since yesterday?"
- "Publish this answer's insight to the daily desk-cost table."

## Required Review Themes

- Every plan is validated against the governed semantic layer (`0008`); no SQL or
  code field ever reaches a plan.
- Restricted metrics/dimensions are masked, not merely denied — existence is never
  revealed to an unauthorized viewer.
- Every number in the narrative traces to the computed result; no unbacked number,
  no unearned causal claim.
- Write-back is dry-run by default, approved explicitly, idempotent, and reversible
  by run id.
- Chart choice is handed to `data_visualization`; metric definitions are handed to
  `metrics_semantic_layer`; raw data access is handed to `sql-integration-agent` —
  this agent orchestrates, it does not reimplement any of the three.
