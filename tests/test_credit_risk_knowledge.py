"""Acceptance tests for spec 0072 — credit risk domain foundation.

Each test names the acceptance criterion it proves. Where a criterion describes
a rejection, the test proves the invalid configuration actually fails; a test
that only shows the valid case passing would not prove the criterion.
"""

from __future__ import annotations

from pathlib import Path
import copy
import json

import pytest

from quantsmith.pipelines.credit_risk_knowledge import (
    CONSUMER_DECISION_OBLIGATIONS,
    FAIRNESS_TESTING_OBLIGATIONS,
    adverse_impact_ratio,
    REQUIRED_CAPABILITY_DOMAINS,
    REQUIRED_GOVERNANCE_ARTIFACTS,
    CreditRiskValidationError,
    adverse_action_reasons,
    admit_derived_evidence,
    is_deployable,
    load_domain_pack,
    normalize_alias,
    point_in_time_admission,
    records_available_as_of,
    run_golden_cases,
    transition_allowed,
    validate_domain_pack,
    validate_or_raise,
    _validate_decision_paths,
    _validate_common_records,
    _validate_conventions,
)


ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "knowledge" / "credit_risk"


def _pack():
    return load_domain_pack(ROOT)


# --- AC-001: capability map covers every required domain --------------------


def test_required_capability_domains_AC_001():
    caps = _pack()["coverage"]["capabilities"]
    covered = {c["domain"] for c in caps}
    assert REQUIRED_CAPABILITY_DOMAINS <= covered

    for cap in caps:
        assert cap["scope"]
        assert cap["coverage_level"]
        assert cap["current_artifacts"]
        assert cap["limitation"]
        assert cap["owning_spec"]


def test_coverage_level_claim_requires_a_runtime_AC_001():
    """A runtime claim without a runtime module must fail."""

    pack = _pack()
    cap = copy.deepcopy(pack["coverage"]["capabilities"][0])
    cap["coverage_level"] = "reference_runtime"
    assert not any(a.endswith(".py") for a in cap["current_artifacts"])

    errors: list[str] = []
    from quantsmith.pipelines.credit_risk_knowledge import _validate_coverage

    _validate_coverage({"capabilities": [cap]}, ROOT, errors)
    assert any("without a named runtime module" in e for e in errors)


# --- AC-002: taxonomy IDs, aliases, and non-interchangeable sets -------------


def test_taxonomy_ids_aliases_and_distinctions_AC_002():
    taxonomy = _pack()["taxonomy"]
    concepts = taxonomy["concepts"]
    ids = [c["id"] for c in concepts]
    assert len(ids) == len(set(ids))

    ambiguous = {normalize_alias(r["alias"]) for r in taxonomy["ambiguity_rules"]}
    owner: dict[str, str] = {}
    for concept in concepts:
        for alias in concept["aliases"]:
            key = normalize_alias(alias)
            if key in ambiguous:
                continue
            assert owner.get(key, concept["id"]) == concept["id"]
            owner[key] = concept["id"]

    by_id = {c["id"]: c for c in concepts}
    pairs = taxonomy["non_interchangeable_pairs"]
    assert pairs
    for left, right in pairs:
        assert left != right
        assert left in by_id and right in by_id
        left_aliases = {normalize_alias(a) for a in by_id[left]["aliases"]} - ambiguous
        right_aliases = {normalize_alias(a) for a in by_id[right]["aliases"]} - ambiguous
        assert not (left_aliases & right_aliases)


@pytest.mark.parametrize(
    "left,right",
    [
        ("measure.pd.one_year.ttc", "measure.pd.one_year.pit"),
        ("measure.pd.one_year.pit", "measure.pd.lifetime"),
        ("measure.ead", "measure.notional"),
        ("measure.ead", "measure.drawn_balance"),
        ("measure.lgd.expected", "measure.recovery_rate"),
        ("measure.charge_off", "measure.write_off"),
        ("measure.rating_grade", "measure.score"),
        ("defn.default.dpd_90", "defn.default.ifrs9_stage3"),
    ],
)
def test_named_pairs_stay_distinct_AC_002(left, right):
    pairs = {tuple(sorted(p)) for p in _pack()["taxonomy"]["non_interchangeable_pairs"]}
    assert tuple(sorted((left, right))) in pairs


def test_shared_alias_between_distinct_concepts_is_rejected_AC_002():
    from quantsmith.pipelines.credit_risk_knowledge import _validate_taxonomy

    taxonomy = copy.deepcopy(_pack()["taxonomy"])
    by_id = {c["id"]: c for c in taxonomy["concepts"]}
    by_id["measure.notional"]["aliases"].append("ead")

    errors: list[str] = []
    _validate_taxonomy(taxonomy, errors)
    assert any("share alias" in e or "also resolves to" in e for e in errors)


# --- AC-003: viewpoint and loss sign on every measure -----------------------


def test_measure_viewpoint_and_sign_required_AC_003():
    for conv in _pack()["conventions"]["conventions"]:
        assert conv["viewpoint_ids"], conv["id"]
        if conv["quantity"] in {"expected_loss", "expected_credit_loss", "loss_given_default"}:
            assert conv["loss_sign"] == "positive_is_loss_to_lender", conv["id"]


def test_loss_bearing_convention_without_sign_is_rejected_AC_003():
    pack = _pack()
    concept_ids = {c["id"] for c in pack["taxonomy"]["concepts"]}
    conv = copy.deepcopy(
        next(c for c in pack["conventions"]["conventions"] if c["quantity"] == "expected_loss")
    )
    conv["loss_sign"] = "not_applicable"

    errors: list[str] = []
    _validate_conventions({"conventions": [conv]}, concept_ids, errors)
    assert any("loss_sign" in e for e in errors)


# --- AC-004: convention completeness ----------------------------------------


def test_convention_records_are_complete_and_compatible_AC_004():
    pack = _pack()
    concept_ids = {c["id"] for c in pack["taxonomy"]["concepts"]}
    for conv in pack["conventions"]["conventions"]:
        assert conv["unit"] and conv["quantity"]
        assert conv["jurisdiction"] == "US"
        for vid in conv["viewpoint_ids"]:
            assert vid in concept_ids
        if conv["default_definition_id"] is not None:
            assert conv["default_definition_id"] in concept_ids
    assert pack["conventions"]["basis_compatibility_rules"]


# --- AC-005: lifecycle graphs ----------------------------------------------


def test_lifecycle_graphs_and_invalid_transition_AC_005():
    lifecycles = _pack()["lifecycles"]["lifecycles"]
    assert {g["id"] for g in lifecycles} == {
        "lifecycle.credit_exposure",
        "lifecycle.credit_approval_limit",
        "lifecycle.credit_model",
    }

    for graph in lifecycles:
        states = {s["id"] for s in graph["states"]}
        reachable = set(graph["initial_state_ids"])
        stack = list(reachable)
        while stack:
            current = stack.pop()
            for trans in graph["transitions"]:
                if trans["from"] == current and trans["to"] not in reachable:
                    reachable.add(trans["to"])
                    stack.append(trans["to"])
        assert reachable == states, graph["id"]
        assert graph["terminal_state_ids"]
        for trans in graph["transitions"]:
            assert trans["initiating_role_id"]
            assert trans["produces_artifact"]

    model = next(g for g in lifecycles if g["id"] == "lifecycle.credit_model")
    # Independent validation is structurally unavoidable.
    assert not transition_allowed(model, "model.in_development", "model.deployed")
    assert transition_allowed(model, "model.pending_validation", "model.approved")


def test_watch_list_is_not_a_default_state_AC_005():
    graph = next(
        g for g in _pack()["lifecycles"]["lifecycles"] if g["id"] == "lifecycle.credit_exposure"
    )
    watch = next(s for s in graph["states"] if s["id"] == "credit.watch")
    assert any("NOT a default" in inv for inv in watch["invariants"])


# --- AC-006 / AC-020: evidence and promotion gate ---------------------------


def test_reviewed_records_require_resolvable_evidence_AC_006():
    record = {
        "id": "test.reviewed", "record_type": "concept", "name": "t",
        "jurisdiction": "US", "knowledge_class": "stable_mechanic",
        "knowledge_as_of": "2026-09-09", "effective_from": None, "effective_to": None,
        "source_refs": [], "review_status": "reviewed",
        "review": {"reviewer": "a-handle", "review_date": "2026-09-09", "scope": "s"},
        "supersedes": [],
    }
    errors: list[str] = []
    _validate_common_records([record], {"cfpb"}, errors)
    assert any("must cite at least one source" in e for e in errors)


def test_review_promotion_rejects_missing_reviewer_or_high_gap_AC_020():
    base = {
        "id": "test.promote", "record_type": "concept", "name": "t",
        "jurisdiction": "US", "knowledge_class": "stable_mechanic",
        "knowledge_as_of": "2026-09-09", "effective_from": None, "effective_to": None,
        "source_refs": ["cfpb"], "review_status": "reviewed", "supersedes": [],
    }
    errors: list[str] = []
    _validate_common_records([dict(base, review=None)], {"cfpb"}, errors)
    assert any("requires a review object" in e for e in errors)

    errors = []
    _validate_common_records(
        [dict(base, review={"reviewer": "", "review_date": "2026-09-09", "scope": "s"})],
        {"cfpb"}, errors,
    )
    assert any("missing review.reviewer" in e for e in errors)

    errors = []
    _validate_common_records(
        [dict(base, review={"reviewer": "a@b.com", "review_date": "2026-09-09", "scope": "s"})],
        {"cfpb"}, errors,
    )
    assert any("handle, not an email" in e for e in errors)


def test_every_committed_record_is_still_draft_AC_020():
    """Honest state: no reviewer is named yet, so nothing may be reviewed."""

    report = validate_domain_pack(ROOT)
    assert report.counts["reviewed"] == 0
    assert report.counts["draft"] == report.counts["records"]


# --- AC-007: knowledge time precedes effective time -------------------------


def test_later_known_version_excluded_from_earlier_asof_AC_007():
    records = [
        {"id": "v1", "knowledge_as_of": "2024-01-01",
         "effective_from": "2024-01-01", "effective_to": "2026-01-01"},
        {"id": "v2", "knowledge_as_of": "2026-06-01",
         "effective_from": "2024-01-01", "effective_to": None},
    ]
    admitted = records_available_as_of(records, as_of="2025-01-01", effective_date="2025-06-01")
    # v2's effective interval covers the date, but it was not knowable in 2025.
    assert [r["id"] for r in admitted] == ["v1"]

    later = records_available_as_of(records, as_of="2026-09-09", effective_date="2026-06-01")
    assert [r["id"] for r in later] == ["v2"]


# --- AC-008: credit-specific leakage ----------------------------------------


def test_outcome_window_violation_rejected_AC_008():
    result = point_in_time_admission(
        decision_date="2024-01-15",
        feature_as_of="2024-06-30",
        label_outcome_window_end="2025-01-15",
        used_as="feature",
    )
    assert result["admitted"] is False
    # Every violated rule is reported, not just the first.
    assert result["violated_rules"] == [
        "rule.pit.attribute_as_of",
        "rule.pit.outcome_window_alignment",
    ]

    same_dates_as_label = point_in_time_admission(
        decision_date="2024-01-15",
        feature_as_of="2023-12-31",
        label_outcome_window_end="2025-01-15",
        used_as="label",
    )
    assert same_dates_as_label["admitted"] is True


def test_all_six_leakage_rules_are_declared_AC_008():
    rules = {r["id"] for r in _pack()["golden_cases"]["point_in_time_rules"]}
    assert rules == {
        "rule.pit.attribute_as_of",
        "rule.pit.outcome_window_alignment",
        "rule.pit.reject_inference",
        "rule.pit.scenario_vintage",
        "rule.pit.restatement_backfill",
        "rule.pit.survivorship",
    }


# --- AC-009: gap register ---------------------------------------------------


def test_gap_register_rows_have_evidence_and_owners_AC_009():
    import re

    text = (PACK / "gap_register.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| (G-0072-\d{3}) \|(.+)$", text, re.M)
    assert len(rows) >= 10
    for gap_id, rest in rows:
        cells = [c.strip() for c in rest.split("|")]
        gap, evidence, severity, _affected, disposition, owner = cells[:6]
        assert gap and evidence, gap_id
        assert severity.lower() in {"high", "medium", "low"}, gap_id
        assert disposition and owner, gap_id


def test_no_capability_claims_more_than_contract_only_AC_009():
    """Nothing is implemented yet; the coverage matrix must say so."""

    for cap in _pack()["coverage"]["capabilities"]:
        assert cap["coverage_level"] in {"absent", "prose_only", "contract_only"}


# --- AC-010: golden cases ---------------------------------------------------


def test_golden_cases_are_complete_and_repeatable_AC_010():
    first = run_golden_cases(ROOT)
    second = run_golden_cases(ROOT)
    assert first == second

    expected_ids = {
        "golden.el.pd_lgd_ead",
        "golden.el.basis_mismatch_rejected",
        "golden.ead.ccf_undrawn",
        "golden.ecl.twelve_month_vs_lifetime",
        "golden.rwa.irb_risk_weight",
        "golden.score.points_to_odds",
        "golden.adverse_action.reason_ranking",
        "golden.migration.row_stochastic",
        "golden.temporal.outcome_window_rejected",
        "golden.temporal.admitted",
    }
    assert expected_ids <= set(first)


def test_expected_loss_and_ead_identities_AC_010():
    results = run_golden_cases(ROOT)
    assert results["golden.el.pd_lgd_ead"]["expected_loss"] == pytest.approx(9000.0)
    assert results["golden.ead.ccf_undrawn"]["ead"] == pytest.approx(700000.0)
    assert results["golden.rwa.irb_risk_weight"]["rwa"] == pytest.approx(595000.0)


def test_twelve_month_ecl_is_a_slice_of_lifetime_AC_010():
    ecl = run_golden_cases(ROOT)["golden.ecl.twelve_month_vs_lifetime"]
    assert ecl["twelve_month_ecl"] < ecl["lifetime_ecl"]


def test_migration_matrix_rows_sum_to_one_AC_010():
    result = run_golden_cases(ROOT)["golden.migration.row_stochastic"]
    assert result["rows_stochastic"] is True
    for total in result["row_sums"]:
        assert total == pytest.approx(1.0, abs=1e-12)


def test_basis_mismatch_is_rejected_not_computed_AC_010():
    result = run_golden_cases(ROOT)["golden.el.basis_mismatch_rejected"]
    assert result["admitted"] is False
    assert result["violated_rules"] == ["rule.basis.el_operands"]


# --- AC-011: agent charter gating -------------------------------------------


def test_agent_charter_requires_coverage_row_AC_011():
    workflows = _pack()["workflows"]["workflows"]
    owning_specs = {c["owning_spec"] for c in _pack()["coverage"]["capabilities"]}
    future = [
        agent
        for flow in workflows
        for agent in flow["participating_agents"]
        if agent["status"] == "future"
    ]
    assert future
    for agent in future:
        assert agent["owning_spec"] in owning_specs, agent


def test_no_credit_agent_exists_yet_AC_011():
    """The charter gates creation: no agent ships ahead of its coverage row."""

    assert not (ROOT / "agents" / "credit_risk").exists()


# --- AC-012 / AC-013: workflows and runtime boundary ------------------------


def test_workflow_contracts_are_complete_AC_012():
    pack = _pack()
    path_ids = {p["id"] for p in pack["decision_paths"]["decision_paths"]}
    pillars = set()
    for flow in pack["workflows"]["workflows"]:
        for field in ("stages", "required_inputs", "produced_artifacts", "gates",
                      "human_decision_points", "participating_agents"):
            assert flow[field], (flow["id"], field)
        assert flow["decision_path_id"] in path_ids
        pillars.add(flow["pillar"])
    assert len(pack["workflows"]["workflows"]) == 6
    assert pillars == {
        "wholesale_counterparty_credit",
        "retail_underwriting",
        "accounting_regulatory_capital",
        "credit_document_intelligence",
    }


def test_runtime_boundary_has_no_hardcoded_policy_constants_AC_013():
    pack = _pack()
    levels = set(pack["workflows"]["runtime_boundary_levels"])
    for flow in pack["workflows"]["workflows"]:
        assert flow["runtime_boundary"] in levels

    required = [
        (conv["id"], param)
        for conv in pack["conventions"]["conventions"]
        for param in conv["parameters"]
        if param["required"]
    ]
    assert required, "policy-specific values must be parameterized, not absent"
    for conv_id, param in required:
        assert param["default"] is None, (conv_id, param["id"])
        assert param["rationale"]


def test_required_parameter_with_a_default_is_rejected_AC_013():
    pack = _pack()
    concept_ids = {c["id"] for c in pack["taxonomy"]["concepts"]}
    conv = copy.deepcopy(
        next(c for c in pack["conventions"]["conventions"] if c["parameters"])
    )
    conv["parameters"][0]["default"] = 0.5

    errors: list[str] = []
    _validate_conventions({"conventions": [conv]}, concept_ids, errors)
    assert any("carries a default" in e for e in errors)


# --- AC-014: the decision contract ------------------------------------------


def test_consumer_decision_path_obligations_AC_014():
    paths = _pack()["decision_paths"]["decision_paths"]
    consumer = [p for p in paths if p["consumer_decision"]]
    assert consumer

    for path in consumer:
        if path["sole_basis_adverse_action_permitted"]:
            for field in CONSUMER_DECISION_OBLIGATIONS:
                assert path[field], (path["id"], field)
            assert path["reason_codes"]["derivable"] is True
            assert path["reason_codes"]["excludes_protected_attributes"] is True
            assert path["protected_attributes_in_features"] == []

    support_only = [p for p in paths if not p["sole_basis_adverse_action_permitted"]]
    assert any(p["id"] == "path.credit_document_intelligence" for p in support_only)


def test_unsafe_consumer_path_is_unrepresentable_AC_014():
    """The load-bearing negative case: obligations unmet AND sole basis permitted."""

    path = copy.deepcopy(
        next(
            p for p in _pack()["decision_paths"]["decision_paths"]
            if p["id"] == "path.retail_underwriting_decision"
        )
    )
    path["disparate_impact_hook"] = None

    errors: list[str] = []
    _validate_decision_paths({"decision_paths": [path]}, errors)
    assert any("sole-basis adverse action" in e for e in errors)

    # Restating it as decision-support-only is the valid alternative.
    path["sole_basis_adverse_action_permitted"] = False
    errors = []
    _validate_decision_paths({"decision_paths": [path]}, errors)
    assert not errors


def test_protected_attribute_in_features_is_rejected_AC_014():
    path = copy.deepcopy(
        next(
            p for p in _pack()["decision_paths"]["decision_paths"]
            if p["id"] == "path.retail_underwriting_decision"
        )
    )
    path["protected_attributes_in_features"] = ["attr.age"]

    errors: list[str] = []
    _validate_decision_paths(
        {"decision_paths": [path],
         "protected_attribute_registry": {"attribute_ids": ["attr.age"]}},
        errors,
    )
    assert any("protected attribute" in e for e in errors)


# --- AC-015: deterministic adverse action reasons ---------------------------


def test_adverse_action_reasons_are_deterministic_and_clean_AC_015():
    args = dict(
        feature_points={"income": 40.0, "utilization": 20.0,
                        "delinquency": 10.0, "inquiries": 25.0},
        max_attainable_points={"income": 100.0, "utilization": 80.0,
                               "delinquency": 60.0, "inquiries": 30.0},
        stable_feature_order=["utilization", "income", "delinquency", "inquiries"],
        max_reasons=3,
    )
    first = adverse_action_reasons(**args)
    second = adverse_action_reasons(**args)
    assert first == second

    # income and utilization both lose 60 points; the declared order breaks it.
    assert first["points_lost"]["income"] == first["points_lost"]["utilization"] == 60.0
    assert first["ordered_reason_codes"] == [
        "reason.utilization", "reason.income", "reason.delinquency",
    ]

    # Reordering the dict must not change the disclosed reasons.
    reordered = dict(args)
    reordered["feature_points"] = {
        "inquiries": 25.0, "delinquency": 10.0, "income": 40.0, "utilization": 20.0,
    }
    assert adverse_action_reasons(**reordered) == first


def test_protected_attribute_cannot_become_a_reason_AC_015():
    with pytest.raises(CreditRiskValidationError, match="protected attribute"):
        adverse_action_reasons(
            feature_points={"income": 40.0, "attr.age": 10.0},
            max_attainable_points={"income": 100.0, "attr.age": 50.0},
            stable_feature_order=["income", "attr.age"],
            max_reasons=2,
            protected_attributes=["attr.age"],
        )


def test_unordered_feature_is_rejected_AC_015():
    with pytest.raises(CreditRiskValidationError, match="non-deterministic"):
        adverse_action_reasons(
            feature_points={"income": 40.0, "surprise": 5.0},
            max_attainable_points={"income": 100.0, "surprise": 10.0},
            stable_feature_order=["income"],
            max_reasons=2,
        )


# --- AC-016: deployability is computed --------------------------------------


def test_deployability_requires_governance_artifacts_AC_016():
    pack = _pack()
    governance, paths = pack["governance"], pack["decision_paths"]

    complete = {
        "governance_evidence": [{"artifact_id": a} for a in REQUIRED_GOVERNANCE_ARTIFACTS],
        "decision_path_id": "path.retail_underwriting_decision",
    }
    assert is_deployable(complete, governance, paths) is True

    for missing in sorted(REQUIRED_GOVERNANCE_ARTIFACTS):
        partial = {
            "governance_evidence": [
                {"artifact_id": a} for a in REQUIRED_GOVERNANCE_ARTIFACTS if a != missing
            ],
            "decision_path_id": "path.retail_underwriting_decision",
        }
        assert is_deployable(partial, governance, paths) is False, missing

    blocked = dict(complete, open_high_gap_ids=["G-0072-005"])
    assert is_deployable(blocked, governance, paths, open_high_gap_ids=["G-0072-005"]) is False


def test_there_is_no_deployable_field_to_set_AC_016():
    raw = json.loads((PACK / "coverage.json").read_text(encoding="utf-8"))
    for cap in raw["capabilities"]:
        assert "deployable" not in cap
    predicate = _pack()["governance"]["deployability_predicate"]
    assert predicate["computed_not_asserted"] is True


# --- AC-017: LLM evidence admission -----------------------------------------


def test_llm_derived_input_admission_AC_017():
    governance = _pack()["governance"]
    complete = {
        "artifact_ref": "0071:artifact:1",
        "source_spans": [{"doc": "d", "start": 0, "end": 10}],
        "envelope_ref": "0070:envelope:1",
        "prompt_context_manifest": "manifest:1",
        "assumption_ledger_entry": "assumption:1",
        "replay_ref": "replay:1",
    }
    admitted = admit_derived_evidence(complete, governance)
    assert admitted["admitted"] is True
    # Without named human review it is evidence, never a decision input.
    assert admitted["evidence_class"] == "derived_evidence"

    promoted = admit_derived_evidence(
        dict(complete, review={"reviewer": "a-handle", "review_date": "2026-09-09",
                               "scope": "covenant extraction"}),
        governance,
    )
    assert promoted["evidence_class"] == "decision_input"

    for field in complete:
        incomplete = {k: v for k, v in complete.items() if k != field}
        result = admit_derived_evidence(incomplete, governance)
        assert result["admitted"] is False, field
        assert field in result["missing"]


def test_automated_promotion_is_prohibited_AC_017():
    admission = _pack()["governance"]["evidence_admission"]
    assert admission["automated_promotion_permitted"] is False
    assert admission["initial_evidence_class"] == "derived_evidence"
    assert "named human reviewer" in admission["promotion_requires"]


# --- AC-018 / AC-019: discoverability ---------------------------------------


def test_handoff_reserves_child_specs_and_next_number_AC_018():
    handoff = (ROOT / "docs" / "handoff.md").read_text(encoding="utf-8")
    for spec in ("0073", "0074", "0075", "0076", "0077", "0078", "0079"):
        assert f"`{spec}`" in handoff
    assert "Next unreserved spec number: `0080`" in handoff

    index = (ROOT / "specs" / "README.md").read_text(encoding="utf-8")
    assert "0072-credit-risk-domain-foundation" in index
    assert "Next unreserved spec number: `0080`" in index


def test_instructions_and_agents_cite_canonical_pack_AC_019():
    instructions = ROOT / "instructions" / "credit_risk.md"
    assert instructions.exists()
    text = instructions.read_text(encoding="utf-8")
    assert "knowledge/credit_risk" in text
    assert "0072" in text


# --- AC-023 / AC-024: substantive fairness testing --------------------------


def test_consumer_paths_declare_substantive_fairness_testing_AC_023():
    for path in _pack()["decision_paths"]["decision_paths"]:
        fairness = path["fairness_testing"]
        if not path["consumer_decision"]:
            assert fairness is None, path["id"]
            continue
        for field in FAIRNESS_TESTING_OBLIGATIONS:
            assert fairness[field], (path["id"], field)
        assert fairness["measured_at_applied_cutoff"] is True
        assert fairness["versioned_with_model"] is True
        lda = fairness["less_discriminatory_alternative"]
        assert lda["required_when"] == "disparity_threshold_breached"
        assert set(lda["outcome_required"]) == {
            "alternative_adopted", "business_need_rationale",
        }


@pytest.mark.parametrize("missing", FAIRNESS_TESTING_OBLIGATIONS)
def test_missing_fairness_obligation_blocks_sole_basis_AC_023(missing):
    """Each obligation is load-bearing: dropping any one must be rejected."""

    path = copy.deepcopy(
        next(
            p for p in _pack()["decision_paths"]["decision_paths"]
            if p["id"] == "path.retail_underwriting_decision"
        )
    )
    path["fairness_testing"][missing] = None

    errors: list[str] = []
    _validate_decision_paths({"decision_paths": [path]}, errors)
    assert any("sole-basis adverse action" in e for e in errors), missing

    # decision_support_only remains the valid restatement.
    path["sole_basis_adverse_action_permitted"] = False
    errors = []
    _validate_decision_paths({"decision_paths": [path]}, errors)
    assert not errors


def test_attribute_absence_alone_is_not_enough_AC_023():
    """The gap this amendment closes: an empty feature list must not suffice."""

    path = copy.deepcopy(
        next(
            p for p in _pack()["decision_paths"]["decision_paths"]
            if p["id"] == "path.retail_underwriting_decision"
        )
    )
    # Procedurally perfect and no protected attribute in features...
    assert path["protected_attributes_in_features"] == []
    for field in CONSUMER_DECISION_OBLIGATIONS:
        assert path[field]
    # ...but with no substantive fairness testing it is still rejected.
    path["fairness_testing"] = None

    errors: list[str] = []
    _validate_decision_paths({"decision_paths": [path]}, errors)
    assert any("fairness_testing" in e for e in errors)


def test_protected_class_estimate_cannot_be_a_feature_AC_024():
    path = copy.deepcopy(
        next(
            p for p in _pack()["decision_paths"]["decision_paths"]
            if p["id"] == "path.retail_underwriting_decision"
        )
    )
    path["fairness_testing"]["estimation_use"] = "feature_and_testing"

    errors: list[str] = []
    _validate_decision_paths({"decision_paths": [path]}, errors)
    assert any("testing only" in e for e in errors)


def test_disparity_breach_requires_an_lda_record_AC_024():
    breach = adverse_impact_ratio(
        approved_protected=180, total_protected=500,
        approved_reference=600, total_reference=1000,
        disparity_threshold=0.8,
    )
    assert breach["selection_rate_protected"] == pytest.approx(0.36)
    assert breach["selection_rate_reference"] == pytest.approx(0.60)
    assert breach["adverse_impact_ratio"] == pytest.approx(0.6)
    assert breach["threshold_breached"] is True
    assert breach["less_discriminatory_alternative_required"] is True

    clear = adverse_impact_ratio(
        approved_protected=290, total_protected=500,
        approved_reference=600, total_reference=1000,
        disparity_threshold=0.8,
    )
    assert clear["threshold_breached"] is False
    assert clear["less_discriminatory_alternative_required"] is False


def test_disparity_threshold_is_supplied_not_builtin_AC_024():
    """The four-fifths ratio is a screening convention, not a constant we own."""

    args = dict(approved_protected=180, total_protected=500,
                approved_reference=600, total_reference=1000)
    assert adverse_impact_ratio(disparity_threshold=0.8, **args)["threshold_breached"] is True
    assert adverse_impact_ratio(disparity_threshold=0.5, **args)["threshold_breached"] is False

    params = {
        p["id"]: p
        for conv in _pack()["conventions"]["conventions"]
        for p in conv["parameters"]
    }
    for pid in ("param.fairness.disparity_threshold",
                "param.fairness.protected_class_estimation_method"):
        assert params[pid]["required"] is True
        assert params[pid]["default"] is None


def test_deployability_requires_fairness_testing_AC_024():
    pack = _pack()
    governance, paths = pack["governance"], pack["decision_paths"]
    entry = {
        "governance_evidence": [{"artifact_id": a} for a in REQUIRED_GOVERNANCE_ARTIFACTS],
        "decision_path_id": "path.retail_underwriting_decision",
    }
    assert is_deployable(entry, governance, paths) is True

    stripped = copy.deepcopy(paths)
    for path in stripped["decision_paths"]:
        if path["id"] == "path.retail_underwriting_decision":
            path["fairness_testing"] = None
    assert is_deployable(entry, governance, stripped) is False


# --- AC-021 / AC-022: fixtures and a clean offline run ----------------------


def test_no_real_credit_data_is_committed_AC_021():
    """Every committed value is synthetic; the pack stores no credit data."""

    for path in sorted(PACK.glob("*.json")):
        raw = path.read_text(encoding="utf-8")
        # Locator-only sourcing: no bureau/vendor payloads, no personal data keys.
        for forbidden in ("ssn", "social_security", "date_of_birth", "account_number",
                          "customer_name", "bureau_score_raw"):
            assert forbidden not in raw.lower(), (path.name, forbidden)


def test_pack_validates_offline_AC_022():
    report = validate_or_raise(ROOT)
    assert report.ok
    assert report.counts["records"] > 0
