"""Dataset Investigator — spec ``0099``.

Inspect one tabular dataset with registered deterministic tools, rank findings,
test hypotheses, validate every claim, and export the Python package that
reproduces each result. Needs the optional ``investigator`` extra
(``pip install quantsmith[investigator]``); nothing else in ``quantsmith``
imports this package.

* ``analysis/`` — the deterministic core, copied verbatim into every exported package;
* :mod:`.context` — what each language-model role may see (aggregates only);
* :mod:`.export` — builds the analysis package;
* :mod:`.cli` — ``quantsmith-dataset-investigator``;
* :mod:`.synthetic` — synthetic data with planted structure (tests, example, benchmark).
"""

from .analysis import Config, InvestigationState, investigate, reproduce, rerun
from .export import build_package

__all__ = ["Config", "InvestigationState", "build_package", "investigate", "reproduce", "rerun"]
