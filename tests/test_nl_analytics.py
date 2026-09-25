"""Acceptance tests for spec 0080 — natural-language analytics.

Covers T-001 through T-010: plan, interpret, authorize, execute, chart,
insights, narrate, respond. Each test names the acceptance criterion it
proves.
"""

from __future__ import annotations

import pytest

from quantsmith.pipelines.dashboard_spec import DashboardSpec
from quantsmith.pipelines.metrics_semantic_layer import Fact, MetricDefinition, SemanticLayer
from quantsmith.pipelines.powerbi_profile import render_powerbi
from quantsmith.nl_analytics.plan import (
    Clarification,
    Comparison,
    Filter,
    PlanError,
    QueryPlan,
    TimeWindow,
    describe_plan,
    validate_plan,
)
from quantsmith.nl_analytics.interpret import (
    InterpretContext,
    KeywordInterpreter,
    interpret,
    register_interpreter,
)
from quantsmith.nl_analytics.authorize import AccessPolicy, authorize_clarification, authorize_plan
from quantsmith.nl_analytics.execute import execute
from quantsmith.nl_analytics.chart import ChartError, choose_chart, is_minimal_vega_lite, to_markdown_table, to_panel, to_vega_lite
from quantsmith.nl_analytics.insights import compute_insights
from quantsmith.nl_analytics.narrate import default_caveats, ground, template_narrative
from quantsmith.nl_analytics.respond import AnswerContext, ChatResponse, ResponseError, answer


@pytest.fixture
def layer():
    layer = SemanticLayer()
    layer.define(
        name="funding_cost", owner="treasury", grain="day",
        dimensions=("desk", "currency"), source="cost", agg="sum",
    )
    layer.define(name="revenue", owner="finance", grain="day", dimensions=("desk",), source="rev", agg="sum")
    return layer


def _plan(metric="funding_cost", dims=(), filters=(), window=None, comparison=None, interpreter="test/1"):
    return QueryPlan(
        metric=metric, dimensions=dims, filters=filters,
        window=window or TimeWindow(1, 7, "day"), comparison=comparison,
        rank=None, defaults_applied=(), interpreter=interpreter,
    )


# --- AC-001: governed plan, no SQL/code field -------------------------------


def test_ac001_plan_is_governed_and_has_no_sql_field(layer):
    plan = _plan(dims=("desk",))
    validate_plan(plan, layer)
    fields = {f for f in plan.__dataclass_fields__}
    assert fields == {"metric", "dimensions", "filters", "window", "comparison", "rank",
                      "defaults_applied", "interpreter"}
    assert not any("sql" in f.lower() or "code" in f.lower() or "expr" in f.lower() for f in fields)
    with pytest.raises(PlanError):
        _plan(dims=("desk", "currency", "region"))  # over MAX_DIMENSIONS


def test_ac001_filter_and_window_reject_bad_values():
    with pytest.raises(PlanError):
        Filter(dimension="desk", op="eq", values=())
    with pytest.raises(PlanError):
        Filter(dimension="desk", op="eq", values=("a", "b"))
    with pytest.raises(PlanError):
        TimeWindow(start_period=10, end_period=1, grain="day")
    with pytest.raises(PlanError):
        Comparison(kind="prior_insight")  # needs a reference


# --- AC-002: unknown metric / undeclared dimension -> clarification --------


def test_ac002_unknown_metric_or_dimension_rejected(layer):
    with pytest.raises(PlanError):
        validate_plan(_plan(metric="no_such_metric"), layer)
    with pytest.raises(PlanError):
        validate_plan(_plan(dims=("no_such_dim",)), layer)
    with pytest.raises(PlanError):
        validate_plan(_plan(filters=(Filter("no_such_dim", "eq", ("x",)),)), layer)


def test_ac002_keyword_interpreter_returns_clarification_for_unknown_question(layer):
    ctx = InterpretContext(today_period=100)
    result = interpret("what about the widget factor", layer, ctx)
    assert isinstance(result, Clarification)
    assert result.candidates == ()


def test_ac002_ambiguous_question_lists_candidates(layer):
    layer.define(name="funding_spread", owner="x", grain="day", dimensions=(), source="fs", agg="sum")
    ctx = InterpretContext(today_period=100, default_window_periods=7)
    result = interpret("funding cost spread", layer, ctx)
    assert isinstance(result, Clarification)
    assert set(result.candidates) == {"funding_cost", "funding_spread"}


# --- AC-003: default window applied and echoed ------------------------------


def test_ac003_default_window_applied_and_echoed(layer):
    ctx = InterpretContext(today_period=100, default_window_periods=7, default_grain="day")
    plan = interpret("funding cost", layer, ctx)
    assert isinstance(plan, QueryPlan)
    assert plan.defaults_applied == ("window",)
    assert plan.window.end_period == 100 and plan.window.start_period == 94
    assert "defaults applied: window" in describe_plan(plan)


def test_ac003_no_default_window_configured_is_a_clarification(layer):
    ctx = InterpretContext(today_period=100)  # no default_window_periods
    result = interpret("funding cost", layer, ctx)
    assert isinstance(result, Clarification)
    assert "no time window" in result.reason


def test_ac003_relative_phrase_needs_no_default(layer):
    ctx = InterpretContext(today_period=100)
    plan = interpret("funding cost yesterday", layer, ctx)
    assert isinstance(plan, QueryPlan)
    assert plan.defaults_applied == ()
    assert plan.window.start_period == plan.window.end_period == 99


# --- AC-004: one validator for every interpreter ----------------------------


class _StubGoodInterpreter:
    name = "stub-good"

    def interpret(self, question, layer, context):
        return _plan(dims=("desk",), interpreter=self.name)


class _StubBadInterpreter:
    name = "stub-bad"

    def interpret(self, question, layer, context):
        return _plan(dims=("region",), interpreter=self.name)  # undeclared dimension


def test_ac004_llm_style_interpreter_shares_the_same_validator(layer):
    register_interpreter(_StubGoodInterpreter())
    register_interpreter(_StubBadInterpreter())
    ctx = InterpretContext(today_period=100)

    good = interpret("anything", layer, ctx, interpreter=_StubGoodInterpreter())
    validate_plan(good, layer)  # does not raise

    bad = interpret("anything", layer, ctx, interpreter=_StubBadInterpreter())
    with pytest.raises(PlanError):
        validate_plan(bad, layer)


# --- AC-005: restricted metric masked as nonexistent ------------------------


def test_ac005_restricted_metric_is_masked():
    policy = AccessPolicy(metric_levels={"funding_cost": "restricted"})
    plan = _plan()
    result = authorize_plan(plan, policy, "internal")
    assert isinstance(result, Clarification)
    assert result.reason == "no known metric matched the question"

    clarification = Clarification(reason="ambiguous", candidates=("funding_cost", "revenue"))
    masked = authorize_clarification(clarification, policy, "internal")
    assert masked.candidates == ("revenue",)


def test_ac005_public_metric_passes_through():
    policy = AccessPolicy()
    plan = _plan()
    assert authorize_plan(plan, policy, "public") is plan


def test_ac005_restricted_dimension_is_dropped_not_named():
    policy = AccessPolicy(dimension_levels={"currency": "restricted"})
    plan = _plan(dims=("desk", "currency"))
    result = authorize_plan(plan, policy, "internal")
    assert isinstance(result, QueryPlan)
    assert result.dimensions == ("desk",)


# --- AC-006: execute respects as-of, hashes, reports counts -----------------


def test_ac006_execute_respects_as_of_and_hashes(layer):
    rows = [
        Fact(period=1, dims={"desk": "rates"}, measures={"cost": 10.0}),
        Fact(period=5, dims={"desk": "rates"}, measures={"cost": 20.0}),
        Fact(period=9, dims={"desk": "rates"}, measures={"cost": 999.0}),  # outside window
        Fact(period=6, dims={"desk": "rates"}, measures={"cost": 999.0}),  # after as_of
    ]
    plan = _plan(window=TimeWindow(1, 7, "day"))

    result = execute(plan, layer, reader=lambda p: rows, as_of=5)
    assert result.row_count == 2
    assert result.latest_period == 5
    assert result.values[()] == pytest.approx(30.0)

    result2 = execute(plan, layer, reader=lambda p: rows, as_of=5)
    assert result2.content_hash == result.content_hash

    result3 = execute(_plan(window=TimeWindow(1, 7, "day")), layer, reader=lambda p: rows, as_of=6)
    assert result3.content_hash != result.content_hash
    assert result3.row_count == 3


def test_ac006_execute_groups_by_declared_dimensions(layer):
    rows = [
        Fact(period=1, dims={"desk": "rates", "currency": "usd"}, measures={"cost": 10.0}),
        Fact(period=1, dims={"desk": "fx", "currency": "usd"}, measures={"cost": 5.0}),
        Fact(period=1, dims={"desk": "rates", "currency": "eur"}, measures={"cost": 7.0}),
    ]
    plan = _plan(dims=("desk", "currency"), window=TimeWindow(1, 1, "day"))
    result = execute(plan, layer, reader=lambda p: rows, as_of=1)
    assert result.values[("rates", "usd")] == pytest.approx(10.0)
    assert result.values[("fx", "usd")] == pytest.approx(5.0)
    assert result.values[("rates", "eur")] == pytest.approx(7.0)


def test_ac006_execute_applies_filters(layer):
    rows = [
        Fact(period=1, dims={"desk": "rates"}, measures={"cost": 10.0}),
        Fact(period=1, dims={"desk": "fx"}, measures={"cost": 5.0}),
    ]
    plan = _plan(filters=(Filter("desk", "eq", ("rates",)),), window=TimeWindow(1, 1, "day"))
    result = execute(plan, layer, reader=lambda p: rows, as_of=1)
    assert result.row_count == 1
    assert result.values[()] == pytest.approx(10.0)


# --- AC-007 / AC-008: chart form rule and Panel promotion -------------------


def test_ac007_form_rule_by_result_shape(layer):
    rows_ts = [Fact(period=p, dims={"desk": "rates"}, measures={"cost": float(p)}) for p in range(1, 6)]
    plan_ts = _plan(window=TimeWindow(1, 5, "day"))
    result_ts = execute(plan_ts, layer, reader=lambda p: rows_ts, as_of=5)
    chart_ts = choose_chart(result_ts, layer)
    assert chart_ts.chart_type == "line"

    rows_bar = [
        Fact(period=1, dims={"desk": "rates"}, measures={"cost": 10.0}),
        Fact(period=1, dims={"desk": "fx"}, measures={"cost": 30.0}),
    ]
    plan_bar = _plan(dims=("desk",), window=TimeWindow(1, 1, "day"))
    result_bar = execute(plan_bar, layer, reader=lambda p: rows_bar, as_of=1)
    chart_bar = choose_chart(result_bar, layer)
    assert chart_bar.chart_type == "bar" and chart_bar.sort == "descending"
    assert [row["desk"] for row in chart_bar.data] == ["fx", "rates"]  # sorted descending by value

    plan_kpi = _plan(window=TimeWindow(1, 1, "day"))
    result_kpi = execute(plan_kpi, layer, reader=lambda p: [rows_bar[0]], as_of=1)
    chart_kpi = choose_chart(result_kpi, layer)
    assert chart_kpi.chart_type == "kpi"

    plan_table = _plan(dims=("desk", "currency"), window=TimeWindow(1, 1, "day"))
    rows_table = [
        Fact(period=1, dims={"desk": "rates", "currency": "usd"}, measures={"cost": 1.0}),
        Fact(period=1, dims={"desk": "fx", "currency": "eur"}, measures={"cost": 2.0}),
    ]
    result_table = execute(plan_table, layer, reader=lambda p: rows_table, as_of=1)
    chart_table = choose_chart(result_table, layer)
    assert chart_table.chart_type == "table"

    layer.define(name="revenue2", owner="finance", grain="day", dimensions=(), source="rev2", agg="sum")
    plan_y = _plan(metric="revenue2", window=TimeWindow(1, 1, "day"))
    result_y = execute(plan_y, layer, reader=lambda p: [Fact(1, {}, {"rev2": 4.0})], as_of=1)
    chart_scatter = choose_chart(result_kpi, layer, compare=result_y)
    assert chart_scatter.chart_type == "scatter"

    for c in (chart_ts, chart_bar, chart_kpi, chart_table, chart_scatter):
        assert c.title and c.footnote and c.alt_text


def test_ac008_chart_promotes_to_panel_and_renders(layer):
    rows = [Fact(period=1, dims={"desk": "rates"}, measures={"cost": 10.0}),
            Fact(period=1, dims={"desk": "fx"}, measures={"cost": 5.0})]
    plan = _plan(dims=("desk",), window=TimeWindow(1, 1, "day"))
    result = execute(plan, layer, reader=lambda p: rows, as_of=1)
    chart = choose_chart(result, layer)
    panel = to_panel(chart)
    spec = DashboardSpec(title="Test", dataset="nl_analytics", panels=(panel,))
    payload = render_powerbi(spec)
    assert payload is not None


def test_ac007_vega_lite_and_markdown_are_minimal_and_reflect_data(layer):
    rows = [Fact(period=1, dims={"desk": "rates"}, measures={"cost": 10.0})]
    plan = _plan(window=TimeWindow(1, 1, "day"))
    result = execute(plan, layer, reader=lambda p: rows, as_of=1)
    chart = choose_chart(result, layer, units="usd")
    vl = to_vega_lite(chart)
    assert is_minimal_vega_lite(vl)
    md = to_markdown_table(chart)
    assert "value" in md and "10" in md


def test_chart_rejects_bad_type():
    from dataclasses import replace as _replace
    rows = [Fact(period=1, dims={}, measures={"cost": 1.0})]
    layer2 = SemanticLayer()
    layer2.define(name="x", owner="o", grain="day", dimensions=(), source="cost", agg="sum")
    plan = QueryPlan(metric="x", dimensions=(), filters=(), window=TimeWindow(1, 1, "day"),
                     comparison=None, rank=None, defaults_applied=(), interpreter="t/1")
    result = execute(plan, layer2, reader=lambda p: rows, as_of=1)
    chart = choose_chart(result, layer2)
    with pytest.raises(ChartError):
        _replace(chart, chart_type="pie")


# --- AC-009: insights match hand computation --------------------------------


def test_ac009_insights_match_hand_computed(layer):
    rows_now = [
        Fact(period=2, dims={"desk": "rates"}, measures={"cost": 30.0}),
        Fact(period=2, dims={"desk": "fx"}, measures={"cost": 10.0}),
    ]
    rows_prior = [
        Fact(period=1, dims={"desk": "rates"}, measures={"cost": 20.0}),
        Fact(period=1, dims={"desk": "fx"}, measures={"cost": 20.0}),
    ]
    plan = _plan(dims=("desk",), window=TimeWindow(2, 2, "day"))
    result = execute(plan, layer, reader=lambda p: rows_now, as_of=2)
    comparison_plan = _plan(dims=("desk",), window=TimeWindow(1, 1, "day"))
    comparison = execute(comparison_plan, layer, reader=lambda p: rows_prior, as_of=2)

    insights = compute_insights(result, comparison)
    by_kind = {i.kind: i for i in insights}

    assert by_kind["level"].values["level"] == pytest.approx(40.0)
    assert by_kind["change"].values["absolute"] == pytest.approx(0.0)  # 40 - 40

    # Force a real net change to check contributor shares sum to it.
    rows_now2 = [
        Fact(period=2, dims={"desk": "rates"}, measures={"cost": 50.0}),
        Fact(period=2, dims={"desk": "fx"}, measures={"cost": 10.0}),
    ]
    result2 = execute(plan, layer, reader=lambda p: rows_now2, as_of=2)
    insights2 = compute_insights(result2, comparison)
    by_kind2 = {i.kind: i for i in insights2}
    change = by_kind2["change"].values["absolute"]
    assert change == pytest.approx(20.0)
    shares = by_kind2["contributor"].values["shares"]
    assert sum(shares.values()) == pytest.approx(1.0, abs=1e-9)
    diffs = by_kind2["contributor"].values["diffs"]
    assert sum(diffs.values()) == pytest.approx(change, abs=1e-9)

    concentration = by_kind2["concentration"].values
    assert concentration["top_share"] == pytest.approx(50.0 / 60.0)


def test_ac009_trend_and_outlier_match_hand_computed(layer):
    values = [10.0, 10.0, 10.0, 10.0, 100.0]  # clear outlier at the end
    rows = [Fact(period=i + 1, dims={}, measures={"cost": v}) for i, v in enumerate(values)]
    plan = _plan(window=TimeWindow(1, 5, "day"))
    result = execute(plan, layer, reader=lambda p: rows, as_of=5)
    insights = compute_insights(result)
    by_kind = {i.kind: i for i in insights}

    assert by_kind["trend"].values["first_value"] == pytest.approx(10.0)
    assert by_kind["trend"].values["last_value"] == pytest.approx(100.0)
    assert "increasing" in by_kind["trend"].statement

    flagged = by_kind["outlier"].values["flagged"]
    assert len(flagged) == 1 and flagged[0]["period"] == 5

    flat_rows = [Fact(period=i + 1, dims={}, measures={"cost": 10.0}) for i in range(5)]
    flat_result = execute(plan, layer, reader=lambda p: flat_rows, as_of=5)
    flat_insights = {i.kind: i for i in compute_insights(flat_result)}
    assert flat_insights["outlier"].values["flagged"] == []


# --- AC-010 / AC-011: grounding, causal flags, caveats ----------------------


def test_ac010_grounding_rejects_unbacked_numbers_and_flags_causal(layer):
    rows = [Fact(period=1, dims={}, measures={"cost": 42.0})]
    plan = _plan(window=TimeWindow(1, 1, "day"))
    result = execute(plan, layer, reader=lambda p: rows, as_of=1)
    insights = compute_insights(result)

    good = ground("The level is 42.", insights, result)
    assert good.ok

    bad = ground("The level is 999.", insights, result)
    assert not bad.ok
    assert "999" in bad.unbacked_numbers

    causal = ground("The level is 42 because of a rule change.", insights, result)
    assert causal.causal_flags == ("because",)


def test_ac011_caveats_triggered(layer):
    rows = [Fact(period=1, dims={}, measures={"cost": 1.0})]
    plan = _plan(window=TimeWindow(1, 1, "day"))
    result = execute(plan, layer, reader=lambda p: rows, as_of=1)

    assert any("synthetic" in c for c in default_caveats(result, synthetic=True))
    assert any("Small sample" in c for c in default_caveats(result, min_sample_rows=5))

    stale_rows = [Fact(period=1, dims={}, measures={"cost": 1.0})]
    plan_stale = _plan(window=TimeWindow(1, 1, "day"))
    stale_result = execute(plan_stale, layer, reader=lambda p: stale_rows, as_of=10)
    assert any("stale" in c for c in default_caveats(stale_result, staleness_periods=2))

    partial_rows = [
        Fact(period=1, dims={"desk": "rates"}, measures={"cost": 1.0}),
        Fact(period=1, dims={"desk": "fx"}, measures={"cost": 1.0}),
        Fact(period=2, dims={"desk": "rates"}, measures={"cost": 1.0}),
    ]
    plan_partial = _plan(dims=("desk",), window=TimeWindow(1, 2, "day"))
    partial_result = execute(plan_partial, layer, reader=lambda p: partial_rows, as_of=2)
    assert any("partial" in c for c in default_caveats(partial_result))


# --- AC-012 / AC-022: end-to-end response, typed status on every path -------


def _context(layer, reader, as_of=10, **overrides):
    ctx = dict(
        layer=layer, reader=reader, as_of=as_of,
        interpret_context=InterpretContext(today_period=as_of, default_window_periods=5, default_grain="day"),
    )
    ctx.update(overrides)
    return AnswerContext(**ctx)


def test_ac012_chat_response_complete(layer):
    rows = [Fact(period=p, dims={"desk": "rates"}, measures={"cost": float(p)}) for p in range(6, 11)]
    ctx = _context(layer, reader=lambda p: rows)
    response = answer("funding cost", ctx)

    assert response.status == "answered"
    assert response.headline and response.insights
    assert response.chart is not None
    assert is_minimal_vega_lite(response.vega_lite)
    assert response.markdown_table
    assert "funding_cost" in response.plan_echo
    assert any("owner" in c for c in response.citations)
    assert any(str(ctx.as_of) in c for c in response.citations)


def test_ac022_typed_status_on_every_failure_path(layer):
    rows = [Fact(period=10, dims={"desk": "rates"}, measures={"cost": 1.0})]

    # clarification_needed: unknown metric
    r1 = answer("no such thing at all", _context(layer, reader=lambda p: rows))
    assert r1.status == "clarification_needed" and r1.reason and r1.chart is None

    # masked: restricted metric
    policy = AccessPolicy(metric_levels={"funding_cost": "restricted"})
    r2 = answer("funding cost", _context(layer, reader=lambda p: rows, access_policy=policy, viewer_clearance="public"))
    assert r2.status == "masked" and r2.reason and r2.chart is None

    # empty: no rows in the window
    r3 = answer("funding cost", _context(layer, reader=lambda p: [], as_of=10))
    assert r3.status == "empty" and r3.reason and r3.chart is None

    # stale: latest data far before as-of
    old_rows = [Fact(period=1, dims={"desk": "rates"}, measures={"cost": 1.0})]
    ctx_stale = _context(layer, reader=lambda p: old_rows, as_of=100,
                         interpret_context=InterpretContext(today_period=100, default_window_periods=200))
    r4 = answer("funding cost", ctx_stale)
    assert r4.status == "stale" and r4.reason and r4.chart is None

    for r in (r1, r2, r3, r4):
        assert r.status in ("clarification_needed", "masked", "empty", "stale")
        with pytest.raises(ResponseError):
            ChatResponse(status=r.status, reason="", headline="", insights=(), chart=None,
                        vega_lite=None, markdown_table=None, plan_echo="", caveats=(), citations=())
        with pytest.raises(ResponseError):
            from quantsmith.nl_analytics.chart import ChartSpec as _CS
            ChatResponse(status=r.status, reason="x", headline="", insights=(),
                        chart=object.__new__(_CS), vega_lite=None, markdown_table=None,
                        plan_echo="", caveats=(), citations=())
