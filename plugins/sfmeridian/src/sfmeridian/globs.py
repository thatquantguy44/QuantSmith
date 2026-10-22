"""Path globs with ``**`` for repository include/exclude rules (spec ``0114`` REQ-003).

``fnmatch`` lets ``*`` cross ``/``, which makes ``<dir>/**/*.sql`` miss files
directly inside ``<dir>``. These rules are the usual ones instead:

* ``**/`` matches zero or more whole directories;
* ``**`` at the end matches everything below;
* ``*`` matches within one path segment; ``?`` one character in a segment.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from functools import lru_cache

__all__ = ["compile_glob", "matches", "selected"]


@lru_cache(maxsize=256)
def compile_glob(pattern: str) -> re.Pattern[str]:
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


def matches(path: str, pattern: str) -> bool:
    return compile_glob(pattern).match(path) is not None


def selected(path: str, include: Iterable[str], exclude: Iterable[str] = ()) -> bool:
    """True when ``path`` matches an include glob and no exclude glob."""
    return any(matches(path, p) for p in include) and not any(matches(path, p) for p in exclude)
