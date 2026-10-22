"""Query-repository fetchers: local folders, Git at a pinned ref, object stores.

Spec ``0114`` REQ-003 (realizing ``0113`` REQ-004). Every fetcher returns a
:class:`RepoSnapshot` — a deterministic ref plus the selected files' bytes —
and nothing about any repository's location lives in this package: it all
comes from configuration.

* ``local``: walks a directory; refuses symlinks or paths that escape it; the
  ref is ``local:<sha256>`` over the sorted (path, content-hash) pairs.
* ``git``: clones the configured URI bare into a cache, fetches, and resolves
  ``ref`` to a commit SHA; files are read from that commit, never a work tree.
  Credentials come from the user's Git credential helper, never config, and
  prompts are disabled so a missing credential fails instead of hanging.
* ``object_store``: reads through a caller-injected client
  (``list_objects(prefix) -> [(key, version)]``, ``get_object(key) -> bytes``);
  no SDK ships here. The ref is ``object:<sha256>`` over (key, version) pairs.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from .globs import selected

__all__ = ["ObjectStoreClient", "RepoFetchError", "RepoSnapshot", "SourceFile", "fetch", "redact_uri"]

_URI_USERINFO_RE = re.compile(r"(://)[^/@\s]+@")


class RepoFetchError(RuntimeError):
    code = "E_REPO_FETCH"

    def __init__(self, repo_id: str, message: str) -> None:
        super().__init__(f"{repo_id}: {message}")
        self.repo_id = repo_id
        self.message = message


class ObjectStoreClient(Protocol):  # pragma: no cover - interface only
    def list_objects(self, prefix: str) -> Iterable[tuple[str, str]]: ...
    def get_object(self, key: str) -> bytes: ...


@dataclass(frozen=True)
class SourceFile:
    path: str          # POSIX path relative to the repository root
    sha256: str
    data: bytes


@dataclass(frozen=True)
class RepoSnapshot:
    repo_id: str
    kind: str
    ref: str
    files: tuple[SourceFile, ...] = field(default_factory=tuple)

    def file(self, path: str) -> SourceFile | None:
        return next((f for f in self.files if f.path == path), None)


def redact_uri(uri: str) -> str:
    """Drop any ``user[:password]@`` from a URI before it reaches a message."""
    return _URI_USERINFO_RE.sub(r"\1***@", uri)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _content_ref(prefix: str, pairs: Iterable[tuple[str, str]]) -> str:
    h = hashlib.sha256()
    for path, digest in sorted(pairs):
        h.update(path.encode("utf-8") + b"\0" + digest.encode("ascii") + b"\n")
    return f"{prefix}:{h.hexdigest()}"


def _safe_relative(path: str) -> bool:
    pure = PurePosixPath(path)
    return not pure.is_absolute() and ".." not in pure.parts and path == pure.as_posix()


# --------------------------------------------------------------------------
# local
# --------------------------------------------------------------------------

def _fetch_local(repo: Mapping[str, Any], root: Path) -> RepoSnapshot:
    repo_id = repo["id"]
    if not root.is_dir():
        raise RepoFetchError(repo_id, f"local repository not found: {root}")
    root_resolved = root.resolve()
    include = repo["paths"]["include"]
    exclude = repo["paths"].get("exclude", [])
    files: list[SourceFile] = []
    for dirpath, dirnames, filenames in os.walk(root_resolved, followlinks=False):
        dirnames.sort()
        for name in sorted(filenames):
            full = Path(dirpath) / name
            rel = full.relative_to(root_resolved).as_posix()
            if not selected(rel, include, exclude):
                continue
            if full.is_symlink():
                target = full.resolve()
                if root_resolved not in target.parents:
                    raise RepoFetchError(repo_id, f"refusing {rel}: symlink escapes the repository root")
            data = full.read_bytes()
            files.append(SourceFile(rel, _digest(data), data))
    files.sort(key=lambda f: f.path)
    return RepoSnapshot(repo_id, "local", _content_ref("local", ((f.path, f.sha256) for f in files)),
                        tuple(files))


# --------------------------------------------------------------------------
# git
# --------------------------------------------------------------------------

def _git(args: list[str], repo_id: str, uri: str, cwd: Path | None = None) -> bytes:
    env = dict(os.environ)
    env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "true", "LC_ALL": "C"})
    try:
        done = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, check=False, timeout=600)
    except FileNotFoundError:
        raise RepoFetchError(repo_id, "the git command is not installed") from None
    except subprocess.TimeoutExpired:
        raise RepoFetchError(repo_id, f"git {args[0]} timed out for {redact_uri(uri)}") from None
    if done.returncode != 0:
        lines = done.stderr.decode("utf-8", "replace").strip().splitlines()
        stderr = redact_uri(lines[-1]) if lines else "no error output"
        raise RepoFetchError(repo_id, f"git {args[0]} failed for {redact_uri(uri)}: {stderr}")
    return done.stdout


def _fetch_git(repo: Mapping[str, Any], uri: str, cache_dir: Path) -> RepoSnapshot:
    repo_id = repo["id"]
    ref = repo["ref"]
    if ref.startswith("-"):
        raise RepoFetchError(repo_id, f"invalid ref {ref!r}")
    cache = cache_dir / f"{repo_id}.git"
    if not (cache / "HEAD").exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        _git(["clone", "--bare", "--quiet", "--", uri, str(cache)], repo_id, uri)
    else:
        _git(["--git-dir", str(cache), "fetch", "--quiet", "--prune", "--tags", "origin",
              "+refs/heads/*:refs/heads/*"], repo_id, uri)
    commit = _git(["--git-dir", str(cache), "rev-parse", "--verify", "--quiet", "--end-of-options",
                   f"{ref}^{{commit}}"], repo_id, uri).decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40}([0-9a-f]{24})?", commit):
        raise RepoFetchError(repo_id, f"ref {ref!r} did not resolve to a commit")
    listing = _git(["--git-dir", str(cache), "ls-tree", "-r", "-z", "--full-tree", commit], repo_id, uri)
    include = repo["paths"]["include"]
    exclude = repo["paths"].get("exclude", [])
    files: list[SourceFile] = []
    for entry in listing.split(b"\0"):
        if not entry:
            continue
        meta, _, path_bytes = entry.partition(b"\t")
        mode, kind, obj = meta.decode().split(" ")
        path = path_bytes.decode("utf-8")
        if kind != "blob" or mode == "120000" or not selected(path, include, exclude):
            continue  # symlinks inside Git are never followed
        if not _safe_relative(path):
            raise RepoFetchError(repo_id, f"refusing unsafe path {path!r}")
        data = _git(["--git-dir", str(cache), "cat-file", "blob", obj], repo_id, uri)
        files.append(SourceFile(path, _digest(data), data))
    files.sort(key=lambda f: f.path)
    return RepoSnapshot(repo_id, "git", commit, tuple(files))


# --------------------------------------------------------------------------
# object_store
# --------------------------------------------------------------------------

def _fetch_object_store(repo: Mapping[str, Any], uri: str,
                        clients: Mapping[str, ObjectStoreClient]) -> RepoSnapshot:
    repo_id = repo["id"]
    scheme, sep, rest = uri.partition("://")
    if not sep:
        raise RepoFetchError(repo_id, "object_store uri must look like <scheme>://<bucket>/<prefix>")
    client = clients.get(scheme)
    if client is None:
        raise RepoFetchError(repo_id, f"no object-store client injected for scheme {scheme!r}")
    bucket, _, prefix = rest.partition("/")
    prefix = prefix.rstrip("/") + "/" if prefix else ""
    include = repo["paths"]["include"]
    exclude = repo["paths"].get("exclude", [])
    pairs: list[tuple[str, str]] = []
    files: list[SourceFile] = []
    for key, version in sorted(client.list_objects(f"{bucket}/{prefix}" if bucket else prefix)):
        full_prefix = f"{bucket}/{prefix}" if bucket else prefix
        rel = key.removeprefix(full_prefix)
        if not _safe_relative(rel):
            raise RepoFetchError(repo_id, f"refusing unsafe object key {key!r}")
        if not selected(rel, include, exclude):
            continue
        data = client.get_object(key)
        pairs.append((rel, str(version)))
        files.append(SourceFile(rel, _digest(data), data))
    files.sort(key=lambda f: f.path)
    return RepoSnapshot(repo_id, "object_store", _content_ref("object", pairs), tuple(files))


def fetch(repo: Mapping[str, Any], *, base_dir: Path, cache_dir: Path,
          clients: Mapping[str, ObjectStoreClient] | None = None) -> RepoSnapshot:
    """Snapshot one configured repository.

    ``base_dir`` resolves relative ``local`` paths (normally the config file's
    directory); ``cache_dir`` holds bare Git clones.
    """
    kind = repo["kind"]
    uri = repo["uri"]
    if kind == "local":
        root = Path(uri)
        return _fetch_local(repo, root if root.is_absolute() else base_dir / root)
    if kind == "git":
        local = Path(uri)
        if "://" not in uri and not uri.startswith("git@") and not local.is_absolute():
            uri = str((base_dir / local).resolve())
        return _fetch_git(repo, uri, cache_dir)
    if kind == "object_store":
        return _fetch_object_store(repo, uri, clients or {})
    raise RepoFetchError(repo["id"], f"unknown repository kind {kind!r}")
