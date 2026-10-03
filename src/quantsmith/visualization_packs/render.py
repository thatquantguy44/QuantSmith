"""Portable, escaped story artifacts; rendering never computes new metrics."""
from __future__ import annotations

import html
import json


def _text(value):
    return html.escape(str(value), quote=True)


def _md(value):
    return _text(value).replace("|", "\\|").replace("\n", " ").replace("`", "\\`")


def render_json(story):
    return json.dumps(story.to_dict(), indent=2, sort_keys=True, allow_nan=False) + "\n"


def _rows(chart):
    columns = list(chart.data[0]) if chart.data else []
    return columns, [[row.get(c, "") for c in columns] for row in chart.data]


def render_markdown(story):
    if story.status != "ready":
        return f"Status: {_md(story.status)}\n\n{_md(story.reason)}\n"
    lines = [f"# {_md(story.decision)}", "", "## Executive view", "", _md(story.headline)]
    lines += ["", *["- " + _md(s) for s in story.supporting_findings], "", "## Next investigation", "", _md(story.action),
              "", "Evidence: " + ", ".join(_md(e) for e in story.action_evidence_ids), "", "## Caveats", ""]
    lines += ["- " + _md(c) for c in story.caveats]
    for section in story.sections:
        lines += ["", f"## {_md(section.section_id)}", "", _md(section.observation), "",
                  "Question for investigation: " + _md(section.interpretation), "", "Chart rule: " + _md(section.rule), ""]
        cols, rows = _rows(section.chart)
        lines += ["| " + " | ".join(_md(c) for c in cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
        lines += ["| " + " | ".join(_md(v) for v in row) + " |" for row in rows]
        lines += ["", _md(section.chart.footnote)]
    lines += ["", "## Analyst evidence", "", "Pack versions: " + _md(story.pack_versions)]
    for e in story.evidence:
        lines += ["", f"### {_md(e.evidence_id)}", "", _md(e.source), "", "```json",
                  json.dumps(dict(e.payload(), digest=e.digest), indent=2, sort_keys=True, allow_nan=False), "```"]
    lines += ["", "## Inherited chart conventions", ""] + ["- " + _md(c) for c in story.conventions]
    return "\n".join(lines) + "\n"


def _table(chart):
    cols, rows = _rows(chart)
    return ("<div class='table-scroll'><table><caption>Exact governed observations</caption><thead><tr>" +
            "".join(f"<th scope='col'>{_text(c)}</th>" for c in cols) + "</tr></thead><tbody>" +
            "".join("<tr>" + "".join(f"<td>{_text(v)}</td>" for v in row) + "</tr>" for row in rows) +
            "</tbody></table></div>")


def _svg(chart):
    if chart.chart_type == "kpi":
        return f"<p class='kpi'>{_text(format(chart.data[0][chart.y], ',.6g'))} <small>{_text(chart.units)}</small></p>"
    if chart.chart_type not in ("bar", "line") or not chart.data:
        return ""
    # All numerical inputs have been checked at evidence collection. Scale
    # arithmetic affects geometry only; it never becomes an analytical claim.
    values = [float(row[chart.y]) for row in chart.data]
    low, high = min(0, min(values)), max(0, max(values))
    span = high - low or 1.0
    width, height, left, right, top, bottom = 800, 310, 155, 720, 22, 254
    pieces = [f"<svg role='img' viewBox='0 0 {width} {height}' aria-label='{_text(chart.alt_text)}'>",
              f"<title>{_text(chart.alt_text)}</title>"]
    if chart.chart_type == "bar":
        height = max(170, 40 * len(values) + 70)
        pieces[0] = f"<svg role='img' viewBox='0 0 {width} {height}' aria-label='{_text(chart.alt_text)}'>"
        zero = left + (0 - low) / span * (right - left)
        pieces.append(f"<line x1='{zero}' x2='{zero}' y1='12' y2='{height-40}' stroke='#64748b'/>")
        for i, (row, value) in enumerate(zip(chart.data, values)):
            endpoint = left + (value - low) / span * (right - left)
            y = 22 + i * 40
            pieces += [f"<text x='{left-12}' y='{y+17}' text-anchor='end'>{_text(row[chart.x])}</text>",
                       f"<rect x='{min(zero, endpoint)}' y='{y}' width='{abs(endpoint-zero)}' height='25' fill='#147d78'/>",
                       f"<text x='{right+10}' y='{y+17}'>{_text(format(value, '.5g'))}</text>"]
        pieces.append(f"<text x='{left}' y='{height-10}'>{_text(chart.units)} · zero baseline</text>")
    else:
        points = [(left + i * (right-left)/max(1, len(values)-1), bottom - (v-low)/span*(bottom-top)) for i, v in enumerate(values)]
        pieces += [f"<line x1='{left}' x2='{right}' y1='{bottom}' y2='{bottom}' stroke='#64748b'/>",
                   f"<polyline fill='none' stroke='#147d78' stroke-width='3' points='{' '.join(f'{x},{y}' for x,y in points)}'/>"]
        for i, ((x, y), row, value) in enumerate(zip(points, chart.data, values)):
            pieces += [f"<circle cx='{x}' cy='{y}' r='4' fill='#147d78'><title>{_text(row[chart.x])}: {_text(value)} {_text(chart.units)}</title></circle>"]
            if len(points) <= 8 or i in (0, len(points)-1):
                pieces.append(f"<text x='{x}' y='{bottom+25}' text-anchor='middle'>{_text(row[chart.x])}</text>")
        pieces += [f"<text x='{left-12}' y='{top+8}' text-anchor='end'>{_text(format(high, '.5g'))}</text>",
                   f"<text x='{left-12}' y='{bottom}' text-anchor='end'>{_text(format(low, '.5g'))}</text>",
                   f"<text x='{left}' y='{height-8}'>{_text(chart.units)} · observed periods in order; equal spacing</text>"]
    pieces.append("</svg>")
    return "".join(pieces)


def render_html(story):
    """Self-contained HTML: no script, remote resource, or upload required."""
    title = story.decision if story.status == "ready" else "Visualization unavailable"
    css = """
        *{box-sizing:border-box}body{margin:0;background:#f3f6f8;color:#172c3b;font:16px/1.55 system-ui,sans-serif}
        main{max-width:1060px;margin:auto;padding:48px 28px}header{border-top:6px solid #147d78;padding:28px;background:#132d3e;color:white}
        h1{font-size:30px;line-height:1.25;margin:12px 0}h2{font-size:21px}h3{font-size:17px}small,.meta{font-size:13px}
        .eyebrow{letter-spacing:.1em;text-transform:uppercase;font-size:12px}.lead{font-size:19px;font-weight:550}
        section{margin:22px 0;padding:26px;background:white;border:1px solid #d8e2e8;border-radius:6px}
        .notice{background:#fff9e7;border-color:#d6bb6e}.question{border-left:4px solid #147d78;padding-left:14px}
        .kpi{font-size:42px;font-weight:650}.kpi small{font-size:18px}svg{display:block;width:100%;height:auto;margin:20px 0}svg text{font:13px system-ui;fill:#172c3b}
        .table-scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:9px 12px;border-bottom:1px solid #d8e2e8}
        caption{text-align:left;font-weight:600;margin:10px 0}th{background:#eef4f6}summary{cursor:pointer;font-weight:600}
        pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eef4f6;padding:16px;font-size:12px}.footnote{font-size:12px;overflow-wrap:anywhere}
        li{margin:8px 0}@media(max-width:640px){main{padding:20px 12px}header,section{padding:18px}h1{font-size:24px}}
    """
    body = f"<header><div class='eyebrow'>QuantSmith · visual decision brief</div><h1>{_text(title)}</h1></header>"
    if story.status != "ready":
        body += f"<section><h2>{_text(story.status)}</h2><p>{_text(story.reason)}</p></section>"
    else:
        body += (f"<section><div class='eyebrow'>Executive view</div><p class='lead'>{_text(story.headline)}</p><ul>" +
                 "".join(f"<li>{_text(s)}</li>" for s in story.supporting_findings) + "</ul>" +
                 f"<h2>Next investigation</h2><p>{_text(story.action)}</p><p class='meta'>Evidence: {_text(', '.join(story.action_evidence_ids))}</p></section>")
        body += "<section class='notice'><h2>Read with these caveats</h2><ul>" + "".join(f"<li>{_text(c)}</li>" for c in story.caveats) + "</ul></section>"
        for section in story.sections:
            body += (f"<section><div class='eyebrow'>{_text(section.section_id)}</div><h2>{_text(section.observation)}</h2>" +
                     _svg(section.chart) + _table(section.chart) +
                     f"<p class='question'><strong>Question for investigation:</strong> {_text(section.interpretation)}</p>" +
                     f"<p class='meta'>Chart rule: {_text(section.rule)}</p><p class='footnote'>{_text(section.chart.footnote)}</p></section>")
        body += "<section><h2>Analyst evidence</h2><p class='meta'>Pack versions: " + _text(story.pack_versions) + "</p>"
        for e in story.evidence:
            payload = json.dumps(dict(e.payload(), digest=e.digest), indent=2, sort_keys=True, allow_nan=False)
            body += f"<details><summary>{_text(e.evidence_id)} · {_text(e.source)}</summary><pre>{_text(payload)}</pre></details>"
        body += "<h3>Inherited chart conventions</h3><ul>" + "".join(f"<li>{_text(c)}</li>" for c in story.conventions) + "</ul></section>"
    return f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{_text(title)}</title><style>{css}</style></head><body><main>{body}</main></body></html>\n"
