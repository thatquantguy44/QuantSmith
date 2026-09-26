# Plan: Enterprise Risk Agents

- **Spec:** 0082-enterprise-risk-agents (`spec.md`)
- **Status:** Approved
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-09-25

> HOW. This plan requires an approved `spec.md`. Every requirement in the spec
> appears in the traceability matrix below.

## Approach

Follow the shape `0022` (asset-class mechanics) and `0033` (economists) already
established for a contract-only agent expansion: one category folder, one
shared instructions standard, four files per agent, a catalog row per agent,
no runtime. The one addition beyond that precedent is a shared "never" table
in the standard — because unlike asset-class mechanics or macro commentary,
several of these six disciplines sit directly next to a regulated human
decision (model approval, SAR filing, CSA terms), and the boundary needs to
be stated once, centrally, rather than reinvented per agent.

Content for each agent was derived directly from checking what its
discipline actually requires (Basel event types for operational risk,
netting-before-comparison for counterparty XVA, PCAF-style attribution for
climate) against what `agents/risk`'s own README already covers — the gap
is the agent's charter.

## Architecture & Components

```
instructions/enterprise_risk.md          (shared standard: rule + never-table)
        │
agents/enterprise_risk/
  ├── README.md                          (group: why it exists, catalog, boundary)
  ├── operational_risk/           (README, instructions, tasks, prompt)
  ├── model_risk_management/      (README, instructions, tasks, prompt)
  ├── counterparty_credit_risk/   (README, instructions, tasks, prompt)
  ├── aml_financial_crime/        (README, instructions, tasks, prompt)
  ├── liquidity_treasury_risk/    (README, instructions, tasks, prompt)
  └── climate_esg_risk/           (README, instructions, tasks, prompt)
        │
agents/README.md                         (+ Enterprise Risk Agents section)
        │
knowledge/analytics_packs/*.json         (7 packs: reviewer_agents re-pointed,
                                           builds_on gains instructions/enterprise_risk.md)
        │
knowledge/analytics_packs/README.md      (catalog table regenerated)
```

No code module. The four agent files per agent were generated from one
Python script (kept in the session's scratch area, not committed — the
committed files are the source of truth from here, edited directly like any
other agent contract) so all six share identical section structure and the
group's boundary language is applied consistently rather than retyped six
times with drift.

## Interfaces & Data Contracts

No typed interfaces — this is a documentation/agent-contract change. The one
structural contract that matters: every `0081` pack's `reviewer_agents` entry
must resolve to a real `agents/<path>/prompt.md` (enforced by
`analytics_packs.validate_pack`'s existing REQ-006 check, unchanged by this
spec — it simply now finds these six new paths).

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | The shared "never" table is enforceable structurally today only through `analytics_packs`' agent-existence check and human review; a future runtime would need its own guardrail, noted as an open question, not silently deferred. |
| P5 Reversibility | yes | Adding agents and re-pointing `reviewer_agents` is a pure addition/pointer change; reverting is deleting the six directories and the standard, and pointing the seven packs back. |
| P6 Observability | n/a | No runtime, no metric to monitor yet. |
| P9 Security & data | yes | No data or credentials; `aml_financial_crime`'s confidentiality boundary is stated as an instruction, since no data flows through this contract-only agent yet. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | Six agent directories, four files each | T-001 |
| REQ-002 | `instructions/enterprise_risk.md` | T-002 |
| REQ-003 | Each agent's README "Runtime" section states what it never does | T-001 |
| REQ-004 | Seven `0081` pack JSON files: `reviewer_agents` updated | T-003 |
| REQ-005 | `agents/README.md` Enterprise Risk Agents section | T-004 |
| REQ-006 | No edits outside the seven named packs and `agents/risk/` untouched | T-003 (verified, not edited) |
| NFR-001 | `agent-catalog-check.sh` run and passing | T-005 |
| NFR-002 | `analytics_packs.validate_catalog` run and passing | T-005 |
| NFR-003 | Each agent's own "never" statement plus the shared table | T-001, T-002 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Scope | Six agents for the six confirmed-mismatched disciplines | One `enterprise_risk` agent covering all six | Would recreate the exact `agents/risk` overload problem this spec fixes, one level down. |
| Market risk | Excluded — `agents/risk` already fits | A seventh `market_risk` agent | Duplicate charter; `agents/risk`'s own README already matches VaR/sensitivity/stress review closely. |
| Runtime | None (contract-only) | Build a runtime now | No caller-supplied data model exists yet for any of the six; `0022`/`0033` show contract-first is the right sequencing, and a runtime can follow once real usage defines the inputs. |
| Knowledge pack | None — `instructions/enterprise_risk.md` only | A `knowledge/enterprise_risk/` pack like `0072`/`0063` | No coverage-gap register or golden-case apparatus is justified yet for a contract-only group; revisit if a runtime is built. |
| Re-pointing scope | Only the 7 packs where `agents/risk` was a clear mismatch | Re-point all 27 packs using `agents/risk` | The other 20 use it correctly, as a secondary investment/portfolio-risk reviewer for a business-line pack — not this spec's problem to fix. |

## Validation Strategy

- `hooks/stages/agent-catalog-check.sh` (AC-001, AC-007) — structural,
  every-agent-has-four-files check, already exists, not modified.
- `PYTHONPATH=src python3 -m quantsmith.pipelines.analytics_packs` and
  `pytest tests/test_analytics_packs.py` (AC-004, AC-008) — the existing
  `0081` validator and test suite, re-run to prove the re-pointing resolves
  cleanly.
- Manual diff review for AC-006: `git diff` scoped to
  `knowledge/analytics_packs/*.json` shows exactly the seven named files
  changed, nothing else in that directory.
- Reading each new `README.md` for AC-002/AC-003 (a "never" statement present
  and matching the shared standard's table) — a documentation content check,
  not automatable without a much larger apparatus this spec's Non-Goals rule
  out for now.

## Rollout, Observability & Rollback

No rollout — this is documentation and agent contracts, live as soon as
merged; nothing to deploy. No observability, since there is no runtime.
Rollback: delete `agents/enterprise_risk/` and
`instructions/enterprise_risk.md`, revert the seven pack JSON files and the
two catalog READMEs.

## Open Questions

- Should any of the six ever get a knowledge pack (see spec's own open
  question)? Deferred until a runtime or real usage shows which one needs it.
- Should a runtime be built for any of these six, and if so, which first?
  Deferred until an adopter has real data behind one of them.
