"""Which copy is in effect, does it match the lock, and is a review due. Spec 0100 REQ-006, REQ-012, REQ-014, RISK-008.

Resolution order (plan: Approach): ``QS_AGENT_SKILLS_PATH`` override, then the repo's ``vendor/agent-skills/``, then the
copy bundled in the ``quantsmith`` wheel. Reads local files only; Claude Code's own registry under ``~/.claude/plugins``
is read to report whether this checkout has opted in and whether another agent-skills install could load alongside it.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
from importlib import resources
from pathlib import Path

from .config import Config
from .source import Snapshot, _from_dir
from .vendor import plan_sync, read_lock, sha256, verify

OVERRIDE_ENV = "QS_AGENT_SKILLS_PATH"
BUNDLE_PARTS = ("_bundled", "agent_skills")  # a marketplace root: .claude-plugin/marketplace.json + agent-skills/


def bundled_marketplace() -> Path | None:
    try:
        root = Path(str(resources.files("quantsmith").joinpath(*BUNDLE_PARTS)))
    except (ModuleNotFoundError, TypeError):
        return None
    return root if (root / ".claude-plugin" / "marketplace.json").is_file() else None


def _head(path: Path) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, check=False)
    except FileNotFoundError:
        return None
    return r.stdout.decode().strip() if r.returncode == 0 else None


def _matches(locked: dict[str, str], files: dict[str, bytes]) -> bool:
    return {p: sha256(b) for p, b in files.items()} == locked


def review_state(lock: dict | None, review_days: int, today: dt.date) -> dict:
    if not lock or not lock.get("synced_on"):
        return {"due": False, "age_days": None, "review_days": review_days}
    age = (today - dt.date.fromisoformat(lock["synced_on"])).days
    return {"due": age > review_days, "age_days": age, "review_days": review_days}


def claude_registry(cfg: Config, home: Path) -> dict:
    plugins = home / ".claude" / "plugins"
    known = _load(plugins / "known_marketplaces.json")
    installed = _load(plugins / "installed_plugins.json").get("plugins", {})
    mine = known.get(cfg.marketplace, {}).get("source", {})
    registered = mine.get("source") == "directory" and Path(mine.get("path", "")).resolve() == cfg.root
    duplicates = sorted(k for k in installed if k.split("@")[0] == cfg.plugin_name and k.split("@")[-1] != cfg.marketplace)
    remote = sorted(n for n, m in known.items()
                    if (m.get("source") or {}).get("repo") in (cfg.upstream, cfg.fork))
    return {"registered_here": registered, "duplicate_installs": duplicates, "remote_marketplaces": remote}


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def status(cfg: Config, env: dict | None = None, home: Path | None = None, today: dt.date | None = None) -> dict:
    env = os.environ if env is None else env
    home = Path.home() if home is None else home
    today = today or dt.datetime.now(dt.timezone.utc).date()
    lock = read_lock(cfg)
    out: dict = {"lock": None, "in_effect": None, "findings": [], "notes": []}
    if lock:
        out["lock"] = {k: lock.get(k) for k in ("commit", "version", "plugin_version", "synced_on", "source_kind")}

    override = env.get(OVERRIDE_ENV)
    bundle = bundled_marketplace()
    if override:
        path = Path(override).expanduser().resolve()
        if not path.is_dir():
            out["findings"].append(f"{OVERRIDE_ENV}={override}: not a directory")
        else:
            plan = plan_sync(cfg, Snapshot("directory", _head(path), _from_dir(path)), today)
            matches = bool(lock) and plan.ok and _matches(lock["files"], plan.files)
            out["in_effect"] = {"kind": "override", "path": str(path), "commit": _head(path), "pinned": False,
                                "matches_lock": matches,
                                "load_with": f'claude --plugin-dir "{path}"'}
            out["notes"].append("override is unpinned; it is used only for sessions started with --plugin-dir")
            if not matches:
                out["notes"].append("override differs from the lock: " + json.dumps(plan.changes, sort_keys=True))
    elif cfg.vendor_dir.is_dir():
        found = verify(cfg)
        out["in_effect"] = {"kind": "repo", "path": str(cfg.vendor_dir), "commit": (lock or {}).get("commit"),
                            "pinned": bool(lock and lock.get("commit")), "matches_lock": not any(
                                "modified" in f or "missing" in f or "not in the lock" in f for f in found)}
        out["findings"] += found
    elif bundle:
        block = _load(bundle / "agent-skills.lock.json")
        plugin_dir = bundle / cfg.plugin_name
        files = {p.relative_to(plugin_dir).as_posix(): p.read_bytes() for p in plugin_dir.rglob("*") if p.is_file()}
        files = {p: b for p, b in files.items() if p in block.get("files", {})}
        out["in_effect"] = {"kind": "bundled", "path": str(bundle), "commit": block.get("commit"),
                            "pinned": bool(block.get("commit")), "matches_lock": _matches(block.get("files", {}), files)}
        lock = lock or block
    else:
        out["in_effect"] = {"kind": "none"}
        out["notes"].append("nothing vendored or bundled yet; run `quantsmith-agent-skills sync` from a local clone")

    out["review"] = review_state(lock, cfg.review_days, today)
    if out["review"]["due"]:
        out["notes"].append(f"quarterly review due: last sync {out['review']['age_days']} days ago "
                            f"(> {cfg.review_days}); run `diff` against your local clone (instructions/agent_skills.md)")
    reg = claude_registry(cfg, home)
    out["claude"] = reg
    if reg["duplicate_installs"]:
        out["findings"].append("another agent-skills install can load alongside the pinned one: "
                               + ", ".join(reg["duplicate_installs"]) + " (remove it: claude plugin uninstall <id>)")
    if out["in_effect"].get("kind") == "repo" and not reg["registered_here"]:
        out["notes"].append("this checkout has not opted in; run `quantsmith-agent-skills install --scope project`")
    return out


def install_commands(cfg: Config, scope: str, path: Path | None = None) -> list[list[str]]:
    """The Claude Code CLI calls for an opt-in (plan: Settings). Project scope never runs `plugin install` (T-001 check 6)."""
    if scope == "project":
        return [["claude", "plugin", "marketplace", "add", str(cfg.root), "--scope", "local"]]
    target = path or bundled_marketplace() or cfg.root
    return [["claude", "plugin", "marketplace", "add", str(target), "--scope", "user"],
            ["claude", "plugin", "install", f"{cfg.plugin_name}@{cfg.marketplace}", "--scope", "user"]]
