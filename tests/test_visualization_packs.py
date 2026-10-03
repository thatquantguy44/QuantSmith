"""Spec 0093 acceptance and adversarial integration tests (AC-001–AC-014)."""
import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest

from quantsmith.nl_analytics.authorize import AccessPolicy
from quantsmith.nl_analytics.plan import Filter, QueryPlan, TimeWindow
from quantsmith.pipelines.metrics_semantic_layer import Fact, SemanticLayer
from quantsmith.visualization_packs import (
    Benchmark, VisualizationError, bind_claim, build_story, collect_evidence,
    dashboard_handoff, load_catalog, render_html, render_json, render_markdown,
    validate_claim, validate_pack,
)
from quantsmith.visualization_packs.example import run_example

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def catalog():
    return load_catalog(ROOT)


def plan(metric, dims=(), start=12, end=12, filters=()):
    return QueryPlan(metric, tuple(dims), tuple(filters), TimeWindow(start, end, "month"), None, None, (), "test/0093")


def collect(catalog, metric="revenue", pid="finance_performance", view="level", eid="revenue",
            dims=(), start=12, end=12, rows=None, agg=None, layer=None, **kwargs):
    if layer is None:
        layer = SemanticLayer()
        meta = next(m for m in catalog.analytics[pid]["metrics"] if m["name"] == metric)
        layer.define(name=metric, owner="test-owner", grain="month", dimensions=tuple(dims), source=metric,
                     agg=agg or ("mean" if meta["additivity"] == "non_additive" else "sum"))
    if rows is None:
        rows = [Fact(p, {d: "A" for d in dims}, {metric: float(p)}) for p in range(start, end + 1)]
    options = dict(source="Synthetic test fixture", as_of=12, synthetic=True)
    options.update(kwargs)
    return collect_evidence(eid, pid, plan(metric, dims, start, end), view, catalog=catalog,
                            layer=layer, reader=lambda _: rows, **options), layer


@pytest.mark.parametrize("mutation", ["schema", "duplicate", "metric", "dimension", "reviewer", "override", "malformed", "review", "causal_action"])
def test_ac001_invalid_catalog_contracts(catalog, mutation):
    """AC-001: malformed references and contracts give actionable errors."""
    p = copy.deepcopy(catalog.packs["credit_risk"])
    section = p["recipes"][0]["sections"][0]
    if mutation == "schema": p["schema_version"] = "future"
    if mutation == "duplicate": p["recipes"][1]["recipe_id"] = p["recipes"][0]["recipe_id"]
    if mutation == "metric": section["metric"] = "undeclared"
    if mutation == "dimension": section["dimensions"] = ["unknown"]
    if mutation == "reviewer": p["reviewer_agents"] = ["agents/missing-reviewer"]
    if mutation == "override": section["unit"] = "inferred"
    if mutation == "malformed": p["recipes"] = [None, {}]
    if mutation == "review": p["review"] = {"status": "reviewed", "reviewer": "", "reviewed_on": "2026-02-30"}
    if mutation == "causal_action": p["recipes"][0]["action"] = "Revenue rose because of a policy change."
    assert validate_pack(p, catalog.analytics, ROOT)


@pytest.mark.parametrize("pid,metric", [("credit_risk", "pd"), ("market_risk", "var")])
def test_ac002_nonadditive_sum_and_attribution_refused(catalog, pid, metric):
    """AC-002: no arithmetic or attribution loophole for rates and quantiles."""
    evidence, _ = collect(catalog, metric, pid, agg="sum")
    assert evidence.status == "invalid" and "non-additive" in evidence.reason
    dim = catalog.analytics[pid]["dimensions"][0]["name"]
    evidence, _ = collect(catalog, metric, pid, view="attribution", dims=(dim,))
    assert evidence.status == "invalid" and "suppresses" in evidence.reason


def test_ac002_snapshot_is_not_summed_over_time(catalog):
    """AC-002: same snapshot observations are valid as a trend, invalid as a total."""
    evidence, _ = collect(catalog, "ead", "credit_risk", start=10)
    assert evidence.status == "invalid" and "across time" in evidence.reason
    trend, _ = collect(catalog, "ead", "credit_risk", view="trend", start=10)
    assert trend.status == "ready"
    assert trend.result.values[()] == 12 and sum(trend.result.series[p][()] for p in [10, 11, 12]) == 33


def test_ac003_selection_and_ambiguity(catalog):
    """AC-003: order invariant selection, unknown and overlapping scopes explicit."""
    tags = catalog.analytics["finance_performance"]["source_domains"]
    assert catalog.select(tags, "comparison") == catalog.select(list(reversed(tags)), "comparison")
    assert catalog.select(tags, "comparison").status == "selected"
    assert catalog.select(["unknown"], "comparison").status == "unavailable"
    duplicate = copy.deepcopy(catalog.packs["finance_performance"])
    duplicate["pack_id"] = "another_finance"
    catalog.packs["another_finance"] = duplicate
    assert catalog.select(tags, "comparison").status == "clarification_needed"


def test_ac004_ac007_executive_findings_and_action_are_bound():
    """AC-004, AC-007: bounded summary and labelled investigation, not invented causality."""
    story = run_example(ROOT)["finance_performance"]
    assert story.status == "ready" and len(story.supporting_findings) <= 3
    assert story.headline == story.sections[0].observation
    assert story.action_evidence_ids == tuple(e.evidence_id for e in story.evidence)
    assert all(s.interpretation.endswith("?") for s in story.sections)
    assert "Arithmetic attribution" in " ".join(story.caveats)
    assert "caused" not in story.headline and "because" not in story.headline


def recipe_fixture(catalog, pid, recipe):
    layer, evidence = SemanticLayer(), []
    for section in recipe["sections"]:
        metric, dims = section["metric"], tuple(section["dimensions"])
        base = next(m for m in catalog.analytics[pid]["metrics"] if m["name"] == metric)
        layer.define(name=metric, owner="fixture", grain="month", dimensions=dims, source=metric,
                     agg="mean" if base["additivity"] == "non_additive" else "sum")
        start = 10 if section["view"] == "trend" else 12
        periods = range(start, 13)
        rows = [Fact(p, {d: label for d in dims}, {metric: value}) for p in periods for label, value in [("A", 12.5), ("B", 8.5)]]
        e, _ = collect(catalog, metric, pid, section["view"], section["section_id"], dims, start,
                       rows=rows, layer=layer)
        evidence.append(e)
        if section["view"] == "comparison":
            baseline, _ = collect(catalog, metric, pid, "comparison", section["section_id"] + "_baseline",
                                  dims, 11, 11, rows=[Fact(11, {}, {metric: 14})], layer=layer)
            evidence.append(baseline)
    return evidence, layer


@pytest.mark.parametrize("pid", ["asset_management", "rates_fixed_income", "credit_risk", "finance_performance", "aml_financial_crime", "operations_settlement", "economics_macro"])
def test_ac010_all_fourteen_recipes_produce_governed_stories(catalog, pid):
    """AC-010: every authored recipe has runnable, domain-valid evidence."""
    for recipe in catalog.packs[pid]["recipes"]:
        evidence, layer = recipe_fixture(catalog, pid, recipe)
        story = build_story(catalog, pid, recipe["recipe_id"], evidence, layer)
        assert story.status == "ready", story.reason
        assert story.to_dict() == build_story(catalog, pid, recipe["recipe_id"], list(reversed(evidence)), layer).to_dict()
        assert len(story.sections) == len(recipe["sections"])


def test_ac005_chart_shapes_and_fallback(catalog):
    """AC-005: KPI, line, bar, two-dimensional table, and declared fallback."""
    from quantsmith.nl_analytics.chart import choose_chart
    for dims, view, start, expected in [((), "level", 12, "kpi"), ((), "trend", 10, "line"), (("segment",), "breakdown", 12, "bar"), (("segment", "scenario"), "breakdown", 12, "table")]:
        e, layer = collect(catalog, dims=dims, view=view, start=start)
        chart = choose_chart(e.result, layer, units=e.unit)
        assert chart.chart_type == expected and chart.units and chart.alt_text and chart.footnote
    recipe = catalog.packs["rates_fixed_income"]["recipes"][0]
    es, layer = recipe_fixture(catalog, "rates_fixed_income", recipe)
    story = build_story(catalog, "rates_fixed_income", recipe["recipe_id"], es, layer)
    assert story.sections[0].chart.chart_type == "table"
    assert "Maturity ordering" in " ".join(story.caveats)


@pytest.mark.parametrize("field,value", [("metric", "net_interest_income"), ("unit", "pct"), ("as_of", 11), ("period", 11), ("population", ("B",)), ("evidence_id", "other")])
def test_ac006_same_number_in_wrong_scope_is_rejected(catalog, field, value):
    """AC-006: exact binding, not a bag of numbers."""
    e, _ = collect(catalog)
    claim = bind_claim(e)
    assert validate_claim(claim, e) == ()
    assert validate_claim(replace(claim, **{field: value}), e)


def test_ac006_mutation_after_collection_is_detected(catalog):
    e, _ = collect(catalog)
    claim = bind_claim(e)
    e.result.values[()] += 1
    assert validate_claim(claim, e)


def test_ac008_benchmark_requires_exact_binding(catalog):
    """AC-008: policy-free output has no verdict; supplied policy is traceable."""
    recipe = catalog.packs["economics_macro"]["recipes"][0]
    es, layer = recipe_fixture(catalog, "economics_macro", recipe)
    story = build_story(catalog, "economics_macro", recipe["recipe_id"], es, layer)
    assert story.sections[0].assessment is None
    benchmark = Benchmark("declared-policy", es[0].evidence_id, es[0].digest, es[0].unit, 15, "lower")
    story = build_story(catalog, "economics_macro", recipe["recipe_id"], es, layer, benchmarks=[benchmark])
    assert story.sections[0].assessment["policy_id"] == "declared-policy"
    assert story.sections[0].assessment["meets_policy"] is True
    bad = replace(benchmark, unit="currency")
    assert build_story(catalog, "economics_macro", recipe["recipe_id"], es, layer, benchmarks=[bad]).status == "invalid"


def test_ac009_artifacts_preserve_evidence_and_caveats():
    """AC-009: rendered, portable, and dashboard artifacts retain their companion evidence."""
    story = run_example(ROOT)["finance_performance"]
    handoff = dashboard_handoff(story, "example-finance")
    assert handoff["dashboard_spec"]["panels"][0]["metric"] == "revenue"
    assert handoff["story"]["caveats"] == story.caveats
    for output in [render_json(story), render_markdown(story), render_html(story)]:
        assert "Synthetic" in output and "Unreviewed" in output
        assert all(e.digest in output for e in story.evidence)
    assert "<svg role='img'" in render_html(story) and "<table>" in render_html(story)


def test_ac010_coverage_is_explicit(catalog):
    """AC-010: exactly seven initial domains; every other domain explicitly uncovered."""
    coverage = catalog.coverage()
    assert len(coverage) == 40 and list(coverage.values()).count("covered") == 7
    assert coverage["liquidity_risk"] == "uncovered"
    assert len({catalog.analytics[p]["family"] for p in catalog.packs}) == 7


@pytest.mark.parametrize("state", ["masked", "empty", "stale", "clarification_needed"])
def test_ac011_upstream_refusal_never_becomes_a_story(catalog, state):
    """AC-011: upstream refusal survives, with no chart, metric, or source leak."""
    e, layer = collect(catalog, "ead", "credit_risk", "breakdown", "exposure", ("portfolio",), upstream_status=state)
    story = build_story(catalog, "credit_risk", "exposure_profile", [e], layer)
    assert story.status == state and not story.sections and not story.headline and not story.evidence
    assert "Synthetic test fixture" not in render_json(story)


@pytest.mark.parametrize("restricted", ["metric", "dimension", "filter", "dataset"])
def test_ac011_authorization_precedes_reader(catalog, restricted):
    layer = SemanticLayer()
    layer.define(name="revenue", owner="test", grain="month", dimensions=("segment",), source="revenue")
    query = plan("revenue", ("segment",) if restricted == "dimension" else (), filters=(Filter("segment", "eq", ("secret",)),) if restricted == "filter" else ())
    policy = AccessPolicy(metric_levels={"revenue": "restricted"} if restricted == "metric" else {},
                          dimension_levels={"segment": "restricted"} if restricted in ("dimension", "filter") else {},
                          dataset_level="restricted" if restricted == "dataset" else "public")
    def reader(_):
        pytest.fail("Denied evidence must never reach the reader")
    e = collect_evidence("private", "finance_performance", query, "level", catalog=catalog, layer=layer,
                         reader=reader, source="secret-source", as_of=12, access_policy=policy)
    assert e.status == "masked" and e.result is None and not e.source


def test_ac011_empty_stale_and_nonfinite_refused(catalog):
    assert collect(catalog, rows=[])[0].status == "empty"
    assert collect(catalog, start=8, end=8)[0].status == "stale"
    assert collect(catalog, rows=[Fact(12, {}, {"revenue": float("nan")})])[0].status == "invalid"
    assert collect(catalog, rows=[Fact(12, {}, {})])[0].status == "invalid"


def test_ac012_example_reproduces_and_refuses_invalid_arithmetic():
    """AC-012: actual pipeline through charts and narrative, with its own negative case."""
    first, second = run_example(ROOT), run_example(ROOT)
    for pid in ("finance_performance", "credit_risk", "economics_macro"):
        assert first[pid].status == "ready"
        assert render_json(first[pid]) == render_json(second[pid])
        assert render_html(first[pid]) == render_html(second[pid])
    assert first["refused_pd_sum"].status == "invalid"
    assert not first["refused_pd_sum"].sections


def test_ac013_missing_or_incompatible_comparator(catalog):
    """AC-013: missing/invalid baseline stays unavailable; no invented zero."""
    recipe = catalog.packs["finance_performance"]["recipes"][1]
    es, layer = recipe_fixture(catalog, "finance_performance", recipe)
    story = build_story(catalog, "finance_performance", recipe["recipe_id"], es[:1], layer)
    assert story.status == "unavailable" and "revenue_baseline" in story.reason
    baseline = replace(es[1], unit="pct")
    baseline = replace(baseline, digest=baseline.fingerprint())
    assert build_story(catalog, "finance_performance", recipe["recipe_id"], [es[0], baseline], layer).status == "invalid"


def test_ac014_import_does_not_modify_existing_contracts():
    """AC-014: opt-in API preserves existing dashboard vocabulary/version."""
    from quantsmith.pipelines.dashboard_spec import CHART_TYPES, SCHEMA_VERSION
    assert SCHEMA_VERSION == "1.0"
    assert CHART_TYPES == ("bar", "line", "area", "scatter", "table", "kpi", "gauge", "map")


def test_html_escapes_caller_supplied_labels(catalog):
    recipe = catalog.packs["credit_risk"]["recipes"][0]
    e, layer = collect(catalog, "ead", "credit_risk", "breakdown", "exposure", ("portfolio",),
                       rows=[Fact(12, {"portfolio": "<script>alert('x')</script>"}, {"ead": 100})])
    story = build_story(catalog, "credit_risk", recipe["recipe_id"], [e], layer)
    html = render_html(story)
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_missing_filter_dimensions_and_future_windows(catalog):
    e, _ = collect(catalog, dims=("segment",), view="breakdown", rows=[Fact(12, {}, {"revenue": 12})])
    assert e.status == "invalid"
    assert collect(catalog, end=13)[0].status == "invalid"


def test_governed_ratio_preserves_numerator_and_denominator(catalog):
    layer = SemanticLayer()
    layer.define(name="pd", owner="test", grain="month", dimensions=(), numerator="defaults", denominator="count")
    rows = [Fact(12, {}, {"defaults": 1, "count": 10}), Fact(12, {}, {"defaults": 2, "count": 90})]
    e, _ = collect(catalog, "pd", "credit_risk", layer=layer, rows=rows)
    assert e.status == "ready" and e.result.values[()] == 0.03
    assert collect(catalog, "pd", "credit_risk", layer=layer, rows=[Fact(12, {}, {"defaults": 1, "count": 0})])[0].status == "invalid"
