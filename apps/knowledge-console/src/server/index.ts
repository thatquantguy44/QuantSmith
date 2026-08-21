// Production Node HTTP server. Serves the built client (dist/) and dispatches
// /api/* through the shared router (same route modules the dev plugin uses).
// Read-only; binds loopback by default. `npm start` runs this after `npm build`.

import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { extname, join, normalize, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { handleApi, isApiPath } from "./router";

const HERE = fileURLToPath(new URL(".", import.meta.url));
const CLIENT_DIR = resolve(HERE, "..", "dist");

const HOST = process.env.HOST || "127.0.0.1";
const PORT = Number(process.env.PORT || 8787);

const MIME: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".woff2": "font/woff2",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".map": "application/json; charset=utf-8",
};

function readJson(req: IncomingMessage): Promise<unknown> {
  return new Promise((res) => {
    const chunks: Buffer[] = [];
    req.on("data", (c) => chunks.push(c as Buffer));
    req.on("end", () => {
      if (!chunks.length) return res({});
      try {
        res(JSON.parse(Buffer.concat(chunks).toString("utf-8")));
      } catch {
        res({});
      }
    });
    req.on("error", () => res({}));
  });
}

function sendJson(res: ServerResponse, status: number, json: unknown): void {
  const body = JSON.stringify(json);
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  });
  res.end(body);
}

function serveStatic(res: ServerResponse, pathname: string): void {
  // Resolve within CLIENT_DIR only (traversal guard).
  const rel = normalize(decodeURIComponent(pathname)).replace(/^(\.\.[/\\])+/, "");
  let filePath = join(CLIENT_DIR, rel);
  if (!filePath.startsWith(CLIENT_DIR)) {
    res.writeHead(404).end("not found");
    return;
  }
  if (!existsSync(filePath) || statSync(filePath).isDirectory()) {
    // SPA fallback: unknown non-file routes are client-side React Router paths.
    filePath = join(CLIENT_DIR, "index.html");
  }
  if (!existsSync(filePath)) {
    res.writeHead(404).end("client build not found — run `npm run build`");
    return;
  }
  res.writeHead(200, { "Content-Type": MIME[extname(filePath)] || "application/octet-stream" });
  createReadStream(filePath).pipe(res);
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);
  if (isApiPath(url.pathname)) {
    const body = req.method === "POST" ? await readJson(req) : {};
    const result = await handleApi(req.method || "GET", url, body);
    return sendJson(res, result.status, result.json);
  }
  if (req.method !== "GET" && req.method !== "HEAD") {
    return sendJson(res, 405, { error: "method not allowed" });
  }
  serveStatic(res, url.pathname);
});

server.listen(PORT, HOST, () => {
  // eslint-disable-next-line no-console
  console.log(`QuantSmith Knowledge Terminal on http://${HOST}:${PORT}`);
});
