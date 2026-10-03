# Plan: Venture Request Routing and Orchestrator

- **Spec:** 0096-venture-request-routing-and-orchestrator (`spec.md`)
- **Status:** Draft (built)
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-10-03

> HOW. Requires the Draft spec; `tasks.md` tracks status.

## Approach

Keep the rules in data and the code small. `routing.json` holds task kinds, forbidden intents, regions, and class
rules; `plan_request` applies them in a fixed order (refusals, classification, region expansion, language step, class and
clearance); the pack validator checks every reference so a typo cannot ship (it caught `entity_resolution` versus
`entity_resolution_agent` on first use). The orchestrator agent contract describes the same behaviour for a language-model
runtime that wraps the function.

## Architecture & Components

```
knowledge/venture_intelligence/routing.json         rules (draft records)
src/quantsmith/pipelines/venture_routing.py         load_routing, detect_regions, classify_task, forbidden_hits, plan_request
src/quantsmith/pipelines/venture_pack.py            routing validation; routing in FILES and the review sign-off
agents/venture_intelligence/venture_orchestrator/
tests/test_venture_routing.py
```

## Interfaces & Data Contracts

- `plan_request(text, caller_clearance, pack) -> {"status": planned | refused | needs_clarification | denied, "task_kind", "steps": [{"order", "agent", "path", "class"}], "decision_path_class", "required_clearance", "human_review", "decision_owner", "refusals": [{"intent", "refusal", "decision_owner", "alternatives"}], "notes", "limits", "request"}`; `candidates` accompanies a tie.
- Order: empty check; refusals; classification (most distinct keyword hits; tie asks); region expansion of `{regional_lead}` and `{regional_structure_analyst}`; skip of single-region agents elsewhere; non-English-script step first; strictest class; clearance check; gates.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Every reference validated; ambiguity asks |
| P5 Reversibility | yes | Additive |
| P6 Observability | partial | Plans carry notes and limits |
| P9 Security & data | yes | Clearance required; denial reveals no steps; requests not stored |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `routing.json` | T-001 |
| REQ-002 | validator routing block | T-002 |
| REQ-003 | reachability test | T-002 |
| REQ-004 | forbidden intents, `plan_request` | T-003 |
| REQ-005 | `classify_task` | T-004 |
| REQ-006 | `detect_regions`, placeholder expansion | T-005 |
| REQ-007 | language step | T-006 |
| REQ-008 | class and clearance logic | T-007 |
| REQ-009 | plan shape, determinism | T-008 |
| REQ-010 | agent, coverage, indexes, registry | T-009 |
| NFR-001 | stdlib only | T-008 |
| NFR-002 | `limits`, agent text | T-009 |
| NFR-003 | gates, full suite | T-010 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected | Why |
| --- | --- | --- | --- |
| Classifier | Keyword hits, tie asks | Learned or LLM classifier | Auditable; no training data; ambiguity is honest |
| Refusals vs routing | Refusals first, legitimate part still planned | Refuse the whole request | A mixed request has a useful allowed half |
| Class of a plan | Strictest agent | The task kind's declared class | The class follows the agents actually used (a region adds the sovereign-adjacent analyst) |
| Unbuilt regions | Stated gap | Route to nearest region | A wrong market is worse than a gap |

## Validation Strategy

`tests/test_venture_routing.py`; the pack validator; gates and the full suite.

## Rollout, Observability & Rollback

Additive. Rollback: delete the module, agent, rules file, and tests and revert the validator block and doc edits.

## Open Questions

Whether region-naming diligence should always need restricted clearance; refusal wording and keyword lists.
