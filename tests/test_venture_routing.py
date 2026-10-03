"""Acceptance tests for spec 0096 -- venture request routing and the orchestrator agent.

Every request here is synthetic (spec 0025). The router is keyword matching, so these tests pin its rules;
they do not show that it understands requests.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from quantsmith.pipelines.venture_pack import load_pack, validate_pack
from quantsmith.pipelines.venture_routing import (classify_task, detect_regions, forbidden_hits, plan_request)

ROOT = Path(__file__).resolve().parents[1]
PACK = load_pack(ROOT)
ROUTING = PACK["routing"]


def plan(text, clearance="restricted"):
    return plan_request(text, clearance, PACK)


def agents_of(p):
    return [s["agent"] for s in p["steps"]]


# ---------------------------------------------------------------- AC-001 the data
def test_ac001_routing_data_validates_and_covers_every_built_agent():
    assert validate_pack(PACK, ROOT) == []
    built = {a["id"] for a in PACK["coverage"]["agents"] if a["status"] == "built" and a["id"] != "venture_orchestrator"}
    routed = {e for t in ROUTING["task_kinds"] for e in t["chain"] if not e.startswith("{")}
    routed |= {r[k] for r in ROUTING["regions"] for k in ("lead", "structure_analyst") if r.get(k)}
    assert built <= routed, sorted(built - routed)                      # every agent can be reached through some request
    for rec in ROUTING["task_kinds"] + ROUTING["forbidden_intents"] + ROUTING["regions"]:
        assert rec["review_status"] == "draft" and rec["citation"].strip()
    assert ROUTING["limits"].startswith("Keyword matching")


def test_ac001_validator_rejects_broken_routing():
    bad = copy.deepcopy(PACK)
    bad["routing"]["task_kinds"][0]["chain"].append("not_an_agent")
    assert any("not a built agent" in e for e in validate_pack(bad, ROOT))
    bad = copy.deepcopy(PACK)
    bad["routing"]["forbidden_intents"][0]["patterns"].append("(unclosed")
    assert any("invalid pattern" in e for e in validate_pack(bad, ROOT))
    bad = copy.deepcopy(PACK)
    bad["routing"]["forbidden_intents"][0]["decision_owner"] = None                       # None is not a name
    assert any("needs a refusal and a decision_owner" in e for e in validate_pack(bad, ROOT))
    bad = copy.deepcopy(PACK)
    bad["routing"]["forbidden_intents"][0]["alternatives"] = ["task.nonexistent"]
    assert any("is not a task kind" in e for e in validate_pack(bad, ROOT))
    bad = copy.deepcopy(PACK)
    bad["routing"]["regions"][0]["lead"] = None
    assert any("built but has no lead" in e for e in validate_pack(bad, ROOT))
    bad = copy.deepcopy(PACK)
    del bad["routing"]["class_rules"]["required_clearance"]["person_adjacent"]
    assert any("class rules" in e for e in validate_pack(bad, ROOT))
    bad = copy.deepcopy(PACK)
    bad["routing"]["task_kinds"][1]["decision_owner"] = None
    assert any("needs a decision_owner" in e for e in validate_pack(bad, ROOT))


# ---------------------------------------------------------------- AC-002 refusals
REFUSED = {
    "intent.recommend_investment": "Should we invest in this company?",
    "intent.designate_or_attribute": "Designate this entity as a front company.",
    "intent.profile_individual": "Profile the founder and her personal history.",
    "intent.non_public_collection": "Bypass the paywall and use the leaked files.",
    "intent.release_without_review": "Publish the brief without a reviewer.",
    "intent.set_valuation": "Approve the new valuation for this holding.",
    "intent.classify_export": "What is the ECCN for this product?",
    "intent.forecast_returns": "Forecast the fund's IRR for next year.",
}


@pytest.mark.parametrize("intent,text", sorted(REFUSED.items()))
def test_ac002_each_forbidden_intent_is_refused_with_its_owner(intent, text):
    hits = {h["id"] for h in forbidden_hits(text, ROUTING)}
    assert intent in hits
    p = plan(text)
    assert intent in {r["intent"] for r in p["refusals"]}
    r = next(r for r in p["refusals"] if r["intent"] == intent)
    assert r["decision_owner"] and r["refusal"] and r["alternatives"]
    assert all(a in {t["id"] for t in ROUTING["task_kinds"]} for a in r["alternatives"])


def test_ac002_a_pure_forbidden_request_is_refused_and_a_mixed_one_is_split():
    p = plan("Should we invest? Yes or no.")
    assert p["status"] == "refused" and p["steps"] == [] and p["refusals"][0]["decision_owner"] == "the investment committee"
    mixed = plan("Prepare the due diligence for the committee and tell us whether we should invest in it.")
    assert mixed["status"] == "planned" and mixed["task_kind"] == "task.diligence_memo"
    assert [r["intent"] for r in mixed["refusals"]] == ["intent.recommend_investment"]       # the legitimate part is still planned
    assert "investment_memo_writer" in agents_of(mixed)


def test_ac002_recommendation_requests_are_caught_in_every_word_order():
    for text in ("Should we invest in it?", "Tell me whether we should invest.", "Decide whether to back this company.",
                 "I should buy this, right?", "Is it worth investing in this round?", "Is this a good investment?"):
        assert "intent.recommend_investment" in {h["id"] for h in forbidden_hits(text, ROUTING)}, text


def test_ac002_benign_requests_are_not_refused():
    for text in ("Report TVPI and DPI for the fund vintage.", "Draft an intelligence brief with a BLUF.",
                 "Review the valuation mark and stale mark flags.", "Technology landscape for battery storage in Japan.",
                 "Run reserve scenarios for follow-on with a hit rate."):
        assert forbidden_hits(text, ROUTING) == [], text
        assert plan(text)["refusals"] == []


# ---------------------------------------------------------------- AC-003 classification
KINDS = {
    "task.document_extraction": "Extract the terms from this term sheet.",
    "task.entity_resolution": "Are these two records the same company? Match records by registry id.",
    "task.region_overview": "Give me a market overview and funding trend for Vietnam.",
    "task.company_longlist": "Build a longlist of candidate companies in Thailand.",
    "task.landscape_scan": "Technology landscape for battery storage.",
    "task.signal_thesis": "Build a thesis from these signals and test competing hypotheses.",
    "task.diligence_memo": "Prepare the due diligence for a committee memo.",
    "task.counter_diligence": "Check the beneficial owner and foreign capital exposure.",
    "task.fund_review": "Report TVPI and DPI for the fund vintage.",
    "task.mark_review": "Review the valuation mark and stale mark flags.",
    "task.reserve_scenarios": "Run reserve scenarios for follow-on with a hit rate.",
    "task.brief_draft": "Draft an intelligence brief with a BLUF.",
    "task.source_grading": "Grade source reliability and credibility.",
    "task.collection_gaps": "List the missing evidence as an information requirement.",
}


@pytest.mark.parametrize("kind,text", sorted(KINDS.items()))
def test_ac003_each_task_kind_is_reachable_from_a_natural_request(kind, text):
    ranked = classify_task(text, ROUTING)
    assert ranked and ranked[0][1]["id"] == kind, [(s, t["id"]) for s, t in ranked[:3]]
    p = plan(text)
    assert p["status"] in ("planned", "needs_clarification") and p["task_kind"] in (kind, None)
    if p["status"] == "planned":
        assert p["task_kind"] == kind and p["steps"] and p["decision_owner"] and p["human_review"]
        assert [s["order"] for s in p["steps"]] == list(range(1, len(p["steps"]) + 1))
        assert len(set(agents_of(p))) == len(p["steps"])                            # no agent twice


def test_ac003_ambiguous_or_unmatched_requests_ask_rather_than_guess():
    none = plan("hello there")
    assert none["status"] == "needs_clarification" and none["steps"] == [] and "no task kind matched" in none["notes"][0]
    assert plan("")["status"] == "needs_clarification" and plan("   ")["notes"] == ["the request is empty"]
    tie = plan("Compare the thesis with the foreign influence picture.")             # one keyword from two kinds
    assert tie["status"] == "needs_clarification" and set(tie["candidates"]) >= {"task.signal_thesis", "task.counter_diligence"}
    assert tie["steps"] == []


# ---------------------------------------------------------------- AC-004 regions
def test_ac004_regions_are_detected_by_country_and_city():
    names = lambda t: [r["name"] for r in detect_regions(t, ROUTING)]                # noqa: E731
    assert names("start-ups in Jakarta") == ["Southeast Asia"]
    assert names("the Shenzhen and Tokyo filings") == ["Greater China and East Asia"]
    assert names("Singapore versus India") == ["Southeast Asia", "South Asia"]
    assert names("Almaty and Tashkent") == ["Central Asia"]
    assert names("Dubai and Berlin") == [] and names("Europe and Africa") == ["Deferred regions"]
    assert names("indonesian") == ["Southeast Asia"] and names("the english channel") == []   # prefix of a place, not a substring


def test_ac004_multiple_regions_give_multiple_leads_in_order():
    p = plan("Technology landscape of battery storage in Singapore and India and Kazakhstan.")
    leads = [a for a in agents_of(p) if a.endswith("lead")]
    assert leads == ["southeast_asia_regional_lead", "south_asia_lead", "central_asia_lead"]


def test_ac004_structure_analysts_exist_only_where_built_and_gaps_are_stated():
    p = plan("Map the foreign ownership chain of the Shenzhen company.")
    assert "greater_china_east_asia_entity_structure_analyst" in agents_of(p)
    p = plan("Map the foreign ownership chain of the Mumbai company.")
    assert not any("structure_analyst" in a for a in agents_of(p))
    assert any("South Asia has no structure analyst" in n for n in p["notes"])
    p = plan("Map the foreign ownership chain of the company.")
    assert any("no region named" in n for n in p["notes"])


def test_ac004_deferred_regions_are_a_stated_gap_not_a_silent_reroute():
    p = plan("Technology landscape for batteries in Europe.")
    assert p["status"] == "planned" and any("no agent yet" in n and "0087" in n for n in p["notes"])
    assert not any(a.endswith("lead") for a in agents_of(p))


def test_ac004_region_overview_needs_a_market_and_sea_only_agents_are_skipped_elsewhere():
    ask = plan("Give me a market overview and funding trend.")
    assert ask["status"] == "needs_clarification" and any("name a market" in n for n in ask["notes"])
    p = plan("Give me a market overview and funding trend for India.")
    assert agents_of(p) == ["south_asia_lead"] and any("covers Southeast Asia only" in n for n in p["notes"])
    p = plan("Give me a market overview and funding trend for Vietnam.")
    assert agents_of(p) == ["southeast_asia_regional_lead", "southeast_asia_funding_ecosystem_analyst"]


# ---------------------------------------------------------------- AC-005 language
def test_ac005_non_english_script_puts_document_extraction_first_once():
    p = plan("Extract the terms from this 融资5000万元 term sheet.")
    assert agents_of(p)[0] == "multilingual_document_nlp" and agents_of(p).count("multilingual_document_nlp") == 1
    assert any("non-English script" in n for n in p["notes"]) is False                 # already first by the chain: no insertion note
    q = plan("Technology landscape of batteries in Bangkok: บริษัทลงทุน")
    assert agents_of(q)[0] == "multilingual_document_nlp" and any("non-English script" in n for n in q["notes"])
    assert "multilingual_document_nlp" not in agents_of(plan("Technology landscape of batteries in Bangkok."))
    ru = plan("Technology landscape for Almaty: Компания привлекла инвестиции")
    assert agents_of(ru)[0] == "multilingual_document_nlp"


# ---------------------------------------------------------------- AC-006 class and clearance
def test_ac006_class_is_the_strictest_among_the_steps():
    assert plan("Report TVPI and DPI for the fund vintage.")["decision_path_class"] == "analytic_support"
    thesis = plan("Build a thesis from these signals and test competing hypotheses.")
    assert thesis["decision_path_class"] == "person_adjacent" and thesis["required_clearance"] == "restricted"   # hiring analyst is in the chain
    screen = plan("Check the beneficial owner and foreign capital exposure in Singapore.")
    assert screen["decision_path_class"] == "sovereign_adjacent"
    assert any("counsel" in g for g in screen["human_review"]) and screen["decision_owner"].startswith("counsel")
    assert any("named human review" in g for g in thesis["human_review"])
    assert plan("Technology landscape for battery storage.")["required_clearance"] == "public"


def test_ac006_a_caller_below_the_required_clearance_is_denied_without_steps():
    ok = plan("Check the beneficial owner and foreign capital exposure.", "restricted")
    assert ok["status"] == "planned"
    for level in ("public", "internal"):
        d = plan("Check the beneficial owner and foreign capital exposure.", level)
        assert d["status"] == "denied" and d["steps"] == [] and d["decision_path_class"] is None
        assert d["notes"] == ["this class of work needs a higher clearance than the caller holds"]
    assert plan("Report TVPI and DPI for the fund vintage.", "public")["status"] == "planned"
    for missing in (None, "", "top-secret"):
        with pytest.raises(PermissionError):
            plan_request("anything", missing, PACK)


def test_ac006_a_diligence_request_naming_a_region_pulls_in_the_sovereign_adjacent_analyst():
    p = plan("Prepare the due diligence memo for this Indonesian marketplace.", "restricted")
    assert p["status"] == "planned" and "southeast_asia_entity_structure_analyst" in agents_of(p)
    assert p["decision_path_class"] == "sovereign_adjacent"
    assert agents_of(p)[-1] == "investment_memo_writer"
    d = plan("Prepare the due diligence memo for this Indonesian marketplace.", "internal")
    assert d["status"] == "denied"                                                    # honest consequence of the suite's own rules


# ---------------------------------------------------------------- AC-007 determinism
def test_ac007_plans_are_deterministic_and_do_not_mutate_inputs():
    snapshot = copy.deepcopy(PACK["routing"])
    text = "Technology landscape of battery storage in Singapore and Japan."
    assert plan(text) == plan(text)
    assert json.dumps(plan(text), sort_keys=True) == json.dumps(plan(text), sort_keys=True)
    assert PACK["routing"] == snapshot
    p = plan(text)
    assert set(p) >= {"status", "task_kind", "steps", "decision_path_class", "required_clearance", "human_review",
                      "decision_owner", "refusals", "notes", "limits", "request"}
    for s in p["steps"]:
        assert (ROOT / s["path"] / "prompt.md").is_file()


# ---------------------------------------------------------------- AC-008 the agent
def test_ac008_orchestrator_is_built_indexed_registered_and_bounded():
    cov = {a["id"]: a for a in PACK["coverage"]["agents"]}["venture_orchestrator"]
    assert cov["status"] == "built" and cov["creating_spec"] == "0096"
    base = ROOT / "agents/venture_intelligence/venture_orchestrator"
    for f in ("README.md", "instructions.md", "tasks.md", "prompt.md"):
        assert (base / f).is_file()
    readme = (base / "README.md").read_text(encoding="utf-8")
    assert "decide, recommend, or release anything, override a refusal" in readme and "keyword matching" in readme.lower()
    assert "venture_intelligence/venture_orchestrator/" in (ROOT / "agents/README.md").read_text(encoding="utf-8")
    assert "venture_intelligence/venture_orchestrator" in (ROOT / "agents/agent_registry.yaml").read_text(encoding="utf-8")
    assert "`venture_orchestrator`" in (ROOT / "instructions/venture_intelligence.md").read_text(encoding="utf-8")
    roadmap = {r["spec"]: r for r in PACK["coverage"]["roadmap"]}
    assert roadmap["0096"]["closes"] == ["venture_orchestrator"]
    nxt = lambda p: re.search(r"Next unreserved spec number: `(\d+)`", (ROOT / p).read_text(encoding="utf-8")).group(1)   # noqa: E731
    assert nxt("specs/README.md") == nxt("docs/handoff.md") and int(nxt("specs/README.md")) >= 97
