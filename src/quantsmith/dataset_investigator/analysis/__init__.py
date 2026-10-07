"""Dataset analysis — the deterministic core of the Dataset Investigator (spec ``0099``).

This directory is self-contained: an exported analysis package carries a
byte-identical copy of it as ``dataset_analysis``. Importing it registers every
analysis tool.

High level::

    from dataset_analysis import investigate
    state = investigate("transactions.parquet", out_dir="investigation_run")

Individual tools::

    from dataset_analysis.anomalies import detect_outliers
"""

from . import (  # noqa: F401  (register tools)
    anomalies,
    distributions,
    profile,
    quality,
    relationships,
    segmentation,
    temporal,
)
from .models import Config, InvestigationState
from .pipeline import investigate, reproduce, rerun
from .registry import TOOL_REGISTRY, catalog

__all__ = ["TOOL_REGISTRY", "Config", "InvestigationState", "catalog", "investigate", "reproduce", "rerun"]
