// Bridge to the Python view-model — the single source of truth.
//
// The 0057 Python package (quantsmith.knowledge_console) already parses the
// memory/ store into the 0048 record model and derives counts, trends, the
// knowledge graph, the git changes feed, and the review queue. Rather than
// re-implement any of that in TypeScript (which would duplicate tested logic and
// drift from it), this terminal shells out to the Python CLI and renders what it
// returns. Same store, one definition of "the model".

import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { Model, QueryAnswer } from "./types";

const PY = process.env.QF_PYTHON || "python3";
const CACHE_MS = 3000;

let cache: { at: number; model: Model } | null = null;

function findRepoRoot(): string {
  if (process.env.QF_REPO_ROOT) return process.env.QF_REPO_ROOT;
  const starts = [process.cwd(), dirname(fileURLToPath(import.meta.url))];
  for (const start of starts) {
    let dir = start;
    for (let i = 0; i < 8; i += 1) {
      if (existsSync(join(dir, "memory", "manifest.yaml"))) return dir;
      const parent = resolve(dir, "..");
      if (parent === dir) break;
      dir = parent;
    }
  }
  // Fall back to three levels up from apps/knowledge-console/*.
  return resolve(process.cwd(), "..", "..");
}

const repoRoot = findRepoRoot();
const memoryRoot = process.env.QF_MEMORY_ROOT || join(repoRoot, "memory");

function runPython(args: string[]): Promise<string> {
  return new Promise((res, rej) => {
    execFile(
      PY,
      ["-m", "quantsmith.knowledge_console", ...args],
      {
        cwd: repoRoot,
        env: { ...process.env, PYTHONPATH: join(repoRoot, "src") },
        timeout: 15000,
        maxBuffer: 32 * 1024 * 1024,
      },
      (err, stdout) => (err ? rej(err) : res(stdout)),
    );
  });
}

function emptyModel(): Model {
  const nowIso = new Date().toISOString();
  return {
    generated_at: nowIso,
    as_of: nowIso.slice(0, 10),
    freshness_days: 90,
    counts: {
      total: 0,
      by_type: {},
      by_status: {},
      by_confidence: {},
      by_access_level: {},
      by_workflow: {},
    },
    records: [],
    trends: {
      cumulative_by_date: [],
      confirmations_by_month: [],
      staleness: { fresh: 0, overdue: 0 },
    },
    graph: { nodes: [], edges: [] },
    changes: [],
    review_queue: [],
    findings: [],
  };
}

export async function getModel(force = false): Promise<Model> {
  if (!force && cache && Date.now() - cache.at < CACHE_MS) return cache.model;
  try {
    const out = await runPython(["print", "--root", memoryRoot]);
    const model = JSON.parse(out) as Model;
    cache = { at: Date.now(), model };
    return model;
  } catch {
    // Degrade to a well-formed empty model (parity with Python NFR-005).
    return emptyModel();
  }
}

export async function runQuery(question: string, k = 5): Promise<QueryAnswer> {
  const q = (question || "").trim();
  if (!q) {
    return { answer: "Ask a question about the store.", citations: [], mode: "keyword", matched: false };
  }
  try {
    const out = await runPython([
      "query",
      "--root",
      memoryRoot,
      "--question",
      q,
      "--k",
      String(k),
    ]);
    return JSON.parse(out) as QueryAnswer;
  } catch {
    return {
      answer: "The query engine is unavailable right now.",
      citations: [],
      mode: "keyword",
      matched: false,
    };
  }
}

export function health() {
  return { status: "ok", generated_at: new Date().toISOString(), memory_root: memoryRoot, repo_root: repoRoot };
}
