import { health } from "../../../lib/pyModel";

// GET /api/health
export async function GET() {
  return { status: 200, json: health() };
}
