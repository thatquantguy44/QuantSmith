# SFMeridian Orchestrator Agent

## Purpose

The SFMeridian Orchestrator is the single desk-question entrypoint. It
validates configuration and calls the shared governed-first `ask` runtime,
returning governed answers or clarifications without tail fall-through and
requiring run citations for every numeric result.

## Use When

- A desk user asks a securities-lending data question.
- A governed ambiguity must be returned for clarification.
- Reviewed-query tail execution or an unavailable-source escalation is needed.
- A publish/persist request must be refused in this phase.

## Inputs

- Question, ISO as-of, caller handle, and database profile.
- Optional exact tail parameters and PIT columns.

## Outputs

- Typed route and tier, answer or shadow result, citations, caveats, and trace.
- A clarification, abstention, or coded escalation when evidence is unavailable.
- `E_WRITEBACK_DISABLED` for every write intent.

## Runtime

Tested loop agent (`0116`): `sfmeridian.orchestrator.run_orchestrator`. Manifest:
`plugins/sfmeridian/src/sfmeridian/data/agents/sfmeridian_orchestrator.json`.
