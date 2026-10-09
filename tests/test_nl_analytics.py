"""Acceptance tests for spec 0080 — natural-language analytics.

Covers T-001 through T-010: plan, interpret, authorize, execute, chart,
insights, narrate, respond. Each test names the acceptance criterion it
proves.
"""

from __future__ import annotations

import datetime
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from quantsmith.pipelines.dashboard_spec import DashboardSpec
from quantsmith.pipelines.access_control import Roster, _parse_roster_text, roles_for, validate_roster
from quantsmith.pipelines.metrics_semantic_layer import Fact, SemanticLayer
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
    LLMInterpreter,
    interpret,
    register_interpreter,
)
from quantsmith.nl_analytics.authorize import AccessPolicy, authorize_clarification, authorize_plan
from quantsmith.nl_analytics.execute import execute
from quantsmith.nl_analytics.chart import ChartError, choose_chart, is_minimal_vega_lite, to_markdown_table, to_panel, to_vega_lite
from quantsmith.nl_analytics.insights import compute_insights
from quantsmith.nl_analytics.narrate import LLMNarrator, default_caveats, ground
from quantsmith.nl_analytics.respond import AnswerContext, ChatResponse, ResponseError, WriteBackRequest, answer


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

    # masked: restricted metric, reported exactly like an unknown one (REQ-004)
    policy = AccessPolicy(metric_levels={"funding_cost": "restricted"})
    r2 = answer("funding cost", _context(layer, reader=lambda p: rows, access_policy=policy, viewer_clearance="public"))
    assert r2.status == "clarification_needed" and r2.reason and r2.chart is None
    assert (r2.status, r2.reason) == (r1.status, r1.reason)

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
        assert r.status in ("clarification_needed", "empty", "stale")
        with pytest.raises(ResponseError):
            ChatResponse(status=r.status, reason="", headline="", insights=(), chart=None,
                        vega_lite=None, markdown_table=None, plan_echo="", caveats=(), citations=())
        with pytest.raises(ResponseError):
            from quantsmith.nl_analytics.chart import ChartSpec as _CS
            ChatResponse(status=r.status, reason="x", headline="", insights=(),
                        chart=object.__new__(_CS), vega_lite=None, markdown_table=None,
                        plan_echo="", caveats=(), citations=())


# --- T-011/T-012/T-020: write-back contract, publish/reverse, SQLite -------


from quantsmith.nl_analytics.writeback import (
    SCHEMA_COLUMNS,
    WriteBackContract,
    WriteBackError,
    build_records,
    default_contract,
    load_contract,
    prior_insights,
    publish,
    reverse,
)
from quantsmith.nl_analytics.writeback_sqlite import SQLiteWriter, open_writer
from quantsmith.nl_analytics.respond import comparison_key


class _RecordingWriter:
    """An in-memory stand-in for the `WriteBackWriter` protocol."""

    def __init__(self):
        self.rows = {}

    def write(self, records):
        written = 0
        for r in records:
            if r["record_key"] not in self.rows:
                self.rows[r["record_key"]] = dict(r)
                written += 1
        return written

    def reverse(self, run_id, reversed_at):
        count = 0
        for r in self.rows.values():
            if r["run_id"] == run_id and r["reversed_at"] is None:
                r["reversed_at"] = reversed_at
                count += 1
        return count

    def read(self, key):
        metric, *dims = key.split("|")
        dims_json = json.dumps(dims, sort_keys=True)
        return [r for r in self.rows.values() if r["metric"] == metric and r["dimensions_json"] == dims_json]


def _built_records(layer, run_id="run-1", created_at=10, value=42.0):
    rows = [Fact(period=10, dims={"desk": "rates"}, measures={"cost": value})]
    plan = _plan(dims=(), window=TimeWindow(10, 10, "day"))
    result = execute(plan, layer, reader=lambda p: rows, as_of=10)
    insight_set = compute_insights(result)
    records = build_records(
        plan, result, insight_set, run_id=run_id, question="funding cost",
        metric_definition_hash="hash-of-def", author_handle="anon-1",
        interpreter_mode="keyword/1", created_at=created_at,
    )
    return plan, result, records


def test_ac013_writeback_contract_rejections(layer):
    with pytest.raises(WriteBackError):
        WriteBackContract(name="x", columns=("only", "two"), idempotency_key="record_key",
                          source_tables_denied=())

    contract = default_contract("test", source_tables_denied=("fact_*", "source_*"))
    _, _, records = _built_records(layer)
    writer = _RecordingWriter()

    with pytest.raises(WriteBackError):
        publish(records, contract, writer, target_table="fact_positions", dry_run=True)

    bad_records = [dict(records[0])]
    del bad_records[0]["headline"]  # missing a required column
    with pytest.raises(WriteBackError):
        publish(bad_records, contract, writer, dry_run=True)

    bad_records2 = [dict(records[0], extra_column="nope")]
    with pytest.raises(WriteBackError):
        publish(bad_records2, contract, writer, dry_run=True)


def test_load_contract_parses_template_fields(tmp_path):
    filled = tmp_path / "test_writeback_contract.md"
    filled.write_text(
        "# Write-Back Contract: test\n\n"
        "## Target\n\n- **Name:** test — a test target\n\n"
        "## Approval\n\n- **`auto_approve`:** `true` — always commit\n\n"
        "## Source-Table Deny-List\n\n- `fact_*`\n- `source_*`\n\n"
        "## Reversal\n\n- some other section\n",
        encoding="utf-8",
    )
    contract = load_contract(str(filled))
    assert contract.name == "test"
    assert contract.auto_approve is True
    assert contract.source_tables_denied == ("fact_*", "source_*")
    assert contract.targets_denied_table("fact_positions")
    assert not contract.targets_denied_table("other_table")

    with pytest.raises(WriteBackError):
        load_contract("templates/data/writeback_contract.md")  # unfilled <target-name>


# --- AC-014 / AC-015: dry-run default, idempotent commit, approval, reversal


@pytest.mark.parametrize("make_writer", [
    lambda: _RecordingWriter(),
    lambda: SQLiteWriter(sqlite3.connect(":memory:"), default_contract("sqlite-test")),
])
def test_ac014_dry_run_default_and_idempotent_commit(layer, make_writer):
    contract = default_contract("sqlite-test", source_tables_denied=("fact_*",))
    _, _, records = _built_records(layer)
    writer = make_writer()

    dry = publish(records, contract, writer, dry_run=True)
    assert dry.status == "dry_run"
    assert dry.records == tuple(dict(r) for r in records)
    assert dry.written_count == 0

    committed = publish(records, contract, writer, dry_run=False, approved=True)
    assert committed.status == "committed"
    assert committed.written_count == len(records)

    committed_again = publish(records, contract, writer, dry_run=False, approved=True)
    assert committed_again.written_count == 0


def test_ac015_approval_required_and_reversal_by_run_id(layer):
    contract = default_contract("t")
    _, _, records = _built_records(layer, run_id="run-approve")
    writer = _RecordingWriter()

    with pytest.raises(WriteBackError):
        publish(records, contract, writer, dry_run=False, approved=False)

    auto_contract = default_contract("t", auto_approve=True)
    outcome = publish(records, auto_contract, writer, dry_run=False, approved=False)
    assert outcome.status == "committed"

    reversed_outcome = reverse("run-approve", 999, auto_contract, writer)
    assert reversed_outcome.status == "reversed"
    assert reversed_outcome.written_count == len(records)
    assert all(r["reversed_at"] == 999 for r in writer.rows.values() if r["run_id"] == "run-approve")

    with pytest.raises(WriteBackError):
        reverse("", 1, auto_contract, writer)


# --- AC-016: "since yesterday" uses the persisted, as-of-bounded prior insight


def test_ac016_since_yesterday_uses_prior_insight_as_of(layer):
    contract = default_contract("t", auto_approve=True)
    writer = _RecordingWriter()

    # Two persisted days for the same governed question.
    plan1, result1, records1 = _built_records(layer, run_id="run-yesterday", created_at=1)
    publish(records1, contract, writer, dry_run=False)
    plan2, result2, records2 = _built_records(layer, run_id="run-today", created_at=2)
    publish(records2, contract, writer, dry_run=False)
    key = comparison_key(plan1)

    # Bounded strictly to "yesterday" (as_of=1): only run-yesterday is visible,
    # even though run-today already exists in the store.
    prior_yesterday = prior_insights(writer.read, key, as_of=1)
    assert prior_yesterday is not None and prior_yesterday.run_id == "run-yesterday"

    # A wider as-of (2, "today") legitimately sees the most recent persisted
    # record, including one created today — a record created strictly after
    # the as-of is what must never leak in, not same-day records in general.
    prior_today = prior_insights(writer.read, key, as_of=2)
    assert prior_today is not None and prior_today.run_id == "run-today"

    # Nothing existed before either record was created.
    assert prior_insights(writer.read, key, as_of=0) is None

    # Reversal is bounded the same way: reversed at period 1 means invisible
    # from period 1 onward, but the reversal itself never leaks backwards.
    reverse("run-yesterday", 1, contract, writer)
    assert prior_insights(writer.read, key, as_of=0) is None  # still never existed at 0
    assert prior_insights(writer.read, key, as_of=1) is None  # reversed_at=1 is not > as_of=1

    # The store is never mutated by a read.
    before = {k: dict(v) for k, v in writer.rows.items()}
    prior_insights(writer.read, key, as_of=2)
    assert before == writer.rows


def test_ac016_respond_yesterday_reference_shifts_as_of_by_one(layer):
    """The 'since yesterday' phrase respond.py resolves shifts the lookup's
    as-of back one period, so a same-day persisted record never stands in
    for yesterday's (AC-016's own scenario, exercised through answer())."""
    contract = default_contract("t", auto_approve=True)
    writer = _RecordingWriter()
    # Different levels so the test can tell which one respond.py actually used.
    plan_yday, _, records_yday = _built_records(layer, run_id="run-yday", created_at=9, value=42.0)
    publish(records_yday, contract, writer, dry_run=False)
    plan_today, _, records_today = _built_records(layer, run_id="run-today", created_at=10, value=999.0)
    publish(records_today, contract, writer, dry_run=False)

    def lookup(key, as_of):
        return prior_insights(writer.read, key, as_of)

    # The KeywordInterpreter reads "yesterday" in the question as both a
    # relative window (yesterday-only, period 9) and a prior_insight
    # comparison — rows must exist at period 9 for the plan's own window.
    rows = [Fact(period=9, dims={"desk": "rates"}, measures={"cost": 100.0})]
    ctx = AnswerContext(
        layer=layer, reader=lambda p: rows, as_of=10,
        interpret_context=InterpretContext(today_period=10, default_grain="day"),
        prior_insight_lookup=lookup,
    )
    response = answer("funding cost since yesterday", ctx)
    assert response.status == "answered"
    change = next(i for i in response.insights if i.kind == "change")
    assert change.values["prior"] == pytest.approx(42.0)  # run-yday's level, not run-today's 999


def test_writeback_sqlite_file_target(tmp_path, layer):
    contract = default_contract("file-test", auto_approve=True)
    db_path = str(tmp_path / "nl_analytics.sqlite3")
    writer = open_writer(db_path, contract)

    plan, result, records = _built_records(layer, run_id="run-file")
    committed = publish(records, contract, writer, dry_run=False)
    assert committed.written_count == len(records)

    reopened = open_writer(db_path, contract)
    key = comparison_key(plan)
    prior = prior_insights(reopened.read, key, as_of=10)
    assert prior is not None and prior.run_id == "run-file"


# --- T-014: 0070 envelope + replay -----------------------------------------


from quantsmith.orchestration.foundation import replay_envelope_file
from quantsmith.nl_analytics.envelope import emit_answer_evidence


def _answered(layer):
    rows = [Fact(period=p, dims={"desk": "rates"}, measures={"cost": float(p)}) for p in range(6, 11)]
    plan = _plan(window=TimeWindow(6, 10, "day"))
    result = execute(plan, layer, reader=lambda p: rows, as_of=10)
    chart = choose_chart(result, layer)
    insight_set = compute_insights(result)
    ctx = AnswerContext(layer=layer, reader=lambda p: rows, as_of=10,
                        interpret_context=InterpretContext(today_period=10, default_window_periods=5))
    response = answer("funding cost", ctx)
    return plan, result, chart, insight_set, response


def test_ac017_replay_is_byte_identical(layer, tmp_path):
    plan, result, chart, insight_set, response = _answered(layer)
    out1 = tmp_path / "run1"
    envelope1 = emit_answer_evidence(
        "funding cost", plan, result, chart, insight_set, response, out1,
        run_id="run-envelope-1", started_at="2026-01-01T00:00:00Z",
    )
    report = replay_envelope_file(envelope1)
    assert report.status == "replayed", report.findings
    assert report.output_diffs == ()
    assert report.non_reproducible_dependencies == ()

    out2 = tmp_path / "run2"
    envelope2 = emit_answer_evidence(
        "funding cost", plan, result, chart, insight_set, response, out2,
        run_id="run-envelope-1", started_at="2026-01-01T00:00:00Z",
    )
    for name in ("answer_payload.json", "prompt_manifest.json", "context_manifest.json",
                 "assumptions.jsonl", "evaluation_harness.json", "audit_events.jsonl", "run_envelope.json"):
        assert (out1 / name).read_bytes() == (out2 / name).read_bytes(), name


def test_envelope_llm_interpreter_mode_marks_non_deterministic(layer, tmp_path):
    plan, result, chart, insight_set, response = _answered(layer)
    out = tmp_path / "run_llm"
    envelope = emit_answer_evidence(
        "funding cost", plan, result, chart, insight_set, response, out,
        run_id="run-llm-1", started_at="2026-01-01T00:00:00Z",
        interpreter_mode="llm:anthropic/claude",
    )
    report = replay_envelope_file(envelope)
    assert any(d["event_type"] == "model_invocation" for d in
              [dict(e) for e in json.loads(f'[{",".join((out / "audit_events.jsonl").read_text().splitlines())}]')])
    # Non-deterministic without a fixture_path is honestly reported, not hidden.
    assert report.status in ("non_reproducible", "replayed")
    if report.status == "non_reproducible":
        assert any(d["event_type"] == "model_invocation" for d in report.non_reproducible_dependencies)


def test_answer_can_opt_in_to_envelope_emission(layer, tmp_path):
    rows = [Fact(period=p, dims={"desk": "rates"}, measures={"cost": float(p)}) for p in range(6, 11)]
    ctx = AnswerContext(
        layer=layer, reader=lambda p: rows, as_of=10,
        interpret_context=InterpretContext(today_period=10, default_window_periods=5),
        envelope_dir=str(tmp_path / "run"), run_id="run-opt-in-1",
    )
    response = answer("funding cost", ctx)
    assert response.status == "answered"
    assert response.envelope_uri is not None
    report = replay_envelope_file(response.envelope_uri)
    assert report.status == "replayed"

    # Without envelope_dir, no files are written -- no side effects (RISK-004).
    before = set(tmp_path.iterdir())
    ctx_no_envelope = AnswerContext(
        layer=layer, reader=lambda p: rows, as_of=10,
        interpret_context=InterpretContext(today_period=10, default_window_periods=5),
    )
    answer("funding cost", ctx_no_envelope)
    assert set(tmp_path.iterdir()) == before

    # envelope_dir without run_id is refused, not silently skipped.
    with pytest.raises(ResponseError):
        answer("funding cost", AnswerContext(
            layer=layer, reader=lambda p: rows, as_of=10,
            interpret_context=InterpretContext(today_period=10, default_window_periods=5),
            envelope_dir=str(tmp_path / "run2"),
        ))


# --- AC-019: standard library only, no credentials, no network -------------


def test_ac019_stdlib_only_no_credentials_or_network():
    import ast
    import sys
    from pathlib import Path

    pkg_dir = Path("src/quantsmith/nl_analytics")
    py_files = sorted(pkg_dir.glob("*.py"))
    assert py_files, "expected nl_analytics package files to scan"

    stdlib = set(sys.stdlib_module_names)
    network_patterns = ("socket", "urllib.request", "http.client", "requests", "ftplib", "smtplib", "asyncio")
    credential_re = __import__("re").compile(
        r"(?i)\b(password|passwd|api[_-]?key|secret[_-]?key|access[_-]?key|auth[_-]?token)\s*="
    )
    conn_string_re = __import__("re").compile(r"[a-zA-Z][\w+.-]*://[^\s\"']*:[^\s\"'@]*@")

    for path in py_files:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level > 0:
                    continue  # relative import within the package itself
                names = [node.module] if node.module else []
            else:
                continue
            for name in names:
                if name is None:
                    continue
                root = name.split(".")[0]
                assert root in stdlib or root == "quantsmith", (
                    f"{path}: non-stdlib, non-quantsmith import {name!r}"
                )
                assert name not in network_patterns and root not in network_patterns, (
                    f"{path}: network-capable import {name!r}"
                )

        assert not credential_re.search(source), f"{path}: looks like a hardcoded credential"
        assert not conn_string_re.search(source), f"{path}: looks like a connection string"


# --- AC-020: audit redaction and LLM adapter privacy flags -----------------


def test_ac020_audit_redaction_and_privacy_flags(layer, tmp_path):
    plan, result, chart, insight_set, response = _answered(layer)
    out = tmp_path / "run_pii"
    secret_question = "what was the funding cost for client Jane Doe's account"
    envelope = emit_answer_evidence(
        secret_question, plan, result, chart, insight_set, response, out,
        run_id="run-pii-1", started_at="2026-01-01T00:00:00Z",
        interpreter_mode="llm:anthropic/claude",
        dataset_privacy={"contains_pii": True},
    )

    payload = json.loads((out / "answer_payload.json").read_text())
    assert payload["question"] != secret_question
    assert secret_question not in (out / "prompt.md").read_text()
    assert secret_question not in (out / "run_envelope.json").read_text()
    assert secret_question not in (out / "context_manifest.json").read_text()
    assert secret_question not in (out / "audit_events.jsonl").read_text()
    import hashlib
    assert payload["question_hash"] == f"sha256:{hashlib.sha256(secret_question.encode('utf-8')).hexdigest()}"

    events = [json.loads(line) for line in (out / "audit_events.jsonl").read_text().splitlines()]
    interpret_event = next(e for e in events if e["event_type"] == "model_invocation")
    assert interpret_event["payload_ref"]["privacy"] == {
        "contains_pii": True, "contains_mnpi": False, "contains_restricted_positions": False,
    }

    manifest = json.loads((out / "prompt_manifest.json").read_text())
    assert manifest["privacy"]["contains_pii"] is True

    report = replay_envelope_file(envelope)
    assert report.status in ("replayed", "non_reproducible")

    # No privacy classification declared: the question passes through in full.
    out_public = tmp_path / "run_public"
    emit_answer_evidence(
        secret_question, plan, result, chart, insight_set, response, out_public,
        run_id="run-public-1", started_at="2026-01-01T00:00:00Z",
    )
    payload_public = json.loads((out_public / "answer_payload.json").read_text())
    assert payload_public["question"] == secret_question


# --- AC-021: 100k-row benchmark ---------------------------------------------


def test_ac021_benchmark_100k_rows(layer):
    """T-017: the deterministic path (excluding data fetch/LLM calls) answers
    a question over 100,000 synthetic fact rows in under 2s. A trivial
    calibration workload measures the runner's own speed first, so a
    genuinely under-provisioned CI runner is skipped with a recorded reason
    rather than failing on wall-clock noise it has no control over."""
    import time

    desks = [f"desk-{i}" for i in range(200)]
    currencies = ("USD", "EUR", "JPY", "GBP", "CHF")
    rows = [
        Fact(period=period, dims={"desk": desk, "currency": currency}, measures={"cost": float(period)})
        for period in range(1, 101)
        for desk in desks
        for currency in currencies
    ]
    assert len(rows) == 100_000

    calibration_start = time.perf_counter()
    sum(i * i for i in range(2_000_000))
    calibration_elapsed = time.perf_counter() - calibration_start
    if calibration_elapsed > 0.5:
        pytest.skip(
            f"runner under-provisioned for a timing benchmark "
            f"(calibration workload took {calibration_elapsed:.2f}s)"
        )

    ctx = AnswerContext(
        layer=layer, reader=lambda p: rows, as_of=100,
        interpret_context=InterpretContext(today_period=100, default_window_periods=100),
    )

    start = time.perf_counter()
    response = answer("funding cost by desk", ctx)
    elapsed = time.perf_counter() - start

    assert response.status == "answered"
    assert response.chart is not None
    assert elapsed < 2.0, f"deterministic path over 100k rows took {elapsed:.2f}s (NFR-005 budget: 2s)"


# --- T-018: answer() wired end to end to write-back -------------------------


def test_answer_writeback_dry_run_by_default(layer):
    rows = [Fact(period=10, dims={"desk": "rates"}, measures={"cost": 42.0})]
    contract = default_contract("cli_default")
    writer = _RecordingWriter()
    ctx = AnswerContext(
        layer=layer, reader=lambda p: rows, as_of=10,
        interpret_context=InterpretContext(today_period=10, default_window_periods=1),
        run_id="run-wb-1",
        writeback=WriteBackRequest(contract=contract, writer=writer),
    )
    response = answer("funding cost", ctx)
    assert response.status == "answered"
    assert response.run_id == "run-wb-1"
    assert response.writeback is not None
    assert response.writeback.status == "dry_run"
    assert response.writeback.written_count == 0
    assert writer.rows == {}  # dry run never calls the writer


def test_answer_writeback_commits_and_is_idempotent(layer):
    rows = [Fact(period=10, dims={"desk": "rates"}, measures={"cost": 42.0})]
    contract = default_contract("cli_default", auto_approve=True)
    writer = _RecordingWriter()

    def _ctx():
        return AnswerContext(
            layer=layer, reader=lambda p: rows, as_of=10,
            interpret_context=InterpretContext(today_period=10, default_window_periods=1),
            run_id="run-wb-2",
            writeback=WriteBackRequest(contract=contract, writer=writer, dry_run=False),
        )

    first = answer("funding cost", _ctx())
    assert first.writeback.status == "committed"
    assert first.writeback.written_count > 0
    first_count = len(writer.rows)

    second = answer("funding cost", _ctx())
    assert second.writeback.status == "committed"
    assert second.writeback.written_count == 0  # identical run_id -> identical keys
    assert len(writer.rows) == first_count


def test_answer_writeback_without_approval_is_write_rejected(layer):
    rows = [Fact(period=10, dims={"desk": "rates"}, measures={"cost": 42.0})]
    contract = default_contract("cli_default")  # auto_approve=False
    writer = _RecordingWriter()
    ctx = AnswerContext(
        layer=layer, reader=lambda p: rows, as_of=10,
        interpret_context=InterpretContext(today_period=10, default_window_periods=1),
        run_id="run-wb-3",
        writeback=WriteBackRequest(contract=contract, writer=writer, dry_run=False, approved=False),
    )
    response = answer("funding cost", ctx)
    assert response.status == "write_rejected"
    assert response.reason
    assert response.chart is None  # AC-022: a non-answer never carries a chart
    assert writer.rows == {}


def test_answer_writeback_without_run_id_is_refused(layer):
    rows = [Fact(period=10, dims={"desk": "rates"}, measures={"cost": 42.0})]
    contract = default_contract("cli_default")
    ctx = AnswerContext(
        layer=layer, reader=lambda p: rows, as_of=10,
        interpret_context=InterpretContext(today_period=10, default_window_periods=1),
        writeback=WriteBackRequest(contract=contract, writer=_RecordingWriter()),
    )
    with pytest.raises(ResponseError):
        answer("funding cost", ctx)


def test_answer_writeback_against_sqlite(layer, tmp_path):
    rows = [Fact(period=10, dims={"desk": "rates"}, measures={"cost": 42.0})]
    contract = default_contract("cli_default", auto_approve=True)
    writer = open_writer(str(tmp_path / "nl_analytics.db"), contract)
    ctx = AnswerContext(
        layer=layer, reader=lambda p: rows, as_of=10,
        interpret_context=InterpretContext(today_period=10, default_window_periods=1),
        run_id="run-wb-sqlite-1",
        writeback=WriteBackRequest(contract=contract, writer=writer, dry_run=False),
    )
    response = answer("funding cost", ctx)
    assert response.writeback.status == "committed"
    assert response.writeback.written_count > 0
    assert writer.read(comparison_key(_plan()))


# --- T-018: cli.py and examples/nl_analytics/ -------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[1]
_EXAMPLE_DIR = _REPO_ROOT / "examples" / "nl_analytics"


def _run_cli(*args, env=None):
    full_env = {**os.environ, "PYTHONPATH": str(_REPO_ROOT / "src")}
    if env:
        full_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "quantsmith.nl_analytics.cli", *args],
        cwd=str(_REPO_ROOT), capture_output=True, text=True, env=full_env,
    )


def test_cli_ask_answers_from_the_worked_example(tmp_path):
    result = _run_cli(
        "ask", "what is total funding cost",
        "--registry", str(_EXAMPLE_DIR / "registry.json"),
        "--data", str(_EXAMPLE_DIR / "data.json"),
        "--today", "1", "--window", "1", "--json",
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "answered"
    assert payload["headline"] == "funding_cost is 250 as of period 1."
    assert payload["writeback"] is None  # no --db/--publish: no side effects


def test_cli_transcript_reproduces_the_committed_sample_response(tmp_path):
    """Runs the exact three-day transcript from transcript.md and checks day
    3's JSON output matches the committed sample_response.json byte-for-byte
    on every field (T-018)."""
    db = tmp_path / "nl_analytics_demo.db"

    day1 = _run_cli(
        "ask", "what is total funding cost",
        "--registry", str(_EXAMPLE_DIR / "registry.json"),
        "--data", str(_EXAMPLE_DIR / "data.json"),
        "--today", "1", "--window", "1", "--db", str(db),
        "--publish", "--commit", "--approve", "--run-id", "run-day1", "--author", "desk-analyst",
    )
    assert day1.returncode == 0, day1.stderr
    assert "write-back: committed (1 record(s), run_id=run-day1)" in day1.stdout

    day2 = _run_cli(
        "ask", "what is total funding cost by desk",
        "--registry", str(_EXAMPLE_DIR / "registry.json"),
        "--data", str(_EXAMPLE_DIR / "data.json"),
        "--today", "2", "--window", "1", "--db", str(db),
    )
    assert day2.returncode == 0, day2.stderr
    assert "write-back:" not in day2.stdout  # not published

    day3 = _run_cli(
        "ask", "what is total funding cost since yesterday",
        "--registry", str(_EXAMPLE_DIR / "registry.json"),
        "--data", str(_EXAMPLE_DIR / "data.json"),
        "--today", "3", "--window", "1", "--db", str(db),
        "--publish", "--commit", "--approve", "--run-id", "run-day3", "--author", "desk-analyst", "--json",
    )
    assert day3.returncode == 0, day3.stderr
    actual = json.loads(day3.stdout)
    expected = json.loads((_EXAMPLE_DIR / "sample_response.json").read_text(encoding="utf-8"))
    assert actual == expected


def test_cli_publish_without_run_id_errors(tmp_path):
    result = _run_cli(
        "ask", "what is total funding cost",
        "--registry", str(_EXAMPLE_DIR / "registry.json"),
        "--data", str(_EXAMPLE_DIR / "data.json"),
        "--today", "1", "--window", "1", "--db", str(tmp_path / "x.db"),
        "--publish", "--commit", "--approve",
    )
    assert result.returncode == 2
    assert "--run-id" in result.stderr


def test_cli_publish_without_db_errors():
    result = _run_cli(
        "ask", "what is total funding cost",
        "--registry", str(_EXAMPLE_DIR / "registry.json"),
        "--data", str(_EXAMPLE_DIR / "data.json"),
        "--today", "1", "--window", "1", "--publish", "--run-id", "run-x",
    )
    assert result.returncode == 2
    assert "--db" in result.stderr


def test_cli_domain_resolves_packs_and_empty_packs_root_errors(tmp_path):
    args = (
        "ask", "what is total funding cost",
        "--registry", str(_EXAMPLE_DIR / "registry.json"),
        "--data", str(_EXAMPLE_DIR / "data.json"),
        "--today", "1", "--window", "1", "--domain", "treasury", "--json",
    )
    missing = _run_cli(*args, "--packs-root", str(tmp_path))
    assert missing.returncode == 2
    assert "no analytics domain packs under" in missing.stderr
    assert str(tmp_path / "knowledge" / "analytics_packs") in missing.stderr
    assert missing.stdout == ""

    # No --packs-root: the repo's local catalog (cwd is the repo root).
    found = _run_cli(*args)
    assert found.returncode == 0, found.stderr
    assert json.loads(found.stdout)["domain_pack_source"].startswith("local analytics domain packs")


def test_example_disclosure_exists_and_is_declared():
    disclosure = _REPO_ROOT / "docs" / "0080_synthetic_data_disclosure.md"
    assert disclosure.exists()
    text = disclosure.read_text(encoding="utf-8")
    assert "examples/nl_analytics" in text
    assert "Generation method" in text


# --- AC-023..AC-026: analytics domain packs (T-021, T-022) -----------------

import copy
from dataclasses import replace

from quantsmith.nl_analytics.domain import (
    MetricPolicy,
    generic_additivity,
    resolve_policy,
    select,
)
from quantsmith.nl_analytics.narrate import template_narrative
from quantsmith.pipelines.analytics_packs import load_packs

_PACKS = tuple(load_packs("."))

# A 2y/10y/30y curve over two years: 2y moves 4.00% -> 4.20% (+20 bp).
_CURVE = {1: {"2y": 4.00, "10y": 4.10, "30y": 4.30}, 2: {"2y": 4.20, "10y": 4.15, "30y": 4.32}}


def _rates_layer():
    layer = SemanticLayer()
    layer.define(name="yield", owner="rates", grain="year", dimensions=("tenor",), source="ytm", agg="mean")
    layer.define(name="notional", owner="rates", grain="year", dimensions=("desk",), source="face", agg="sum")
    return layer


def _curve_rows(tenors=("2y", "10y", "30y")):
    return [Fact(period=p, dims={"tenor": t}, measures={"ytm": y})
            for p, curve in _CURVE.items() for t, y in curve.items() if t in tenors]


def _yearly_context(layer, rows, **kwargs):
    return AnswerContext(
        layer=layer, reader=lambda p: rows, as_of=2,
        interpret_context=InterpretContext(today_period=2, default_grain="year", default_window_periods=1),
        **kwargs,
    )


def test_ac023_pack_units_and_additivity_applied():
    layer = _rates_layer()
    ctx = _yearly_context(layer, _curve_rows(("2y",)), dataset_domains=("fixed_income_rates",), domain_packs=_PACKS)
    # "YTM" is a rates-pack synonym: pack vocabulary extends interpretation.
    response = answer("YTM yoy", ctx)
    assert response.status == "answered", response.reason
    assert response.domain_packs == ("rates_fixed_income",)
    change = {i.kind: i for i in response.insights}["change"]
    assert change.values["bps"] == pytest.approx(20.0)
    assert change.values["percent"] is None
    assert "+20 bp" in change.statement
    assert "5%" not in change.statement and "+5" not in change.statement
    assert any("+20 bp, not +5%" in c for c in response.caveats)  # the pack's own caveat
    assert response.chart.units == "%"
    assert ground(template_narrative(response.insights), response.insights).ok

    # var under market_risk: no contributor, no concentration, no cross-desk sum.
    risk = SemanticLayer()
    risk.define(name="var", owner="risk", grain="year", dimensions=("desk",), source="var", agg="sum")
    rows = [Fact(period=p, dims={"desk": d}, measures={"var": v})
            for p, d, v in ((1, "rates", 5.0), (1, "fx", 3.0), (2, "rates", 6.0), (2, "fx", 4.0))]
    ctx = _yearly_context(risk, rows, dataset_domains=("market_risk",), domain_packs=_PACKS)
    response = answer("var by desk yoy", ctx)
    assert response.status == "answered", response.reason
    kinds = {i.kind for i in response.insights}
    assert "contributor" not in kinds and "concentration" not in kinds
    level = {i.kind: i for i in response.insights}["level"]
    assert "level" not in level.values  # no firm total
    assert level.values["levels"] == {"fx": 4.0, "rates": 6.0}
    assert "10" not in response.headline  # 6 + 4 is never stated
    assert {i.kind: i for i in response.insights}["change"].values["absolute"] == {"fx": 1.0, "rates": 1.0}
    assert any("Not shown for var: contributor, concentration" in c for c in response.caveats)

    # Ungrouped var over desk-level rows: the total is caveated as a cross-group sum.
    response = answer("var yoy", ctx)
    assert any("it is not a var of any of them" in c for c in response.caveats)


def test_non_additive_metric_is_never_summed_across_groups():
    """The original defect: yields by tenor were summed into one 'level'."""
    layer = _rates_layer()
    rows = _curve_rows()
    plan = _plan(metric="yield", dims=("tenor",), window=TimeWindow(2, 2, "year"))
    result = execute(plan, layer, reader=lambda p: rows, as_of=2)
    policy = resolve_policy(layer, "yield")  # generic: a mean is not additive
    assert policy.additivity == "non_additive"
    by_kind = {i.kind: i for i in compute_insights(result, policy=policy)}
    assert set(by_kind) == {"level"}
    assert by_kind["level"].values["levels"] == {"10y": 4.15, "2y": 4.2, "30y": 4.32}
    assert "12.67" not in by_kind["level"].statement  # 4.20 + 4.15 + 4.32
    assert ground(by_kind["level"].statement, list(by_kind.values()), result).ok  # "10y" is a label

    # Ungrouped, the level is the metric's own value over all rows, not a sum.
    flat = execute(_plan(metric="yield", window=TimeWindow(2, 2, "year")), layer, reader=lambda p: rows, as_of=2)
    level = compute_insights(flat, policy=policy)[0]
    assert level.values["level"] == pytest.approx((4.20 + 4.15 + 4.32) / 3)

    # A ratio metric's level is the ratio of the sums, not the sum of the ratios.
    ratio = SemanticLayer()
    ratio.define(name="sum_cost", owner="o", grain="day", dimensions=("desk",), source="cost")
    ratio.define(name="sum_rev", owner="o", grain="day", dimensions=("desk",), source="rev")
    ratio.define(name="margin", owner="o", grain="day", dimensions=("desk",), numerator="cost", denominator="rev")
    rrows = [Fact(1, {"desk": "a"}, {"cost": 1.0, "rev": 2.0}), Fact(1, {"desk": "b"}, {"cost": 3.0, "rev": 4.0})]
    rres = execute(_plan(metric="margin", dims=("desk",), window=TimeWindow(1, 1, "day")), ratio, lambda p: rrows, 1)
    assert rres.total == pytest.approx(4.0 / 6.0)
    assert compute_insights(rres, policy=resolve_policy(ratio, "margin"))[0].values["levels"] == {"a": 0.5, "b": 0.75}


def test_semi_additive_level_is_the_latest_period_not_a_window_sum():
    layer = _rates_layer()
    rows = [Fact(p, {"desk": d}, {"face": v}) for p in (1, 2, 3) for d, v in (("a", 100.0), ("b", 50.0))]
    plan = _plan(metric="notional", dims=("desk",), window=TimeWindow(1, 3, "year"))
    result = execute(plan, layer, reader=lambda p: rows, as_of=3)
    policy = resolve_policy(layer, "notional", select(("fixed_income_rates",), _PACKS))
    assert policy.additivity == "semi_additive"
    by_kind = {i.kind: i for i in compute_insights(result, policy=policy)}
    assert by_kind["level"].values["level"] == pytest.approx(150.0)  # not 450 over three years
    assert by_kind["level"].values["period"] == 3
    assert by_kind["concentration"].values["top_share"] == pytest.approx(100.0 / 150.0)
    chart = choose_chart(result, layer, snapshot=not policy.sums_across_time)
    assert [row["value"] for row in chart.data] == [100.0, 50.0]


def test_ac024_cross_pack_term_conflict_clarifies(layer):
    ctx = AnswerContext(
        layer=layer, reader=lambda p: [], as_of=1,
        interpret_context=InterpretContext(today_period=1, default_window_periods=1),
        dataset_domains=("equities", "fx"), domain_packs=_PACKS,
    )
    response = answer("vol by pair", ctx)
    assert response.status == "clarification_needed"
    assert "implied_volatility" in response.reason and "realized_volatility" in response.reason
    assert response.chart is None


def test_ac025_draft_pack_caveat_and_writeback_gate():
    layer = _rates_layer()
    rows = _curve_rows(("2y",))
    writer = _RecordingWriter()
    wb = WriteBackRequest(contract=default_contract("cli_default"), writer=writer)

    ctx = _yearly_context(layer, rows, dataset_domains=("fixed_income_rates",), domain_packs=_PACKS)
    chat = answer("yield yoy", ctx)
    assert any("Unreviewed domain pack: rates_fixed_income" in c for c in chat.caveats)

    refused = answer("yield yoy", replace(ctx, run_id="run-pack-1", writeback=wb))
    assert refused.status == "write_rejected"
    assert "rates_fixed_income" in refused.reason
    assert writer.rows == {}

    reviewed = []
    for p in _PACKS:
        p = copy.deepcopy(p)
        p["review"] = {"status": "reviewed", "reviewer": "Test Reviewer", "reviewed_on": "2026-10-01", "notes": ""}
        reviewed.append(p)
    ok = answer("yield yoy", replace(ctx, domain_packs=tuple(reviewed), run_id="run-pack-1", writeback=wb))
    assert ok.status == "answered"
    assert ok.writeback is not None and ok.writeback.status == "dry_run"
    assert not any("Unreviewed" in c for c in ok.caveats)


def test_ac026_generic_fallback_and_restrict_only():
    layer = _rates_layer()
    ctx = _yearly_context(layer, _curve_rows(("2y",)), dataset_domains=("no_such_domain",), domain_packs=_PACKS)
    response = answer("yield yoy", ctx)
    assert response.domain_packs == ()
    assert any("generic behavior was used" in c for c in response.caveats)

    strictness = {"additive": 0, "semi_additive": 1, "non_additive": 2}
    for pack in _PACKS:
        selection = select(tuple(pack["source_domains"]), [pack])
        for m in pack["metrics"]:
            for agg in ("sum", "mean"):
                lay = SemanticLayer()
                lay.define(name=m["name"], owner="o", grain="day", source="x", agg=agg)
                generic, packed = resolve_policy(lay, m["name"]), resolve_policy(lay, m["name"], selection)
                assert set(generic.suppressed) <= set(packed.suppressed), (pack["pack_id"], m["name"])
                assert strictness[packed.additivity] >= strictness[generic.additivity]
                assert strictness[packed.additivity] >= strictness[m["additivity"]]
                assert generic_additivity(lay, m["name"]) == generic.additivity


def test_default_policy_keeps_legacy_additive_behavior(layer):
    assert MetricPolicy().sums_across_dimensions and MetricPolicy().sums_across_time
    rows = [Fact(2, {"desk": "rates"}, {"cost": 30.0}), Fact(2, {"desk": "fx"}, {"cost": 10.0})]
    result = execute(_plan(dims=("desk",), window=TimeWindow(2, 2, "day")), layer, lambda p: rows, 2)
    assert compute_insights(result) == compute_insights(result, policy=resolve_policy(layer, "funding_cost"))


def test_ac027_pack_source_reported_and_missing_catalog_raises(tmp_path, monkeypatch):
    from quantsmith.nl_analytics.envelope import emit_answer_evidence
    from quantsmith.pipelines.analytics_packs import resolve_packs

    monkeypatch.chdir(tmp_path)  # no local catalog: the bundled defaults
    packs, source = resolve_packs()
    assert source.kind == "bundled"
    layer = _rates_layer()
    rows = _curve_rows(("2y",))
    ctx = _yearly_context(layer, rows, dataset_domains=("fixed_income_rates",),
                          domain_packs=tuple(packs), domain_pack_source=source)
    response = answer("yield yoy", ctx)
    assert response.status == "answered"
    assert response.domain_pack_source == source.describe()
    cited = [c for c in response.citations if c.startswith("domain packs:")]
    assert cited and "bundled" in cited[0] and source.version in cited[0] and source.content_hash in cited[0]

    plan = _plan(metric="yield", window=TimeWindow(2, 2, "year"))
    result = execute(plan, layer, reader=lambda p: rows, as_of=2)
    emit_answer_evidence("yield yoy", plan, result, response.chart, response.insights, response,
                         tmp_path / "env", run_id="run-src-1", started_at="2026-01-01T00:00:00Z")
    payload = json.loads((tmp_path / "env" / "answer_payload.json").read_text(encoding="utf-8"))
    assert payload["domain_pack_source"] == source.describe()
    assert payload["domain_packs"] == ["rates_fixed_income"]

    # Packs passed without a source are still identified, by a hash of what was given.
    unsourced = answer("yield yoy", replace(ctx, domain_pack_source=None))
    assert unsourced.domain_pack_source.startswith("caller-supplied analytics domain packs")

    # No pack applied: nothing to cite.
    generic = answer("yield yoy", replace(ctx, dataset_domains=("no_such_domain",)))
    assert generic.domain_pack_source == ""
    assert not any(c.startswith("domain packs:") for c in generic.citations)

    with pytest.raises(ResponseError, match="domain_packs is empty"):
        answer("yield yoy", replace(ctx, domain_packs=(), domain_pack_source=None))


# --- AC-029: LLM interpreter and narrator, gated (T-025, REQ-020) -----------



class _Model:
    """A stub completion callable: returns a fixed reply (or raises), recording each call."""

    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def __call__(self, prompt, system):
        self.calls.append((prompt, system))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply(prompt) if callable(self.reply) else self.reply


def _rows():
    return [Fact(period=p, dims={"desk": d}, measures={"cost": float(p) + (2.0 if d == "fx" else 0.0)})
            for p in range(6, 11) for d in ("rates", "fx")]


def _no_read(plan):
    raise AssertionError("nothing may execute for an ungoverned or unparsed plan")


_GOOD_PLAN = {"metric": "funding_cost", "dimensions": ["desk"], "filters": [],
              "window": {"start_period": 6, "end_period": 10, "grain": "day"}, "comparison": None, "rank": None}


def test_ac029_valid_llm_plan_executes_through_the_same_gate(layer):
    model = _Model(json.dumps(_GOOD_PLAN))
    response = answer("what did funding cost do by desk this week", _context(layer, reader=lambda p: _rows(),
                      interpreter=LLMInterpreter(model)))
    assert response.status == "answered", response.reason
    assert "funding_cost" in response.plan_echo and "by desk" in response.plan_echo
    prompt, system = model.calls[0]
    vocab = json.loads(prompt)["vocabulary"]
    assert {m["name"] for m in vocab["metrics"]} == {"funding_cost", "revenue"} and vocab["today_period"] == 10
    assert "JSON" in system and "never write SQL" in system


@pytest.mark.parametrize("reply, reason", [
    ("Sure! Here is the plan: funding_cost by desk", "not a valid plan"),
    ("```json\n{\"metric\": \"funding_cost\"", "not a valid plan"),
    (json.dumps({**_GOOD_PLAN, "dimensions": ["counterparty"]}), "not declared"),
    (json.dumps({**_GOOD_PLAN, "sql": "SELECT 1"}), "unknown field"),
    (json.dumps({**_GOOD_PLAN, "metric": "secret_pnl"}), "undefined metric"),
    (json.dumps({**_GOOD_PLAN, "window": {"start_period": 9, "end_period": 12, "grain": "day"}}), "after today"),
    (json.dumps({**_GOOD_PLAN, "window": {"start_period": 6, "end_period": 10, "grain": "hourly"}}), "grain"),
])
def test_ac029_bad_llm_output_is_a_clarification_with_no_execution(layer, reply, reason):
    response = answer("funding cost by desk", _context(layer, reader=_no_read, interpreter=LLMInterpreter(_Model(reply))))
    assert response.status == "clarification_needed"
    assert reason in response.reason and response.chart is None


def test_ac029_fenced_json_and_null_window_use_the_declared_default(layer):
    reply = "```json\n" + json.dumps({**_GOOD_PLAN, "window": None}) + "\n```"
    plan = interpret("funding cost by desk", layer, InterpretContext(today_period=10, default_window_periods=5),
                     interpreter=LLMInterpreter(_Model(reply)))
    assert isinstance(plan, QueryPlan)
    assert (plan.window.start_period, plan.window.end_period) == (6, 10) and plan.defaults_applied == ("window",)
    assert plan.interpreter == "llm/1"


def test_ac029_model_clarification_keeps_only_governed_permitted_candidates(layer):
    reply = json.dumps({"clarification": {"reason": "cost could mean two metrics",
                                          "candidates": ["funding_cost", "revenue", "made_up_metric"]}})
    response = answer("cost", _context(layer, reader=_no_read, interpreter=LLMInterpreter(_Model(reply)),
                                       access_policy=AccessPolicy(metric_levels={"revenue": "restricted"})))
    assert response.status == "clarification_needed"
    assert "funding_cost" in response.reason
    assert "made_up_metric" not in response.reason and "revenue" not in response.reason   # masked (AC-005)


def test_ac029_model_failure_is_a_clarification_or_the_keyword_fallback(layer):
    ctx = InterpretContext(today_period=10, default_window_periods=5)
    down = LLMInterpreter(_Model(LookupError("no model")))
    result = interpret("funding cost", layer, ctx, interpreter=down)
    assert isinstance(result, Clarification) and "LookupError" in result.reason
    with_fallback = LLMInterpreter(_Model(LookupError("no model")), fallback=KeywordInterpreter())
    plan = interpret("funding cost", layer, ctx, interpreter=with_fallback)
    assert isinstance(plan, QueryPlan) and plan.interpreter == "keyword/1"


def _echo_statements(prompt):
    return " ".join(i["statement"] for i in json.loads(prompt)["insights"])


def test_ac029_grounded_model_narrative_ships(layer):
    response = answer("funding cost", _context(layer, reader=lambda p: _rows(), narrator=LLMNarrator(_Model(_echo_statements))))
    assert response.status == "answered" and response.narrative_mode == "llm/1"
    assert response.narrative == template_narrative(response.insights)
    assert not any("template" in c for c in response.caveats)


@pytest.mark.parametrize("reply, caveat", [
    ("Funding cost rose to 9999 this week.", "not in the computed results"),
    (lambda prompt: _echo_statements(prompt) + " This happened because of rate hikes.", "causal wording"),
    ("", "returned no text"),
    (RuntimeError("provider down"), "unavailable"),
])
def test_ac029_rejected_model_narrative_falls_back_to_the_template_with_a_caveat(layer, reply, caveat):
    response = answer("funding cost", _context(layer, reader=lambda p: _rows(), narrator=LLMNarrator(_Model(reply))))
    assert response.status == "answered"
    assert response.narrative_mode == "template" and response.narrative == template_narrative(response.insights)
    assert any(caveat in c for c in response.caveats), response.caveats


def test_default_answer_reports_the_template_narrative(layer):
    response = answer("funding cost", _context(layer, reader=lambda p: _rows()))
    assert response.narrative_mode == "template" and response.narrative == template_narrative(response.insights)


# --- AC-032: named approver, approver roles, distinct approver (T-027, REQ-023) --



class _NoWriteWriter(_RecordingWriter):
    def write(self, records):
        raise AssertionError("a refused commit must never reach the writer")


def test_ac032_every_commit_records_its_approver(layer):
    _, _, records = _built_records(layer)
    contract = default_contract("approvals")
    by_author = publish(records, contract, _RecordingWriter(), dry_run=False, approved=True)
    assert {r["approver_handle"] for r in by_author.records} == {"anon-1"}       # the author approved
    named = publish(records, contract, _RecordingWriter(), dry_run=False, approved=True, approver_handle="anon-2")
    assert {r["approver_handle"] for r in named.records} == {"anon-2"}
    dry = publish(records, contract, _RecordingWriter())
    assert {r["approver_handle"] for r in dry.records} == {None}
    auto = publish(records, default_contract("auto", auto_approve=True), _RecordingWriter(), dry_run=False)
    assert auto.status == "committed" and {r["approver_handle"] for r in auto.records} == {None}


def test_ac032_approver_roles_and_distinct_approver_are_enforced_before_writing(layer):
    _, _, records = _built_records(layer)
    gated = default_contract("gated", approver_roles=("desk-lead",))
    with pytest.raises(WriteBackError, match="no entries"):
        publish(records, gated, _NoWriteWriter(), dry_run=False, approved=True, approver_handle="anon-2")
    with pytest.raises(WriteBackError, match="holds none of the roles"):
        publish(records, gated, _NoWriteWriter(), dry_run=False, approved=True, approver_handle="anon-2",
                approver_roles=("analyst",), roster_has_entries=True)
    ok = publish(records, gated, _RecordingWriter(), dry_run=False, approved=True, approver_handle="anon-2",
                 approver_roles=("analyst", "desk-lead"), roster_has_entries=True)
    assert ok.status == "committed"

    four_eyes = default_contract("four-eyes", require_distinct_approver=True)
    with pytest.raises(WriteBackError, match="other than the author"):
        publish(records, four_eyes, _NoWriteWriter(), dry_run=False, approved=True)
    with pytest.raises(WriteBackError, match="other than the author"):
        publish(records, four_eyes, _NoWriteWriter(), dry_run=False, approved=True, approver_handle="anon-1")
    assert publish(records, four_eyes, _RecordingWriter(), dry_run=False, approved=True,
                   approver_handle="anon-2").status == "committed"


def test_ac032_answer_returns_write_rejected_with_the_reason(layer):
    rows = [Fact(period=p, dims={"desk": "rates"}, measures={"cost": float(p)}) for p in range(6, 11)]
    request = WriteBackRequest(contract=default_contract("gated", approver_roles=("desk-lead",)),
                               writer=_NoWriteWriter(), author_handle="anon-1", dry_run=False, approved=True)
    response = answer("funding cost", _context(layer, reader=lambda p: rows, run_id="run-gated", writeback=request))
    assert response.status == "write_rejected" and "roster.yml has no entries" in response.reason


def test_ac032_contract_file_declares_roles_and_distinct_approver(tmp_path):
    text = (_REPO_ROOT / "templates" / "data" / "writeback_contract.md").read_text(encoding="utf-8")
    text = text.replace("- **Name:** <target-name>", "- **Name:** desk_insights", 1)
    text = text.replace("`<role, role>`", "`desk-lead, risk`", 1)
    text = text.replace("- **`require_distinct_approver`:** `false`", "- **`require_distinct_approver`:** `true`", 1)
    path = tmp_path / "contract.md"
    path.write_text(text, encoding="utf-8")
    contract = load_contract(str(path))
    assert contract.approver_roles == ("desk-lead", "risk") and contract.require_distinct_approver
    untouched = tmp_path / "plain.md"
    untouched.write_text(text.replace("`desk-lead, risk`", "`<role, role>`"), encoding="utf-8")
    assert load_contract(str(untouched)).approver_roles == ()


def test_ac032_roster_roles_parse_validate_and_resolve():
    text = ("people:\n"
            "  - handle: u-aaaaaaaaaaaaaaaaaaaaaaaa\n    label: lead\n    clearance: internal\n    roles: [desk-lead, risk]\n"
            "  - handle: u-bbbbbbbbbbbbbbbbbbbbbbbb\n    label: analyst\n    clearance: internal\n    roles: analyst\n"
            "  - handle: u-cccccccccccccccccccccccc\n    label: other\n    clearance: public\n    roles: [Bad Role]\n")
    entries, _ = _parse_roster_text(text, "roster.yml")
    roster = Roster(entries=tuple(entries), enforced=True, source_file="roster.yml")
    assert roles_for(roster, "u-aaaaaaaaaaaaaaaaaaaaaaaa") == ("desk-lead", "risk")
    assert roles_for(roster, "u-bbbbbbbbbbbbbbbbbbbbbbbb") == ("analyst",)
    assert roles_for(roster, "u-unknown") == () and roles_for(roster, None) == ()
    assert [f.message for f in validate_roster(roster) if "role" in f.message] == [
        "role 'Bad Role' must be lowercase letters, digits, and hyphens"]


def test_ac032_sqlite_table_from_before_the_approver_column_is_migrated(layer):
    conn = sqlite3.connect(":memory:")
    old_columns = [c for c in SCHEMA_COLUMNS if c != "approver_handle"]
    cols = ", ".join(f'"{c}" TEXT' for c in old_columns if c != "record_key")
    conn.execute(f'CREATE TABLE "nl_analytics_writeback_legacy" ("record_key" TEXT PRIMARY KEY, {cols})')
    conn.execute('INSERT INTO "nl_analytics_writeback_legacy" ("record_key", "metric", "dimensions_json") '
                 "VALUES ('old', 'funding_cost', '[]')")
    writer = SQLiteWriter(conn, default_contract("legacy"))
    _, _, records = _built_records(layer)
    publish(records, default_contract("legacy"), writer, dry_run=False, approved=True, approver_handle="anon-2")
    rows = {r["record_key"]: r for r in writer.read("funding_cost")}
    assert rows["old"]["approver_handle"] is None
    assert {r["approver_handle"] for k, r in rows.items() if k != "old"} == {"anon-2"}


# --- AC-031: opt-in knowledge candidates (T-028, REQ-022) -------------------


_PROPOSED = datetime.date(2026, 10, 8)


def _publish_ctx(layer, **request):
    rows = [Fact(period=p, dims={"desk": "rates"}, measures={"cost": float(p)}) for p in range(6, 11)]
    wb = WriteBackRequest(contract=default_contract("insights"), writer=_RecordingWriter(), author_handle="anon-1",
                          propose_knowledge=True, knowledge_proposed_at=_PROPOSED, **request)
    return _context(layer, reader=lambda p: rows, run_id="run-k1", writeback=wb)


def test_ac031_committed_publish_proposes_one_reviewable_candidate(layer, tmp_path):
    from quantsmith.pipelines import workflow_memory as wm

    response = answer("funding cost", _publish_ctx(layer, dry_run=False, approved=True))
    assert response.status == "answered" and response.writeback.status == "committed"
    candidate = response.knowledge_candidate
    assert isinstance(candidate, wm.Candidate) and response.knowledge_candidate_reason == ""
    assert candidate.workflow == "nl_analytics" and candidate.source_run == "run-k1"
    assert candidate.proposed_at == _PROPOSED and candidate.candidate_id == "nl_analytics/run-k1/001"
    spec = candidate.spec
    assert spec.scope == "metric:funding_cost" and spec.type == "metric" and spec.confidence == "low"
    assert spec.statement == response.insights[0].statement
    evidence = spec.evidence[0]
    keys = {r["record_key"] for r in response.writeback.records}
    assert evidence["source_run"] == "run-k1" and set(evidence["record_keys"].split(",")) == keys
    assert evidence["plan_hash"] and evidence["metric_definition_hash"].startswith("sha256:")
    assert evidence["as_of_period"] == "10"
    # Staging is the caller's step, and it only ever writes the inbox: nothing is promoted.
    path = wm.stage_candidates([candidate], root=tmp_path / "memory")
    assert "inbox" in path.parts
    assert [p.relative_to(tmp_path / "memory").parts[0] for p in (tmp_path / "memory").rglob("*") if p.is_file()] == ["inbox"]


def test_ac031_dry_run_returns_the_would_be_candidate_without_staging(layer, tmp_path):
    response = answer("funding cost", _publish_ctx(layer))
    assert response.writeback.status == "dry_run"
    assert response.knowledge_candidate is not None and "dry run" in response.knowledge_candidate_reason
    assert not (tmp_path / "memory").exists()


def test_ac031_no_candidate_when_the_write_is_refused_or_not_requested(layer):
    refused = answer("funding cost", _publish_ctx(layer, dry_run=False, approved=False))
    assert refused.status == "write_rejected" and refused.knowledge_candidate is None
    assert refused.knowledge_candidate_reason == "no knowledge candidate: the write-back was refused"

    rows = [Fact(period=p, dims={"desk": "rates"}, measures={"cost": float(p)}) for p in range(6, 11)]
    plain = answer("funding cost", _context(layer, reader=lambda p: rows, run_id="run-k2", writeback=WriteBackRequest(
        contract=default_contract("insights"), writer=_RecordingWriter(), dry_run=False, approved=True)))
    assert plain.knowledge_candidate is None and plain.knowledge_candidate_reason == ""

    no_date = answer("funding cost", _context(layer, reader=lambda p: rows, run_id="run-k3", writeback=WriteBackRequest(
        contract=default_contract("insights"), writer=_RecordingWriter(), dry_run=False, approved=True,
        propose_knowledge=True)))
    assert no_date.knowledge_candidate is None and "knowledge_proposed_at is required" in no_date.knowledge_candidate_reason


def test_ac031_unreviewed_pack_blocks_the_candidate_with_the_write():
    layer = _rates_layer()
    wb = WriteBackRequest(contract=default_contract("cli_default"), writer=_RecordingWriter(),
                          propose_knowledge=True, knowledge_proposed_at=_PROPOSED)
    ctx = _yearly_context(layer, _curve_rows(("2y",)), dataset_domains=("fixed_income_rates",), domain_packs=_PACKS)
    refused = answer("yield yoy", replace(ctx, run_id="run-pack-k", writeback=wb))
    assert refused.status == "write_rejected" and "rates_fixed_income" in refused.reason
    assert refused.knowledge_candidate is None and "write-back was refused" in refused.knowledge_candidate_reason
