"""Parse AddressSanitizer, UndefinedBehaviorSanitizer, LeakSanitizer, ThreadSanitizer and
MemorySanitizer output into structured findings.

A crash is only useful once it is classified: which sanitizer, what defect class, where. These
parsers turn raw stderr into that, so a harness can report ``heap-buffer-overflow at f.cpp:12``
instead of a wall of text. They read text; they run nothing.
"""

from __future__ import annotations

import re
from typing import Dict, List

_ASAN = re.compile(r"ERROR: (AddressSanitizer|LeakSanitizer|MemorySanitizer|ThreadSanitizer): ([A-Za-z0-9_\- ]+?)(?: on| at| \(|$)", re.M)
_UBSAN = re.compile(r"^(?P<loc>[^\s:][^:\n]*:\d+:\d+): runtime error: (?P<msg>.+)$", re.M)
_SUMMARY = re.compile(r"SUMMARY: (\w+Sanitizer): ([^\n]+)")
_FRAME = re.compile(r"^\s*#(\d+) 0x[0-9a-f]+ in (.+?)(?: (\S+:\d+(?::\d+)?))?$", re.M)
_LEAK = re.compile(r"(?:ERROR: )?LeakSanitizer: detected memory leaks")


def parse_sanitizer_output(text: str) -> List[Dict[str, object]]:
    """Findings in order of appearance: ``{sanitizer, kind, location, message, frames}``."""
    findings: List[Dict[str, object]] = []
    for m in _UBSAN.finditer(text):
        findings.append({"sanitizer": "UndefinedBehaviorSanitizer", "kind": _ub_kind(m.group("msg")),
                         "location": m.group("loc"), "message": m.group("msg").strip(), "frames": []})
    for m in _ASAN.finditer(text):
        tail = text[m.start():]
        frames = [{"index": int(i), "function": f.strip(), "location": loc or ""}
                  for i, f, loc in _FRAME.findall(tail.split("\n\n", 1)[0])][:6]
        summary = _SUMMARY.search(tail)
        location = ""
        if summary:
            loc = re.search(r"(\S+:\d+(?::\d+)?)", summary.group(2))
            location = loc.group(1) if loc else ""
        findings.append({"sanitizer": m.group(1), "kind": m.group(2).strip(), "location": location,
                         "message": (summary.group(0) if summary else m.group(0)).strip(), "frames": frames})
    if _LEAK.search(text) and not any(f["sanitizer"] == "LeakSanitizer" for f in findings):
        findings.append({"sanitizer": "LeakSanitizer", "kind": "detected memory leaks", "location": "",
                         "message": "LeakSanitizer: detected memory leaks", "frames": []})
    return findings


def _ub_kind(msg: str) -> str:
    low = msg.lower()
    for needle, kind in (("signed integer overflow", "signed-integer-overflow"), ("unsigned integer overflow", "unsigned-integer-overflow"),
                         ("division by zero", "integer-divide-by-zero"), ("shift exponent", "invalid-shift"),
                         ("null pointer", "null-pointer-use"), ("out of bounds", "array-out-of-bounds"),
                         ("misaligned", "misaligned-access"), ("not a valid value", "invalid-value"),
                         ("outside the range of representable", "float-cast-overflow"), ("left shift", "invalid-shift")):
        if needle in low:
            return kind
    return "undefined-behavior"
