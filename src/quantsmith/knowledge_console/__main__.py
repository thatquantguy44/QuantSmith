"""CLI for the Knowledge Console.

    python -m quantsmith.knowledge_console serve    [--root memory] [--port 8765] [--static web/dist]
    python -m quantsmith.knowledge_console snapshot  [--root memory] [--out model.json]
    python -m quantsmith.knowledge_console print     [--root memory]   # model to stdout

Spec ``0057-knowledge-console`` (T-006, T-010). ``serve`` runs the API + static
front end; ``snapshot`` writes the current view-model as JSON for the
self-contained single-file build to embed.
"""

from __future__ import annotations

import argparse
import datetime
import sys

import json

from . import model as model_mod
from . import query as query_mod
from . import server as server_mod


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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

    p_print = sub.add_parser("print", help="print the view-model to stdout")
    p_print.add_argument("--root", default="memory")

    p_query = sub.add_parser("query", help="answer a question, print JSON to stdout")
    p_query.add_argument("--root", default="memory")
    p_query.add_argument("--question", required=True)
    p_query.add_argument("--k", type=int, default=5)

    args = parser.parse_args(argv)

    if args.command == "query":
        store = model_mod.load_store(args.root)
        records = [lr.record for lr in store.records]
        answer = query_mod.resolve_engine().answer(args.question, records, k=args.k)
        print(json.dumps(answer.to_dict(), ensure_ascii=False))
        return 0

    if args.command == "serve":
        static = args.static or None
        server_mod.serve(memory_root=args.root, static_dir=static,
                         host=args.host, port=args.port)
        return 0

    if args.command in ("snapshot", "print"):
        model = model_mod.build_model_from_root(args.root, generated_at=_utc_now_iso())
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
