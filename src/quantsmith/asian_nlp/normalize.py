"""Offset-preserving text normalization for spec 0094.

Extraction runs on a normalized copy (NFKC, so full-width digits and punctuation
become ASCII, plus Thai digits to ASCII) but every extraction must point back at
the *original* text. ``normalize_with_offsets`` returns the normalized string and,
for each normalized character, the start and end offsets in the original.

Normalization is applied per grapheme cluster (a base character plus its combining
marks), so decomposed Vietnamese or Thai sequences compose the same way precomposed
ones do. A cluster that expands (for example a ligature) maps every output
character to the whole source cluster.
"""

from __future__ import annotations

import unicodedata
from typing import List, Tuple

_THAI_DIGITS = {ord("๐") + k: ord("0") + k for k in range(10)}


def _clusters(text: str) -> List[Tuple[int, int]]:
    out: List[Tuple[int, int]] = []
    for i, ch in enumerate(text):
        if out and unicodedata.combining(ch):
            out[-1] = (out[-1][0], i + 1)
        else:
            out.append((i, i + 1))
    return out


def normalize_with_offsets(text: str) -> Tuple[str, List[int], List[int]]:
    """Return ``(normalized, starts, ends)``; ``starts[i]``/``ends[i]`` index ``text``."""
    chars: List[str] = []
    starts: List[int] = []
    ends: List[int] = []
    for a, b in _clusters(text):
        cluster = unicodedata.normalize("NFKC", text[a:b]).translate(_THAI_DIGITS)
        for ch in cluster:
            chars.append(ch)
            starts.append(a)
            ends.append(b)
    return "".join(chars), starts, ends


def normalize_text(text: str) -> str:
    """Normalize a lexicon string the same way input text is normalized."""
    return normalize_with_offsets(text)[0]


def original_span(starts: List[int], ends: List[int], a: int, b: int) -> Tuple[int, int]:
    """Map a normalized half-open range ``[a, b)`` back to the original text."""
    if not 0 <= a < b <= len(starts):
        raise ValueError(f"range {(a, b)} is outside the normalized text")
    return starts[a], ends[b - 1]
