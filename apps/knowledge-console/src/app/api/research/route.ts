import { getResearch } from "../../../lib/pyModel";

// GET /api/research -> the market-research reference-store model.
// Reference implementation of spec 0056 (Draft) — see research/README.md.
export async function GET(url: URL) {
  const force = url.searchParams.get("refresh") === "1";
  return { status: 200, json: await getResearch(force) };
}
