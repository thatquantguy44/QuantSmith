// Data access. The console runs in two modes, and this module is the only place
// that knows the difference (spec REQ-011, AC-013):
//
//   embedded  -> a self-contained snapshot injected `window.__KB_MODEL__`; there
//                is no server, so we read that and never touch the network.
//   served    -> the stdlib API server is up; we fetch `/api/model` and post to
//                `/api/query`.
//
// The embedded model is checked FIRST, before any fetch, so a static snapshot
// works offline with zero requests.

import type { Model, QueryAnswer, RecordView } from "./types";

export function isEmbedded(): boolean {
  return typeof window !== "undefined" && !!window.__KB_MODEL__;
}

export async function loadModel(): Promise<Model> {
  if (typeof window !== "undefined" && window.__KB_MODEL__) {
    return window.__KB_MODEL__;
  }
  const res = await fetch("/api/model", { headers: { Accept: "application/json" } });
  if (!res.ok) {
    throw new Error(`Failed to load model: HTTP ${res.status}`);
  }
  return (await res.json()) as Model;
}

// Natural-language query. When served, delegate to the pluggable server engine;
// when embedded (no server), run the same grounded keyword search in-browser so
// the Ask view still works offline — mirroring KeywordQueryEngine's contract:
// cite only real ids, and return nothing (matched=false) on zero overlap.
export async function askQuestion(
  question: string,
  model: Model,
  k = 5,
): Promise<QueryAnswer> {
  if (!isEmbedded()) {
    const res = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, k }),
    });
    if (!res.ok) throw new Error(`Query failed: HTTP ${res.status}`);
    return (await res.json()) as QueryAnswer;
  }
  return localKeywordAnswer(question, model.records, k);
}

const STOPWORDS = new Set(
  ("a an and are as at be but by for from how in into is it its no not of on or " +
    "that the their then there these this to use used using was what when where " +
    "which who why with you your do does can could should would we our")
    .split(" "),
);

function tokenize(text: string): string[] {
  return (text.toLowerCase().match(/[a-z0-9]+/g) || []).filter(
    (t) => t.length > 1 && !STOPWORDS.has(t),
  );
}

export function localKeywordAnswer(
  question: string,
  records: RecordView[],
  k = 5,
): QueryAnswer {
  const terms = new Set(tokenize(question));
  if (terms.size === 0 || records.length === 0) {
    return { answer: "Nothing in the store matched that question.", citations: [], mode: "keyword (local)", matched: false };
  }
  const scored: { overlap: number; rec: RecordView }[] = [];
  for (const rec of records) {
    const hay = new Set(tokenize(`${rec.statement} ${rec.scope} ${rec.type}`));
    let overlap = 0;
    terms.forEach((t) => { if (hay.has(t)) overlap += 1; });
    if (overlap > 0) scored.push({ overlap, rec });
  }
  if (scored.length === 0) {
    return {
      answer:
        'Nothing in the store matched that question. Treat that as "not found", not as "no".',
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
    .map(
      (r) =>
        `[${r.id}] ${r.statement} (confidence ${r.confidence}, confirmed ${r.last_confirmed})`,
    )
    .join("; ");
  return {
    answer: `${scored.length} record(s) touch that question. Most relevant: ${body}. Grounded in ${top.length} record(s).`,
    citations: top.map((r) => r.id),
    mode: "keyword (local)",
    matched: true,
  };
}
