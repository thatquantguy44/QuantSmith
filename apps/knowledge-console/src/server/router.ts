// Shared API dispatcher — the one request path used by BOTH the dev plugin and
// the production Node server, so /api/* behaves identically in dev and prod.
//
// Route modules live under src/app/api/**/route.ts (file-system routing
// convention) and export HTTP-verb functions (GET/POST/...). They are registered
// here by their URL path; a static registry keeps the bundler happy where a
// runtime directory scan would not survive bundling.

import * as healthRoute from "../app/api/health/route";
import * as modelRoute from "../app/api/model/route";
import * as queryRoute from "../app/api/query/route";

export interface ApiResult {
  status: number;
  json: unknown;
}

type Verb = (url: URL, body: unknown) => Promise<ApiResult> | ApiResult;

const routes: Record<string, Record<string, Verb>> = {
  "/api/health": healthRoute as Record<string, Verb>,
  "/api/model": modelRoute as Record<string, Verb>,
  "/api/query": queryRoute as Record<string, Verb>,
};

export function isApiPath(pathname: string): boolean {
  return pathname.startsWith("/api/");
}

export async function handleApi(
  method: string,
  url: URL,
  body: unknown,
): Promise<ApiResult> {
  const mod = routes[url.pathname];
  if (!mod) return { status: 404, json: { error: "not found" } };
  const fn = mod[method.toUpperCase()];
  if (typeof fn !== "function") {
    return { status: 405, json: { error: "method not allowed" } };
  }
  try {
    return await fn(url, body);
  } catch (err) {
    return { status: 500, json: { error: "internal error", detail: String(err) } };
  }
}
