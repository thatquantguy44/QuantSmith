import { getModel } from "../../../lib/pyModel";

// GET /api/model -> the full 0057 view-model, recomputed from the memory/ store.
export async function GET(url: URL) {
  const force = url.searchParams.get("refresh") === "1";
  return { status: 200, json: await getModel(force) };
}
