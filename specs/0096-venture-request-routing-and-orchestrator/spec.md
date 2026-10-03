# Spec: Venture Request Routing and Orchestrator

- **ID:** 0096-venture-request-routing-and-orchestrator
- **Status:** Draft (built)
- **Author:** Joshua Lutkemuller, CFA
- **Approver:**
- **Last updated:** 2026-10-03

> WHAT and WHY only. Child of `0083-venture-intelligence-foundation`. Composes the agents of `0084`–`0092` without changing them.

## Problem & Context

The venture suite has 26 contract-only agents across three missions (technology scouting, portfolio
consulting, foreign-influence screening support), but no front door. A user has to know that a Shenzhen
ownership question needs the Greater China structure analyst, the ownership screen, and the dual-use
indicator, that anything touching a person or a sovereign interest needs restricted clearance and named
human review, and that a request to "tell us whether to invest" must be refused and sent to the
investment committee. Getting that wrong either under-routes (a missing gate) or over-reaches (the suite
appears to decide). The repository already has a general `workflow_orchestrator` for the spec-driven
flow; nothing routes these domain requests.

## Goals

- One deterministic router that turns a request into a plan: ordered agents, review gates, decision owner, decision-path class, and required clearance.
- Refusals decided first, each naming the human who owns the decision and the allowed alternative; any legitimate part of a mixed request still planned.
- Honest limits: keyword matching, so ambiguity asks instead of guessing; a region with no agent is a stated gap.
- Routing rules as reviewable data, validated, with every built agent reachable.

## Non-Goals

- No natural-language understanding, LLM call, or learned classifier; the router is rules.
- No execution of the plan, no calling of agents, and no release or decision; the orchestrator plans and refuses.
- No change to any existing agent, to `workflow_orchestrator`, or to the decision-path class rules.
- No routing to regions with no agents (`0087`); they are reported as gaps.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The SDK shall hold routing rules in `knowledge/venture_intelligence/routing.json` (task kinds with keywords, agent chains, review gates and a decision owner; forbidden intents with patterns, a refusal, a decision owner and allowed alternatives; regions with keywords, a lead and a structure analyst; class rules), as draft records with citations and review fields. | must |
| REQ-002 | The pack validator shall reject routing that names an agent that is not built, a task kind without keywords, a chain, a decision owner or review gates, a forbidden intent with an invalid pattern, no refusal or no decision owner (where `None` is never a name), or an alternative that is not a task kind, a built region without a lead, or class rules that do not cover exactly the three decision-path classes. | must |
| REQ-003 | Every built venture agent other than the orchestrator shall be reachable through at least one task kind or region. | must |
| REQ-004 | The router shall refuse, with the owner and the alternatives, a request to recommend an investment (in any word order), designate or attribute, profile an individual, collect from non-public sources, release without review, set or approve a mark, classify export control, or forecast returns; a request that is only a refusal shall return `refused`; a mixed request shall plan the legitimate part and list the refusals. | must |
| REQ-005 | The router shall classify a request to the task kind with the most distinct keyword hits; a tie, a request that matches nothing, and an empty request shall return `needs_clarification`, with candidates for a tie, and never a guess. | must |
| REQ-006 | The router shall detect named regions (countries and major cities) and expand the lead and structure-analyst placeholders to every named built region in a fixed order; state a region with no structure analyst as a gap; skip an agent that covers only another region, with a note; report deferred regions as having no agent yet; and ask for a market when a region overview names none. | must |
| REQ-007 | The router shall insert document extraction first when the request contains non-English script, once. | must |
| REQ-008 | The router shall set the plan's decision-path class to the strictest among its agents, require the matching clearance, attach the class's human-review gate, and return `denied` with no steps to a caller below that clearance; a missing or unknown clearance shall raise. | must |
| REQ-009 | The router shall be deterministic, shall not modify its inputs, and shall return a plan with its status, task kind, ordered unique steps (agent, path, class), class, clearance, gates, owner, refusals, notes, and limits. | must |
| REQ-010 | The SDK shall add the `venture_orchestrator` agent with four contract files and a stated boundary, mark it built, add it to the roadmap and catalog, standard, group README, dictionary, and agent registry. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Determinism and privacy | Standard library only; no network; requests are not stored. |
| NFR-002 | Honesty | The plan states that keyword matching is its limit and that a plan is not authorization to act. |
| NFR-003 | Gates | All gates with enforcement on pass and no existing test regresses. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given the routing data, when validated, then the pack has no errors, every built agent is reachable, all records are draft with citations, and a broken agent reference, invalid pattern, missing owner (including `None`), bad alternative, leadless built region, or incomplete class rules is rejected. | REQ-001, REQ-002, REQ-003 |
| AC-002 | Given each forbidden-intent example, when routed, then it is refused with its owner and a valid alternative; recommendation requests are caught in every word order; benign requests are not refused; a pure refusal returns `refused`; and a mixed request plans the legitimate part and lists the refusal. | REQ-004 |
| AC-003 | Given a natural request for each task kind, when classified, then the intended kind ranks first and a planned result has ordered, unique steps, an owner, and gates; and an ambiguous, unmatched, or empty request asks. | REQ-005 |
| AC-004 | Given requests naming countries and cities, when routed, then regions are detected, multiple leads appear in order, structure analysts appear only where built with a stated gap otherwise, deferred regions are a stated gap, a region overview without a market asks, and a Southeast Asia-only agent is skipped elsewhere. | REQ-006 |
| AC-005 | Given English and non-English text, when routed, then extraction is first exactly once for non-English script and absent otherwise. | REQ-007 |
| AC-006 | Given requests of each class, when routed at each clearance, then the class is the strictest, the gate is attached, a lower clearance is denied without steps, and a missing or unknown clearance raises. | REQ-008 |
| AC-007 | Given repeated routing, when compared, then plans are identical, inputs are unchanged, and every step's path exists. | REQ-009, NFR-001 |
| AC-008 | Given the agent, coverage, roadmap, catalog, standard, registry, and indexes, when read, then the orchestrator is built with four files and its boundary and the indexes agree on the next free spec number. | REQ-010 |
| AC-009 | Given the repository, when gates and the full suite run, then no gate has findings and no previously passing test fails. | NFR-002, NFR-003 |

## Data & Dependencies

Depends on the coverage matrix and decision-path classes (`0083`), the built agents (`0084`–`0092`), clearance tiers
(`0052`), and the Asian-language script detector (`0094`).

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A request is mis-routed because keyword matching misses it. | Missing gate or agent. | Ambiguity asks; limits stated; data is reviewable and testable. |
| RISK-002 | A forbidden request slips past the patterns. | The suite appears to decide. | Patterns in every word order, tested; agent boundaries still apply downstream. |
| RISK-003 | The plan is read as authorization. | Unreviewed action. | Plan states it is not authorization; gates and owners are attached. |
| RISK-004 | Clearance is inferred from the request instead of the caller. | Privilege confusion. | Clearance is a required parameter; denial reveals no steps. |
| RISK-005 | An unbuilt region is silently routed to a neighbour. | Wrong market analysed. | Deferred regions are a stated gap. |

## Assumptions & Open Questions

- Assumption: deterministic rules are the right first router because they are auditable and testable; a language model could later propose a task kind, but the rules would still gate it.
- Open question: whether a diligence request that names a region should always require restricted clearance (today it does, because the structure analyst is sovereign-adjacent).
- Open question: the exact refusal wording and keyword lists the committee and counsel want (they are data).

## Exceptions

None.
