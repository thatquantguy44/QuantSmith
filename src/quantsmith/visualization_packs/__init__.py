"""Opt-in domain visualization packs and evidence-bound executive stories."""
from .catalog import Catalog, Selection, VisualizationError, load_catalog, validate_pack
from .evidence import Claim, Evidence, bind_claim, collect_evidence, validate_claim
from .render import render_html, render_json, render_markdown
from .story import Benchmark, Story, build_story, dashboard_handoff

__all__ = [
    "Benchmark", "Catalog", "Claim", "Evidence", "Selection", "Story", "VisualizationError",
    "bind_claim", "build_story", "collect_evidence", "dashboard_handoff", "load_catalog",
    "render_html", "render_json", "render_markdown", "validate_claim", "validate_pack",
]
