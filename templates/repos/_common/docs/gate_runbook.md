# Gate runbook

What to do when a gate fails. Ordered by how often it actually happens.

Every gate is advisory unless listed in `QF_GATES_BLOCKING` in
`quantsmith.conf`. Run one on its own to see detail:

```sh
sh hooks/stages/<name>-check.sh
```

---

## `secret-scan` — "possible secret detected"

**Checks:** changed files for credential-shaped strings.

**Usual cause:** a real key, or a test fixture that looks like one.

**Do:** if it is real — **do not just delete the line and commit**. It is in
your local history already. Rotate the credential first, then remove it. If it
is a fixture, make it obviously fake (`sk-EXAMPLE-not-a-real-key`).

---

## `spec` — "task cites no requirement" / "AC has no test"

**Checks:** the traceability chain across `spec.md` → `plan.md` → `tasks.md`.

**Usual cause:** a `T-*` added without a `Covers` entry, or an `AC-*` with no
named test.

**Do:** add the missing link. If the task genuinely serves no requirement, that
is worth noticing — it may be work nobody asked for.

---

## `handoff-sync` — "spec not referenced in the roadmap"

**Checks:** every spec directory appears in the roadmap; a new spec arrives
with its entry.

**Usual cause:** you created `specs/NNNN-slug/` and have not written the
roadmap entry yet.

**Do:** add a line to the roadmap. It is two sentences, and it is the only
thing stopping the spec from being invisible to the next person.

---

## `leakage` — "negative shift" / "bfill" / "no shuffle=False"

**Checks:** heuristic look-ahead smells in changed Python.

**Usual cause:** genuine leakage, or a false positive on legitimate code.

**Do:** confirm the time direction by hand. This gate is deliberately
heuristic — it will false-positive, and it is still worth reading every time,
because the failure it catches is silent and expensive.

---

## `backtest` — "no backtest report" / "report missing a section"

**Checks:** a backtest artifact exists and states costs, period, and
look-ahead handling.

**Usual cause:** a run whose report was never rendered.

**Do:** render the report. A backtest with no artifact is not reviewable.

---

## `repro` — "no run manifest" / "no lockfile"

**Checks:** a pinned environment and a recorded run.

**Usual cause:** a fresh repo (expected — this is why the shapes ship it
advisory), or dependencies that drifted off their pins.

**Do:** `pip freeze > requirements.txt`, and record the run in a run card.
Promote this gate to blocking once the repo has its first real run.

---

## `upstream-drift` — "differs from upstream <ref>"

**Checks:** copied surfaces against the pinned upstream ref.

**Usual cause:** someone tuned a gate locally — which is allowed.

**Do:** if deliberate, record it in `docs/ownership.md` so the report stays
readable. If it was accidental, `./scripts/sync-upstream.sh --apply`.

---

## `agent-attribution` — "author is an AI agent"

**Checks:** commit author, committer, and co-author trailers.

**Usual cause:** an agent session committed under its own identity.

**Do:** set a human identity and amend. AI-assisted work is fine; AI-attributed
work is not — someone has to answer for the commit.

---

## `doc-counts` — "says N, actual is M"

**Checks:** stated counts in the narrative docs against the filesystem.

**Usual cause:** you added a gate/spec/agent and a badge still says the old
number.

**Do:** update the number. If the gate reports "no count claims matched", the
patterns have gone stale relative to your prose — fix the pattern, not the doc.

---

## When the runbook does not cover it

The gate's own header comment says what it checks and why, and is usually more
specific than this file. Then `docs/ownership.md`.
