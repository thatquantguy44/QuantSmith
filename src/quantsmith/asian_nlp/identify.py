"""Language and script identification baseline for spec 0094.

Rule-based and dependency-free: Unicode blocks decide the script, and script plus
language-specific evidence (kana, hangul, Thai, Vietnamese letters, Kazakh and Tajik
letters, function words) decides candidate languages. It is conservative by design:
text below ``MIN_LETTERS`` letters, mixed-script text, and Latin text whose function
words do not clearly favour one language return ``undetermined`` with reasons rather
than a guess. It identifies; it does not translate, and it is not validated on real
corpora (``gap.language_id_short_text``).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from .lexicon import (FUNCTION_WORDS, KK_LETTERS, RU_FUNCTION_WORDS, SIMP_TRAD, TG_LETTERS,
                      UZ_CYRL_LETTERS, VI_BASE, VI_BLOCK_END, VI_BLOCK_START)
from .normalize import normalize_text

MIN_LETTERS = 8
MIXED_SHARE = 0.2          # a second script above this share makes the text mixed
MIN_FUNCTION_HITS = 3
DOMINANCE = 1.5            # best Latin score must exceed the runner-up by this factor
MIN_VARIANT_EVIDENCE = 2

_RANGES = (
    ("han", ((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF))),
    ("kana", ((0x3040, 0x30FF),)),
    ("hangul", ((0xAC00, 0xD7AF), (0x1100, 0x11FF), (0x3130, 0x318F))),
    ("thai", ((0x0E00, 0x0E7F),)),
    ("cyrillic", ((0x0400, 0x04FF),)),
    ("devanagari", ((0x0900, 0x097F),)),
)
_SIMP = {s for s, t in SIMP_TRAD}
_TRAD = {t for s, t in SIMP_TRAD}


def _script_of(ch: str) -> str:
    cp = ord(ch)
    for name, spans in _RANGES:
        for lo, hi in spans:
            if lo <= cp <= hi:
                return name
    if ch.isalpha():
        return "latin" if cp < 0x0250 or 0x1E00 <= cp <= 0x1EFF else "other"
    return ""


def script_shares(text: str) -> Dict[str, float]:
    counts: Dict[str, int] = {}
    for ch in text:
        s = _script_of(ch)
        if s:
            counts[s] = counts.get(s, 0) + 1
    total = sum(counts.values())
    return {k: round(v / total, 6) for k, v in sorted(counts.items())} if total else {}


def _letters(text: str) -> int:
    return sum(1 for ch in text if _script_of(ch))


def chinese_variant(text: str) -> Dict[str, Any]:
    """Simplified or Traditional by characters that differ between the forms."""
    s = sum(1 for ch in text if ch in _SIMP)
    t = sum(1 for ch in text if ch in _TRAD)
    if s >= MIN_VARIANT_EVIDENCE and t == 0:
        variant = "zh-Hans"
    elif t >= MIN_VARIANT_EVIDENCE and s == 0:
        variant = "zh-Hant"
    else:
        variant = "zh"
    return {"variant": variant, "simplified_only_chars": s, "traditional_only_chars": t}


def _latin_candidates(text: str) -> List[Dict[str, Any]]:
    low = text.casefold()
    cands: List[Dict[str, Any]] = []
    vi_letters = sum(1 for ch in text if ch in VI_BASE or VI_BLOCK_START <= ord(ch) <= VI_BLOCK_END)
    if vi_letters >= 2:
        cands.append({"language": "vi", "score": vi_letters, "evidence": f"{vi_letters} Vietnamese-only letters"})
    tokens = re.findall(r"[^\W\d_]+", low)
    for lang, words in FUNCTION_WORDS.items():
        if lang == "vi" and vi_letters >= 2:
            continue
        hits = sum(1 for tok in tokens if tok in words)
        if hits:
            cands.append({"language": lang, "score": hits, "evidence": f"{hits} function words"})
    return sorted(cands, key=lambda c: (-c["score"], c["language"]))


def _cyrillic_candidates(text: str) -> List[Dict[str, Any]]:
    low = text.casefold()
    out: List[Dict[str, Any]] = []
    kk = sum(1 for ch in low if ch in KK_LETTERS)
    tg = sum(1 for ch in low if ch in TG_LETTERS)
    uz = sum(1 for ch in low if ch in UZ_CYRL_LETTERS and ch not in KK_LETTERS)
    if kk >= 2:
        out.append({"language": "kk", "score": kk, "evidence": f"{kk} Kazakh-specific letters"})
    if tg >= 1:
        out.append({"language": "tg", "score": tg, "evidence": f"{tg} Tajik-specific letters"})
    if uz >= 1 and kk < 2 and tg == 0:
        out.append({"language": "uz", "score": uz, "evidence": f"{uz} Uzbek-Cyrillic letters"})
    tokens = re.findall(r"[^\W\d_]+", low)
    ru = sum(1 for tok in tokens if tok in RU_FUNCTION_WORDS)
    if ru >= MIN_FUNCTION_HITS and kk < 2 and tg == 0:
        out.append({"language": "ru", "score": ru, "evidence": f"{ru} Russian function words"})
    return sorted(out, key=lambda c: (-c["score"], c["language"]))


def identify(text: str) -> Dict[str, Any]:
    """Identify script and candidate languages. Never guesses on weak evidence.

    Returns ``{"script", "script_shares", "candidates", "language", "status",
    "reasons", "evidence"}``. ``language`` is set only when ``status`` is ``ok``.
    """
    norm = normalize_text(text)
    shares = script_shares(norm)
    letters = _letters(norm)
    result: Dict[str, Any] = {"script": None, "script_shares": shares, "candidates": [],
                              "language": None, "status": "undetermined", "reasons": [], "evidence": {}}
    if not shares:
        result["reasons"].append("no_letters")
        return result
    ranked = sorted(shares.items(), key=lambda kv: (-kv[1], kv[0]))
    top, top_share = ranked[0]
    result["script"] = top
    if letters < MIN_LETTERS:
        result["reasons"].append(f"text_shorter_than_{MIN_LETTERS}_letters")
    # Japanese is Han + kana by nature; treat them as one writing system for the mixed test.
    cjk_combo = shares.get("han", 0) + shares.get("kana", 0)
    effective_top = cjk_combo if top in ("han", "kana") and shares.get("kana", 0) > 0 else top_share
    others = 1.0 - effective_top
    if others > MIXED_SHARE:
        result["reasons"].append("mixed_scripts")
    if result["reasons"]:
        return result

    cands: List[Dict[str, Any]] = []
    if top == "thai":
        cands = [{"language": "th", "score": top_share, "evidence": "Thai script"}]
    elif shares.get("hangul", 0) >= 0.3:
        cands = [{"language": "ko", "score": shares["hangul"], "evidence": "Hangul"}]
    elif shares.get("kana", 0) > 0 and cjk_combo >= 0.5:
        cands = [{"language": "ja", "score": shares["kana"], "evidence": "kana present with Han"}]
    elif top == "han":
        var = chinese_variant(norm)
        result["evidence"]["chinese_variant"] = var
        cands = [{"language": var["variant"], "score": top_share, "evidence": "Han without kana or Hangul"}]
    elif top == "cyrillic":
        cands = _cyrillic_candidates(norm)
        if not cands:
            result["reasons"].append("cyrillic_language_not_distinguishable")
    elif top == "latin":
        cands = _latin_candidates(norm)
        if not cands:
            result["reasons"].append("no_function_word_evidence")
        else:
            best = cands[0]
            second = cands[1]["score"] if len(cands) > 1 else 0
            if best["language"] != "vi" and best["score"] < MIN_FUNCTION_HITS:
                result["reasons"].append("too_few_function_words")
            elif second and best["score"] < DOMINANCE * second:
                result["reasons"].append("ambiguous_latin_languages")
    elif top == "devanagari":
        result["reasons"].append("language_id_not_supported_for_this_script")
    else:
        result["reasons"].append("script_not_supported")
    result["candidates"] = cands
    if result["reasons"] or not cands:
        return result
    result["language"] = cands[0]["language"]
    result["status"] = "ok"
    return result
