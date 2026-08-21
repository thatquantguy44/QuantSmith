import { useState } from "react";
import type { Model, QueryAnswer } from "../lib/types";
import { askQuestion, isEmbedded } from "../lib/api";

const SUGGESTIONS = [
  "why not use adjusted close",
  "how is the liquidity universe defined",
  "what does zero volume mean",
  "join key for prices",
];

export function Ask({ model }: { model: Model }) {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [ans, setAns] = useState<QueryAnswer | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const byId = new Map(model.records.map((r) => [r.id, r]));

  async function run(question: string) {
    const trimmed = question.trim();
    if (!trimmed) return;
    setBusy(true);
    setErr(null);
    setAns(null);
    try {
      setAns(await askQuestion(trimmed, model));
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="card">
        <h3>Ask the knowledge base</h3>
        <div className="ask-box">
          <input
            className="ask-input"
            placeholder="Ask a question grounded in the store…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run(q)}
          />
          <button className="btn" disabled={busy} onClick={() => run(q)}>
            {busy ? "…" : "Ask"}
          </button>
        </div>
        <div className="suggest">
          {SUGGESTIONS.map((s) => (
            <span key={s} className="badge chip" onClick={() => { setQ(s); run(s); }}>{s}</span>
          ))}
        </div>

        <div className="note">
          <strong>Pluggable engine.</strong> Answers today come from a grounded keyword
          engine that cites real records and says "not found" rather than guessing. A real
          LLM engine can register behind the same contract later — the UI and API do not
          change. Current engine: <code>{isEmbedded() ? "keyword (in-browser)" : "server /api/query"}</code>.
        </div>

        {err && <div className="note warn">Query failed: {err}</div>}

        {ans && (
          <div className="answer">
            <div style={{ marginBottom: 10 }}>
              <span className="badge">{ans.matched ? "grounded" : "no match"}</span>{" "}
              <span className="badge">engine: {ans.mode}</span>
            </div>
            <p style={{ color: "var(--fg)" }}>{ans.answer}</p>
            {ans.citations.length > 0 && (
              <>
                <div className="section-title" style={{ fontSize: 13, margin: "14px 0 8px" }}>
                  Citations
                </div>
                <div className="grid" style={{ gap: 8 }}>
                  {ans.citations.map((id) => {
                    const r = byId.get(id);
                    return (
                      <div className="card" key={id} style={{ padding: "10px 14px" }}>
                        <span className="id mono" style={{ color: "var(--accent)", fontWeight: 700 }}>{id}</span>
                        {r && (
                          <>
                            <span className="prov" style={{ marginLeft: 8 }}>
                              {r.workflow} · {r.scope} · confidence {r.confidence} · confirmed {r.last_confirmed}
                            </span>
                            <div className="stmt" style={{ marginTop: 6 }}>{r.statement}</div>
                            <div className="prov">{r.source_file}</div>
                          </>
                        )}
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
