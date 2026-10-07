"""Allowlist configuration (``config/agent_skills.json``). Spec 0100 REQ-007, REQ-011, REQ-013.

The config names *groups* of upstream items; ``enabled_groups`` picks which are vendored. Each group item maps to an
upstream path: a skill is the directory ``skills/<name>/``, a command is ``.claude/commands/<name>.md``, a persona is
``agents/<name>.md`` and a reference is ``references/<file>``. ``excluded`` maps an upstream path or directory prefix
(ending in ``/``) to the reason it is kept out; an exclusion wins over a group.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONFIG_PATH = Path("config") / "agent_skills.json"

KIND_PATHS = {
    "skills": ("skills/", "/"),
    "commands": (".claude/commands/", ".md"),
    "agents": ("agents/", ".md"),
    "references": ("references/", ""),
}

# Items that conflict with QuantSmith's own flow (REQ-007). The gate reports any of these that gets vendored, even if
# someone removes it from ``excluded`` in the config: re-enabling one is a decision a reviewer must see (AC-006).
CONFLICTING = (
    "skills/spec-driven-development/",
    "skills/planning-and-task-breakdown/",
    "skills/using-agent-skills/",
    ".claude/commands/spec.md",
    ".claude/commands/plan.md",
    ".claude/commands/build.md",
    ".claude/commands/ship.md",
    "hooks/",
)


class ConfigError(ValueError):
    """The allowlist config is missing or malformed."""


@dataclass(frozen=True)
class Config:
    raw: dict[str, Any]
    root: Path
    groups: dict[str, dict[str, list[str]]] = field(default_factory=dict)

    @property
    def upstream(self) -> str:
        return self.raw["upstream"]

    @property
    def fork(self) -> str:
        return self.raw["fork"]

    @property
    def plugin_name(self) -> str:
        return self.raw["plugin_name"]

    @property
    def marketplace(self) -> str:
        return self.raw["marketplace"]

    @property
    def vendor_dir(self) -> Path:
        return self.root / self.raw["vendor_dir"]

    @property
    def lock_path(self) -> Path:
        return self.root / self.raw["lock"]

    @property
    def max_file_bytes(self) -> int:
        return int(self.raw["max_file_bytes"])

    @property
    def max_tree_bytes(self) -> int:
        return int(self.raw["max_tree_bytes"])

    @property
    def review_days(self) -> int:
        return int(self.raw["review_days"])

    @property
    def enabled_groups(self) -> list[str]:
        return sorted(self.raw["enabled_groups"])

    @property
    def excluded(self) -> dict[str, str]:
        return dict(self.raw.get("excluded", {}))

    @property
    def citing_agents(self) -> list[str]:
        return list(self.raw.get("citing_agents", []))

    def selection(self, groups: list[str] | None = None) -> list[str]:
        """Upstream paths (files, or directory prefixes ending in ``/``) the enabled groups select, sorted."""
        chosen = self.enabled_groups if groups is None else sorted(groups)
        paths = set(self.raw.get("always", []))
        for g in chosen:
            for kind, names in self.groups[g].items():
                prefix, suffix = KIND_PATHS[kind]
                paths.update(f"{prefix}{n}{suffix}" for n in names)
        return sorted(paths)

    def is_excluded(self, path: str) -> str | None:
        """The reason ``path`` is excluded, or ``None``."""
        for key, reason in self.excluded.items():
            if path == key or (key.endswith("/") and path.startswith(key)):
                return reason
        return None

    def enabled_items(self, kind: str) -> list[str]:
        out: set[str] = set()
        for g in self.enabled_groups:
            out.update(self.groups[g].get(kind, []))
        return sorted(out)


def bundled_config_path() -> Path | None:
    """The config shipped inside the wheel (spec 0100 REQ-012), for machines with no QuantSmith checkout."""
    try:
        from importlib import resources

        p = Path(str(resources.files("quantsmith").joinpath("_bundled", "agent_skills", "agent_skills.json")))
    except (ModuleNotFoundError, TypeError):
        return None
    return p if p.is_file() else None


def load_config(root: str | Path = ".") -> Config:
    """Load ``<root>/config/agent_skills.json``; without one, fall back to the copy bundled in the package."""
    root = Path(root).resolve()
    path = root / CONFIG_PATH
    if not path.is_file():
        path = bundled_config_path() or path
    if not path.is_file():
        raise ConfigError(f"config not found: {root / CONFIG_PATH} (and no bundled copy)")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path}: invalid JSON: {exc}") from exc
    required = ("upstream", "fork", "plugin_name", "marketplace", "vendor_dir", "lock", "max_file_bytes",
                "max_tree_bytes", "review_days", "enabled_groups", "groups")
    missing = [k for k in required if k not in raw]
    if missing:
        raise ConfigError(f"{path}: missing keys {missing}")
    groups = raw["groups"]
    for name, spec in groups.items():
        bad = sorted(set(spec) - set(KIND_PATHS))
        if bad:
            raise ConfigError(f"{path}: group {name!r} has unknown kinds {bad}; allowed {sorted(KIND_PATHS)}")
    unknown = sorted(set(raw["enabled_groups"]) - set(groups))
    if unknown:
        raise ConfigError(f"{path}: enabled_groups names undefined groups {unknown}")
    return Config(raw=raw, root=root, groups=groups)
