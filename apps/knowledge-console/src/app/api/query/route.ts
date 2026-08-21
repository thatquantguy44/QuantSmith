import { runQuery } from "../../../lib/pyModel";

// POST /api/query { question, k } -> grounded answer via the pluggable engine.
export async function POST(_url: URL, body: { question?: string; k?: number }) {
  const question = String(body?.question ?? "");
  const k = Number.isFinite(body?.k) ? Number(body?.k) : 5;
  if (!question.trim()) {
    return { status: 400, json: { error: "missing 'question'" } };
  }
  return { status: 200, json: await runQuery(question, k) };
}
