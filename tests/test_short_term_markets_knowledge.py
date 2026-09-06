"""Acceptance tests for spec 0063 — short-term markets domain foundation."""

from __future__ import annotations

from pathlib import Path
import re

import pytest

from quantsmith.pipelines.short_term_markets_knowledge import (
    REQUIRED_CAPABILITY_DOMAINS,
    REQUIRED_DISCREPANCY_IDS,
    load_domain_pack,
    normalize_alias,
    records_available_as_of,
    run_golden_cases,
    validate_domain_pack,
    validate_or_raise,
    validate_review_envelope,
)


ROOT = Path(__file__).resolve().parents[1]


def _pack():
    return load_domain_pack(ROOT)


# --- AC-001: required capability domains exist with owners and limitations ---


def test_required_capability_domains_AC_001():
    pack = _pack()
    capabilities = pack["coverage"]["capabilities"]
    by_domain = {}
    for capability in capabilities:
        by_domain.setdefault(capability["capability_domain"], []).append(capability)

    assert REQUIRED_CAPABILITY_DOMAINS <= set(by_domain)
    for domain in REQUIRED_CAPABILITY_DOMAINS:
        assert by_domain[domain], domain
        for capability in by_domain[domain]:
            assert capability["coverage_level"] in {
                "absent",
                "prose_only",
                "contract_only",
                "reference_runtime",
                "validated_runtime",
            }
            assert capability["artifact_paths"]
            assert capability["limitations"]
            assert capability["owner_spec"]


# --- AC-002: taxonomy IDs, aliases, and required distinctions are deterministic ---


def test_taxonomy_ids_aliases_and_distinctions_AC_002():
    pack = _pack()
    taxonomy = pack["taxonomy"]
    concepts = taxonomy["concepts"]
    concept_ids = [concept["id"] for concept in concepts]
    preferred_names = [concept["name"] for concept in concepts]

    assert len(concept_ids) == len(set(concept_ids))
    assert len(preferred_names) == len(set(preferred_names))

    non_interchangeable = {tuple(pair) for pair in taxonomy["non_interchangeable_pairs"]}
    for required_pair in {
        ("product.repo", "product.reverse_repo"),
        ("concept.general_collateral", "concept.repo_special"),
        ("concept.borrow_fee", "concept.rebate_rate"),
        ("concept.haircut", "concept.margin_amount"),
        ("concept.price", "concept.rate"),
        ("concept.price", "concept.yield"),
        ("concept.rate", "concept.yield"),
    }:
        assert required_pair in non_interchangeable

    special_rules = [
        rule
        for rule in taxonomy["ambiguity_rules"]
        if normalize_alias(rule["alias"]) == normalize_alias("special")
    ]
    assert special_rules
    assert set(special_rules[0]["allowed_concept_ids"]) == {
        "concept.repo_special",
        "concept.stock_loan_special",
    }
    validate_or_raise(ROOT)


# --- AC-003: repo specialness viewpoint and sign ---


def test_repo_specialness_viewpoint_and_sign_AC_003():
    pack = _pack()
    case = next(
        case
        for case in pack["golden_cases"]["golden_cases"]
        if case["case_id"] == "golden.repo.specialness_sign"
    )
    convention = next(
        item
        for item in pack["conventions"]["conventions"]
        if item["id"] == "convention.repo.specialness_bps"
    )

    assert run_golden_cases(ROOT)["golden.repo.specialness_sign"] == pytest.approx(35.0)
    assert case["viewpoint_ids"] == ["role.repo_cash_provider", "role.repo_cash_taker"]
    assert "GC repo rate - specific collateral repo rate" in convention["sign_convention"]["positive"]
    assert "Stock-loan" in case["invariants"][2]


# --- AC-004: convention records are complete and compatible ---


def test_convention_records_are_complete_and_compatible_AC_004():
    pack = _pack()
    required_fields = {
        "quantity",
        "quote_style",
        "unit",
        "day_count",
        "compounding",
        "calendar",
        "business_day_adjustment",
        "settlement",
        "rounding",
        "viewpoint_ids",
        "formula",
    }
    for convention in pack["conventions"]["conventions"]:
        assert required_fields <= set(convention), convention["id"]
        assert convention["viewpoint_ids"], convention["id"]
        assert convention["formula"]["id"], convention["id"]
    validate_or_raise(ROOT)


# --- AC-005: lifecycle graphs and invalid transition rejection ---


def test_lifecycle_graphs_and_invalid_transition_AC_005():
    results = run_golden_cases(ROOT)
    assert results["golden.lifecycle.repo_valid_transition"] is True
    assert results["golden.lifecycle.repo_invalid_transition"] is False

    report = validate_domain_pack(ROOT)
    assert report.ok, report.errors
    assert report.counts["lifecycles"] == 4


# --- AC-006: reviewed records require resolvable evidence ---


def test_reviewed_records_require_resolvable_evidence_AC_006():
    report = validate_domain_pack(ROOT)
    assert report.ok, report.errors
    assert report.counts["reviewed"] == 0

    candidate = {
        "id": "concept.invalid_review",
        "review_status": "reviewed",
        "review": None,
    }
    errors = validate_review_envelope(candidate)
    assert errors
    assert "requires review object" in errors[0]


# --- AC-007: later-known records are excluded from earlier as-of queries ---


def test_later_known_version_excluded_from_earlier_asof_AC_007():
    records = [
        {
            "id": "observation.v1",
            "knowledge_as_of": "2026-01-02",
            "effective_from": "2026-01-01",
            "effective_to": "2026-04-01",
        },
        {
            "id": "observation.revision",
            "knowledge_as_of": "2026-03-01",
            "effective_from": "2026-01-01",
            "effective_to": "2026-04-01",
        },
    ]
    admitted = records_available_as_of(
        records,
        as_of="2026-02-15",
        effective_date="2026-02-15",
    )
    assert [record["id"] for record in admitted] == ["observation.v1"]
    assert run_golden_cases(ROOT)["golden.temporal.asof_excludes_later_known_rate"] == {
        "included_record_ids": ["observation.gc_repo_rate_v1"],
        "excluded_record_ids": ["observation.gc_repo_rate_revision"],
    }


# --- AC-008: required discrepancies have evidence and owner specs ---


def test_required_discrepancies_have_evidence_and_owners_AC_008():
    text = (ROOT / "knowledge/short_term_markets/gap_register.md").read_text(
        encoding="utf-8"
    )
    for discrepancy_id in REQUIRED_DISCREPANCY_IDS:
        assert discrepancy_id in text
    for required in ("Evidence", "Severity", "Disposition", "Owning spec"):
        assert required in text
    assert "src/quantsmith/quant/agentic_quant/sec_lending.py:103" in text
    assert "src/quantsmith/pipelines/financing_cost_analysis.py:235" in text


# --- AC-009: golden cases are complete and repeatable ---


def test_golden_cases_are_complete_and_repeatable_AC_009():
    first = run_golden_cases(ROOT)
    second = run_golden_cases(ROOT)

    assert first == second
    assert {
        "golden.repo.specialness_sign",
        "golden.seclend.fee_rebate_signs",
        "golden.cash.tbill_discount_yield_price",
        "golden.money_market.act360_accrual",
        "golden.collateral.haircut_amount",
        "golden.lifecycle.repo_valid_transition",
        "golden.lifecycle.repo_invalid_transition",
        "golden.temporal.asof_excludes_later_known_rate",
    } <= set(first)


# --- AC-010: classification thresholds are sourced or parameterized ---


def test_classification_thresholds_are_sourced_or_parameterized_AC_010():
    pack = _pack()
    thresholds = []
    for convention in pack["conventions"]["conventions"]:
        thresholds.extend(
            (convention["id"], threshold)
            for threshold in convention.get("thresholds", [])
        )
    assert thresholds
    for convention_id, threshold in thresholds:
        assert threshold["basis"] in {"parameterized_model_assumption", "sourced_rule"}
        if threshold["basis"] == "parameterized_model_assumption":
            convention = next(
                item
                for item in pack["conventions"]["conventions"]
                if item["id"] == convention_id
            )
            assert convention["knowledge_class"] == "model_assumption"
            assert threshold["artifact_path"].startswith(
                "src/quantsmith/quant/agentic_quant/sec_lending.py:"
            )


# --- AC-011: handoff reserves child specs without activating them ---


def test_handoff_reserves_child_specs_and_next_number_AC_011():
    handoff = (ROOT / "docs/handoff.md").read_text(encoding="utf-8")
    for spec_id in ("0064", "0065", "0066", "0067", "0068", "0069"):
        assert f"`{spec_id}`" in handoff
        assert not (ROOT / f"specs/{spec_id}").exists()
    assert "Do not draft all six child specs at once" in handoff
    next_spec = re.search(r"Next unreserved spec number: `(\d{4})`", handoff)
    assert next_spec is not None
    assert int(next_spec.group(1)) > 69
    assert not any((ROOT / "specs").glob(f"{next_spec.group(1)}-*"))


# --- AC-012: relevant agents reference the canonical foundation ---


def test_relevant_agents_reference_canonical_foundation_AC_012():
    paths = [
        "instructions/securities_financing.md",
        "instructions/asset_class_mechanics.md",
        "agents/securities_financing/README.md",
        "agents/securities_financing/securities_lending/instructions.md",
        "agents/securities_financing/repo_financing/instructions.md",
        "agents/securities_financing/collateral_management/instructions.md",
        "agents/securities_financing/financing_cost_analysis/instructions.md",
        "agents/asset_classes/fixed_income_rates/instructions.md",
    ]
    for path in paths:
        text = (ROOT / path).read_text(encoding="utf-8")
        assert "knowledge/short_term_markets/" in text, path
        assert "instructions/short_term_markets.md" in text, path


# --- AC-014: review promotion rejects missing reviewer or high gaps ---


def test_review_promotion_rejects_missing_reviewer_or_high_gap_AC_014():
    no_reviewer = {
        "id": "golden.invalid.no_reviewer",
        "review_status": "reviewed",
        "review": {
            "reviewer": "",
            "review_date": "2026-09-05",
            "scope": "test",
            "evidence_refs": ["source.ny_fed"],
        },
    }
    blocked_by_gap = {
        "id": "golden.invalid.high_gap",
        "review_status": "reviewed",
        "review": {
            "reviewer": "reviewer-handle",
            "review_date": "2026-09-05",
            "scope": "test",
            "evidence_refs": ["source.ny_fed"],
            "blocks_high_severity_discrepancy": True,
        },
    }

    assert any("reviewer" in error for error in validate_review_envelope(no_reviewer))
    assert any(
        "severity-high discrepancy" in error
        for error in validate_review_envelope(blocked_by_gap)
    )


# --- AC-015: clean offline domain validation ---


def test_domain_pack_validates_offline_AC_015():
    report = validate_domain_pack(ROOT)
    assert report.ok, report.errors
    assert report.counts["records"] > 0
    assert report.counts["draft"] == report.counts["records"]
