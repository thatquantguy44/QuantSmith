"""Segmentation baseline for spec 0094.

Spaced scripts (Latin, Cyrillic, Hangul) split into word tokens. Unspaced scripts
(Han and kana together, so Japanese runs stay whole; Thai separately) become character
n-grams, which is a search-friendly baseline and *not* a word segmentation. A real
dictionary segmenter or model can be supplied through the ``segmenter`` slot; it must
declare ``tokenizer_id`` and ``tokenizer_version`` (the ``0071`` capability profile
records the same pair), so callers never change and the identifier travels with the
tokens.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Callable, Dict, List, Optional

TOKENIZER_ID = "asian-baseline-ngram"
TOKENIZER_VERSION = "1"
DEFAULT_NGRAM = 2

_HAN_KANA = "぀-ヿ㐀-䶿一-鿿豈-﫿"
_THAI = "฀-๿"
_UNSPACED = f"[{_HAN_KANA}]+|[{_THAI}]+"
_WORD = f"(?:(?![{_HAN_KANA}{_THAI}])[^\\W_])+"
_TOKEN_RE = re.compile(f"({_UNSPACED})|({_WORD})")


def _cluster_bounds(run: str) -> List[int]:
    """Start index of each grapheme cluster (a base plus its non-spacing marks) in ``run``."""
    bounds: List[int] = []
    for i, ch in enumerate(run):
        if i == 0 or unicodedata.category(ch) != "Mn":
            bounds.append(i)
    bounds.append(len(run))
    return bounds


def _ngrams(run: str, start: int, n: int) -> List[Dict[str, Any]]:
    b = _cluster_bounds(run)
    k = len(b) - 1
    if k <= n:
        return [{"text": run, "start": start, "end": start + len(run)}]
    return [{"text": run[b[i]:b[i + n]], "start": start + b[i], "end": start + b[i + n]}
            for i in range(k - n + 1)]


def segment(text: str, ngram: int = DEFAULT_NGRAM,
            segmenter: Optional[Callable[[str], List[Dict[str, Any]]]] = None) -> Dict[str, Any]:
    """Tokenize ``text``; every token carries its ``start`` and ``end`` in ``text``.

    ``segmenter`` (optional) takes the text and returns a list of
    ``{"text", "start", "end"}`` dicts. It must expose ``tokenizer_id`` and
    ``tokenizer_version`` attributes or the call is rejected.
    """
    if ngram < 1:
        raise ValueError("ngram must be at least 1")
    if segmenter is not None:
        ident = getattr(segmenter, "tokenizer_id", None)
        ver = getattr(segmenter, "tokenizer_version", None)
        if not ident or not ver:
            raise ValueError("a custom segmenter must declare tokenizer_id and tokenizer_version")
        tokens = segmenter(text)
        for tok in tokens:
            if text[tok["start"]:tok["end"]] != tok["text"]:
                raise ValueError(f"segmenter token {tok['text']!r} does not match its offsets")
        return {"tokens": tokens, "tokenizer": f"{ident}@{ver}", "source": "plugin"}
    tokens: List[Dict[str, Any]] = []
    for m in _TOKEN_RE.finditer(text):
        if m.group(1):
            tokens.extend(_ngrams(m.group(1), m.start(), ngram))
        else:
            tokens.append({"text": m.group(2), "start": m.start(), "end": m.end()})
    return {"tokens": tokens, "tokenizer": f"{TOKENIZER_ID}@{TOKENIZER_VERSION}", "source": "baseline",
            "ngram": ngram}
