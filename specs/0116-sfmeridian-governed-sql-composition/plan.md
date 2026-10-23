# Plan: SFMeridian — Governed SQL Composition, Verification & Execution

- **Spec:** 0116-sfmeridian-governed-sql-composition (`spec.md`)
- **Status:** Approved
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-10-23

> HOW. Implementation starts only after `spec.md` is approved. Every local
> requirement appears in the traceability matrix below.

## Approach

Build one safety chain around the existing shared registry:

```text
question
  -> ask.route (0080 first)
       -> governed: 0080 QueryPlan -> Reader -> compose reviewed metric source
                                   -> verify -> execute -> 0008 Facts -> answer
       -> clarification: return; no fall-through
       -> outside governed vocabulary: search -> compose reuse/adapt/generate
                                           -> verify -> execute -> shadow result
  -> provenance / 0070 envelope / optional bounded specialist handoff
```

The verifier and execution seam are ordinary deterministic tools, not agents.
`sql.execute` has no raw-SQL input: callers submit the opaque verification
token plus the exact parameters. The token is an HMAC over a canonical
verification record using host-injected key material and an injected clock.
The executor re-derives all context hashes and refuses any mismatch before it
touches the connection.

The governed bridge stays under `sfmeridian/governed/`, the only package
allowed to import `quantsmith`. The rest of the plugin remains standard
library only. Database connections, completion functions, token keys, clocks,
and optional cost explainers enter through `ToolContext.clients`; no runtime
secret or connection is loaded from configuration.

## Architecture & Components

```text
plugins/sfmeridian/
  fixtures/execution/
    fixture_db.py             # deterministic SQLite builder + expected results manifest
  src/sfmeridian/
    compose.py                # reuse/adapt/generate records; injected completer only
    verify.py                 # fail-closed structural/policy checks; HMAC token issuer
    execute.py                # token validation, query-only adapter, redaction, provenance
    sql_tools.py              # sql.compose/sql.verify/sql.execute/ask registry handlers
    composer_agent.py         # C-03 deterministic policy and verifiers
    orchestrator.py           # C-04 routing policy, report, verifiers, handoffs
    governed/
      reader.py               # QueryPlan -> available source -> verified Facts
      ask.py                  # 0080-first typed routing; write-back refusal
    data/agents/
      sql_composer.json
      sfmeridian_orchestrator.json
tests/
  test_sfmeridian_sql.py      # AC-001–AC-018
```

Changes to existing modules are bounded: configuration adds verifier token
TTL and validates dialect-specific safety fields; `ToolContext.clients`
receives typed injected adapters; `tools.default_registry()` registers four
handlers; `governance.CONTRACT_TOOLS` and the C-03/C-04 coverage rows become
built; the CLI may expose the same tools for offline acceptance tests. The
query index, catalog, mapping, access layer, harness, and receiving specialist
agents are consumed, not forked.

### Component responsibilities

| Component | Responsibility | Never |
| --- | --- | --- |
| `compose.py` | Retrieve eligible exemplars, bind parameters, adapt or call an injected completer, and emit a canonical composition record. | Execute, verify itself, promote, or accept an unavailable/drifted exemplar. |
| `verify.py` | Parse conservatively, resolve identifiers, validate joins/params/PIT/limit, normalize dialect policy, run optional normalized cost check, and issue the bound token. | Repair SQL, call a model, or connect directly. |
| `execute.py` | Validate token and context, call only query, enforce timeout/limit, redact rows, and construct provenance/replay material. | Accept raw SQL, expose transaction/write methods, or persist signing material. |
| `governed/reader.py` | Turn available metric-source queries into verified `Fact` rows for an exact `QueryPlan`. | Substitute an unavailable source or invent a dimension/filter. |
| `governed/ask.py` | Compile the layer, call `0080`, classify typed outcomes, and invoke the tail only for no-governed-match. | Fall through on governed ambiguity or pass a write-back request. |
| `composer_agent.py` | Exercise retrieval/composition/verification through the loop harness. | Execute or promote. |
| `orchestrator.py` | Exercise end-to-end routing, bounded repair, evidence reporting, and specialist handoff. | Answer from memory, publish, or perform specialist judgement. |

## Interfaces & Data Contracts

### Injected clients

`ToolContext.clients` uses named, host-supplied capabilities:

| Key | Contract |
| --- | --- |
| `connections[profile]` | Query-only object with `query(sql, params, *, timeout_s, row_limit)` or an adapter over `SQLDataSource.query`; optional `read_only` attestation must be true. |
| `completer` | Callable compatible with `agent.ModelPolicy`'s injected completion boundary; receives catalog/mapping/exemplar metadata, never credentials or result rows. |
| `verification_keys` | Keyring with active key ID and bytes; never serializable through tools. Tests inject an explicit synthetic key. |
| `clock` | Callable returning an integer UTC epoch; tests inject a fixed clock. |
| `explainers[profile]` | Optional read-only callable returning normalized numeric cost and safe notes, never a raw driver plan. Required when a profile sets `explain_cost_limit`. |

### Composition record

```json
{
  "sql": "SELECT ... WHERE business_date = :as_of LIMIT 1000",
  "params": {"as_of": "2026-10-22"},
  "path": "reuse",
  "profile": "fixture_db",
  "as_of": "2026-10-22",
  "source_exemplars": [{"id": "...", "repo": "fixture_queries", "ref": "..."}],
  "catalog_objects": ["main.sec_lending_book"],
  "limitations": []
}
```

The serialized record is canonical (sorted keys, stable numeric/text forms).
`reuse` must preserve the reviewed SQL structure and only bind declared
parameters. `adapt` may change projections, filters, grouping, and catalog-
observed joins but cites the base exemplars. `generate` is accepted only as a
candidate for verification and never enters the index.

### Verification record and token

The verifier produces a safe public record plus an opaque token:

```json
{
  "ok": true,
  "token": "v1.<key-id>.<payload>.<signature>",
  "sql_hash": "sha256:...",
  "params_hash": "sha256:...",
  "profile": "fixture_db",
  "dialect": "sqlite",
  "snapshot_id": "...",
  "config_hash": "...",
  "policy_version": "sql-verify/1",
  "clearance": "internal",
  "issued_at": 1792742400,
  "expires_at": 1792742700,
  "row_limit": 1000,
  "timeout_s": 30,
  "explain_cost": null,
  "checks": [{"id": "read_only", "ok": true}]
}
```

The signed payload contains the fields above and the canonical composition
path. It contains hashes rather than raw sensitive parameter values. The token
TTL defaults to five minutes and may only be tightened per call. Verification
uses constant-time signature comparison. Execution needs the in-memory
verified SQL record plus the token; the token is not a bearer encoding of raw
SQL. Replay always verifies again under the recorded policy and compares the
new context hashes.

Stable verifier/execution errors remain the parent contract's:
`E_VERIFY_NOT_READ_ONLY`, `E_VERIFY_MULTI_STATEMENT`,
`E_VERIFY_UNKNOWN_IDENTIFIER`, `E_VERIFY_JOIN_KEY`,
`E_VERIFY_UNBOUND_PARAM`, `E_VERIFY_MISSING_PIT`, `E_VERIFY_NO_LIMIT`,
`E_VERIFY_COST`, `E_VERIFY_TABLE_NOT_ALLOWED`, `E_EXEC_TOKEN`, and
`E_EXEC_TIMEOUT`. Unsupported/ambiguous syntax maps to the narrowest existing
verification code and includes a safe reason; adding a new stable code requires
amending `0113` first.

### Verification algorithm

1. Tokenize/extract with `sqlstructure`; reject parse errors, more than one
   statement, or a non-`SELECT` root before catalog access.
2. Reject write/transaction/control keywords in executable tokens, including
   writable CTEs and dialect-specific escapes. Comments and string contents
   never alter structural classification.
3. Resolve every base table and referenced column with the current
   `catalog.Resolver`; enforce profile schema/table allowlists.
4. Resolve every join edge against catalog primary keys or the reviewed
   `join_graph.json`; require exact left/right pairs, not merely the same
   tables.
5. Compare placeholders with supplied parameter names and dialect style;
   require variable predicates to use placeholders and reject extra/missing
   values. Sensitive values are retained only in run-scoped memory.
6. For an as-of composition, prove a bounded predicate on each time-bearing
   source's declared PIT column. A filter on a different date column does not
   satisfy the check.
7. Require a dialect-correct row limit at or below the configured maximum and
   bind the configured timeout.
8. If cost guarding is enabled, call the injected explainer with the same
   bound parameters and reject missing, failed, or over-limit normalized cost.
9. Canonicalize the record, sign it, and retain the verified SQL/parameters in
   run-scoped state until expiry.

### Execution result and provenance

```json
{
  "rows": [{"security_id": "SYN-001", "value": 125000.0}],
  "provenance": {
    "run_id": "...",
    "query_id": "sl.on_loan_value.by_counterparty.as_of",
    "sql_hash": "sha256:...",
    "path": "reuse",
    "source_exemplars": ["..."],
    "profile": "fixture_db",
    "dialect": "sqlite",
    "snapshot_id": "...",
    "config_hash": "...",
    "policy_version": "sql-verify/1",
    "as_of": "2026-10-22",
    "parameters": {"as_of": "2026-10-22", "counterparty": "<redacted>"},
    "row_count": 1,
    "truncated": false,
    "elapsed_ms": 0,
    "explain_cost": null,
    "clearance": "internal",
    "withheld_columns": []
  }
}
```

The deterministic `run_id` hashes the config, snapshot, normalized query,
parameter hashes, as-of, clearance, and policy version. Wall-clock elapsed time
is observable but excluded from identity and replay hashes. The `0070`
producer receives the public composition, verification checks, provenance,
and artifact hashes; it never receives credentials, signing material, raw
sensitive parameters, or unredacted withheld values.

### Governed Reader and typed routing

`Reader(QueryPlan) -> Sequence[Fact]` loads the already validated mapping
report for the plan metric. Only `metric_sources[].status == "available"` is
eligible. It converts the plan window, as-of, filters, and dimensions into the
source exemplar's declared parameters, then uses the same compose/verify/
execute chain. It maps the configured period/dimension/measure outputs exactly
to `Fact`; numeric conversion and missing output columns fail the source.
Execution provenance is stored in the run-scoped evidence registry keyed by
the facts' batch hash because `Fact` itself intentionally has no provenance
field.

The routing outcome is one of:

| Outcome | Action |
| --- | --- |
| `governed_answer` | Return `0080` response, tier `governed`; no composer call. |
| `governed_clarification` | Return clarification unchanged; no fall-through. |
| `no_governed_match` | Run tail composition; tier becomes `reuse`, `adapt`, or `generate`. |
| `governed_unavailable` | Return unavailable/escalation with `E_METRIC_SOURCE_UNAVAILABLE`; never answer from a tail query under a different definition. |
| `writeback_requested` | Return `E_WRITEBACK_DISABLED`. |

The adapter will not infer `no_governed_match` from arbitrary exception text.
It maps only typed `0080` plan/clarification outcomes and a deliberately narrow
unknown-metric/dimension result. All other failures remain governed failures.

### Tool schemas and effects

| Tool | Required inputs | Key outputs | Effect |
| --- | --- | --- | --- |
| `sql.compose` | question, as_of, profile, route outcome | composition record | `read` |
| `sql.verify` | composition record, caller | verification record + token or coded findings | `read` |
| `sql.execute` | token, exact params | redacted rows + provenance | `execute_read` |
| `ask` | question, as_of, caller, profile | typed outcome, tier, answer/result, citations, caveats, envelope | `execute_read` |

Schemas reject unknown keys and bound string/question sizes. `sql.execute`
does not accept SQL. `ask` accepts no write-back object. Registry error
handling uses `access.scrub_value` before any trace or response is recorded.

### Loop agents and verifiers

`sql_composer` receives a recorded `no_governed_match`. Its deterministic
policy calls `queries.search`, `queries.get`, `catalog.describe`,
`glossary.lookup`, `sql.compose`, and `sql.verify`. Verifiers require: the
route permits composition; all source citations were observed in the run;
the path is consistent with retrieved eligibility; and a valid token exists.
Its manifest grants neither `sql.execute` nor `ask`.

`sfmeridian_orchestrator` calls `config.validate`, `ask`, and, when an output
requests specialist work, the handoff builder exposed inside the orchestrator
(not a receiver invocation). Verifiers require: terminal routing is typed;
no governed answer/clarification called composition; every returned number has
an execution or governed run citation; write-back is refused; handoffs match
the catalog and clearance. Tail repair is bounded by `max_repairs`; verifier
failure feeds back through the existing harness.

### Specialist handoff

Handoffs are data, not direct cross-agent calls. The payload validates the
receiver against `data/handoffs.json` and includes workflow, request, run IDs,
as-of/PIT attestation, profile/snapshot, citations, clearance/redaction, desired
output, and never-boundary. The first implementation covers evidence payloads
for W7–W12; `0119` wires the downstream workflows. Existing receiver files may
gain only a `Related` pointer if repository convention requires it; their
instructions and runtime behavior do not change.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Execute has no raw-SQL interface; exact-context tokens, PIT proof, identifier resolution, and typed routing make the safety order structural. |
| P5 Reversibility | yes | Additive modules, manifests, tools, fixtures, and docs; write-back absent; removing the plugin leaves SDK and receiver behavior unchanged. |
| P6 Observability | yes | Composition, checks, rejection codes, cost, tier, provenance, envelopes, replay mismatches, and handoffs are explicit and scrubbed. |
| P9 Security & data | yes | Query-only injection, allowlists, clearance redaction, HMAC key isolation, sensitive parameter hashing, synthetic fixtures, and no stored credentials. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | Synthetic execution fixture and manifest | T-001 |
| REQ-002 | `compose.py`, composition record, injected completer | T-005 |
| REQ-003 | `verify.py` structural/catalog/join/param/PIT/limit checks | T-002 |
| REQ-004 | Dialect policies, timeout and explainer seam | T-003 |
| REQ-005 | Canonical verification record and HMAC token | T-002, T-003 |
| REQ-006 | `execute.py` query-only seam and redaction | T-004 |
| REQ-007 | Provenance, deterministic run identity, `0070` envelope, replay | T-004, T-010 |
| REQ-008 | `governed/reader.py` and fact-batch evidence registry | T-006 |
| REQ-009 | `governed/ask.py` typed governed-first routing | T-007 |
| REQ-010 | Tail orchestration and bounded repair | T-007, T-009 |
| REQ-011 | Runtime write-back refusal | T-008 |
| REQ-012 | Four shared registry tools and schemas | T-008 |
| REQ-013 | C-03 manifest, policy, verifiers, agent contract | T-009 |
| REQ-014 | C-04 manifest, policy, verifiers, agent contract | T-009 |
| REQ-015 | Validated evidence handoff payloads | T-010 |
| NFR-001 | Canonical inputs, injected clock/key, replay tests | T-001, T-011 |
| NFR-002 | Verify-token boundary and adversarial suite | T-002, T-004, T-011 |
| NFR-003 | Import boundary and injected adapters | T-004, T-006, T-011 |
| NFR-004 | Recorded limits, timeout, cost, overhead benchmark | T-003, T-011 |
| NFR-005 | Synthetic disclosure, scrubbing, redaction scans | T-001, T-004, T-010, T-011 |
| NFR-006 | Targeted and full gates, registries and docs | T-012 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Execution authorization | Short-lived HMAC token plus run-scoped verified record | Boolean `verified=true` or execute-with-guard flag | A caller cannot forge or transplant verification; raw SQL never enters execute. |
| Token contents | Context hashes and policy metadata; SQL/parameters retained only in run memory | Put raw SQL and params in a signed self-contained token | Prevents bearer tokens and traces from carrying sensitive values. |
| Routing | Typed `0080`-first outcome | Search exemplars in parallel and pick the most confident | Parallel paths can disagree and silently bypass governed ambiguity. |
| Tail order | Reuse, then adapt, then constrained generation | Generate first and retrieve as context | Maximizes human-reviewed structure and makes reuse measurable. |
| Verification parser | Extend the existing conservative tokenizer and fail closed | Ship a parser dependency now | Preserves stdlib portability; any optional parser needs admission review and cannot loosen decisions. |
| Identifier/join authority | Current catalog plus reviewed join graph | Model judgement or historical SQL alone | Catalog prevents fabrication; reviewed observations permit legitimate non-PK joins without trusting drafts. |
| Execution dependency | Inject query-only adapter; optional wrapper over `0023` | Import and expose the full `SQLDataSource` object | The parent class includes write and transaction methods; narrowing prevents accidental access. |
| `Fact` provenance | Run-scoped batch registry keyed by fact hash | Add fields to `0008.Fact` | Avoids changing the governed SDK contract while keeping provenance resolvable. |
| Write-back | Runtime refusal in every configuration | Honor explicit enablement before pack review | Parent safety conditions are not yet satisfied; refusal is the only valid Phase 3 behavior. |
| Tail output | Shadow-mode cited result | Release-quality natural-language answer | Claim-level grounding and evaluation belong to `0117`. |

## Validation Strategy

One module, `tests/test_sfmeridian_sql.py`, names all ACs. It copies fixtures
to `tmp_path`, builds a fresh SQLite database, injects a fixed clock and
synthetic signing key, and uses spies/fakes for query sources, explainers, and
completers. No test needs network access or a real credential.

- Fixture/catalog/exemplar consistency and known-result tests prove AC-001.
- Scripted retrieval/completer tests cover all composition tiers (AC-002).
- A table-driven adversarial corpus asserts exact error codes, no token, and
  zero connection calls (AC-003); mutation tests alter every token binding
  (AC-005).
- Dialect fixtures assert identifier quoting, parameter style, PIT and limit
  forms; cost fakes cover missing/over-limit plans (AC-004).
- Query-only spies, access classes, credential-bearing exceptions, provenance,
  envelope validation, and replay cover AC-006/AC-007.
- `0080` `QueryPlan` fixtures and the real `0115` mapping exercise the Reader,
  v2 drift, governed answer, no-match, and clarification paths (AC-008/AC-009).
- Scripted harness runs cover tail repair and both loop agents (AC-010,
  AC-013, AC-014); registry and write-back tables cover AC-011/AC-012.
- Every W7–W12 handoff is schema-validated and scanned after clearance
  redaction (AC-015).
- Repeatability, rejection/fabrication counters, overhead timing with database
  time excluded, import scan, secret scan, and gates cover AC-016–AC-018.

PostgreSQL execution is an optional CI integration when its injected service
exists. Oracle and Databricks remain static verification plus adopter-side
smoke tests; a missing environment is reported skipped, never passed.

## Rollout, Observability & Rollback

- **Rollout:** offline synthetic SQLite only, then CI PostgreSQL if available,
  then adopter nonproduction in shadow mode. No user-facing release occurs
  until `0117` passes its grounding and golden-question gate.
- **Metrics:** route count by tier; verifier rejection count by code;
  verification/token-expiry latency; compose path and exemplar-reuse rate;
  execution row count, truncation, timeout, and normalized cost; unavailable
  metric sources; repair and escalation counts; replay mismatches.
- **Kill switches:** `enabled: false` disables `ask`; retrieval-only mode
  disables `generate`; removing injected connections prevents execution;
  rotating/removing the active verification key invalidates outstanding
  tokens. Write-back has no enable path in this phase.
- **Rollback:** revert the additive modules/manifests and pin the prior plugin
  version; fixture and run artifacts are disposable/versioned; no source
  system state requires reversal.

## Open Questions

- Owner approval of this spec is required before any implementation task.
- The pack and amendment review is non-blocking for shadow-mode governed
  answers but retains the unreviewed-pack caveat.
- Optional database-driver extras remain blocked on admission review; injected
  host drivers are the default.
