"""Acceptance tests for spec 0092 -- venture knowledge integration and product writers.

Every document, note, and product here is synthetic (spec 0025).
"""

from __future__ import annotations

import copy
import re
from pathlib import Path

import pytest

from quantsmith.pipelines import workflow_memory as wm
from quantsmith.pipelines.venture_knowledge import (
    ACCESS_LEVELS, Document, channel_lesson_candidate, load_source_quality, parse_flat_yaml, retrieval_contract_violations,
    retrieve, screening_decision_candidate, source_quirk_candidates, stage_to_local_store, tracked_files_under,
    validate_documents, validate_store,
)
from quantsmith.pipelines.venture_pack import load_pack, validate_overlay, validate_pack
from quantsmith.pipelines.venture_products import index_passages, releasable, render_markdown, validate_product

ROOT = Path(__file__).resolve().parents[1]
AS_OF = "2026-06-01"

DOCS = [
    Document("pat-1", "patentsview", "Solid-state battery patents are filed in many offices.\n\nCount patent families, not raw filings.",
             "public", "2026-01-01", "B2"),
    Document("news-1", "gdelt", "The company announced a financing round for its battery line.", "public", "2026-02-01", "C3"),
    Document("note-1", "analyst_note", "Screening note: ownership layers above the operating company remain unresolved.",
             "restricted", "2026-03-01", "C3"),
    Document("zh-1", "registry_filing", "公司完成固态电池融资5000万元。", "internal", "2026-02-15", "B2", "zh-Hans"),
    Document("future-1", "late_feed", "Battery supplier agreement signed.", "public", "2026-09-01", "C3"),
    Document("old-1", "old_feed", "Battery plant announced.", "public", "2025-01-01", "C3", superseded_by="news-1"),
]


# ---------------------------------------------------------------- AC-001
def test_ac001_local_store_is_ignored_templated_and_gated():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert re.search(r"^/knowledge_local/$", ignore, re.M)
    for f in ("README.md", "store.yml", "memory_manifest_entry.yml", "knowledge_sources_entry.yml"):
        assert (ROOT / "templates/knowledge_local" / f).is_file()
    assert "knowledge_local" in (ROOT / "hooks/stages/docs-link-check.sh").read_text(encoding="utf-8")
    assert "knowledge_local" in (ROOT / "hooks/stages/memory-check.sh").read_text(encoding="utf-8")
    assert tracked_files_under(ROOT) == []                          # nothing under knowledge_local/ is committed


def test_ac001_overlay_store_root_must_be_under_knowledge_local():
    conv = load_pack(ROOT)["conventions"]
    assert validate_overlay({"store_root": "knowledge_local/venture_intelligence"}, conv) == []
    assert validate_overlay({"store_root": "memory/venture"}, conv)
    assert validate_overlay({"store_root": "/tmp/x"}, conv)
    template = (ROOT / "config/venture_overlay.example.yml").read_text(encoding="utf-8")
    assert 'store_root: "knowledge_local/venture_intelligence"' in template


# ---------------------------------------------------------------- AC-002
def _store(tmp_path, **over):
    d = tmp_path / "venture_intelligence"
    d.mkdir()
    meta = {"domain": "venture_intelligence", "access_level": "restricted", "owner": "analyst-7f3a"}
    meta.update(over)
    (d / "store.yml").write_text("\n".join(f"{k}: {v}" for k, v in meta.items()) + "\n", encoding="utf-8")
    return d


def test_ac002_store_manifest_rules(tmp_path):
    assert validate_store(_store(tmp_path)) == []
    for bad, needle in (({"access_level": "secret"}, "access_level"), ({"owner": "Jane Doe"}, "owner"),
                        ({"owner": "someone@example.com"}, "owner"), ({"domain": "other"}, "domain"),
                        ({"owner": "your-pseudonymous-handle"}, "placeholder")):
        d = tmp_path / f"s{abs(hash(str(bad)))}"
        d.mkdir()
        meta = {"domain": d.name if bad.get("domain") is None else bad["domain"], "access_level": "restricted",
                "owner": "analyst-7f3a"}
        meta.update({k: v for k, v in bad.items() if k != "domain"})
        (d / "store.yml").write_text("\n".join(f"{k}: {v}" for k, v in meta.items()), encoding="utf-8")
        assert any(needle in e for e in validate_store(d)), bad
    empty = tmp_path / "empty"
    empty.mkdir()
    assert validate_store(empty) == ["empty: store.yml is missing"]
    assert parse_flat_yaml("a: 1  # c\n# x\nb: 'two'\n") == {"a": "1", "b": "two"}
    assert ACCESS_LEVELS == ("public", "internal", "restricted")


# ---------------------------------------------------------------- AC-003
def test_ac003_source_quirks_come_from_the_catalog():
    q = load_source_quality(ROOT / "sources/patentsview.yml")
    assert q["last_assessed"] == "2026-10-02" and len(q["known_issues"]) == 3
    specs = source_quirk_candidates("patentsview", q["known_issues"], q["last_assessed"])
    assert len(specs) == 3
    assert all(s.scope == "dataset:patentsview" and s.type == "quirk" and s.confidence == "low" for s in specs)
    assert specs[0].evidence == ({"source_run": "source-catalog-patentsview-2026-10-02"},)
    assert specs[0].target_catalog == "_shared/datasets/patentsview/provenance.yaml"
    assert all(s.pit_scope in wm.PIT_SCOPE_KNOWN for s in specs)


def test_ac003_screening_decisions_are_always_restricted_and_clean():
    s = screening_decision_candidate("case-001", "Ownership layers unresolved; counsel to confirm.", "run-1")
    assert s.access_level == "restricted" and s.type == "decision" and s.scope == "case:case-001"
    for bad in ("api_key=abc123 leaked", "contact jane@example.com about it", "", "x" * 600):
        with pytest.raises(ValueError):
            screening_decision_candidate("case-002", bad, "run-1")
    with pytest.raises(ValueError):
        channel_lesson_candidate("hiring_labour", "a lesson", "run-1", kind="decision")
    assert channel_lesson_candidate("hiring_labour", "Postings are not hires.", "run-1").scope == "channel:hiring_labour"


def test_ac003_staging_stays_inside_knowledge_local_and_promotes_nothing(tmp_path):
    repo = tmp_path
    store = repo / "knowledge_local" / "venture_intelligence"
    store.mkdir(parents=True)
    spec = channel_lesson_candidate("patents", "Filing date is not when the world knew.", "run-1")
    path = stage_to_local_store([spec], store_dir=store, repo_root=repo, source_run="run-1")
    assert str(path).startswith(str(store.resolve())) or str(path).startswith(str(store))
    inbox = wm.load_inbox(store / "memory")
    assert len(inbox) == 1 and inbox[0][0].spec.statement == "Filing date is not when the world knew."
    assert not list((store / "memory").rglob("index.yaml"))                          # nothing promoted
    again = stage_to_local_store([spec], store_dir=store, repo_root=repo, source_run="run-1")
    assert again.read_text(encoding="utf-8") == path.read_text(encoding="utf-8")      # idempotent restaging
    for outside in (repo / "memory", repo / "knowledge" / "venture_intelligence", Path("/tmp/elsewhere")):
        with pytest.raises(ValueError):
            stage_to_local_store([spec], store_dir=outside, repo_root=repo, source_run="run-1")


# ---------------------------------------------------------------- AC-004
def test_ac004_manifest_entry_template_is_read_by_the_memory_parser():
    text = (ROOT / "templates/knowledge_local/memory_manifest_entry.yml").read_text(encoding="utf-8")
    entry = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    manifest = wm.parse_memory_file("version: 1\nworkflows:\n" + "\n".join(entry) + "\n")
    wf = manifest["workflows"][0]
    assert wf["name"] == "venture_intelligence" and wf["persistence"] == "external"
    assert wf["path"].startswith("../knowledge_local/venture_intelligence") and wf["access_level"] == "restricted"
    sources = (ROOT / "templates/knowledge_local/knowledge_sources_entry.yml").read_text(encoding="utf-8")
    assert "domains_from_subfolders: true" in sources and "access_level: restricted" in sources


# ---------------------------------------------------------------- AC-005
def test_ac005_retrieval_returns_cited_spans_that_slice_back():
    r = retrieve("patent families filings", DOCS, "public", AS_OF)
    assert r["status"] == "ok" and r["passages"]
    by_id = {d.doc_id: d for d in DOCS}
    for p in r["passages"]:
        doc = by_id[p["doc_id"]]
        assert doc.text[p["start"]:p["end"]] == p["text"]
        assert p["citation_id"] == f"{p['doc_id']}:{p['start']}-{p['end']}"
        assert p["content_hash"] == doc.content_hash and len(p["passage_hash"]) == 64
        assert (p["source_grade"], p["known_at"], p["access_level"]) == (doc.source_grade, doc.known_at, doc.access_level)
    assert r["passages"][0]["doc_id"] == "pat-1"
    assert retrieve("patent families filings", DOCS, "public", AS_OF) == r                  # deterministic


def test_ac005_chinese_query_uses_the_asian_nlp_segmenter():
    r = retrieve("固态电池", DOCS, "internal", AS_OF)
    assert r["status"] == "ok" and r["passages"][0]["doc_id"] == "zh-1" and r["passages"][0]["language"] == "zh-Hans"
    assert r["tokenizer"].startswith("asian-baseline-ngram@")
    assert retrieve("固态电池", DOCS, "public", AS_OF)["passages"] == []                     # that filing is internal


def test_ac005_not_found_is_an_answer():
    r = retrieve("quantum chromodynamics", DOCS, "restricted", AS_OF)
    assert r["status"] == "not_found" and r["passages"] == [] and r["reason"] == "no_passage_above_threshold"
    assert retrieve("", DOCS, "public", AS_OF)["status"] == "not_found"
    with pytest.raises(ValueError):
        retrieve("battery", DOCS, "public", AS_OF, k=0)


# ---------------------------------------------------------------- AC-006
def test_ac006_clearance_is_required_and_applied_before_ranking():
    for missing in (None, "", "top-secret"):
        with pytest.raises(PermissionError):
            retrieve("battery", DOCS, missing, AS_OF)
    for level in ("public", "internal"):
        r = retrieve("ownership layers unresolved screening", DOCS, level, AS_OF)
        assert all(p["doc_id"] != "note-1" for p in r["passages"])
    assert retrieve("ownership layers unresolved screening", DOCS, "restricted", AS_OF)["passages"][0]["doc_id"] == "note-1"


def test_ac006_a_restricted_match_is_indistinguishable_from_no_match():
    restricted_only = [d for d in DOCS if d.doc_id == "note-1"]
    absent = retrieve("ownership layers unresolved", [], "public", AS_OF)
    hidden = retrieve("ownership layers unresolved", restricted_only, "public", AS_OF)
    assert hidden == absent
    future = retrieve("supplier agreement", [d for d in DOCS if d.doc_id == "future-1"], "public", AS_OF)
    assert future == retrieve("supplier agreement", [], "public", AS_OF)
    assert not any(k in hidden for k in ("filtered", "withheld", "hidden", "restricted_count"))


def test_ac006_restricted_documents_cannot_move_a_lower_callers_scores():
    base_docs = [d for d in DOCS if d.access_level != "restricted"]
    a = retrieve("battery financing round", base_docs, "public", AS_OF)
    noisy = base_docs + [Document(f"r{i}", "x", "battery financing round battery financing round", "restricted",
                                  "2026-01-01", "C3") for i in range(25)]
    b = retrieve("battery financing round", noisy, "public", AS_OF)
    assert a == b                                              # same passages, same scores, to the last digit


# ---------------------------------------------------------------- AC-007
def test_ac007_point_in_time_superseded_and_secrets():
    ids = lambda r: {p["doc_id"] for p in r["passages"]}              # noqa: E731
    early = retrieve("battery plant announced supplier agreement", DOCS, "public", "2026-06-01")
    assert "future-1" not in ids(early) and "old-1" not in ids(early)
    assert "future-1" in ids(retrieve("battery supplier agreement", DOCS, "public", "2026-12-31"))
    leaky = DOCS + [Document("leak-1", "x", "battery notes api_key=sk-123456", "public", "2026-01-01", "C3")]
    assert "leak-1" not in ids(retrieve("battery notes", leaky, "public", AS_OF))
    errors = validate_documents(leaky + [DOCS[0], Document("bad", "x", "t", "secret", "June 1")])
    assert any("leak-1" in e and "credential" in e for e in errors)
    assert any("duplicate" in e for e in errors) and any("access level" in e for e in errors) and any("ISO date" in e for e in errors)
    assert validate_documents(DOCS) == []


# ---------------------------------------------------------------- AC-008
def test_ac008_contract_checker_accepts_good_and_rejects_bad_output():
    good = retrieve("patent families", DOCS, "public", AS_OF)
    assert retrieval_contract_violations(good, "public", AS_OF) == []
    assert retrieval_contract_violations(retrieve("zzz", DOCS, "public", AS_OF), "public", AS_OF) == []
    over = copy.deepcopy(retrieve("ownership layers", DOCS, "restricted", AS_OF))
    assert any("exceeds caller clearance" in e for e in retrieval_contract_violations(over, "public", AS_OF))
    future = copy.deepcopy(good)
    future["passages"][0]["known_at"] = "2027-01-01"
    assert any("not known" in e for e in retrieval_contract_violations(future, "public", AS_OF))
    bad = copy.deepcopy(good)
    bad["passages"][0]["citation_id"] = "wrong"
    bad["passages"][0]["start"] = 9
    bad["passages"][0]["end"] = 3
    bad["filtered"] = 4
    errs = retrieval_contract_violations(bad, "public", AS_OF)
    assert any("citation_id" in e for e in errs) and any("offsets" in e for e in errs) and any("dropped" in e for e in errs)
    assert retrieval_contract_violations({"status": "not_found", "passages": [good["passages"][0]]}, "public", AS_OF)
    assert retrieval_contract_violations({"status": "ok", "passages": []}, "public", AS_OF)


# ---------------------------------------------------------------- products
def _index(clearance="internal"):
    return index_passages(retrieve("solid-state battery patents filed offices", DOCS, clearance, AS_OF),
                          retrieve("financing round battery line", DOCS, clearance, AS_OF),
                          retrieve("固态电池 融资", DOCS, clearance, AS_OF))


def _cid(index, doc_id):
    return next(c for c, p in index.items() if p["doc_id"] == doc_id)


def _brief(index):
    pat, news, zh = _cid(index, "pat-1"), _cid(index, "news-1"), _cid(index, "zh-1")
    return {
        "kind": "intelligence_brief", "title": "Battery activity (synthetic)", "as_of": AS_OF, "access_level": "internal",
        "status": "draft_for_human_review", "reviewer": None,
        "bluf": "Patent and financing signals point to growing solid-state battery activity; the evidence is partly single-channel.",
        "evidence": [
            {"id": "E1", "text": "Patents are filed in many offices.", "citations": [pat], "source_grade": "B2",
             "claim_id": "c1", "origin_id": "o1", "channel": "patents"},
            {"id": "E2", "text": "A financing round was announced.", "citations": [news], "source_grade": "C3",
             "claim_id": "c1", "origin_id": "o2", "channel": "narrative_news"},
            {"id": "E3", "text": "A filing reports a round of 5000万元.", "citations": [zh], "source_grade": "B2", "derived": True,
             "reviewer": "bilingual-reviewer-1", "claim_id": "c2", "origin_id": "o3", "channel": "regulatory_filings"}],
        "assumptions": [{"id": "A1", "text": "Patent counts proxy for activity.", "basis": "Families, not filings, are counted."}],
        "judgements": [{"id": "J1", "text": "Activity in this area is growing.", "likelihood": "likely", "probability": 0.7,
                        "evidence_confidence": "high", "rests_on": ["E1", "E2", "A1"]}],
        "open_gaps": [{"id": "G1", "text": "Unpublished applications are not visible."}]}


def test_ac009_a_sound_brief_validates_renders_and_needs_a_reviewer_to_release():
    index = _index()
    brief = _brief(index)
    assert validate_product(brief, index) == []
    md = render_markdown(brief, index)
    assert md == render_markdown(brief, index) and "DRAFT - not reviewed" in md
    assert "## Bottom line up front" in md and "## Evidence" in md and "## Judgement" in md and "## Open gaps" in md
    assert "pat-1:" in md and "[B2]" in md and "(p=0.7)" in md
    ok, reasons = releasable(brief, index)
    assert not ok and any("no_named_reviewer" in r for r in reasons)
    reviewed = {**brief, "reviewer": "reviewer-9c1d", "status": "released"}
    ok, reasons = releasable(reviewed, index)
    assert ok and reasons == [] and "DRAFT" not in render_markdown(reviewed, index)


def _errors(brief, index, needle):
    errs = validate_product(brief, index)
    assert any(needle in e for e in errs), (needle, errs)
    return errs


def test_ac010_citation_rules():
    index = _index()
    b = _brief(index)
    b["evidence"][0]["citations"] = []
    _errors(b, index, "E1: uncited_claim")
    b = _brief(index)
    b["evidence"][0]["citations"] = ["pat-1:0-1"]
    _errors(b, index, "E1: unresolvable_citation")
    b = _brief(index)
    b["as_of"] = "2026-01-15"                                              # earlier than the cited passages
    _errors(b, index, "cites_future_information")
    b = _brief(index)
    b["access_level"] = "public"                                            # cites an internal filing
    _errors(b, index, "cites_above_classification")
    b = _brief(index)
    b["evidence"][1]["source_grade"] = "Z9"
    _errors(b, index, "E2: invalid_source_grade")


def test_ac010_structure_and_judgement_rules():
    index = _index()
    for section in ("evidence", "assumptions", "judgements", "open_gaps", "bluf"):
        b = _brief(index)
        b[section] = [] if section != "bluf" else ""
        _errors(b, index, "missing_section")
    b = _brief(index)
    b["bluf"] = "x" * 601
    _errors(b, index, "bluf_too_long")
    b = _brief(index)
    b["assumptions"][0]["basis"] = ""
    _errors(b, index, "A1: assumption_without_basis")
    b = _brief(index)
    b["judgements"][0]["likelihood"] = "very likely"
    _errors(b, index, "J1: likelihood_mismatch")
    b = _brief(index)
    b["judgements"][0]["text"] = "Activity may be growing."
    _errors(b, index, "J1: vague_wording")
    b = _brief(index)
    b["judgements"][0]["rests_on"] = ["A1"]
    _errors(b, index, "J1: judgement_without_evidence")
    b = _brief(index)
    b["judgements"][0]["rests_on"] = ["E1", "E9"]
    _errors(b, index, "J1: unknown_support")
    b = _brief(index)
    b["judgements"][0]["evidence_confidence"] = "certain"
    _errors(b, index, "invalid_evidence_confidence")
    b = _brief(index)
    b["evidence"][1]["id"] = "E1"
    _errors(b, index, "duplicate_id")
    b = _brief(index)
    b["kind"] = "press_release"
    assert validate_product(b, index)[0].startswith("product: invalid_kind")


def test_ac010_corroboration_and_derived_evidence_rules():
    index = _index()
    b = _brief(index)
    b["judgements"][0]["rests_on"] = ["E3"]                                  # single origin, single channel
    _errors(b, index, "J1: high_confidence_without_corroboration")
    b["judgements"][0]["evidence_confidence"] = "moderate"
    assert not any("high_confidence" in e for e in validate_product(b, index))
    b = _brief(index)
    b["evidence"][2]["reviewer"] = None
    b["judgements"][0].update({"rests_on": ["E3"], "evidence_confidence": "low"})
    _errors(b, index, "rests_only_on_unreviewed_derived_evidence")
    echo = _brief(index)                                                     # two items, one origin: an echo
    echo["evidence"][1]["origin_id"] = "o1"
    _errors(echo, index, "J1: high_confidence_without_corroboration")


def test_ac010_wording_and_release_rules():
    index = _index()
    b = _brief(index)
    b["evidence"][0]["text"] = "The company is evading review."
    _errors(b, index, "conclusion_language")
    b = _brief(index)
    b["status"] = "final"
    _errors(b, index, "premature_final_status")
    assert not any("premature" in e for e in validate_product({**b, "reviewer": "reviewer-9c1d"}, index))


def _memo(index):
    m = _brief(index)
    m["kind"] = "investment_memo"
    m["title"] = "Committee memo (synthetic)"
    m["decision_owner"] = "Investment committee"
    m.pop("bluf")
    return m


def test_ac010_memo_never_recommends():
    index = _index()
    m = _memo(index)
    assert validate_product(m, index) == []
    for phrase in ("We recommend investing now.", "The committee should invest.", "We approve this deal.",
                   "We would pass on this.", "This is a strong buy.", "The proposal is rejected."):
        b = _memo(index)
        b["judgements"][0]["text"] = "Activity is growing. " + phrase
        _errors(b, index, "recommendation_language")
    b = _memo(index)
    b.pop("decision_owner")
    _errors(b, index, "missing_field: decision_owner")
    brief_with_advice = _brief(index)                                            # advice lint is memo-only
    brief_with_advice["judgements"][0]["text"] = "Activity is growing; analysts recommend monitoring."
    assert not any("recommendation_language" in e for e in validate_product(brief_with_advice, index))


# ---------------------------------------------------------------- AC-011 / AC-012
def test_ac011_agents_built_with_boundaries_indexed_and_registered():
    pack = load_pack(ROOT)
    cov = {a["id"]: a for a in pack["coverage"]["agents"]}
    base = ROOT / "agents/venture_intelligence"
    catalog = (ROOT / "agents/README.md").read_text(encoding="utf-8")
    standard = (ROOT / "instructions/venture_intelligence.md").read_text(encoding="utf-8")
    registry = (ROOT / "agents/agent_registry.yaml").read_text(encoding="utf-8")
    boundaries = {"intelligence_brief_writer": "release or publish a brief without a named human reviewer",
                  "investment_memo_writer": "recommend, approve, or reject an investment"}
    for name, boundary in boundaries.items():
        assert cov[name]["status"] == "built" and cov[name]["creating_spec"] == "0092"
        for f in ("README.md", "instructions.md", "tasks.md", "prompt.md"):
            assert (base / name / f).is_file()
        assert boundary in (base / name / "README.md").read_text(encoding="utf-8")
        assert f"venture_intelligence/{name}/" in catalog and f"`{name}`" in standard
        assert f'name: "venture_intelligence/{name}"' in registry
    wfs = {w["id"]: w for w in pack["workflows"]["workflows"]}
    assert "investment_memo_writer" in wfs["workflow.deal_to_memo"]["agents"]
    assert "intelligence_brief_writer" in wfs["workflow.signal_to_thesis"]["agents"]


def test_ac012_conventions_carry_the_rules_as_reviewable_data():
    pack = load_pack(ROOT)
    assert validate_pack(pack, ROOT) == []
    conv = pack["conventions"]
    for key in ("product_rules", "retrieval_contract"):
        assert conv[key]["review_status"] == "draft" and conv[key]["citation"].strip()
    assert "investment_memo" in conv["product_rules"]["kinds"] and conv["product_rules"]["recommendation_terms"]
    assert len(conv["retrieval_contract"]["order"]) == 5
    tampered = copy.deepcopy(pack)
    tampered["conventions"]["product_rules"]["review_status"] = "reviewed"
    assert any("without a review record" in e for e in validate_pack(tampered, ROOT))
