# Repo-local agents

Narrow, inspectable roles specific to THIS repository. Anything reusable across
repositories belongs upstream in the SDK's `agents/` catalog instead.

Each agent is a directory with the four-file contract, enforced by the
`agent-catalog` gate:

```
.agents/<name>/
  README.md        purpose, when to use, inputs, outputs, review themes
  prompt.md        the role instruction
  instructions.md  operating rules + a "Spec-Driven Role" section
  tasks.md         the standard jobs this agent handles
```

Keep responsibilities narrow. An agent that "helps with data" is not
inspectable; one that "validates a pulled row set against a declared contract"
is.
