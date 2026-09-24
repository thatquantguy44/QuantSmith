"""Acceptance tests for spec 0080 — natural-language analytics.

Covers T-001 through T-006: plan, interpret, authorize, execute. Each test
names the acceptance criterion it proves.
"""

from __future__ import annotations

import pytest

from quantsmith.pipelines.metrics_semantic_layer import Fact, MetricDefinition, SemanticLayer
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
