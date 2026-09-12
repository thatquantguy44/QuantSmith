"""Acceptance tests for spec 0077 — credit document intelligence.

These tests exercise real, emitted artifacts rather than hand-typed fixtures:
the bundle is produced by the actual 0071 producer, validated by 0071's own
validators, and bridged into 0072's admission gate through this module's real
functions. Where `tests/test_credit_risk_knowledge.py` proves the admission
contract's shape with illustrative dicts, this module proves the same
contract holds when real artifacts flow through it.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from quantsmith.orchestration import load_json, replay_envelope_file
from quantsmith.text_intelligence import (
    TextDocumentInput,
    replay_text_intelligence_manifest_file,
    validate_text_intelligence_manifest_file,
)
from quantsmith.pipelines.credit_document_intelligence import (
    CreditDocumentIntelligenceError,
    admission_input_from_bundle,
    admit_bundle_result,
    emit_credit_document_evidence,
    generate_credit_document_examples,
    review_from_task_result,
)
from quantsmith.pipelines.credit_risk_knowledge import admit_derived_evidence


ROOT = Path(__file__).resolve().parents[1]
COMMITTED = ROOT / "examples" / "credit_document_intelligence"


@pytest.fixture()
def governance():
    return load_json(ROOT / "knowledge" / "credit_risk" / "governance.json")


@pytest.fixture()
def fresh_bundle(tmp_path_factory):
    """A freshly regenerated bundle, written under the repo root.

    0071's source-registration check walks up from the OUTPUT path looking
    for sources/ + pyproject.toml, so the bundle must be generated under the
    checkout, not a bare OS temp directory.
    """

    out_root = ROOT / "examples" / f".pytest_scratch_{tmp_path_factory.mktemp('x').name}"
    out_root.mkdir(parents=True, exist_ok=True)
    try:
        bundle = generate_credit_document_examples(out_root)
        yield bundle
    finally:
        shutil.rmtree(out_root, ignore_errors=True)


# --- the committed example is real, validated 0071/0070 evidence -----------


def test_committed_example_exists_and_validates():
    manifest = COMMITTED / "text_intelligence_manifest.json"
    assert manifest.exists()
    report = validate_text_intelligence_manifest_file(manifest)
    assert report.ok, report.findings


def test_committed_example_cites_the_credit_document_source():
    corpus = load_json(COMMITTED / "corpus_snapshot.json")
    source_ids = {doc["source_id"] for doc in corpus["documents"]}
    assert source_ids == {"credit_document_fixture"}


def test_documents_must_cite_the_credit_document_source():
    """A caller reusing 0071's generic fixture source is rejected, not silently accepted."""

    with pytest.raises(CreditDocumentIntelligenceError, match="credit_document_fixture"):
        emit_credit_document_evidence(
            (
                TextDocumentInput(
                    document_id="wrong-source",
                    text="test",
                    source_id="text_intelligence_fixture",
                    publication_time="2026-09-08T09:00:00Z",
                    observation_time="2026-09-08T09:00:05Z",
                    ingestion_time="2026-09-08T09:01:00Z",
                ),
            ),
            ROOT / "examples" / ".unused",
        )


# --- classification is text-dependent; the rest is disclosed fixture -------


def test_classification_is_computed_from_document_text():
    """The one output that genuinely reflects this corpus's content."""

    results = load_json(COMMITTED / "task_results.json")["results"]
    classification = next(r for r in results if r["task_type"] == "classification")
    # The documents say "declined" leverage / "improved" EBITDA / "stable"
    # headroom — the lexical check reads any of those as improving.
    assert classification["output"]["label"] == "improving"


def test_other_outputs_are_disclosed_fixture_content_not_extraction():
    """The gap this module is honest about: entity/value/stance/theme are
    the underlying 0071 producer's fixed stubs, unchanged, regardless of
    what this corpus's documents actually say. Asserting the exact stub
    content pins that fact so a future change to 0071's fixture would be
    caught here rather than silently reframed as "credit extraction"."""

    results = load_json(COMMITTED / "task_results.json")["results"]
    by_type = {r["task_type"]: r["output"] for r in results}
    assert by_type["entity_extraction"]["entities"][0]["surface"] == "Issuer Alpha"
    assert by_type["value_extraction"]["values"][0]["name"] == "funding_cost_change"
    for result in results:
        assert "reference fixture" in result["uncertainty"].casefold() \
            or "not production-calibrated" in result["uncertainty"].casefold()


# --- the review field-name adapter -----------------------------------------


def test_review_adapter_maps_0071_fields_to_0072_fields():
    """0071: reviewer/reviewed_at/owner/uncertainty. 0072: reviewer/review_date/scope.
    Neither is wrong; this is the seam between two independently-designed
    review objects, made explicit rather than silently coerced."""

    review_0071 = {
        "status": "fixture_approved",
        "owner": "spec0071",
        "reviewer": "text-intelligence-fixture",
        "reviewed_at": "2026-09-07T12:00:11Z",
        "uncertainty": "Synthetic fixture demonstrates contracts only.",
        "overrides": [],
        "rejected_alternatives": [],
        "escalation_conditions": ["any production use"],
    }
    adapted = review_from_task_result(review_0071)
    assert adapted["reviewer"] == "text-intelligence-fixture"
    assert adapted["review_date"] == "2026-09-07"
    assert adapted["scope"] == "spec0071: Synthetic fixture demonstrates contracts only."


def test_adapted_review_satisfies_0072s_promotion_gate(governance):
    review_0071 = {
        "owner": "spec0071", "reviewer": "someone", "reviewed_at": "2026-09-07T12:00:11Z",
        "uncertainty": "test",
    }
    adapted = review_from_task_result(review_0071)
    for field in ("reviewer", "review_date", "scope"):
        assert adapted[field]


# --- the admission gate, exercised against a real emitted bundle -----------


def test_admission_input_resolves_real_spans_from_the_real_corpus():
    admission_input = admission_input_from_bundle(COMMITTED, include_review=False)
    assert admission_input["source_spans"]
    for span in admission_input["source_spans"]:
        assert {"span_id", "document_id", "start", "end"} <= span.keys()
        assert span["end"] > span["start"]


def test_reviewed_result_is_admitted_as_decision_input(governance):
    admitted = admit_bundle_result(COMMITTED, governance, include_review=True)
    assert admitted == {"admitted": True, "evidence_class": "decision_input", "missing": []}


def test_unreviewed_result_is_admitted_only_as_derived_evidence(governance):
    admitted = admit_bundle_result(COMMITTED, governance, include_review=False)
    assert admitted == {"admitted": True, "evidence_class": "derived_evidence", "missing": []}


def test_missing_envelope_ref_is_rejected_against_real_data(governance):
    admission_input = admission_input_from_bundle(COMMITTED, include_review=True)
    del admission_input["envelope_ref"]
    result = admit_derived_evidence(admission_input, governance)
    assert result == {"admitted": False, "evidence_class": None, "missing": ["envelope_ref"]}


def test_unresolvable_span_id_is_rejected():
    from quantsmith.pipelines.credit_document_intelligence import _resolve_source_spans

    corpus = load_json(COMMITTED / "corpus_snapshot.json")
    with pytest.raises(Exception, match="does not resolve"):
        _resolve_source_spans(corpus, ["span-does-not-exist"])


# --- replay is deterministic, against a freshly regenerated bundle ---------


def test_replay_is_deterministic_on_regeneration(fresh_bundle):
    first = replay_text_intelligence_manifest_file(fresh_bundle)
    second = replay_text_intelligence_manifest_file(fresh_bundle)
    assert first == second
    assert first.orchestration.status == "replayed"
    assert first.orchestration.replay_mode == "deterministic"


def test_regenerated_bundle_matches_committed_hash():
    """The committed example is exactly what generate_credit_document_examples
    produces today — not a stale snapshot from an earlier version of 0071."""

    committed_manifest = load_json(COMMITTED / "text_intelligence_manifest.json")

    out_root = ROOT / "examples" / ".pytest_regen_check"
    shutil.rmtree(out_root, ignore_errors=True)
    try:
        fresh = generate_credit_document_examples(out_root)
        fresh_manifest = load_json(fresh)
        assert fresh_manifest["manifest_id"] == committed_manifest["manifest_id"]
        assert fresh_manifest["corpus_snapshot"]["hash"] == committed_manifest["corpus_snapshot"]["hash"]
        assert fresh_manifest["task_results"]["hash"] == committed_manifest["task_results"]["hash"]
    finally:
        shutil.rmtree(out_root, ignore_errors=True)


def test_committed_envelope_validates_and_replays():
    envelope_path = COMMITTED / "run_envelope.json"
    report = replay_envelope_file(envelope_path)
    assert report.status == "replayed"
    assert not report.output_diffs
