# Spec: Role Operations Agents (Phase 1)

- **ID:** 0024-role-operations-agents
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-08-09

## Problem & Context

A quant/data-science lead's day fills with operational overhead around the
work that actually matters: meeting follow-ups, status updates, prototype
setup, and first-pass research scans. None of that overhead is unique to any
one firm, platform, or title — the same categories of toil recur for anyone
in the role — but any agent built to help must satisfy a hard constraint:
this SDK is a public, shareable scaffold, so it can never carry a real firm's
platform names, client detail, team-member names, or any personal data. The
agent has to be configurable enough to be useful on someone's actual work
without the SDK itself ever holding that work's specifics.

This spec adds the first slice of a four-pillar agent roster (Framework
Design, Client & Stakeholder Engagement, Model Governance, Innovation &
Prototyping) aimed at that overhead, plus the configuration mechanism that
makes it useful without violating the no-company-data constraint: a
gitignored-by-default local config file, a committed template that holds
only placeholders, and a gate that catches the file if it's ever accidentally
committed.

## Goals

- Add `agents/role_operations/` with four agents targeting the
  lowest-risk, highest-frequency toil: `meeting_to_action`, `status_rollup`,
  `rapid_scaffolder`, `prior_art_scanner`.
- Add a configuration mechanism — `templates/role_operations/role_context.yml`
  (template, placeholders only) plus a local, gitignored
  `role_context.yml` at the repo root — so the agents can be tailored to real
  platform/data/domain specifics without those specifics ever entering
  version control.
- Add a gate, `role-context-check`, that deterministically catches a
  committed or staged `role_context.yml` and advisorially checks the shipped
  template for placeholder hygiene.
- Add the backing standard `instructions/role_operations.md`.
- Wire the group into the agent catalog, spec index, and root README.

## Non-Goals

- No Phase 2/3 agents in this slice (demo packaging, tough-question
  rehearsal, model-card drafting, audit-trail keeping, governance-readiness
  checklist, experiment ledger, build-handoff writer, alert triage) — they
  are follow-ups, deliberately sequenced after this lower-stakes slice earns
  trust (see `tasks.md` Follow-ups).
- No literal PII/company-data detector; the `role-context` gate's
  deterministic check is "is `role_context.yml` tracked by git," not a
  general-purpose PII classifier. The advisory template-hygiene check is a
  narrow heuristic (email-shaped and SSN-shaped patterns), not a claim of
  comprehensive PII detection — the same honestly-scoped limitation the
  `leakage` and `secret-scan` gates already carry.
- No integration with a real calendar, ticketing, or chat system; each
  agent's input is supplied directly by the user in the session, not pulled
  from a live system.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The system shall provide four role-operations agents (`meeting_to_action`, `status_rollup`, `rapid_scaffolder`, `prior_art_scanner`) on the four-file contract, each usable with no configuration and sharpened by optional local configuration. | must |
| REQ-002 | The system shall provide a configuration template (`templates/role_operations/role_context.yml`) containing only placeholder values, with a documented resolution order for a local, real-valued copy. | must |
| REQ-003 | The system shall provide a gate that deterministically flags a tracked or staged `role_context.yml` (blocking under `QF_STAGE_ENFORCE=1`) and advisorially checks the shipped template for placeholder hygiene. | must |
| REQ-004 | The agent catalog, spec index, root README, and `.gitignore` shall document and enforce the group and its no-company-data guarantee. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Agent contract consistency | Every new public agent has `README.md`, `prompt.md`, `instructions.md`, `tasks.md`, each with a `Spec-Driven Role` section. |
| NFR-002 | Repository hygiene | `spec`, `agent-catalog`, `docs-link`, `spec-index`, `secret-scan`, and the new `role-context` gate all pass. |
| NFR-003 | Data safety | No real firm, platform, client, team-member, or PII-shaped value anywhere in the template, agent docs, or spec; `role_context.yml` is gitignored by default. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given `templates/role_operations/role_context.yml`, when inspected, then every value is an evident placeholder (category-level description, not a real name), and the `role-context` gate's hygiene check finds nothing. | REQ-002, NFR-003 |
| AC-002 | Given a `role_context.yml` staged or force-added at the repo root, when the `role-context` gate runs, then it is flagged, and blocks under `QF_STAGE_ENFORCE=1`. | REQ-003, NFR-003 |
| AC-003 | Given no `role_context.yml` present anywhere, when the `role-context` gate runs, then it reports "not configured" and exits cleanly with no findings. | REQ-003, NFR-002 |
| AC-004 | Given each of the four agents' `instructions.md`, when inspected, then each explicitly states it must work without configuration, must never persist real specifics into a tracked file, and never fabricates a name/number/decision absent from its input. | REQ-001, NFR-003 |
| AC-005 | Given the full gate suite, when run, then `spec`, `agent-catalog`, `docs-link`, `spec-index`, `secret-scan`, and `role-context` all pass. | NFR-002 |

## Data & Dependencies

No data dependencies. No runtime code in this slice — the agents are
Markdown contracts, consistent with `0004`/`0014`/`0022`. The `role-context`
gate is a POSIX shell script consistent with the existing `hooks/stages/`
gates and adds no new tooling dependency.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A user fills in `role_context.yml` locally and force-commits it despite `.gitignore`. | Real platform/team/data specifics enter git history. | The `role-context` gate's deterministic tracked-file check catches this independent of `.gitignore` (which only prevents *accidental* adds); document the risk explicitly in `instructions/role_operations.md`'s Common Failure Modes. |
| RISK-002 | An agent, under this group, fabricates a plausible-sounding detail (an owner, a citation, a result) to fill a gap in thin input. | A drafted follow-up, status update, or scan misleads the person reviewing it. | Every agent's `instructions.md` states "never fabricate" as an operating rule and a check; outputs are explicitly labeled drafts requiring human review before use. |
| RISK-003 | The advisory template-hygiene heuristic (email/SSN-shaped patterns) gives false confidence that no PII-shaped content exists. | A real identifier that doesn't match the narrow heuristic ships in a committed example. | Documented as a narrow, best-effort heuristic in both the gate's comments and this spec's Non-Goals — the deterministic tracked-file check (AC-002), not the heuristic, is the real safeguard. |

## Assumptions & Open Questions

- Assumption: four agents (the Phase 1 slice from the underlying efficiency
  plan) is the right first increment — enough to prove the pattern without
  building all fourteen roles before any of them has been used.
- Assumption: a gitignored local file plus a deterministic git-tracking
  check is a stronger guarantee against accidental company-data leakage than
  a documentation-only convention, for the same reason secrets never belong
  in the repo (constitution P9).
- Open question: should Phase 2 (demo packaging, tough-question rehearsal,
  experiment ledger) follow next, or should governance-adjacent Phase 3
  agents wait even longer given their higher stakes?

## Exceptions

None.
