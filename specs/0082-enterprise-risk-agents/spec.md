# Spec: Enterprise Risk Agents

- **ID:** 0082-enterprise-risk-agents
- **Status:** Approved
- **Author:** Joshua Lutkemuller, CFA
- **Approver:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-09-25

> WHAT and WHY only. Implementation lives in `plan.md`.

## Problem & Context

Building spec `0081`'s 40 analytics domain packs surfaced a real gap: 27 of
the 40 packs named `agents/risk` as a reviewer, because nothing more specific
existed. Checking `agents/risk/README.md` against what those packs actually
needed showed a mismatch — its charter is explicitly the risk of *a signal,
model, portfolio, or strategy* (`instructions/risk_management.md`), not
operational loss events, model-inventory governance, derivative counterparty
exposure and XVA, AML program health, bank-level liquidity and IRRBB, or
climate/ESG risk. Each of those is a real discipline in a bank or
diversified financial-services firm, with its own inventory, its own
regulatory expectations, and its own accountable owner. Folding all of them
into one generic agent is the same failure mode credit risk had before spec
`0072` gave it its own domain foundation — a review that is technically
present but structurally wrong.

Checking further: `agents/securities_financing/` and
`agents/credit_risk/counterparty_limits` already have narrowly-scoped,
correctly-fitted agents (confirmed by inspection, not assumption), so this
gap is specific to the six disciplines named above — not a general "risk
needs more agents" claim.

## Goals

- Give each of the six mismatched disciplines its own narrowly-scoped agent,
  matching what `0072` did for credit risk.
- Re-point every `0081` pack currently falling back to `agents/risk` for one
  of these six disciplines to the correctly-scoped new agent.
- Leave `agents/risk/` itself unchanged — it is a correct fit for investment
  and portfolio risk, and for the many business-line packs that name it as a
  secondary "does this look risky" reviewer alongside a domain-specific
  agent; that use is within its stated charter and out of scope here.
- Establish the group's shared rule up front: every agent here measures,
  aggregates, or reviews what it is given; none of them scores, prices,
  approves, files, or decides on behalf of the human accountable for that
  decision — the same boundary `agents/credit_risk/` already draws around
  rating and PD/LGD estimation.

## Non-Goals

- **No executable runtime.** Like `0022` (asset-class mechanics) and `0033`
  (economists), this spec ships agent contracts only; a runtime, if one is
  ever built, is a later, separately-approved spec.
- **No new knowledge pack** (a `knowledge/` directory with its own
  taxonomy/conventions/gap-register apparatus, the way `0072` and `0063`
  work). `instructions/enterprise_risk.md` is the standard; it does not
  duplicate `instructions/risk_management.md` or `instructions/credit_risk.md`.
- **Not touching `agents/risk/` itself**, or the packs where it is correctly
  used as a secondary reviewer for a business-line pack.
- **Not deciding, scoring, pricing, approving, or filing anything** — the
  shared rule above is a hard boundary, not a starting point to relax later
  without a new spec and an explicit exception.
- **Market risk** is explicitly excluded from the new agent list:
  `agents/risk/` already covers VaR, sensitivities, and stress testing
  correctly; adding a duplicate `market_risk` agent would recreate the exact
  problem this spec fixes, in the other direction.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The SDK shall add six agents under a new `agents/enterprise_risk/` category folder: `operational_risk`, `model_risk_management`, `counterparty_credit_risk`, `aml_financial_crime`, `liquidity_treasury_risk`, `climate_esg_risk` — each with `README.md`, `instructions.md`, `tasks.md`, `prompt.md`, and a `Spec-Driven Role` section in `instructions.md`. | must |
| REQ-002 | The SDK shall add `instructions/enterprise_risk.md`, the standard shared across the six agents, stating the group's shared rule (measure/aggregate/review, never decide) and naming what each agent must never do. | must |
| REQ-003 | Each agent's `README.md` shall state at least one thing it never does, and to whom that decision belongs. | must |
| REQ-004 | The `0081` analytics domain packs `operational_risk`, `model_risk`, `counterparty_risk_xva`, `aml_financial_crime`, `liquidity_risk`, `treasury_alm_irrbb`, and `climate_esg_risk` shall name the matching new agent in `reviewer_agents`, replacing the generic `agents/risk` fallback where it was present. | must |
| REQ-005 | `agents/README.md` shall gain an `Enterprise Risk Agents` catalog section naming why the group exists (the `0081` finding) and listing all six agents, each with what it never does. | must |
| REQ-006 | `agents/risk/` and every pack using it as a secondary reviewer for a business-line pack (not one of the six disciplines in REQ-004) shall be left unmodified. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Catalog consistency | `hooks/stages/agent-catalog-check.sh` passes with all six new agents recognized. |
| NFR-002 | Pack validity | `analytics_packs.validate_catalog` reports zero errors after the re-pointing in REQ-004. |
| NFR-003 | No scope creep | No agent in this group computes a number from data it was not given, or takes a decision named in its own "never" list. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given `agents/enterprise_risk/`, when listed, then it contains exactly the six named subdirectories, each with all four contract files. | REQ-001 |
| AC-002 | Given `instructions/enterprise_risk.md`, when read, then it states the shared "measure, never decide" rule and a per-agent "never does this" table. | REQ-002 |
| AC-003 | Given each of the six agents' `README.md`, when read, then its "Runtime" or an equivalent section names at least one action it never performs and who the decision belongs to. | REQ-003 |
| AC-004 | Given the seven named `0081` packs, when their `reviewer_agents` are read, then each names its matching new `enterprise_risk` agent, and none of the seven still names the bare `agents/risk`. | REQ-004 |
| AC-005 | Given `agents/README.md`, when read, then an `Enterprise Risk Agents` section exists, names the `0081` finding as its reason for existing, and lists all six agents. | REQ-005 |
| AC-006 | Given the full set of `0081` packs that use `agents/risk` as a secondary reviewer for a business-line pack, when diffed against this change, then none of them changed. | REQ-006 |
| AC-007 | Given the repository, when `hooks/stages/agent-catalog-check.sh` runs, then it passes with no findings and reports the increased agent count. | NFR-001 |
| AC-008 | Given the repository, when `analytics_packs.validate_catalog` runs, then it reports zero errors. | NFR-002 |

## Data & Dependencies

- Depends on the `0081` finding (27 of 40 packs falling back to
  `agents/risk`) as its problem statement's evidence.
- References `instructions/risk_management.md` (what `agents/risk/` already
  covers, to state the boundary clearly) and `instructions/credit_risk.md`
  (the precedent for a domain outgrowing a generic reviewer).
- No data, credentials, or company information — this is an agent-contract
  and documentation change only.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A new agent's charter drifts to overlap `agents/risk/` or an existing agent (e.g. `credit_risk/counterparty_limits`). | Duplicate, conflicting review paths. | Each agent's `README.md` states what it is distinct from and hands off to; `agents/enterprise_risk/README.md` states the boundary explicitly. |
| RISK-002 | One of these agents is asked to make a decision it should refuse (approve a model, file a SAR). | The agent oversteps into a regulated human decision. | The shared "never" rule (REQ-002/REQ-003) plus each agent's own `tasks.md` Boundary Check. |
| RISK-003 | AML confidentiality is treated as a formatting preference rather than a hard boundary. | Individual-level disclosure of alerts, cases, or SAR content. | `aml_financial_crime`'s instructions state it as an absolute boundary with no acceptable mitigation short of removal. |

## Assumptions & Open Questions

- Assumption: a contract-only agent (no runtime) is still worth shipping now,
  the same bet `0022`/`0033` made — it gives the pack's `reviewer_agents`
  something real and narrowly-scoped to point at today, and a runtime can
  follow later without changing the contract.
- Open question: should any of these six eventually get a knowledge pack the
  way credit risk and short-term markets did? Deferred until real usage
  shows which one needs it first.

## Exceptions

None.
