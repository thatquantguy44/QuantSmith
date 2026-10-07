"""Run metadata. Spec ``0099`` (REQ-015)."""

from __future__ import annotations

import platform
from importlib import metadata as _md
from typing import Any, Dict

from .models import InvestigationState

LIBRARIES = ("numpy", "pandas", "scipy", "scikit-learn", "pyarrow", "pydantic", "PyYAML", "matplotlib", "quantsmith")

# Fields that legitimately differ between two otherwise identical runs.
NON_DETERMINISTIC_FIELDS = ("created_at", "analyses[].duration_s", "python", "libraries")


def library_versions() -> Dict[str, str]:
    out = {}
    for lib in LIBRARIES:
        try:
            out[lib] = _md.version(lib)
        except _md.PackageNotFoundError:
            out[lib] = "not installed"
    return out


def run_metadata(state: InvestigationState) -> Dict[str, Any]:
    d = state.dataset
    return {
        "run_id": state.run_id,
        "spec_version": state.spec_version,
        "created_at": state.created_at,
        "python": platform.python_version(),
        "libraries": library_versions(),
        "random_seed": state.config.seed,
        "dataset": {"source": d.source, "format": d.format, "sha256": d.file_sha256,
                    "content_sha256": d.content_sha256, "rows": d.rows, "columns": d.columns},
        "analyses": [{"execution_id": e.execution_id, "function": e.tool, "module": f"dataset_analysis.{e.module}",
                      "version": e.version, "params": e.params, "origin": e.origin,
                      "sampled_rows": e.sampled_rows, "duration_s": e.duration_s}
                     for e in state.executions],
        "configuration": state.config.model_dump(mode="json"),
        "non_deterministic_fields": list(NON_DETERMINISTIC_FIELDS),
    }


def write_run_metadata(state: InvestigationState, path) -> None:
    import yaml

    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(run_metadata(state), fh, sort_keys=False, allow_unicode=True)
