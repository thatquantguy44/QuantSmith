"""Knowledge Console — a read-only analytics surface over the memory store.

Spec ``0057-knowledge-console``. Builds on ``0002`` (the store) and ``0048``
(``workflow_memory``: the parser, typed ``Record``, ``query``, ``validate``).

This package turns the machine-readable store into a *legible* one:

- ``model`` — a filesystem store-loader (``load_store``) and a pure view-model
  builder (``build_model``): counts, trend series, a knowledge graph, a git
  changes feed, and a needed-review queue.
- ``query`` — a pluggable natural-language query seam: a ``QueryEngine``
  protocol, a grounded ``KeywordQueryEngine`` default, and ``resolve_engine`` so
  a real LLM engine can register later behind the same contract.
- ``server`` — a standard-library HTTP server exposing the view-model and the
  query endpoint, and serving the built front end (see ``web/``).

Everything here is read-only: no code path writes, deletes, or renames anything
under ``memory/`` (spec NFR-003). Standard library only (spec NFR-001).
"""

from __future__ import annotations

from .model import (
    LoadedRecord,
    Store,
    build_model,
    git_changes,
    load_store,
)
from .query import (
    Answer,
    KeywordQueryEngine,
    QueryEngine,
    register_engine,
    resolve_engine,
)

__all__ = [
    "LoadedRecord",
    "Store",
    "load_store",
    "git_changes",
    "build_model",
    "QueryEngine",
    "KeywordQueryEngine",
    "Answer",
    "resolve_engine",
    "register_engine",
]
