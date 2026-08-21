import type { Model, QueryAnswer, RecordView, ResearchModel } from "./types";

// Two modes, decided here and nowhere else:
//   served    -> the Node API is up; fetch /api/model, /api/research, POST /api/query.
//   embedded  -> a self-contained snapshot injected window.__KB_MODEL__ /
//                window.__KB_RESEARCH__ (no server); read those and run the Ask
//                query in-browser.
function embedded(): Model | null {
  return typeof window !== "undefined" && window.__KB_MODEL__ ? window.__KB_MODEL__ : null;
}

function embeddedResearch(): ResearchModel | null {
  return typeof window !== "undefined" && window.__KB_RESEARCH__ ? window.__KB_RESEARCH__ : null;
}

export function isEmbedded(): boolean {
  return embedded() !== null;
}

export async function fetchModel(refresh = false): Promise<Model> {
  const snap = embedded();
  if (snap) return snap;
  const res = await fetch(`/api/model${refresh ? "?refresh=1" : ""}`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`GET /api/model -> ${res.status}`);
  return (await res.json()) as Model;
}

export async function fetchResearch(refresh = false): Promise<ResearchModel> {
  const snap = embeddedResearch();
  if (snap) return snap;
  const res = await fetch(`/api/research${refresh ? "?refresh=1" : ""}`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`GET /api/research -> ${res.status}`);
  return (await res.json()) as ResearchModel;
}

export async function askQuestion(question: string, k = 5): Promise<QueryAnswer> {
  const snap = embedded();
  if (snap) return localKeywordAnswer(question, snap.records, k);
  const res = await fetch("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, k }),
  });
  if (!res.ok) throw new Error(`POST /api/query -> ${res.status}`);
  return (await res.json()) as QueryAnswer;
}

const STOPWORDS = new Set(
  ("a an and are as at be but by for from how in into is it its no not of on or " +
    "that the their then there these this to use used using was what when where " +
    "which who why with you your do does can could should would we our")
    .split(" "),
);
function tokenize(text: string): string[] {
  return (text.toLowerCase().match(/[a-z0-9]+/g) || []).filter((t) => t.length > 1 && !STOPWORDS.has(t));
}

// Mirror of KeywordQueryEngine for the server-less snapshot: cite only real ids,
// return matched=false with no citations on zero overlap (never invent one).
export function localKeywordAnswer(question: string, records: RecordView[], k = 5): QueryAnswer {
  const terms = new Set(tokenize(question));
  if (terms.size === 0 || records.length === 0) {
    return { answer: "Nothing in the store matched that question.", citations: [], mode: "keyword (local)", matched: false };
  }
  const scored: { overlap: number; rec: RecordView }[] = [];
  for (const rec of records) {
    const hay = new Set(tokenize(`${rec.statement} ${rec.scope} ${rec.type}`));
    let overlap = 0;
    terms.forEach((t) => {
      if (hay.has(t)) overlap += 1;
    });
    if (overlap > 0) scored.push({ overlap, rec });
  }
  if (scored.length === 0) {
    return {
      answer: 'Nothing in the store matched that question. Treat that as "not found", not as "no".',
      citations: [],
      mode: "keyword (local)",
      matched: false,
    };
  }
  const rank: Record<string, number> = { high: 3, medium: 2, low: 1 };
  scored.sort(
    (a, b) =>
      b.overlap - a.overlap ||
      (rank[b.rec.confidence] || 0) - (rank[a.rec.confidence] || 0) ||
      b.rec.corroboration_derived - a.rec.corroboration_derived ||
      a.rec.id.localeCompare(b.rec.id),
  );
  const top = scored.slice(0, Math.max(1, k)).map((s) => s.rec);
  const body = top
    .map((r) => `[${r.id}] ${r.statement} (confidence ${r.confidence}, confirmed ${r.last_confirmed})`)
    .join("; ");
  return {
    answer: `${scored.length} record(s) touch that question. Most relevant: ${body}. Grounded in ${top.length} record(s).`,
    citations: top.map((r) => r.id),
    mode: "keyword (local)",
    matched: true,
  };
}
