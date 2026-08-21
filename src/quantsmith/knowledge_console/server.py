"""Standard-library HTTP server for the Knowledge Console.

Spec ``0057-knowledge-console`` (T-006, REQ-007, NFR-001, NFR-003). Three JSON
routes plus static serving for the built front end — no third-party web
framework (the API is small enough that a framework is not earned).

Guarantees:

- **Read-only.** No route writes, deletes, or renames anything (spec NFR-003).
- **Loopback by default.** Binds ``127.0.0.1`` unless a host is passed.
- **Traversal-guarded static serving.** A request can only reach files inside
  the served directory; anything else is a 404, never a traceback (AC-014).
- **Stdlib only** (spec NFR-001).

Routes:

- ``GET  /api/health`` → ``{"status": "ok", ...}``
- ``GET  /api/model``  → the full view-model (recomputed per request, so a live
  tree is always shown fresh)
- ``POST /api/query``  → ``{"question", "k"}`` → grounded answer via the active
  :class:`~quantsmith.knowledge_console.query.QueryEngine`
"""

from __future__ import annotations

import datetime
import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

from . import model as model_mod
from . import query as query_mod


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ConsoleConfig:
    """What one server instance serves."""

    def __init__(self, memory_root: str | os.PathLike = "memory",
                 static_dir: Optional[str | os.PathLike] = None) -> None:
        self.memory_root = str(memory_root)
        self.static_dir = Path(static_dir).resolve() if static_dir else None


class ConsoleHandler(BaseHTTPRequestHandler):
    server_version = "QuantSmithKnowledgeConsole/0.1"
    config: ConsoleConfig = ConsoleConfig()  # replaced by the factory

    # --- helpers ----------------------------------------------------------

    def _send_json(self, obj, status: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_bytes(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _not_found(self) -> None:
        self._send_json({"error": "not found"}, status=404)

    def log_message(self, fmt, *args):  # noqa: D401 - quiet by default
        """Silence the default stderr access log; tests and CLI stay clean."""
        return

    # --- static serving with a traversal guard (AC-014, NFR-003) ----------

    def _serve_static(self, path: str) -> None:
        static_dir = self.config.static_dir
        if static_dir is None or not static_dir.is_dir():
            # No built front end available: point at the API rather than 500.
            if path in ("/", "/index.html"):
                self._send_bytes(_PLACEHOLDER_HTML.encode("utf-8"),
                                 "text/html; charset=utf-8")
            else:
                self._not_found()
            return

        rel = unquote(path.lstrip("/")) or "index.html"
        candidate = (static_dir / rel).resolve()
        try:
            candidate.relative_to(static_dir)
        except ValueError:
            self._not_found()  # escaped the served directory
            return
        if candidate.is_dir():
            candidate = candidate / "index.html"
        if not candidate.is_file():
            self._not_found()
            return

        ctype, _ = mimetypes.guess_type(str(candidate))
        if candidate.suffix == ".js":
            ctype = "text/javascript"
        try:
            self._send_bytes(candidate.read_bytes(),
                             ctype or "application/octet-stream")
        except OSError:
            self._not_found()

    # --- routes -----------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        route = urlparse(self.path).path
        if route == "/api/health":
            self._send_json({"status": "ok", "generated_at": _utc_now_iso(),
                             "memory_root": self.config.memory_root})
        elif route == "/api/model":
            self._send_json(self._build_model())
        elif route.startswith("/api/"):
            self._not_found()
        else:
            self._serve_static(route)

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_POST(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        if route != "/api/query":
            self._not_found()
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            length = 0
        raw = self.rfile.read(length) if length > 0 else b""
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json({"error": "invalid JSON body"}, status=400)
            return

        question = str(payload.get("question", "")).strip()
        k = payload.get("k", 5)
        try:
            k = int(k)
        except (TypeError, ValueError):
            k = 5
        if not question:
            self._send_json({"error": "missing 'question'"}, status=400)
            return

        store = model_mod.load_store(self.config.memory_root)
        records = [lr.record for lr in store.records]
        engine = query_mod.resolve_engine()
        self._send_json(engine.answer(question, records, k=k).to_dict())

    # --- model --------------------------------------------------------------

    def _build_model(self) -> dict:
        return model_mod.build_model_from_root(
            self.config.memory_root, generated_at=_utc_now_iso())


_PLACEHOLDER_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>QuantSmith Knowledge Console</title></head><body
style="font-family:system-ui,sans-serif;max-width:40rem;margin:4rem auto;padding:0 1rem">
<h1>Knowledge Console</h1>
<p>The API is running. The built front end was not found.</p>
<p>Build it with <code>npm --prefix web install &amp;&amp; npm --prefix web run build</code>,
then restart the server, or query the API directly:</p>
<ul><li><a href="/api/model">/api/model</a></li><li><a href="/api/health">/api/health</a></li></ul>
</body></html>"""


def make_server(memory_root: str | os.PathLike = "memory",
                static_dir: Optional[str | os.PathLike] = None,
                host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    """Build (but do not start) a console server.

    ``port=0`` asks the OS for an ephemeral port — used by the tests. Binds
    loopback by default (spec NFR-003).
    """
    config = ConsoleConfig(memory_root=memory_root, static_dir=static_dir)

    handler = type("BoundConsoleHandler", (ConsoleHandler,), {"config": config})
    return ThreadingHTTPServer((host, port), handler)


def serve(memory_root: str | os.PathLike = "memory",
          static_dir: Optional[str | os.PathLike] = None,
          host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run the console server until interrupted."""
    httpd = make_server(memory_root, static_dir, host, port)
    bound_host, bound_port = httpd.server_address[:2]
    print(f"Knowledge Console on http://{bound_host}:{bound_port}  "
          f"(memory: {memory_root}, static: {static_dir or 'none'})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
