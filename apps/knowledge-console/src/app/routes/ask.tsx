import { useState } from "react";
import { Send } from "lucide-react";
import { useConsole } from "../../lib/store";
import { askQuestion } from "../../lib/api";
import type { QueryAnswer } from "../../lib/types";
import { Panel, Chip } from "../../components/ui";

const SUGGESTIONS = [
  "why not use adjusted close",
  "how is the liquidity universe defined",
  "what does zero volume mean",
  "join key for prices",
];

export function Ask() {
  const model = useConsole((s) => s.model)!;
  const byId = new Map(model.records.map((r) => [r.id, r]));
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [ans, setAns] = useState<QueryAnswer | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function run(question: string) {
    const t = question.trim();
    if (!t) return;
    setBusy(true);
    setErr(null);
    setAns(null);
    try {
      setAns(await askQuestion(t));
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Panel title="Ask the Knowledge Base">
        <div className="flex gap-2">
          <input
            className="term-input"
            placeholder="Ask a question grounded in the store…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run(q)}
          />
          <button className="btn-amber flex items-center gap-2" disabled={busy} onClick={() => run(q)}>
            <Send size={13} /> {busy ? "…" : "Ask"}
          </button>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => {
                setQ(s);
                run(s);
              }}
              className="chip border-term-border-2 text-term-dim hover:border-term-amber hover:text-term-amber"
            >
              {s}
            </button>
          ))}
        </div>
        <div className="mt-3 border-l-2 border-term-info bg-term-info/5 px-3 py-2 text-2xs text-term-dim">
          <span className="font-semibold uppercase tracking-wider text-term-info">Pluggable engine.</span> Answers today
          come from a grounded keyword engine that cites real records and says "not found" rather than guessing. A real
          Claude engine registers behind the same contract later — this UI and the API do not change.
        </div>
      </Panel>

      {err && (
        <div className="border border-term-down/50 bg-term-down/10 p-3 text-xs text-term-down">Query failed: {err}</div>
      )}

      {ans && (
        <Panel
          title="Answer"
          right={
            <div className="flex gap-2">
              <Chip className={ans.matched ? "border-term-up/40 text-term-up" : "border-term-border-2 text-term-muted"}>
                {ans.matched ? "grounded" : "no match"}
              </Chip>
              <Chip className="border-term-border-2 text-term-dim">engine: {ans.mode}</Chip>
            </div>
          }
        >
          <p className="text-sm leading-relaxed text-term-text">{ans.answer}</p>
          {ans.citations.length > 0 && (
            <div className="mt-4">
              <div className="label mb-2">citations</div>
              <div className="flex flex-col gap-2">
                {ans.citations.map((id) => {
                  const r = byId.get(id);
                  return (
                    <div key={id} className="border border-term-border bg-term-panel-2 px-3 py-2">
                      <span className="font-semibold text-term-amber">{id}</span>
                      {r && (
                        <>
                          <span className="ml-2 text-3xs text-term-muted">
                            {r.workflow} · {r.scope} · confidence {r.confidence} · confirmed {r.last_confirmed}
                          </span>
                          <div className="mt-1 text-xs text-term-text">{r.statement}</div>
                          <div className="text-3xs text-term-muted">{r.source_file}</div>
                        </>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </Panel>
      )}
    </div>
  );
}
