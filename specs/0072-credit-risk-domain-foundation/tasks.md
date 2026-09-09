# Tasks: Credit Risk Domain Foundation

- **Spec:** 0072-credit-risk-domain-foundation (`spec.md`, `plan.md`)
- **Last updated:** 2026-09-09

> Ordered, testable units of work. Every task cites the requirement(s) it
> advances. Nothing below is implemented yet: this branch delivers the spec
> chain and its roadmap entries only, and every task is honestly `todo`.

## Definition of Done (applies to every task)

- Work matches the approved spec and plan; deviations are recorded in `plan.md`
  before content or code changes.
- Every machine-readable artifact validates offline; every acceptance criterion
  has deterministic evidence, including a negative case where the criterion
  describes a rejection.
- Measurement basis is explicit wherever it changes an answer: horizon,
  conditioning, default definition, collateral treatment, discounting, currency,
  viewpoint, and loss sign.
- Knowledge/as-of time, effective time, source support, and review status are
  present on every record; nothing unsupported is promoted to `reviewed`.
- No consumer PII, loan-level tape, bureau attribute value, credit file,
  internal counterparty term, MNPI, secret, licensed vendor documentation, or
  rating-agency methodology text is committed. Fixtures are synthetic and carry
  a `0025` disclosure.
- No existing runtime's numerical output changes under `0072`; behavioral work
  belongs to `0073`–`0079`.
- Documentation and indexes are updated in the same change, and repository gates
  report reality.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Create the `0072` spec chain (`spec.md`, `plan.md`, `tasks.md`) and define the capability surface across the four pillars. | REQ-001 | done | Spec chain written on this branch. The capability surface is specified; `coverage.json` itself is T-008. |
| T-002 | Index `0072` in `specs/README.md`, add the handoff item, reserve `0073`–`0079` with dependencies and activation rules, and set `0080` as next unreserved. | REQ-017, REQ-018, NFR-005 | done | Roadmap work only. Implementation stays gated on spec approval. |
| T-003 | Author `taxonomy.json`: obligors, facilities, exposures, counterparties, measures, roles, rating/score concepts, and default definitions, with aliases, relations, and every non-interchangeable set enforced. | REQ-002, REQ-003, NFR-005 | todo | The PD/LGD/EAD and default-definition distinctions are the load-bearing part; a shared alias across a distinct pair is a validation failure. |
| T-004 | Author `conventions.json`: units, horizon, conditioning, default-definition ID, collateral treatment, discounting basis, currency, seasoning, calibration population, and formula references. | REQ-003, REQ-004 | todo | Includes the formula-operand basis check: a lifetime ECL formula cannot consume a one-year PD without a recorded conversion. |
| T-005 | Author `lifecycles.json` for credit state, credit approval/limit management, and the SR 11-7 model lifecycle, each transition naming its initiating role and produced artifact. | REQ-005 | todo | Must cover forbearance/modification, cure, charge-off, and recovery, not only the performing-to-default path. |
| T-006 | Write `source_policy.md`, register the first authoritative public sources through `0027`, and implement evidence, conflict, access/license, knowledge-time, effective-time, freshness, and supersession rules. | REQ-006, REQ-007, REQ-019, NFR-003 | todo | Locator-only registration; live ingestion is `0078`. Public citation only, per the policy `0063` already set. |
| T-007 | Author `decision_paths.json` and the consumer-decision contract: reason-code derivation, policy version, cutoff, override recording, empty protected-attribute feature set, and a callable disparate-impact hook. | REQ-014, NFR-008 | todo | Correct-by-construction requirement: a consumer-decision path failing any obligation must be unrepresentable except as `decision_support_only`. |
| T-008 | Author `coverage.json` and `gap_register.md`; crosswalk every relevant current agent, instruction, runtime, source entry, and test, with severity, disposition, and owning spec for each gap. | REQ-001, REQ-009 | todo | Coverage level is evidence-backed: no row claims `reference-runtime` without a named artifact and test. |
| T-009 | Implement the credit point-in-time and leakage admission rules for all six modes in REQ-008, with vintage and outcome-window fixtures. | REQ-007, REQ-008, NFR-002 | todo | Each rejection names the violated rule so failures are diagnostic. |
| T-010 | Author `golden_cases.json` and implement the standard-library validator `credit_risk_knowledge.py`. | REQ-010, NFR-001, NFR-006 | todo | Cases: EL from PD/LGD/EAD; EAD from CCF; 12-month vs lifetime ECL with EIR discounting; IRB risk weight; points-to-odds and cutoff; adverse action ranking; migration-matrix row stochasticity; outcome-window rejection. Validator exposes validation helpers only, never a scoring or provisioning API. |
| T-011 | Author the `agents/credit_risk/` charter: roster, per-agent responsibility, inputs/outputs, serving workflow, and the coverage row justifying each agent. Create only the agents the matrix justifies. | REQ-011 | todo | Each created agent needs `README.md`, `instructions.md`, `prompt.md`, `tasks.md`, a `Spec-Driven Role` section, and an `agents/README.md` row. Creating none is a valid outcome if the matrix justifies none. |
| T-012 | Define the six end-to-end workflow contracts with stages, participating agents, inputs, artifacts, gates, and human decision points; classify each capability's runtime boundary. | REQ-012, REQ-013 | todo | Every referenced agent must exist in the charter or be marked future work with its owning spec. |
| T-013 | Author `governance.json`: the credit model card extension, required validation evidence, challenger comparison, monitoring thresholds, override log, owner, and kill switch, with deployability as a computed predicate. | REQ-013, REQ-015 | todo | Extends `templates/docs/model_card.md` and `model_monitoring_plan.md` rather than replacing them. Deployability must not be settable by assertion. |
| T-014 | Implement the LLM evidence admission boundary over `0070` envelopes and `0071` artifacts: source spans, prompt/context manifest, assumption-ledger entry, replay reference, and `derived_evidence` labeling. | REQ-016, NFR-007 | todo | Promotion to `decision_input` requires named human review; no automated path performs it. |
| T-015 | Add `instructions/credit_risk.md` and update touching agents to cite the canonical pack instead of redefining shared terms. | REQ-018 | todo | Adding an instruction standard changes the `doc-counts` truth; update the stated counts in `README.md`, `docs/handoff.md`, and `docs/sdk_plan.md` in the same change. |
| T-016 | Complete two-part human review — credit practitioner review of measures, conventions, lifecycles, and decision paths, and a model-validation review of temporal and numerical cases — recording reviewer handles, scope, dates, and dispositions. | REQ-019, NFR-003, NFR-004 | blocked | Requires a named credit-domain reviewer, which is an open question in `spec.md`. Structural automation cannot satisfy this; records stay `draft` until it is resolved. |
| T-017 | Run the credit validation module, full `pytest`, and the required repository gates (`spec`, `docs-link`, `spec-index`, `doc-counts`, `handoff-sync`, `source-catalog`, `data-provenance`, `secret-scan`, `agent-catalog`, `readme-sync`), and record exact evidence. | NFR-001, NFR-006 | todo | Evidence recorded honestly, including any failure. No existing runtime result may change. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

All tests live in `tests/test_credit_risk_knowledge.py` unless noted, and each
names its criterion in the test name, following `0063`'s convention.

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_required_capability_domains_AC_001` | todo |
| AC-002 | `test_taxonomy_ids_aliases_and_distinctions_AC_002` | todo |
| AC-003 | `test_measure_viewpoint_and_sign_required_AC_003` | todo |
| AC-004 | `test_convention_records_are_complete_and_compatible_AC_004` | todo |
| AC-005 | `test_lifecycle_graphs_and_invalid_transition_AC_005` | todo |
| AC-006 | `test_reviewed_records_require_resolvable_evidence_AC_006` | todo |
| AC-007 | `test_later_known_version_excluded_from_earlier_asof_AC_007` | todo |
| AC-008 | `test_outcome_window_violation_rejected_AC_008` | todo |
| AC-009 | `test_gap_register_rows_have_evidence_and_owners_AC_009` | todo |
| AC-010 | `test_golden_cases_are_complete_and_repeatable_AC_010` | todo |
| AC-011 | `test_agent_charter_requires_coverage_row_AC_011` | todo |
| AC-012 | `test_workflow_contracts_are_complete_AC_012` | todo |
| AC-013 | `test_runtime_boundary_has_no_hardcoded_policy_constants_AC_013` | todo |
| AC-014 | `test_consumer_decision_path_obligations_AC_014` | todo |
| AC-015 | `test_adverse_action_reasons_are_deterministic_and_clean_AC_015` | todo |
| AC-016 | `test_deployability_requires_governance_artifacts_AC_016` | todo |
| AC-017 | `test_llm_derived_input_admission_AC_017` | todo |
| AC-018 | `test_handoff_reserves_child_specs_and_next_number_AC_018` | todo |
| AC-019 | `test_instructions_and_agents_cite_canonical_pack_AC_019` | todo |
| AC-020 | `test_review_promotion_rejects_missing_reviewer_or_high_gap_AC_020` | todo |
| AC-021 | Release-review diff inspection: no existing runtime output changed; every fixture synthetic and `0025`-disclosed | todo |
| AC-022 | Credit validation module + `spec`, `docs-link`, `spec-index`, `doc-counts`, `handoff-sync`, `source-catalog`, `data-provenance`, `secret-scan` gates; full `pytest -q`; `git diff --check` | todo |

## Validation Evidence

None yet. `T-001` and `T-002` are planning and roadmap work; no credit artifact,
validator, test, or agent exists on this branch, so there is nothing to report
beyond the repository gates run against the spec chain itself. Evidence is
recorded here as tasks complete, including failures.

## Follow-ups

Reserved in `docs/handoff.md`, not active specs. Create one only after `0072` is
approved and the dependency named in its reservation is satisfied.

- `0073` — wholesale credit measurement runtime (rating, PD/LGD/EAD, exposure,
  limits and concentration).
- `0074` — retail underwriting and fair-lending runtime (scorecards, cutoffs,
  adverse action, disparate impact, reject inference).
- `0075` — IFRS 9 / CECL expected credit loss engine (staging, lifetime
  measurement, EIR discounting, macro overlays).
- `0076` — regulatory capital and supervisory stress testing (IRB risk weights,
  scenario expansion, capital planning inputs).
- `0077` — credit document intelligence (memos, covenant extraction, financial
  spreading, early warning) over `0070`/`0071`.
- `0078` — credit data sources and ingestion contracts.
- `0079` — credit model risk management and monitoring runtime.

Deliberately deferred beyond these: non-U.S. jurisdictions, insurance and
sovereign credit, securitization and structured credit, counterparty credit
valuation adjustments, and any credit derivative pricing. Each needs a concrete
consumer and coverage evidence before it earns a number.
