import type { IncomingMessage } from "node:http";
import type { Plugin } from "vite";
import { handleApi, isApiPath } from "../src/server/router";

// Dev-only: dispatch /api/* to the same file-system route modules the production
// Node server uses, so the API contract is identical in `vite` dev and `npm start`.
function readJson(req: IncomingMessage): Promise<unknown> {
  return new Promise((resolve) => {
    const chunks: Buffer[] = [];
    req.on("data", (c) => chunks.push(c as Buffer));
    req.on("end", () => {
      if (chunks.length === 0) return resolve({});
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString("utf-8")));
      } catch {
        resolve({});
      }
    });
    req.on("error", () => resolve({}));
  });
}

export function devApi(): Plugin {
  return {
    name: "qf-dev-api",
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        const url = new URL(req.url || "/", "http://localhost");
        if (!isApiPath(url.pathname)) return next();
        const body = req.method === "POST" ? await readJson(req) : {};
        const result = await handleApi(req.method || "GET", url, body);
        res.statusCode = result.status;
        res.setHeader("Content-Type", "application/json; charset=utf-8");
        res.setHeader("Cache-Control", "no-store");
        res.end(JSON.stringify(result.json));
      });
    },
  };
}
