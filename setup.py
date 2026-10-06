"""Build hook for the ``quantsmith`` package. Spec ``0081`` (REQ-013, NFR-004).

All metadata lives in ``pyproject.toml``. This file only adds one build step:
copy the analytics domain pack catalog (``knowledge/analytics_packs/*.json``,
which lives in the repository scaffold, outside ``src/``) byte for byte into
the built package as read-only bundled defaults at
``quantsmith/_bundled/analytics_packs/``. A build that finds no packs fails
rather than shipping an empty bundle. The catalog is validated in CI before
any build (``tests/test_analytics_packs.py``), not here.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

PACKS_SOURCE = Path("knowledge") / "analytics_packs"
PACKS_BUNDLED = Path("quantsmith") / "_bundled" / "analytics_packs"


class BuildPyWithPacks(build_py):
    """``build_py`` plus the bundled analytics domain pack catalog."""

    def run(self) -> None:
        super().run()
        source = Path(__file__).resolve().parent / PACKS_SOURCE
        files = sorted(source.glob("*.json")) if source.is_dir() else []
        if not files:
            raise SystemExit(f"error: no analytics domain packs under {source}; refusing to build an empty bundle")
        dest = Path(self.build_lib) / PACKS_BUNDLED
        if dest.is_dir():
            shutil.rmtree(dest)  # a pack removed from the catalog must not linger in the bundle
        dest.mkdir(parents=True)
        for f in files:
            shutil.copyfile(f, dest / f.name)


setup(cmdclass={"build_py": BuildPyWithPacks})
