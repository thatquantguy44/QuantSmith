"""CLI for the Knowledge Console.

    python -m quantsmith.knowledge_console serve    [--root memory] [--port 8765] [--static web/dist]
    python -m quantsmith.knowledge_console snapshot  [--root memory] [--out model.json]
    python -m quantsmith.knowledge_console print     [--root memory]   # model to stdout
    python -m quantsmith.knowledge_console query     --question "..." [--root memory]
    python -m quantsmith.knowledge_console research  [--root research]  # research model to stdout
    python -m quantsmith.knowledge_console preview-access [--viewer-override HANDLE_OR_LEVEL]

Spec ``0057-knowledge-console`` (T-006, T-010). ``serve`` runs the API + static
front end; ``snapshot`` writes the current view-model as JSON for the
self-contained single-file build to embed.

``--viewer-override`` (spec 0058 REQ-014, on ``print``/``snapshot``/``research``/
``query``) previews what a specific roster handle or clearance level
(``public``/``internal``/``restricted``) would see, without changing who is
actually running the process. ``preview-access`` is the same preview reduced
to counts, for a quick "what would change" check before editing the roster.
"""

from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

import json

from . import model as model_mod
from . import query as query_mod
from . import research as research_mod
from . import server as server_mod
from quantsmith.pipelines import access_control


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _viewer_filtered_records(root: str, viewer_clearance):
    store = model_mod.load_store(root)
    records = [lr.record for lr in store.records]
    if viewer_clearance is None:
        return records
    return [r for r in records
            if access_control.access_level_allows(r.access_level, viewer_clearance)]


def _preview_access(root: str, research_root: str, viewer_override):
    """Counts-only preview (spec 0058 REQ-014): visible vs. total, no full model."""
    mem_root_path = Path(root)
    mem_access_root = mem_root_path.parent if mem_root_path.name else mem_root_path
    clearance = access_control.resolve_viewer_clearance(
        override=viewer_override, root=mem_access_root)

    mem_store = model_mod.load_store(root)
    mem_total = len(mem_store.records)
    mem_visible = mem_total if clearance is None else sum(
        1 for lr in mem_store.records
        if access_control.access_level_allows(lr.record.access_level, clearance)
    )

    res_store = research_mod.load_research_store(research_root)
    res_total = len(res_store.items)
    res_visible = res_total if clearance is None else sum(
        1 for it in res_store.items
        if access_control.access_level_allows(it.access_level, clearance)
    )

    return {
        "viewer_override": viewer_override,
        "resolved_clearance": clearance,
        "enforced": clearance is not None,
        "memory": {"total": mem_total, "visible": mem_visible},
        "research": {"total": res_total, "visible": res_visible},
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="quantsmith.knowledge_console",
                                     description="Read-only analytics console over the memory store.")
    sub = parser.add_subparsers(dest="command")

    p_serve = sub.add_parser("serve", help="run the API + front-end server")
    p_serve.add_argument("--root", default="memory", help="memory/ store root")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8765)
    p_serve.add_argument("--static", default="web/dist",
                         help="built front-end directory (served at /)")

    p_snap = sub.add_parser("snapshot", help="write the view-model as JSON")
    p_snap.add_argument("--root", default="memory")
    p_snap.add_argument("--out", default="-", help="output file, or - for stdout")
    p_snap.add_argument("--viewer-override", default=None,
                        help="preview as a roster handle or clearance level")

    p_print = sub.add_parser("print", help="print the view-model to stdout")
    p_print.add_argument("--root", default="memory")
    p_print.add_argument("--viewer-override", default=None,
                         help="preview as a roster handle or clearance level")

    p_query = sub.add_parser("query", help="answer a question, print JSON to stdout")
    p_query.add_argument("--root", default="memory")
    p_query.add_argument("--question", required=True)
    p_query.add_argument("--k", type=int, default=5)
    p_query.add_argument("--viewer-override", default=None,
                         help="preview as a roster handle or clearance level")

    p_research = sub.add_parser("research", help="print the research-store model to stdout")
    p_research.add_argument("--root", default="research")
    p_research.add_argument("--viewer-override", default=None,
                            help="preview as a roster handle or clearance level")

    p_preview = sub.add_parser(
        "preview-access",
        help="show visible-vs-total counts for a viewer, without changing identity")
    p_preview.add_argument("--root", default="memory")
    p_preview.add_argument("--research-root", default="research")
    p_preview.add_argument("--viewer-override", default=None,
                           help="preview as a roster handle or clearance level")

    args = parser.parse_args(argv)

    if args.command == "research":
        model = research_mod.build_research_model_from_root(
            args.root, generated_at=_utc_now_iso(), viewer_override=args.viewer_override)
        print(json.dumps(model, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "query":
        access_root = Path(args.root).parent if Path(args.root).name else Path(args.root)
        viewer_clearance = access_control.resolve_viewer_clearance(
            override=args.viewer_override, root=access_root)
        records = _viewer_filtered_records(args.root, viewer_clearance)
        answer = query_mod.resolve_engine().answer(args.question, records, k=args.k)
        print(json.dumps(answer.to_dict(), ensure_ascii=False))
        return 0

    if args.command == "serve":
        static = args.static or None
        server_mod.serve(memory_root=args.root, static_dir=static,
                         host=args.host, port=args.port)
        return 0

    if args.command == "preview-access":
        summary = _preview_access(args.root, args.research_root, args.viewer_override)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command in ("snapshot", "print"):
        model = model_mod.build_model_from_root(
            args.root, generated_at=_utc_now_iso(), viewer_override=args.viewer_override)
        text = model_mod.model_json(model)
        out = getattr(args, "out", "-")
        if out in ("-", None):
            print(text)
        else:
            with open(out, "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
            print(f"wrote {out} ({model['counts']['total']} record(s))", file=sys.stderr)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
