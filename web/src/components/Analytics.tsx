import { useState } from "react";
import type { AnalyticsAnswer } from "../lib/types";
import { askAnalytics, isEmbedded } from "../lib/api";

// Read-only data questions (spec 0080 T-026, REQ-021). The answer table is the
// server's markdown table, rendered as HTML; no chart library is bundled yet.
// Write-back and knowledge candidates stay with the nl_analytics CLI.

function parseTable(md: string): { head: string[]; rows: string[][] } | null {
  const lines = md.trim().split("\n").filter((l) => l.trim().startsWith("|"));
  if (lines.length < 2) return null;
  const cells = (l: string) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
  return { head: cells(lines[0]), rows: lines.slice(2).map(cells) };
}

export function Analytics() {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [ans, setAns] = useState<AnalyticsAnswer | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function run() {
    const question = q.trim();
    if (!question) return;
    setBusy(true);
    setErr(null);
    setAns(null);
    try {
      setAns(await askAnalytics(question));
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  const table = ans?.markdown_table ? parseTable(ans.markdown_table) : null;

  return (
    <div className="card">
      <h3>Ask a data question</h3>
      <div className="ask-box">
        <input
          className="ask-input"
          placeholder="e.g. funding cost by desk"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && run()}
        />
        <button className="btn" disabled={busy || isEmbedded()} onClick={run}>
          {busy ? "…" : "Ask"}
        </button>
      </div>
      <div className="note">
        <strong>Read-only.</strong> Answers come from governed metrics under your clearance. This page
        never writes results back or proposes knowledge; use the <code>nl_analytics</code> CLI for that.
      </div>

      {err && <div className="note warn">{err}</div>}

      {ans && ans.status !== "answered" && (
        <div className="note warn">{ans.reason}</div>
      )}

      {ans && ans.status === "answered" && (
        <div className="answer">
          <p style={{ color: "var(--fg)", fontWeight: 600 }}>{ans.headline}</p>
          {/* A template narrative only restates the insights below, so show model-written text only. */}
          {ans.narrative && ans.narrative_mode !== "template" && (
            <p>
              {ans.narrative} <span className="badge">narrative: {ans.narrative_mode}</span>
            </p>
          )}
          {table && (
            <table className="tbl">
              <thead>
                <tr>{table.head.map((h) => <th key={h}>{h}</th>)}</tr>
              </thead>
              <tbody>
                {table.rows.map((r, i) => (
                  <tr key={i}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>
                ))}
              </tbody>
            </table>
          )}
          {ans.insights.length > 0 && (
            <ul>{ans.insights.map((i, n) => <li key={n}>{i.statement}</li>)}</ul>
          )}
          <div className="prov">Plan: {ans.plan_echo}</div>
          {ans.caveats.map((c) => <div className="note" key={c}>{c}</div>)}
          <div className="prov">Sources: {ans.citations.join(" · ")}</div>
        </div>
      )}
    </div>
  );
}
