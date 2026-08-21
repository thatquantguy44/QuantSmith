#!/usr/bin/env python3
"""Build the self-contained single-file Knowledge Console snapshot.

Spec 0057 (T-010, REQ-012). Runs the single-file Vite build, embeds a current
view-model snapshot as ``window.__KB_MODEL__``, and writes one HTML file that
renders the whole UI with no server and no network requests — suitable for a
shareable preview or an Artifact.

Usage:
    python web/build-snapshot.py [--root memory] [--out web/dist-single/console.html] [--no-build]

Requires the front end to have been built once with `npm --prefix web run build:single`
(or run without --no-build to build it here).
"""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(REPO / "memory"))
    ap.add_argument("--out", default=str(REPO / "web" / "dist-single" / "console.html"))
    ap.add_argument("--no-build", action="store_true",
                    help="reuse an existing single-file build instead of rebuilding")
    args = ap.parse_args(argv)

    single_html = REPO / "web" / "dist-single" / "index.html"
    if not args.no_build:
        subprocess.run(["npm", "--prefix", str(REPO / "web"), "run", "build:single"],
                       check=True)
    if not single_html.is_file():
        print(f"error: {single_html} not found; run without --no-build first", file=sys.stderr)
        return 1

    # Build the model with the repo on the path (no install required).
    sys.path.insert(0, str(SRC))
    from quantsmith.knowledge_console import model as model_mod  # noqa: E402

    model = model_mod.build_model_from_root(args.root, generated_at=_utc_now_iso())
    payload = json.dumps(model, ensure_ascii=False)

    html = single_html.read_text(encoding="utf-8")
    inject = (
        "<script>window.__KB_MODEL__ = "
        + payload.replace("</", "<\\/")  # never let a record close the script tag
        + ";</script>"
    )
    # Inject just before the bundled module script so the model is defined first.
    marker = "<script"
    idx = html.find(marker)
    html = html[:idx] + inject + "\n" + html[idx:] if idx != -1 else inject + html

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({len(html)} bytes, {model['counts']['total']} records embedded)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
