"""Chart specifications built only from registered evidence.

Spec ``0121`` REQ-012 (POC AC-14). Charts are Vega-Lite v5 specifications
(JSON), so the plugin needs no plotting dependency and any host can render
them. Every chart names its units, denominator, scope, and the evidence it
draws on; :func:`validate_chart` rejects one that does not.
"""

from __future__ import annotations

from typing import Any

from .evidence import ResearchSession

__all__ = ["build_charts", "validate_chart"]

SCHEMA = "https://vega.github.io/schema/vega-lite/v5.json"


def _chart(chart_id: str, title: str, mark: str, x: str, y: str, x_title: str, y_title: str,
           values: list[dict[str, Any]], *, units: str, denominator: Any, scope: str,
           evidence_ids: list[str], x_type: str = "nominal") -> dict[str, Any]:
    return {
        "$schema": SCHEMA, "title": title,
        "description": f"Scope: {scope}; denominator: {denominator}; units: {units}",
        "data": {"values": values}, "mark": mark,
        "encoding": {"x": {"field": x, "type": x_type, "title": x_title},
                     "y": {"field": y, "type": "quantitative", "title": y_title}},
        "usermeta": {"sfmeridian": {"chart_id": chart_id, "units": units, "denominator": denominator,
                                    "scope": scope, "evidence_ids": evidence_ids}},
    }


def _label(v: Any) -> str:
    return v["untrusted_text"] if isinstance(v, dict) and "untrusted_text" in v else str(v)


def build_charts(s: ResearchSession) -> list[dict[str, Any]]:
    charts: list[dict[str, Any]] = []
    for e in s.evidence.as_list():
        v = e["value"]
        if e["tool"] == "research.inspect_missingness":
            charts.append(_chart(f"C-{len(charts) + 1:02d}", f"Missing {v['column']} by {v['group_by']}", "bar",
                                 "group", "rate", v["group_by"], "share of rows missing",
                                 [{"group": _label(g["group"]), "rate": g["rate"], "n": g["n"]} for g in v["groups"]],
                                 units="fraction of rows", denominator=f"rows per {v['group_by']}",
                                 scope=e["scope"], evidence_ids=[e["evidence_id"]]))
        elif e["tool"] == "research.inspect_time":
            charts.append(_chart(f"C-{len(charts) + 1:02d}", "Rows by date", "line", "date", "rows", "date", "rows",
                                 [{"date": d, "rows": n} for d, n in sorted(v["rows_by_date"].items())],
                                 units="rows", denominator="rows per date", scope=e["scope"],
                                 evidence_ids=[e["evidence_id"]], x_type="temporal"))
        elif e["tool"] == "research.check_domain_rules" and "groups" in v:
            charts.append(_chart(f"C-{len(charts) + 1:02d}", f"{v['rule_id']} violations by {v['group_by']}", "bar",
                                 "group", "violations", v["group_by"], "violating rows",
                                 [{"group": _label(g["group"]), "violations": g["violations"],
                                   "applicable": g["applicable"]} for g in v["groups"]],
                                 units="rows", denominator="applicable rows per group", scope=e["scope"],
                                 evidence_ids=[e["evidence_id"]]))
        elif e["tool"] == "research.inspect_numeric" and v.get("histogram"):
            h = v["histogram"]
            charts.append(_chart(f"C-{len(charts) + 1:02d}", f"Distribution of {v['column']}", "bar", "bin_start",
                                 "count", f"{v['column']} (bin start)", "rows",
                                 [{"bin_start": round(h["bin_start"] + i * h["bin_width"], 9), "count": c}
                                  for i, c in enumerate(h["counts"])],
                                 units="rows", denominator=f"{v['n_numeric']} numeric values", scope=e["scope"],
                                 evidence_ids=[e["evidence_id"]], x_type="quantitative"))
    return charts


def validate_chart(spec: dict[str, Any]) -> list[str]:
    problems = []
    for key in ("$schema", "title", "data", "mark", "encoding", "usermeta"):
        if key not in spec:
            problems.append(f"missing {key}")
    meta = spec.get("usermeta", {}).get("sfmeridian", {})
    for key in ("units", "denominator", "scope", "evidence_ids"):
        if not meta.get(key):
            problems.append(f"missing usermeta.{key}")
    if not isinstance(spec.get("data", {}).get("values"), list):
        problems.append("data.values must be a list")
    for axis in ("x", "y"):
        enc = spec.get("encoding", {}).get(axis, {})
        if not enc.get("field") or not enc.get("title"):
            problems.append(f"encoding.{axis} needs field and title")
    return problems
