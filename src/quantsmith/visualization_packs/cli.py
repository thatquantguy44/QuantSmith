"""Catalog validation, coverage, and an explicit local demonstration command."""
import argparse
import json
from pathlib import Path

from .catalog import VisualizationError, load_catalog
from .example import run_example
from .render import render_html, render_json, render_markdown


def main(argv=None):
    parser = argparse.ArgumentParser(description="Domain visualization packs (0093)")
    parser.add_argument("command", choices=("validate", "coverage", "demo"))
    parser.add_argument("--root", default=".", help="Repository/catalog root")
    parser.add_argument("--output-dir", help="Explicit local artifact destination for demo")
    args = parser.parse_args(argv)
    try:
        catalog = load_catalog(args.root)
        if args.command == "coverage":
            print(json.dumps(catalog.coverage(), indent=2))
        elif args.command == "validate":
            print(f"Validated {len(catalog.packs)} visualization packs and {sum(len(p['recipes']) for p in catalog.packs.values())} recipes.")
        else:
            stories = run_example(args.root)
            if args.output_dir:
                out = Path(args.output_dir)
                out.mkdir(parents=True, exist_ok=True)
                for name, story in stories.items():
                    for extension, render in (("html", render_html), ("json", render_json), ("md", render_markdown)):
                        (out / f"{name}.{extension}").write_text(render(story), encoding="utf-8")
            print(json.dumps({name: {"status": s.status, "reason": s.reason} for name, s in stories.items()}, indent=2))
            return 0 if all(s.status == "ready" for name, s in stories.items() if name != "refused_pd_sum") and stories["refused_pd_sum"].status == "invalid" else 1
    except (VisualizationError, ValueError, OSError) as exc:
        parser.exit(1, str(exc) + "\n")
    return 0
