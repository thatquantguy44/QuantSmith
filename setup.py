"""Build hook for the ``quantsmith`` package. Spec ``0081`` (REQ-013, NFR-004).

All metadata lives in ``pyproject.toml``. This file only adds one build step:
copy the analytics domain pack catalog (``knowledge/analytics_packs/*.json``,
which lives in the repository scaffold, outside ``src/``) byte for byte into
the built package as read-only bundled defaults at
``quantsmith/_bundled/analytics_packs/``. A build that finds no packs fails
rather than shipping an empty bundle. The catalog is validated in CI before
any build (``tests/test_analytics_packs.py``), not here.

Spec ``0100`` (REQ-012) adds a second step: the vendored agent-skills subset
(``vendor/agent-skills/`` plus its lock) is bundled at
``quantsmith/_bundled/agent_skills/`` as a local Claude Code marketplace, so
``quantsmith-agent-skills install --scope user`` works with no checkout. Every
vendored file is re-hashed against the lock first; a mismatch fails the build.
Before the first sync there is nothing to bundle and the step is skipped.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

PACKS_SOURCE = Path("knowledge") / "analytics_packs"
PACKS_BUNDLED = Path("quantsmith") / "_bundled" / "analytics_packs"


def bundle_agent_skills(repo: Path, build_lib: Path) -> None:
    """Spec 0100 REQ-012. Loaded by file path: the package is not importable while it is being built."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_qs_agent_skills_bundle", repo / "src" / "quantsmith" / "agent_skills" / "bundle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    print(module.bundle(repo, build_lib / "quantsmith" / "_bundled" / "agent_skills"))


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
        bundle_agent_skills(Path(__file__).resolve().parent, Path(self.build_lib))


setup(cmdclass={"build_py": BuildPyWithPacks})
