"""agent-skills as a pinned, offline upstream (spec 0100).

Copies an allowlisted subset of ``agent-skills`` from a *local* source (a directory, a ref in a local Git clone, or a
``git archive`` tarball) into ``vendor/agent-skills/``, records a per-file SHA-256 lock, verifies the vendored tree
against it, and registers the tree with Claude Code as a local plugin marketplace. Standard library only; vendored
content is read and hashed, never executed. Command line: ``quantsmith-agent-skills`` (see ``cli.py``).
"""

from .config import Config, ConfigError, load_config
from .source import SourceError, SourceRejected, read_source
from .vendor import SyncPlan, plan_sync, verify, write_sync

__all__ = [
    "Config",
    "ConfigError",
    "SourceError",
    "SourceRejected",
    "SyncPlan",
    "load_config",
    "plan_sync",
    "read_source",
    "verify",
    "write_sync",
]
