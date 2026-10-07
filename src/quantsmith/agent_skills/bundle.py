"""Bundle the vendored agent-skills subset into the built package. Spec 0100 REQ-012, AC-016.

Standard library only and free of package-relative imports: ``setup.py`` loads this file by path while the package is
being built. The bundle is a Claude Code marketplace root::

    _bundled/agent_skills/
      .claude-plugin/marketplace.json   (plugin "agent-skills", source "./agent-skills")
      agent-skills/                     (the vendored tree, re-hashed against the lock)
      agent-skills.lock.json
      agent_skills.json                 (the allowlist config, used when there is no checkout)

A vendored file that does not match the lock fails the build; with no lock (before the first sync) nothing is bundled.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

VENDOR = Path("vendor") / "agent-skills"
LOCK = Path("vendor") / "agent-skills.lock.json"
CONFIG = Path("config") / "agent_skills.json"
OWNED = (".claude-plugin/plugin.json", "README.md")


class BundleError(RuntimeError):
    """The vendored tree does not match its lock."""


def bundle(repo: Path, dest: Path) -> str:
    """Write the bundle to ``dest`` (replacing it). Returns a one-line summary."""
    vendor, lock_path = repo / VENDOR, repo / LOCK
    if dest.is_dir():
        shutil.rmtree(dest)
    if not lock_path.is_file():
        return "agent-skills: not vendored yet (no lock); nothing bundled"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    bad = sorted(rel for rel, digest in lock["files"].items()
                 if not (vendor / rel).is_file()
                 or "sha256:" + hashlib.sha256((vendor / rel).read_bytes()).hexdigest() != digest)
    missing_owned = [rel for rel in OWNED if not (vendor / rel).is_file()]
    if bad or missing_owned:
        raise BundleError(f"vendored agent-skills does not match its lock ({(bad + missing_owned)[:5]}); re-sync first")
    plugin = dest / "agent-skills"
    for rel in [*lock["files"], *OWNED]:
        (plugin / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(vendor / rel, plugin / rel)
    shutil.copyfile(lock_path, dest / "agent-skills.lock.json")
    shutil.copyfile(repo / CONFIG, dest / "agent_skills.json")
    (dest / ".claude-plugin").mkdir(parents=True)
    marketplace = {
        "name": "quantsmith-local",
        "description": "agent-skills subset bundled in the quantsmith package (spec 0100)",
        "owner": {"name": "QuantSmith"},
        "plugins": [{"name": "agent-skills", "source": "./agent-skills",
                     "description": "Pinned, allowlisted subset of addyosmani/agent-skills"}],
    }
    (dest / ".claude-plugin" / "marketplace.json").write_text(json.dumps(marketplace, indent=2) + "\n", encoding="utf-8")
    return f"agent-skills: bundled {len(lock['files'])} files at {lock.get('version')}"
