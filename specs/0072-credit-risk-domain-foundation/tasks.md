# Tasks: Credit Risk Domain Foundation

- **Spec:** 0072-credit-risk-domain-foundation (`spec.md`, `plan.md`)
- **Last updated:** 2026-09-09

> Ordered, testable units of work. Every task cites the requirement(s) it
> advances. The knowledge pack, validator, and acceptance tests are built; the
> agent charter and the human review are not. Statuses below say which is which.

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
| T-003 | Author `taxonomy.json`: obligors, facilities, exposures, counterparties, measures, roles, rating/score concepts, and default definitions, with aliases, relations, and every non-interchangeable set enforced. | REQ-002, REQ-003, NFR-005 | done | 53 concepts, 6 ambiguity rules, 46 non-interchangeable pairs. A shared alias across a distinct pair fails validation; `test_shared_alias_between_distinct_concepts_is_rejected_AC_002` proves the rejection rather than only the pass. |
| T-004 | Author `conventions.json`: units, horizon, conditioning, default-definition ID, collateral treatment, discounting basis, currency, seasoning, calibration population, and formula references. | REQ-003, REQ-004 | done | 13 conventions plus 3 basis-compatibility rules. 6 required parameters carry `default: null` — a required parameter with a default is rejected, so an institution-specific value cannot enter as a constant. |
| T-005 | Author `lifecycles.json` for credit state, credit approval/limit management, and the SR 11-7 model lifecycle, each transition naming its initiating role and produced artifact. | REQ-005 | done | 3 graphs, 32 states, 45 transitions; all reachable, terminals explicit, every transition names its initiating role and produced artifact. There is deliberately no development-to-deployment edge: independent validation is structurally unavoidable. |
| T-006 | Write `source_policy.md`, register the first authoritative public sources through `0027`, and implement evidence, conflict, access/license, knowledge-time, effective-time, freshness, and supersession rules. | REQ-006, REQ-007, REQ-019, NFR-003 | done | `source_policy.md` written; `cfpb`, `fasb`, `ifrs_foundation`, `bis_basel`, `occ` registered as locator-only public sources and indexed. Live ingestion remains `0078`. |
| T-007 | Author `decision_paths.json` and the consumer-decision contract: reason-code derivation, policy version, cutoff, override recording, empty protected-attribute feature set, and a callable disparate-impact hook. | REQ-014, NFR-008 | done | 7 decision paths, 2 consumer-facing. The load-bearing negative case passes: obligations unmet **and** sole basis permitted is rejected, and restating the path as `decision_support_only` is the valid alternative. |
| T-008 | Author `coverage.json` and `gap_register.md`; crosswalk every relevant current agent, instruction, runtime, source entry, and test, with severity, disposition, and owning spec for each gap. | REQ-001, REQ-009 | done | 8 capabilities covering all 8 required domains, all honestly at `contract_only`; 10 gap rows with evidence, severity, disposition, and owner. A `reference_runtime` claim without a runtime module fails validation. |
| T-009 | Implement the credit point-in-time and leakage admission rules for all six modes in REQ-008, with vintage and outcome-window fixtures. | REQ-007, REQ-008, NFR-002 | done | All six credit leakage modes declared and enforced; a rejection names every violated rule, not just the first, so failures are diagnostic. |
| T-010 | Author `golden_cases.json` and implement the standard-library validator `credit_risk_knowledge.py`. | REQ-010, NFR-001, NFR-006 | done | 10 golden cases and a stdlib validator. Expected values are computed, not transcribed. `credit_risk_knowledge.py` exposes validation helpers only — no scoring, provisioning, capital, or underwriting API. |
| T-011 | Author the `agents/credit_risk/` charter: roster, per-agent responsibility, inputs/outputs, serving workflow, and the coverage row justifying each agent. Create only the agents the matrix justifies. | REQ-011 | todo | Not started, and deliberately so: the charter gates creation on a coverage row, and `test_no_credit_agent_exists_yet_AC_011` currently asserts no `agents/credit_risk/` directory exists. `workflows.json` names the future agents and their owning specs. |
| T-012 | Define the six end-to-end workflow contracts with stages, participating agents, inputs, artifacts, gates, and human decision points; classify each capability's runtime boundary. | REQ-012, REQ-013 | done | 6 workflows across the 4 pillars, each naming stages, inputs, artifacts, gates, human decision points, and runtime boundary. Every future agent names its owning spec. |
| T-013 | Author `governance.json`: the credit model card extension, required validation evidence, challenger comparison, monitoring thresholds, override log, owner, and kill switch, with deployability as a computed predicate. | REQ-013, REQ-015 | done | 7 governance artifacts and a computed deployability predicate. There is no `deployable` field to set; `test_there_is_no_deployable_field_to_set_AC_016` asserts its absence from the committed JSON. |
| T-014 | Implement the LLM evidence admission boundary over `0070` envelopes and `0071` artifacts: source spans, prompt/context manifest, assumption-ledger entry, replay reference, and `derived_evidence` labeling. | REQ-016, NFR-007 | done | Admission requires all six of artifact ref, source spans, envelope ref, manifest, assumption-ledger entry, and replay ref; each missing field is proven to block admission. Promotion to `decision_input` requires named human review and no automated path performs it. |
| T-015 | Add `instructions/credit_risk.md` and update touching agents to cite the canonical pack instead of redefining shared terms. | REQ-018 | done | `instructions/credit_risk.md` added. Instruction-count truth moved 35 to 36; `README.md`, `docs/handoff.md`, and `docs/sdk_plan.md` updated in the same change and `doc-counts` is clean. |
| T-016 | Complete two-part human review — credit practitioner review of measures, conventions, lifecycles, and decision paths, and a model-validation review of temporal and numerical cases — recording reviewer handles, scope, dates, and dispositions. | REQ-019, NFR-003, NFR-004 | blocked | Unchanged and genuinely blocked. All 107 records remain `draft`; `test_every_committed_record_is_still_draft_AC_020` asserts that rather than letting the count drift quietly. Resolution is a named credit-domain reviewer, which no automation here can substitute. |
| T-017 | Run the credit validation module, full `pytest`, and the required repository gates (`spec`, `docs-link`, `spec-index`, `doc-counts`, `handoff-sync`, `source-catalog`, `data-provenance`, `secret-scan`, `agent-catalog`, `readme-sync`), and record exact evidence. | NFR-001, NFR-006 | done | Evidence recorded below. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

All tests live in `tests/test_credit_risk_knowledge.py` unless noted, and each
names its criterion in the test name, following `0063`'s convention.

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_required_capability_domains_AC_001` | done |
| AC-002 | `test_taxonomy_ids_aliases_and_distinctions_AC_002` | done |
| AC-003 | `test_measure_viewpoint_and_sign_required_AC_003` | done |
| AC-004 | `test_convention_records_are_complete_and_compatible_AC_004` | done |
| AC-005 | `test_lifecycle_graphs_and_invalid_transition_AC_005` | done |
| AC-006 | `test_reviewed_records_require_resolvable_evidence_AC_006` | done |
| AC-007 | `test_later_known_version_excluded_from_earlier_asof_AC_007` | done |
| AC-008 | `test_outcome_window_violation_rejected_AC_008` | done |
| AC-009 | `test_gap_register_rows_have_evidence_and_owners_AC_009` | done |
| AC-010 | `test_golden_cases_are_complete_and_repeatable_AC_010` | done |
| AC-011 | `test_agent_charter_requires_coverage_row_AC_011` | done |
| AC-012 | `test_workflow_contracts_are_complete_AC_012` | done |
| AC-013 | `test_runtime_boundary_has_no_hardcoded_policy_constants_AC_013` | done |
| AC-014 | `test_consumer_decision_path_obligations_AC_014` | done |
| AC-015 | `test_adverse_action_reasons_are_deterministic_and_clean_AC_015` | done |
| AC-016 | `test_deployability_requires_governance_artifacts_AC_016` | done |
| AC-017 | `test_llm_derived_input_admission_AC_017` | done |
| AC-018 | `test_handoff_reserves_child_specs_and_next_number_AC_018` | done |
| AC-019 | `test_instructions_and_agents_cite_canonical_pack_AC_019` | done |
| AC-020 | `test_review_promotion_rejects_missing_reviewer_or_high_gap_AC_020` | done |
| AC-021 | `test_no_real_credit_data_is_committed_AC_021` (mechanical: committed JSON carries no personal-data keys) plus release-review diff inspection for the unchanged-runtime half | done |
| AC-022 | Credit validation module + `spec`, `docs-link`, `spec-index`, `doc-counts`, `handoff-sync`, `source-catalog`, `data-provenance`, `secret-scan` gates; full `pytest -q`; `git diff --check` | done |

## Validation Evidence

Captured 2026-09-09 on `claude/credit-risk-agents-spec-zttp6c`.

- `PYTHONPATH=src python3 -m quantsmith.pipelines.credit_risk_knowledge` ->
  `credit-risk validation OK (capabilities=8, concepts=53, conventions=13,
  decision_paths=7, draft=107, golden_cases=10, lifecycles=3, records=107,
  reviewed=0, workflows=6)`
- `PYTHONPATH=src pytest -q tests/test_credit_risk_knowledge.py` -> `49 passed`
- `PYTHONPATH=src pytest -q` -> `596 passed, 1 skipped` (was `547 passed, 1
  skipped` before this change; no existing test changed behaviour)
- `hooks/stages/run-stage.sh spec spec-index handoff-sync doc-counts docs-link
  source-catalog data-provenance secret-scan agent-catalog readme-sync` ->
  clean except one pre-existing `readme-sync` finding for spec `0066`, which
  reproduces on `main` and is not this change's
- `git diff --check` -> no whitespace errors

Two honest caveats:

- `pytest` and `numpy` were absent from this container and were installed to run
  the suite. The credit module itself imports neither: it is standard library
  only, and `python3 -m quantsmith.pipelines.credit_risk_knowledge` runs with no
  third-party dependency at all.
- AC-021's diff inspection is partly mechanical (`test_no_real_credit_data_is_
  committed_AC_021` scans committed JSON for personal-data keys) and partly
  human: the claim that no existing runtime's numerical output changed rests on
  this change adding only new files plus index and count edits, and on the full
  suite passing unchanged.

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
