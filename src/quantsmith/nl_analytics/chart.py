"""Deterministic chart choice. Spec ``0080`` (REQ-006).

The chart type is never a model's choice: a declared form rule maps the
*shape* of a :class:`~quantsmith.nl_analytics.execute.Result` to one of
``dashboard_spec.CHART_TYPES``, the same governed vocabulary the SDK's seven
dashboard renderers already draw from. Pie and dual-axis charts are not
representable, because they are not in that vocabulary (RISK-005).

Standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence, Tuple

from quantsmith.pipelines.dashboard_spec import CHART_TYPES, DashboardSpecError, Panel
from quantsmith.pipelines.metrics_semantic_layer import SemanticLayer

from .execute import Result

# Vega-Lite's own top-level keys this module always fills, so a consumer can
# tell a real (if minimal) spec from an empty dict (REQ-009, AC-012).
_MINIMAL_VEGA_LITE_KEYS = ("$schema", "description", "mark", "encoding", "data")


class ChartError(ValueError):
    """Raised when a chart cannot be built from a result (e.g. no data)."""


@dataclass(frozen=True)
class ChartSpec:
    """A chosen chart: type, encoding, and the exact rows behind it.

    ``data`` is self-contained — everything needed to render this chart
    without recomputing from the ``Result`` — one row per data point, with
    keys matching ``x``/``y``/``series`` (when set).
    """

    chart_type: str
    title: str
    metric: str
    dimensions: Tuple[str, ...]
    data: Tuple[Dict[str, object], ...]
    x: str
    y: str
    series: Optional[str]
    units: str
    sort: Optional[str]  # None | "descending" | "ascending"
    zero_baseline: bool
    footnote: str
    alt_text: str

    def __post_init__(self) -> None:
        if self.chart_type not in CHART_TYPES:
            raise ChartError(f"chart_type {self.chart_type!r} not in {CHART_TYPES}")


def _footnote(layer: SemanticLayer, metric: str, result: Result) -> str:
    owner = layer.definition(metric).owner
    return f"Source: {metric} (owner: {owner}); as of period {result.as_of}."


def choose_chart(
    result: Result,
    layer: SemanticLayer,
    *,
    compare: Optional[Result] = None,
    units: str = "",
) -> ChartSpec:
    """Choose a chart deterministically from ``result``'s shape (REQ-006).

    Precedence, matching the five shapes AC-007 names:

    1. ``compare`` given (a second metric's result over the same window) ->
       ``scatter`` (a two-measure pair).
    2. Two declared dimensions -> ``table`` (a two-dimension breakdown).
    3. One declared dimension -> ``bar``, sorted descending (a single
       categorical breakdown).
    4. No dimensions, more than one period in the series -> ``line`` (a time
       series).
    5. No dimensions, one or zero periods -> ``kpi`` (a single value).
    """
    metric = result.plan.metric
    dims = result.plan.dimensions
    footnote = _footnote(layer, metric, result)

    if compare is not None:
        return _scatter(result, compare, layer, units, footnote)
    if len(dims) == 2:
        return _table(result, dims, units, footnote)
    if len(dims) == 1:
        return _bar(result, dims, units, footnote)
    if len(result.series) > 1:
        return _line(result, units, footnote)
    return _kpi(result, units, footnote)


def _kpi(result: Result, units: str, footnote: str) -> ChartSpec:
    value = result.values.get((), 0.0)
    metric = result.plan.metric
    return ChartSpec(
        chart_type="kpi", title=f"{metric} is {value:g}{(' ' + units) if units else ''}",
        metric=metric, dimensions=(), data=({"metric": metric, "value": value},),
        x="metric", y="value", series=None, units=units, sort=None, zero_baseline=False,
        footnote=footnote, alt_text=f"{metric} is {value:g}{(' ' + units) if units else ''}.",
    )


def _line(result: Result, units: str, footnote: str) -> ChartSpec:
    metric = result.plan.metric
    data = tuple({"period": p, "value": v.get((), 0.0)} for p, v in sorted(result.series.items()))
    return ChartSpec(
        chart_type="line", title=f"{metric} over time", metric=metric, dimensions=(),
        data=data, x="period", y="value", series=None, units=units, sort=None,
        zero_baseline=False, footnote=footnote,
        alt_text=f"{metric} plotted over {len(data)} periods from {data[0]['period']} to {data[-1]['period']}.",
    )


def _bar(result: Result, dims: Tuple[str, ...], units: str, footnote: str) -> ChartSpec:
    metric = result.plan.metric
    dim = dims[0]
    ordered = sorted(result.values.items(), key=lambda kv: kv[1], reverse=True)
    data = tuple({dim: (k[0] if k[0] else "(none)"), "value": v} for k, v in ordered)
    return ChartSpec(
        chart_type="bar", title=f"{metric} by {dim}", metric=metric, dimensions=dims,
        data=data, x=dim, y="value", series=None, units=units, sort="descending",
        zero_baseline=True, footnote=footnote,
        alt_text=f"{metric} by {dim}, sorted highest to lowest, across {len(data)} values of {dim}.",
    )


def _table(result: Result, dims: Tuple[str, ...], units: str, footnote: str) -> ChartSpec:
    metric = result.plan.metric
    d1, d2 = dims
    data = tuple(
        {d1: (k[0] if k[0] else "(none)"), d2: (k[1] if k[1] else "(none)"), "value": v}
        for k, v in sorted(result.values.items())
    )
    return ChartSpec(
        chart_type="table", title=f"{metric} by {d1} and {d2}", metric=metric, dimensions=dims,
        data=data, x=d1, y="value", series=d2, units=units, sort=None, zero_baseline=False,
        footnote=footnote, alt_text=f"{metric} broken down by {d1} and {d2}, {len(data)} rows.",
    )


def _scatter(result: Result, compare: Result, layer: SemanticLayer, units: str, footnote: str) -> ChartSpec:
    metric_x, metric_y = result.plan.metric, compare.plan.metric
    common_keys = sorted(set(result.values) & set(compare.values))
    data = tuple({"x": result.values[k], "y": compare.values[k], "key": "|".join(k) or "(total)"} for k in common_keys)
    return ChartSpec(
        chart_type="scatter", title=f"{metric_x} vs {metric_y}", metric=metric_x,
        dimensions=result.plan.dimensions, data=data, x="x", y="y", series="key", units=units,
        sort=None, zero_baseline=False,
        footnote=f"{footnote} Compared against {metric_y} (owner: {layer.definition(metric_y).owner}).",
        alt_text=f"{metric_x} plotted against {metric_y} for {len(data)} matching groups.",
    )


def to_vega_lite(spec: ChartSpec) -> Dict[str, object]:
    """A minimal, portable Vega-Lite spec (REQ-009). ``table``/``kpi`` still
    get one — as a bar-shaped fallback mark — since every chart must have one
    (AC-012); the Markdown table remains the primary rendering for those two.
    """
    mark = {"bar": "bar", "line": "line", "scatter": "point", "kpi": "text", "table": "bar"}[spec.chart_type]
    encoding: Dict[str, object] = {
        "x": {"field": spec.x, "type": "nominal" if spec.chart_type in ("bar", "table") else "quantitative"},
        "y": {"field": spec.y, "type": "quantitative"},
    }
    if spec.series:
        encoding["color"] = {"field": spec.series, "type": "nominal"}
    if spec.sort == "descending":
        encoding["x"]["sort"] = "-y"
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "description": spec.alt_text,
        "title": spec.title,
        "mark": mark,
        "encoding": encoding,
        "data": {"values": list(spec.data)},
    }


def is_minimal_vega_lite(payload: Dict[str, object]) -> bool:
    """Whether ``payload`` carries every key the declared minimal schema requires (AC-012)."""
    return all(k in payload for k in _MINIMAL_VEGA_LITE_KEYS)


def to_markdown_table(spec: ChartSpec) -> str:
    """The Markdown-table fallback every response carries (REQ-009)."""
    if not spec.data:
        return "(no data)"
    columns = list(spec.data[0].keys())
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in spec.data:
        lines.append("| " + " | ".join(str(row[c]) for c in columns) + " |")
    return "\n".join(lines)


def to_panel(spec: ChartSpec) -> Panel:
    """Promote a chart spec to a governed ``DashboardSpec`` ``Panel`` (REQ-006)."""
    try:
        return Panel(title=spec.title, chart_type=spec.chart_type, metric=spec.metric, dimensions=spec.dimensions)
    except DashboardSpecError as exc:
        raise ChartError(str(exc)) from exc
