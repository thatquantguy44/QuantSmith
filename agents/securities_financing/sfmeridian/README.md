# SFMeridian Agents

SFMeridian is the securities finance intelligence plugin (specs `0113`–`0120`):
grounded answers to securities-lending questions from an adopter's own
databases, learned from a configurable repository of reviewed SQL queries.
The runtime lives in `plugins/sfmeridian/` (package `sfmeridian`).

Every agent in this group is a **loop agent**, not only a contract: a
manifest (`plugins/sfmeridian/src/sfmeridian/data/agents/<name>.json`) grants
it a least-privilege set of tools from the shared tool registry, and the
loop harness (`sfmeridian.agent`) runs it under step and tool-call budgets,
with deterministic verifiers that must pass before a run is `completed` and
explicit human checkpoints where it escalates instead of deciding. Apps and
agents call the same tools.

| Agent | Coverage row | Status | Spec |
| --- | --- | --- | --- |
| `query_librarian/` | C-01 | built (loop agent) | `0114` |
| `semantic_mapping_steward` | C-02 | planned | `0115` |
| `sql_composer` | C-03 | planned | `0116` |
| `sfmeridian_orchestrator` | C-04 | planned | `0116` |
| `answer_grounding_reviewer` | C-05 | planned | `0117` |
| `lending_revenue_analyst` | C-08 | planned (first `0119` agent) | `0119` |
| `utilization_specials_analyst` | C-06 | planned | `0119` |
| `recall_buyin_risk_analyst` | C-07 | planned | `0119` |
| `lending_reporting_check` | C-09 | planned | `0120` |

The full roster, each planned agent's loop (tools, verifiers, human
checkpoints, stop condition), and the 34 existing agents SFMeridian hands work
to are machine-readable in `plugins/sfmeridian/src/sfmeridian/data/coverage.json`
and `handoffs.json`, validated by `python -m sfmeridian governance validate`.
