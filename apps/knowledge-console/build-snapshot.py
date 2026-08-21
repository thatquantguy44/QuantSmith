#!/usr/bin/env python3
"""Build the self-contained single-file Knowledge Terminal snapshot.

Mirrors web/build-snapshot.py for the Bloomberg-terminal app: runs the
single-file Vite build (hash-routed, since a snapshot opens from an arbitrary
base path), then embeds a current view-model as window.__KB_MODEL__ so the
result renders with no server and no network requests.

Usage:
    python apps/knowledge-console/build-snapshot.py [--root memory] [--out apps/knowledge-console/dist-single/terminal.html] [--no-build]
"""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
APP = Path(__file__).resolve().parent
SRC = REPO / "src"


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(REPO / "memory"))
    ap.add_argument("--out", default=str(APP / "dist-single" / "terminal.html"))
    ap.add_argument("--no-build", action="store_true")
    args = ap.parse_args(argv)

    single_html = APP / "dist-single" / "index.html"
    if not args.no_build:
        subprocess.run(["npm", "--prefix", str(APP), "run", "build:single"], check=True)
    if not single_html.is_file():
        print(f"error: {single_html} not found; run without --no-build first", file=sys.stderr)
        return 1

    sys.path.insert(0, str(SRC))
    from quantsmith.knowledge_console import model as model_mod  # noqa: E402

    model = model_mod.build_model_from_root(args.root, generated_at=_utc_now_iso())
    payload = json.dumps(model, ensure_ascii=False)

    html = single_html.read_text(encoding="utf-8")
    inject = "<script>window.__KB_MODEL__ = " + payload.replace("</", "<\\/") + ";</script>"
    idx = html.find("<script")
    html = html[:idx] + inject + "\n" + html[idx:] if idx != -1 else inject + html

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({len(html)} bytes, {model['counts']['total']} records embedded)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
