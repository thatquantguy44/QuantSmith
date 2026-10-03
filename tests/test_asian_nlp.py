"""Acceptance tests for spec 0094 -- Asian-language NLP foundation.

Every fixture text is a synthetic template sentence (spec 0025). Expected values in the
fixtures are written from template parameters, not produced by the extractor, so these
tests compare two independent sources.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from quantsmith.asian_nlp import (
    KNOWN_FAILURE_MODES, PooledScoreRefused, agreement_by_language, below_threshold, chinese_variant,
    compare, decision_ready, evaluate_cases, extract, identify, load_conventions, normalize_text,
    normalize_with_offsets, original_span, parse_number, pooled_score, render_markdown, segment,
    validate_model_item, verify_spans,
)

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "src/quantsmith/asian_nlp/fixtures"
EXTRACTION = json.loads((FIX / "extraction_cases.json").read_text(encoding="utf-8"))
IDENT = json.loads((FIX / "identification_cases.json").read_text(encoding="utf-8"))
CASES = EXTRACTION["cases"]
IN_SCOPE = ["zh-Hans", "zh-Hant", "ja", "ko", "th", "vi", "id/ms", "fil", "ru", "kk", "uz", "en"]


# ---------------------------------------------------------------- AC-001
def test_ac001_identification_fixtures_clear_and_undetermined():
    for c in IDENT["cases"]:
        r = identify(c["text"])
        assert r["status"] == c["expect_status"], c["text"]
        assert r["language"] == c["expect_language"], c["text"]
        if c["expect_status"] == "undetermined":
            assert r["language"] is None and r["reasons"]
            assert c["expect_reason"] in r["reasons"], (c["text"], r["reasons"])


def test_ac001_every_supported_language_has_clear_samples():
    clear = {}
    for c in IDENT["cases"]:
        if c["expect_status"] == "ok":
            clear[c["expect_language"]] = clear.get(c["expect_language"], 0) + 1
    for lang in ("zh-Hans", "zh-Hant", "ja", "ko", "th", "vi", "id/ms", "fil", "ru", "kk", "en"):
        assert clear.get(lang, 0) >= 3, lang


def test_ac001_never_returns_language_without_evidence():
    assert identify("")["language"] is None and identify("")["reasons"] == ["no_letters"]
    assert identify("12345 67890")["language"] is None
    # an Uzbek (Latin) sentence has no supported function-word evidence: undetermined, not a guess
    uz = identify("Kompaniya o'tgan yilda investorlardan mablag' jalb qildi va rivojlandi")
    assert uz["language"] is None


# ---------------------------------------------------------------- AC-002
def test_ac002_simplified_traditional_and_shared():
    from quantsmith.asian_nlp.lexicon import SIMP_TRAD
    assert all(s != t for s, t in SIMP_TRAD)
    hans = chinese_variant("国际资产管理公司融资")
    hant = chinese_variant("國際資產管理公司融資")
    shared = chinese_variant("公司人民大学北京")
    assert hans["variant"] == "zh-Hans" and hans["simplified_only_chars"] >= 2 and hans["traditional_only_chars"] == 0
    assert hant["variant"] == "zh-Hant" and hant["traditional_only_chars"] >= 2 and hant["simplified_only_chars"] == 0
    assert shared["variant"] == "zh" and shared["simplified_only_chars"] == 0
    mixed = chinese_variant("国际資產")
    assert mixed["variant"] == "zh"


# ---------------------------------------------------------------- AC-003
def test_ac003_segmentation_baseline():
    r = segment("融资5000万元 Rp 5 miliar")
    assert r["tokenizer"] == "asian-baseline-ngram@1" and r["source"] == "baseline"
    texts = [t["text"] for t in r["tokens"]]
    assert texts == ["融资", "5000", "万元", "Rp", "5", "miliar"]
    ja = segment("東京大学に行く")
    assert [t["text"] for t in ja["tokens"]][:2] == ["東京", "京大"]
    th = segment("บริษัทลงทุน")
    assert all("ั" not in t["text"][:1] for t in th["tokens"])        # no token starts with a bare vowel mark
    ko = segment("회사는 투자를 유치했습니다")
    assert [t["text"] for t in ko["tokens"]] == ["회사는", "투자를", "유치했습니다"]
    for text in ("融资5000万元", "東京大学に行く abc", "บริษัทลงทุน 2567"):
        for t in segment(text)["tokens"]:
            assert text[t["start"]:t["end"]] == t["text"]


def test_ac003_segmenter_slot_replaces_baseline_without_changing_caller():
    def whitespace_chars(text):
        return [{"text": ch, "start": i, "end": i + 1} for i, ch in enumerate(text) if not ch.isspace()]
    with pytest.raises(ValueError):
        segment("融资", segmenter=whitespace_chars)                     # must declare id and version
    whitespace_chars.tokenizer_id, whitespace_chars.tokenizer_version = "unit-test-chars", "0"
    r = segment("融资 5", segmenter=whitespace_chars)
    assert r["tokenizer"] == "unit-test-chars@0" and r["source"] == "plugin"
    assert [t["text"] for t in r["tokens"]] == ["融", "资", "5"]

    def bad(text):
        return [{"text": "x", "start": 0, "end": 1}]
    bad.tokenizer_id, bad.tokenizer_version = "bad", "1"
    with pytest.raises(ValueError):
        segment("融资", segmenter=bad)
    with pytest.raises(ValueError):
        segment("x", ngram=0)


# ---------------------------------------------------------------- AC-004
@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_ac004_extraction_fixture(case):
    items = extract(case["text"], case["language"])
    assert len(items) == 1, items
    got, exp = items[0], case["expected"][0]
    assert got["type"] == exp["type"] == case["kind"]
    assert got["span"] == exp["span"]
    assert got["value"] == exp["value"]
    assert got.get("currency") == exp["currency"]
    assert got["ambiguous"] == exp["ambiguous"]
    assert case["text"][got["start"]:got["end"]] == got["span"]
    assert got["language"] == case["language"]
    assert got["method"] == "rule" and got["rule_id"].startswith("extract.")
    assert isinstance(got["conventions"], list)


def test_ac004_items_carry_required_fields():
    for it in extract("估值1,200万美元,2024年3月31日", "zh-Hans"):
        for f in ("type", "span", "start", "end", "language", "rule_id", "method", "value", "ambiguous", "conventions"):
            assert f in it
    amount = extract("估值1,200万美元", "zh-Hans")[0]
    assert "norm.wan" in amount["conventions"] and "cur.usd" in amount["conventions"]


# ---------------------------------------------------------------- AC-005
def test_ac005_ambiguity_is_flagged_not_guessed():
    zhao = extract("规模3兆", "zh-Hans")[0]
    assert zhao["ambiguous"] and zhao["value"] is None and "ambiguous_symbol" in zhao["ambiguity_reasons"][0]
    sep = extract("1.250 juta")                                       # language undetermined (short)
    assert sep and sep[0]["ambiguous"] and sep[0]["value"] is None
    assert extract("1.250 juta", "id/ms")[0]["value"] == 1250000000
    assert extract("1.250 million", "en")[0]["value"] == 1250000
    yen = extract("¥3億")
    assert yen[0]["ambiguous"] and yen[0]["currency"] is None
    assert extract("¥3億", "ja")[0]["currency"] == "JPY" and extract("¥3億", "zh-Hans")[0]["currency"] == "CNY"
    d = extract("Dated 10/12/2024", "en")[0]
    assert d["ambiguous"] and d["value"] is None
    inv = extract("文件日期2024年2月30日", "zh-Hans")[0]
    assert inv["ambiguous"] and inv["value"] is None and "invalid_calendar_date" in inv["ambiguity_reasons"]
    assert extract("ปี 1800", "th")[0]["ambiguous"]


def test_ac005_parse_number_rules():
    assert parse_number("1,200", "en") == (1200, [])
    assert parse_number("1.250.000", "id/ms") == (1250000, [])
    assert parse_number("1 250 000,5", "ru") == (1250000.5, [])
    assert parse_number("3.5", "en") == (3.5, [])
    assert parse_number("3,5", "vi") == (3.5, [])
    assert parse_number("1.234,56", None) == (1234.56, [])
    value, reasons = parse_number("1.250", None)
    assert value is None and reasons
    assert parse_number("1.250", "en") == (1.25, [])
    assert parse_number("1,250", "en") == (1250, [])


def test_ac005_unit_and_currency_data_comes_from_conventions():
    conv = load_conventions()
    symbols = {u["symbol"] for u in conv["normalization"]["numeral_units"]}
    assert {"万", "亿", "億", "萬", "만", "억", "조", "lakh", "crore", "ล้าน", "juta", "млн"} <= symbols
    assert {c["code"] for c in conv["normalization"]["currency_markers"]} >= {"CNY", "JPY", "KRW", "THB", "IDR", "VND"}
    # a changed convention changes the result: there is no second copy of the multiplier
    altered = copy.deepcopy(conv)
    for u in altered["normalization"]["numeral_units"]:
        if u["symbol"] == "万":
            u["multiplier"] = 7
    assert extract("估值5万美元", "zh-Hans", altered)[0]["value"] == 35
    assert extract("估值5万美元", "zh-Hans")[0]["value"] == 50000


# ---------------------------------------------------------------- AC-006
def test_ac006_span_verification_rejects_corruption():
    text = "估值1,200万美元"
    items = extract(text, "zh-Hans")
    assert verify_spans(text, items) == []
    bad = copy.deepcopy(items)
    bad[0]["start"] += 1
    assert verify_spans(text, bad)
    bad = copy.deepcopy(items)
    bad[0]["end"] = len(text) + 5
    assert verify_spans(text, bad)
    bad = copy.deepcopy(items)
    bad[0]["span"] = "other"
    assert verify_spans(text, bad)


def test_ac006_every_fixture_span_equals_the_slice():
    for c in CASES:
        for it in extract(c["text"], c["language"]):
            assert c["text"][it["start"]:it["end"]] == it["span"]


# ---------------------------------------------------------------- AC-007
def test_ac007_fixture_coverage_and_synthetic_flags():
    minimum = EXTRACTION["min_cases_per_cell"]
    assert EXTRACTION["synthetic"] is True and IDENT["synthetic"] is True
    assert all(c["synthetic"] is True for c in CASES) and all(c["synthetic"] is True for c in IDENT["cases"])
    counts = {}
    for c in CASES:
        counts[(c["language"], c["kind"])] = counts.get((c["language"], c["kind"]), 0) + 1
    for kind, langs in EXTRACTION["applicability"].items():
        for lang in langs:
            assert counts.get((lang, kind), 0) >= minimum, (lang, kind)
    assert set(EXTRACTION["applicability"]["amount"]) == set(IN_SCOPE)
    assert set(EXTRACTION["applicability"]["date"]) == set(IN_SCOPE)
    assert set(EXTRACTION["applicability"]["era_year"]) == {"ja", "zh-Hant", "th"}
    assert set(EXTRACTION["applicability"]["fiscal_period"]) == {"zh-Hans", "zh-Hant", "ja", "ko", "th", "en"}
    assert "synthetic" in EXTRACTION["disclosure"].lower()


# ---------------------------------------------------------------- AC-008
def test_ac008_per_language_report_and_pooled_refusal():
    report = evaluate_cases(CASES)
    for lang in IN_SCOPE:
        assert lang in report and "amount" in report[lang] and "date" in report[lang]
    for lang, kinds in report.items():
        for kind, cell in kinds.items():
            assert cell["n_expected"] >= 6 and cell["n_cases"] >= 6
            assert cell["precision"] == 1.0 and cell["recall"] == 1.0 and cell["exact_match"] == 1.0
    assert below_threshold(report, 6) == []
    pooled = pooled_score(report, 6)
    assert pooled["precision"] == 1.0 and "synthetic" in pooled["note"]
    with pytest.raises(PooledScoreRefused):
        pooled_score(report, 7)
    thin = evaluate_cases([c for c in CASES if c["language"] != "th"] + [c for c in CASES if c["language"] == "th"][:3])
    with pytest.raises(PooledScoreRefused) as exc:
        pooled_score(thin, 6)
    assert "th/" in str(exc.value)
    md = render_markdown(report)
    assert "| th | amount |" in md and "Precision" in md


def test_ac008_a_wrong_prediction_lowers_the_cell():
    case = next(c for c in CASES if c["language"] == "zh-Hans" and c["kind"] == "amount")
    wrong = {case["id"]: [dict(extract(case["text"], "zh-Hans")[0], value=1)]}
    report = evaluate_cases([case], wrong)
    cell = report["zh-Hans"]["amount"]
    assert cell["precision"] == 0.0 and cell["recall"] == 0.0 and cell["exact_match"] == 0.0


# ---------------------------------------------------------------- AC-009 / AC-010
def _model_item(base, **over):
    m = {"type": base["type"], "span": base["span"], "start": base["start"], "end": base["end"],
         "value": base["value"], "currency": base.get("currency"),
         "provenance": {"model": "synthetic-model", "prompt_manifest": "pm-1", "envelope_ref": "env-1"}}
    m.update(over)
    return m


def test_ac009_comparison_never_overwrites_baseline():
    text = "估值1,200万美元,融资5000万元"
    base = extract(text, "zh-Hans")
    agree = _model_item(base[0])
    disagree = _model_item(base[1], value=999)
    extra = {"type": "date", "span": "x", "start": 0, "end": 1, "value": "2024",
             "provenance": {"model": "m", "prompt_manifest": "p", "envelope_ref": "e"}}
    snapshot = copy.deepcopy(base)
    out = compare(base, [agree, disagree, extra])
    assert base == snapshot and out["baseline_unchanged"] is True
    assert len(out["agree"]) == 1 and len(out["disagree"]) == 1 and len(out["model_only"]) == 1
    assert out["disagree"][0]["baseline"]["value"] == 50000000 and out["disagree"][0]["model"]["value"] == 999
    merged_values = [m["value"] for m in out["merged"] if m["type"] == "amount"]
    assert merged_values == [12000000, 50000000]                      # baseline kept where they disagree
    assert all(m["derived"] is True and m["method"] == "llm" for m in out["agree"] and [x["model"] for x in out["agree"]])
    assert all(m["derived"] is True for m in out["model_only"])
    rates = agreement_by_language([out], ["zh-Hans"])
    assert rates["zh-Hans"]["agreement_rate"] == 0.5 and rates["zh-Hans"]["model_only"] == 1


def test_ac010_provenance_and_reviewer_required():
    base = extract("估值1,200万美元", "zh-Hans")[0]
    no_prov = {k: v for k, v in _model_item(base).items() if k != "provenance"}
    assert validate_model_item(no_prov)
    with pytest.raises(ValueError):
        compare([base], [no_prov])
    out = compare([base], [_model_item(base)])
    model = out["agree"][0]["model"]
    assert model["derived"] is True and decision_ready(model) is False        # no reviewer named
    reviewed = copy.deepcopy(model)
    reviewed["provenance"]["reviewer"] = "A. Bilingual Reviewer"
    assert decision_ready(reviewed) is True
    assert decision_ready(base) is True                                     # unambiguous rule output
    amb = extract("规模3兆", "zh-Hans")[0]
    assert decision_ready(amb) is False
    contract = (ROOT / "agents/venture_intelligence/multilingual_document_nlp/README.md").read_text(encoding="utf-8")
    for needle in ("quantsmith.asian_nlp", "bilingual human reviewer", "derived: true", "0070"):
        assert needle in contract, needle


# ---------------------------------------------------------------- AC-011
def test_ac011_gap_register_updated():
    gaps = {g["id"]: g for g in json.loads(
        (ROOT / "knowledge/venture_intelligence/gaps.json").read_text(encoding="utf-8"))["gaps"]}
    assert gaps["gap.low_resource_languages"]["owner_spec"] == "0094"
    assert gaps["gap.language_id_short_text"]["owner_spec"] == "0094"
    assert gaps["gap.segmentation_no_dictionary"]["owner_spec"] == "0094"
    assert "gap.kk_uz_fil_month_lexicons" in gaps


# ---------------------------------------------------------------- AC-012
def test_ac012_fullwidth_and_thai_digits_normalize_with_original_offsets():
    text = "融资５０００万元于２０２４年３月３１日"
    items = extract(text, "zh-Hans")
    amount = next(i for i in items if i["type"] == "amount")
    assert amount["value"] == 50000000 and amount["span"] == "５０００万元"
    assert text[amount["start"]:amount["end"]] == "５０００万元"
    date = next(i for i in items if i["type"] == "date")
    assert date["value"] == "2024-03-31" and text[date["start"]:date["end"]] == date["span"]
    thai = extract("ลงทุน ๕ ล้านบาท", "th")[0]
    assert thai["value"] == 5000000 and thai["span"] == "๕ ล้านบาท"
    norm, starts, ends = normalize_with_offsets("ＡＢ㈱５")
    assert norm.startswith("AB(株)5") and len(starts) == len(ends) == len(norm)
    assert original_span(starts, ends, 0, 1) == (0, 1)
    assert original_span(starts, ends, 2, 5) == (2, 3)                       # ㈱ expands to (株) -> one source char
    with pytest.raises(ValueError):
        original_span(starts, ends, 3, 99)
    assert normalize_text("５０") == "50"


def test_ac012_known_failure_modes_are_documented_per_language():
    for key in ("all", "zh", "ja", "ko", "th", "vi", "id/ms", "fil", "ru", "kk", "uz", "en"):
        assert KNOWN_FAILURE_MODES[key], key


# ---------------------------------------------------------------- AC-013
def test_ac013_determinism():
    for c in CASES[:60]:
        assert extract(c["text"], c["language"]) == extract(c["text"], c["language"])
    assert json.dumps(evaluate_cases(CASES), sort_keys=True) == json.dumps(evaluate_cases(CASES), sort_keys=True)
    t = "融资5000万元 2024年3月31日"
    assert identify(t) == identify(t) and segment(t) == segment(t)
