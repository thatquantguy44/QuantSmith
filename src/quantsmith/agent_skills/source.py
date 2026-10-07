"""Read an agent-skills tree from a *local* source. Spec 0100 REQ-003, NFR-001, NFR-003.

Three source kinds, none of which touches the network:

* ``git-clone``  - a local Git repository plus ``--ref``; read with ``git archive`` from the local object store
  (``git fetch`` is never run).
* ``tarball``    - a ``.tar``/``.tar.gz``/``.tgz`` file, e.g. from ``git archive``; its commit is taken from the pax
  header ``git archive`` writes, when present.
* ``directory``  - a plain directory. Unpinned: the lock records no commit.

Anything that looks like a URL (``scheme://`` or ``user@host:path``) is rejected before any I/O (AC-003). Entries keep
their type and mode so the sync can refuse symlinks, special files and executables instead of copying them.
"""

from __future__ import annotations

import io
import json
import os
import re
import stat
import subprocess
import tarfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

URL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://|^[^/\s]+@[^:/\s]+:")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
READ_CAP = 4 * 1024 * 1024  # never buffer more than this per file; anything near it is refused as oversize anyway


class SourceError(RuntimeError):
    """The source could not be read (missing path, bad ref, unreadable archive)."""


class SourceRejected(SourceError):
    """The source is not local. Only directories, local clones and archives are accepted."""


@dataclass(frozen=True)
class Entry:
    kind: str  # "file" | "symlink" | "other"
    mode: int
    size: int
    data: bytes | None = None
    unsafe_name: bool = False


@dataclass
class Snapshot:
    kind: str
    commit: str | None
    files: dict[str, Entry] = field(default_factory=dict)

    @property
    def plugin_version(self) -> str | None:
        e = self.files.get(".claude-plugin/plugin.json")
        if not e or e.data is None:
            return None
        try:
            return str(json.loads(e.data.decode("utf-8")).get("version") or "") or None
        except (ValueError, UnicodeDecodeError):
            return None


def reject_url(source: str) -> None:
    if URL_RE.search(source.strip()):
        raise SourceRejected(f"only local sources are accepted (a directory, a local Git clone, or an archive); got {source!r}")


def _git(src: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_ALLOW_PROTOCOL="file")
    return subprocess.run(["git", "-C", str(src), *args], capture_output=True, env=env, check=False)


def _is_git_repo(src: Path) -> bool:
    try:
        return _git(src, "rev-parse", "--git-dir").returncode == 0
    except FileNotFoundError:
        return False


def _safe(name: str) -> tuple[str, bool]:
    p = PurePosixPath(name)
    parts = [x for x in p.parts if x not in ("", ".")]
    unsafe = p.is_absolute() or ".." in parts
    return "/".join(parts), unsafe


def _from_tar(data: bytes) -> tuple[dict[str, Entry], str | None]:
    files: dict[str, Entry] = {}
    try:
        tf = tarfile.open(fileobj=io.BytesIO(data), mode="r:*")  # noqa: SIM115 - closed by the with block below
    except tarfile.TarError as exc:
        raise SourceError(f"unreadable archive: {exc}") from exc
    with tf:
        comment = (tf.pax_headers or {}).get("comment", "")
        for m in tf.getmembers():
            if m.isdir():
                continue
            name, unsafe = _safe(m.name)
            if not name:
                continue
            if m.issym() or m.islnk():
                files[name] = Entry("symlink", m.mode, 0, None, unsafe)
            elif m.isfile():
                body = None
                if m.size <= READ_CAP and not unsafe:
                    fh = tf.extractfile(m)
                    body = fh.read() if fh else None
                files[name] = Entry("file", m.mode, m.size, body, unsafe)
            else:
                files[name] = Entry("other", m.mode, 0, None, unsafe)
    return _strip_prefix(files), (comment if SHA_RE.match(comment or "") else None)


def _strip_prefix(files: dict[str, Entry]) -> dict[str, Entry]:
    """Drop a single top-level directory (``agent-skills-<sha>/...``) when the plugin manifest sits under it."""
    tops = {k.split("/", 1)[0] for k in files}
    if len(tops) == 1 and ".claude-plugin/plugin.json" not in files:
        top = tops.pop()
        if f"{top}/.claude-plugin/plugin.json" in files:
            return {k.split("/", 1)[1]: v for k, v in files.items() if "/" in k}
    return files


def _from_dir(src: Path) -> dict[str, Entry]:
    files: dict[str, Entry] = {}
    for dirpath, dirnames, filenames in os.walk(src, followlinks=False):
        rel_dir = Path(dirpath).relative_to(src)
        if rel_dir.parts[:1] == (".git",):
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if not (rel_dir == Path(".") and d == ".git")]
        for name in sorted(dirnames) + sorted(filenames):
            full = Path(dirpath) / name
            st = full.lstat()
            rel = (rel_dir / name).as_posix()
            if stat.S_ISLNK(st.st_mode):
                files[rel] = Entry("symlink", st.st_mode, 0)
            elif stat.S_ISREG(st.st_mode):
                body = full.read_bytes() if st.st_size <= READ_CAP else None
                files[rel] = Entry("file", st.st_mode, st.st_size, body)
            elif not stat.S_ISDIR(st.st_mode):
                files[rel] = Entry("other", st.st_mode, 0)
    return files


def read_source(source: str, ref: str | None = None) -> Snapshot:
    """Read the whole source tree into memory. Raises ``SourceRejected`` for URLs, ``SourceError`` otherwise."""
    reject_url(source)
    src = Path(source).expanduser()
    if src.is_file():
        if ref:
            raise SourceError("--ref applies to a Git clone, not to an archive")
        files, commit = _from_tar(src.read_bytes())
        return Snapshot("tarball", commit, files)
    if not src.is_dir():
        raise SourceError(f"source not found: {src}")
    if _is_git_repo(src):
        if not ref:
            raise SourceError(f"{src} is a Git repository; pass --ref <sha|tag|branch> (e.g. --ref HEAD) so the sync is pinned")
        rp = _git(src, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
        if rp.returncode != 0:
            raise SourceError(f"ref {ref!r} not found in {src} (local object store only; nothing is fetched)")
        commit = rp.stdout.decode().strip()
        ar = _git(src, "archive", "--format=tar", commit)
        if ar.returncode != 0:
            raise SourceError(f"git archive failed: {ar.stderr.decode(errors='replace').strip()}")
        files, _ = _from_tar(ar.stdout)
        return Snapshot("git-clone", commit, files)
    if ref:
        raise SourceError(f"--ref given but {src} is not a Git repository")
    return Snapshot("directory", None, _from_dir(src))
