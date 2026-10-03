"""Rule-based extraction of amounts, currencies, dates, era years, and fiscal periods
for spec 0094.

Every extraction carries the verbatim span, character offsets into the *original*
text, the language, a rule ID, the convention IDs it applied, and ``method: "rule"``.
Anything ambiguous (an unresolved currency sign, an ambiguous unit such as 兆, a
number whose thousands/decimal separator cannot be resolved, a partial compound
numeral, an impossible date) is flagged ``ambiguous`` with ``value: None`` rather
than guessed. Normalization rules (units, eras, locales, currency markers) are read
from ``knowledge/venture_intelligence/conventions.json``; only month names and
identification word lists live in ``lexicon.py``.

This is a deterministic baseline, not a replacement for review. Known failure modes
are listed in ``KNOWN_FAILURE_MODES``.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import lexicon as lx
from .identify import _script_of, identify
from .normalize import normalize_text, normalize_with_offsets, original_span

RULE_VERSION = "1"
EXTRACTION_TYPES = ("amount", "date", "era_year", "fiscal_period")

KNOWN_FAILURE_MODES: Dict[str, List[str]] = {
    "all": ["numerals written as words ('five million', '五千万') are not extracted",
            "vertical text and OCR noise are not handled",
            "decomposed Unicode is composed per grapheme cluster, but unusual sequences may not match",
            "text with no recognized unit, currency, or date pattern yields nothing, not an error"],
    "zh": ["compound numerals beyond 亿+万 (for example 兆) are flagged, not parsed",
           "bare '元' is an ambiguous currency unless the text names it"],
    "ja": ["兆 is ambiguous and flagged", "era names other than 令和/平成/昭和 are not recognized"],
    "ko": ["compound Sino-Korean numerals with 천/백 inside 억 or 만 are flagged as partial"],
    "th": ["abbreviated month names (ม.ค.) are not recognized",
           "Buddhist-era detection assumes years 2400-2700 or an explicit พ.ศ. marker"],
    "vi": ["'đ' as a currency sign is only matched when no letter follows it"],
    "id/ms": ["Indonesian and Malay are not separated; 'bilion' is flagged ambiguous"],
    "fil": ["month-name lexicon is unverified"],
    "ru": ["case endings beyond the listed forms of 'миллион'/'миллиард' are not matched"],
    "kk": ["Kazakh month-name lexicon is unverified"],
    "uz": ["Uzbek month-name lexicon is unverified; Cyrillic Uzbek is treated as Russian-style"],
    "en": ["numeric dates such as 03/04/2024 are ambiguous unless a part exceeds 12"],
}

_DAY_FIRST = {"ru", "kk", "uz", "tg", "ky", "id/ms", "vi", "fil"}
_PERIOD_THOUSANDS = {"id/ms", "vi", "ru", "kk", "uz", "tg", "ky"}
_SPACE_GROUP_LANGS = {"ru", "kk", "uz", "tg", "ky"}


def load_conventions(root: Optional[Path] = None) -> Dict[str, Any]:
    base = Path(root) if root else Path(__file__).resolve().parents[3]
    return json.loads((base / "knowledge/venture_intelligence/conventions.json").read_text(encoding="utf-8"))


def _family(language: Optional[str]) -> Optional[str]:
    if not language:
        return None
    return "zh" if language.startswith("zh") else language


def _ascii_letters(s: str) -> bool:
    return all(ch.isascii() and ch.isalpha() for ch in s)


def _boundary_after(sym: str) -> str:
    scripts = {_script_of(ch) for ch in sym if ch.isalpha()}
    return r"(?![^\W\d_])" if scripts and scripts <= {"latin", "cyrillic"} else ""


def _boundary_before(sym: str) -> str:
    return r"(?<![A-Za-z])" if _ascii_letters(sym) else ""


def _alt(markers: Sequence[str], plural_s: bool = False) -> str:
    parts = []
    for m in sorted({normalize_text(x) for x in markers}, key=len, reverse=True):
        s = re.escape(m) + ("s?" if plural_s and _ascii_letters(m) else "") + _boundary_after(m)
        parts.append(_boundary_before(m) + s)
    return "(?:" + "|".join(parts) + ")"


class _Rules:
    """Compiled patterns built once from the conventions."""

    def __init__(self, conv: Dict[str, Any]):
        norm = conv["normalization"]
        self.units = {normalize_text(u["symbol"]).casefold(): u for u in norm["numeral_units"]}
        self.ambiguous_symbols = {normalize_text(a["symbol"]).casefold(): a for a in norm["ambiguous_symbols"]}
        self.eras = {u["id"]: u for u in norm["calendar_offsets"]}
        self.currency = {}
        self.currency_prefix: List[str] = []
        self.currency_suffix: List[str] = []
        for cur in norm["currency_markers"]:
            for m in cur["prefix_markers"]:
                self.currency[normalize_text(m).casefold()] = cur
                self.currency_prefix.append(m)
            for m in cur["suffix_markers"]:
                self.currency[normalize_text(m).casefold()] = cur
                self.currency_suffix.append(m)
        self.currency_ambiguous = {normalize_text(a["marker"]).casefold(): a for a in norm["currency_ambiguous"]}
        for a in norm["currency_ambiguous"]:
            m = a["marker"]
            if m in ("$", "¥", "Rs"):
                self.currency_prefix.append(m)
            else:
                self.currency_suffix.append(m)
        unit_syms = list(self.units) + list(self.ambiguous_symbols)
        self.unit_re = _alt(unit_syms, plural_s=True)
        # Chinese currency words may also precede the number (人民币3亿元, 新台幣2.5億元).
        cjk_words = [m for cur in norm["currency_markers"] for m in cur["suffix_markers"]
                     if any(_script_of(ch) == "han" for ch in m)]
        self.pre_re = _alt(self.currency_prefix + cjk_words)
        self.suf_only_re = re.compile(rf" ?(?P<suf>{_alt(self.currency_suffix)})", re.IGNORECASE)
        self.suf_re = _alt(self.currency_suffix)
        num_core = r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?"
        num_space = r"\d{1,3}(?: \d{3})+(?:,\d+)?|" + num_core
        self.amount_re = {}
        for key, num in (("plain", num_core), ("space", num_space)):
            self.amount_re[key] = re.compile(
                rf"(?P<pre>{self.pre_re} ?)?(?<![\d.,])(?P<num>{num})(?: ?(?P<unit>{self.unit_re}))?"
                rf"(?: ?(?P<suf>{self.suf_re}))?", re.IGNORECASE)
        self.compound_re = re.compile(
            rf"\s?(?P<n2>{num_core})(?P<mult>[千百천백])?\s?(?P<u2>万|萬|만)")
        self.partial_re = re.compile(r"\s?\d+\s?[千百천백]")


_CACHE: Dict[int, _Rules] = {}


def _rules(conv: Dict[str, Any]) -> _Rules:
    key = id(conv)
    if key not in _CACHE:
        _CACHE[key] = _Rules(conv)
    return _CACHE[key]


# ------------------------------------------------------------------- numbers
def parse_number(token: str, family: Optional[str]) -> Tuple[Optional[float], List[str]]:
    """Parse a number token; return ``(value, reasons)``; ``value`` is None when ambiguous."""
    t = token.strip()
    if " " in t:
        t = t.replace(" ", "")
        if "," in t:
            t = t.replace(",", ".")
        return _num(t), []
    has_dot, has_comma = "." in t, "," in t
    if has_dot and has_comma:
        last = max(t.rfind("."), t.rfind(","))
        dec = t[last]
        thou = "," if dec == "." else "."
        return _num(t.replace(thou, "").replace(dec, ".")), []
    sep = "." if has_dot else ("," if has_comma else None)
    if sep is None:
        return _num(t), []
    if t.count(sep) > 1:
        return _num(t.replace(sep, "")), []
    head, tail = t.split(sep)
    if len(tail) == 3 and 1 <= len(head) <= 3:
        if family is None:
            return None, [f"separator_ambiguous:{token}"]
        period_thousands = family in _PERIOD_THOUSANDS
        if (sep == "." and period_thousands) or (sep == "," and not period_thousands):
            return _num(head + tail), []
        return _num(head + "." + tail), []
    return _num(head + "." + tail), []


def _num(s: str) -> float:
    v = float(s)
    return int(v) if v == int(v) else v


def _tidy(v: float) -> float:
    v = round(v, 6)
    return int(v) if v == int(v) else v


# -------------------------------------------------------------------- amounts
def _resolve_currency(rules: _Rules, pre: Optional[str], suf: Optional[str], family: Optional[str]):
    def look(m: Optional[str]):
        if not m:
            return None
        key = normalize_text(m).strip().casefold()
        if key in rules.currency:
            return ("code", rules.currency[key]["code"], rules.currency[key]["id"], m.strip())
        if key in rules.currency_ambiguous:
            res = rules.currency_ambiguous[key]["resolution"]
            if family in res:
                return ("code", res[family], "cur.ambiguous_resolved_by_language", m.strip())
            return ("ambiguous", None, "cur.ambiguous", m.strip())
        return None
    a, b = look(pre), look(suf)
    if a and b and a[0] == "code" and b[0] == "code" and a[1] != b[1]:
        return None, None, True, ["currency_conflict"], [a[2], b[2]]
    pick = a if (a and a[0] == "code") else (b if (b and b[0] == "code") else (a or b))
    if not pick:
        return None, None, False, [], []
    if pick[0] == "ambiguous":
        return None, pick[3], True, [f"currency_ambiguous:{pick[3]}"], [pick[2]]
    return pick[1], pick[3], False, [], [pick[2]]


def _amounts(norm: str, rules: _Rules, family: Optional[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    rx = rules.amount_re["space" if family in _SPACE_GROUP_LANGS else "plain"]
    pos = 0
    while True:
        m = rx.search(norm, pos)
        if not m:
            break
        pre, suf, unit = m.group("pre"), m.group("suf"), m.group("unit")
        a, b = m.start(), m.end()
        pos = b
        if not (pre or suf or unit):
            pos = max(pos, a + 1)
            continue
        reasons: List[str] = []
        conventions: List[str] = []
        value, nreasons = parse_number(m.group("num"), family)
        reasons += nreasons
        mult = 1
        if unit:
            key = unit.casefold()
            if key.endswith("s") and key[:-1] in rules.units and key not in rules.units:
                key = key[:-1]
            if key in rules.ambiguous_symbols:
                reasons.append(f"ambiguous_symbol:{unit}")
                value = None
            elif key in rules.units:
                mult = rules.units[key]["multiplier"]
                conventions.append(rules.units[key]["id"])
                if value is not None and key in ("億", "亿", "억"):
                    comp = rules.compound_re.match(norm, b)
                    if comp:
                        n2, _ = parse_number(comp.group("n2"), family)
                        m2 = {"千": 1000, "百": 100, "천": 1000, "백": 100}.get(comp.group("mult") or "", 1)
                        if n2 is not None:
                            value = value * mult + n2 * m2 * 10000
                            mult = 1
                            conventions.append("norm.wan")
                            b = comp.end()
                            if not suf:
                                ms = rules.suf_only_re.match(norm, b)
                                if ms:
                                    suf, b = ms.group("suf"), ms.end()
            else:
                reasons.append(f"unknown_unit:{unit}")
                value = None
        if value is not None and mult != 1:
            value = value * mult
        if rules.partial_re.match(norm, b):
            reasons.append("partial_compound_numeral")
            value = None
        code, marker, amb_cur, cur_reasons, cur_conv = _resolve_currency(rules, pre, suf, family)
        reasons += cur_reasons
        conventions += cur_conv
        out.append({"type": "amount", "_a": a, "_b": b, "value": None if value is None else _tidy(value),
                    "currency": code, "currency_marker": marker, "conventions": conventions,
                    "ambiguous": bool(reasons), "ambiguity_reasons": reasons, "notes": []})
        pos = max(pos, b)
    return out


# ----------------------------------------------------------------------- dates
def _month_table() -> Dict[str, int]:
    t: Dict[str, int] = {}
    for i, name in enumerate(lx.MONTHS_TH, 1):
        t[normalize_text(name).casefold()] = i
    for i, names in enumerate(lx.MONTHS_ID, 1):
        for n in names:
            t[n] = i
    for i, names in enumerate(lx.MONTHS_EN, 1):
        for n in names:
            t.setdefault(n, i)
    for i, name in enumerate(lx.MONTHS_FIL, 1):
        t.setdefault(name, i)
    for i, name in enumerate(lx.MONTHS_RU, 1):
        t[name] = i
    for i, name in enumerate(lx.MONTHS_KK, 1):
        t[normalize_text(name).casefold()] = i
    for i, name in enumerate(lx.MONTHS_UZ, 1):
        t.setdefault(name, i)
    return t


_MONTHS = _month_table()
_MONTH_ALT = "|".join(re.escape(k) for k in sorted(_MONTHS, key=len, reverse=True))


def _iso(y: int, m: Optional[int], d: Optional[int]) -> Optional[str]:
    try:
        if d is not None:
            return date(y, m, d).isoformat()
        if m is not None:
            date(y, m, 1)
            return f"{y:04d}-{m:02d}"
        return f"{y:04d}"
    except ValueError:
        return None


def _item(kind, a, b, value, precision, conventions, era=None, reasons=None, extra=None):
    d = {"type": kind, "_a": a, "_b": b, "value": value, "precision": precision,
         "conventions": conventions, "ambiguous": bool(reasons), "ambiguity_reasons": list(reasons or []),
         "notes": []}
    if era:
        d["era"] = era
    if extra:
        d.update(extra)
    return d


def _year_be(y: int, family: Optional[str], explicit_be: bool, rules: _Rules):
    """Resolve a possibly Buddhist-era year; return ``(gregorian_year or None, conventions, reasons)``.

    An explicit พ.ศ. marker always means Buddhist era. In Thai text a year of 2400-2700 is
    taken as Buddhist era, 1900-2100 as Gregorian, and anything else is ambiguous.
    Outside Thai, the year is Gregorian.
    """
    be = rules.eras["norm.buddhist_era"]["offset"]
    if explicit_be or (family == "th" and 2400 <= y <= 2700):
        return y + be, ["norm.buddhist_era"], []
    if family == "th" and not (1900 <= y <= 2100):
        return None, [], [f"year_era_ambiguous:{y}"]
    return y, [], []


def _fiscal(kind_value: Dict[str, Any], a, b, conventions, notes=None, reasons=None):
    """A fiscal-period item. ``notes`` are informational (for example the year-end month
    is not stated); ``reasons`` make the item ambiguous."""
    return {"type": "fiscal_period", "_a": a, "_b": b, "value": kind_value, "precision": "period",
            "conventions": conventions, "ambiguous": bool(reasons), "ambiguity_reasons": list(reasons or []),
            "notes": list(notes or [])}


def _dates_and_periods(norm: str, rules: _Rules, family: Optional[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    fis: List[Dict[str, Any]] = []
    eras = {"令和": "norm.reiwa", "平成": "norm.heisei", "昭和": "norm.showa",
            "民國": "norm.roc", "民国": "norm.roc"}

    def era_year(name: str, ystr: str) -> Tuple[int, str]:
        n = 1 if ystr == "元" else int(ystr)
        eid = eras[name]
        return n + rules.eras[eid]["offset"], eid

    # ---- fiscal periods first (they take priority over plain dates)
    for m in re.finditer(r"(令和|平成|昭和)(\d{1,2}|元)年(\d{1,2})月期", norm):
        y, eid = era_year(m.group(1), m.group(2))
        fis.append(_fiscal({"fiscal_year": y, "year_end_month": int(m.group(3))}, m.start(), m.end(), [eid]))
    for m in re.finditer(r"(\d{4})年(\d{1,2})月期", norm):
        fis.append(_fiscal({"fiscal_year": int(m.group(1)), "year_end_month": int(m.group(2))}, m.start(), m.end(), []))
    for m in re.finditer(r"(\d{4})年度第([1-4一二三四])(?:季度|四半期)", norm):
        q = "一二三四".find(m.group(2)) + 1 if m.group(2) in "一二三四" else int(m.group(2))
        fis.append(_fiscal({"fiscal_year": int(m.group(1)), "quarter": q, "year_end_month": None}, m.start(), m.end(),
                           [], ["fiscal_year_end_unspecified"]))
    for m in re.finditer(r"(\d{4})年第([1-4一二三四])季度", norm):
        q = "一二三四".find(m.group(2)) + 1 if m.group(2) in "一二三四" else int(m.group(2))
        fis.append(_fiscal({"year": int(m.group(1)), "quarter": q, "basis": "unspecified"}, m.start(), m.end(), []))
    for m in re.finditer(r"(\d{4})\s?(?:财年|財年|财政年度|財政年度|会计年度|會計年度)", norm):
        fis.append(_fiscal({"fiscal_year": int(m.group(1)), "year_end_month": None}, m.start(), m.end(), [],
                           ["fiscal_year_end_unspecified"]))
    for m in re.finditer(r"(\d{4})年度(?!第)", norm):
        fis.append(_fiscal({"fiscal_year": int(m.group(1)), "year_end_month": None}, m.start(), m.end(), [],
                           ["fiscal_year_end_unspecified"]))
    for m in re.finditer(r"(\d{4})년\s?([1-4])분기", norm):
        fis.append(_fiscal({"year": int(m.group(1)), "quarter": int(m.group(2)), "basis": "unspecified"},
                           m.start(), m.end(), []))
    for m in re.finditer(r"(\d{4})년\s?(?:회계연도|사업연도)", norm):
        fis.append(_fiscal({"fiscal_year": int(m.group(1)), "year_end_month": None}, m.start(), m.end(), [],
                           ["fiscal_year_end_unspecified"]))
    for m in re.finditer(normalize_text("ปีงบประมาณ") + r"\s?(\d{4})", norm):
        y, conv, reasons = _year_be(int(m.group(1)), "th", False, rules)
        fis.append(_fiscal({"fiscal_year": y, "year_end_month": None}, m.start(), m.end(), conv,
                           ["fiscal_year_end_unspecified"], reasons))
    for m in re.finditer(r"năm tài chính\s?(\d{4})", norm, re.I):
        fis.append(_fiscal({"fiscal_year": int(m.group(1)), "year_end_month": None}, m.start(), m.end(), [],
                           ["fiscal_year_end_unspecified"]))
    for m in re.finditer(r"tahun buku\s?(\d{4})", norm, re.I):
        fis.append(_fiscal({"fiscal_year": int(m.group(1)), "year_end_month": None}, m.start(), m.end(), [],
                           ["fiscal_year_end_unspecified"]))
    for m in re.finditer(r"(?<![A-Za-z])FY\s?(\d{4})(?:\s?[-/–]\s?(\d{2,4}))?(?!\d)", norm):
        y1 = int(m.group(1))
        if m.group(2):
            y2 = int(m.group(2)) if len(m.group(2)) == 4 else (y1 // 100) * 100 + int(m.group(2))
            fis.append(_fiscal({"fiscal_year_label": f"{y1}-{y2}", "start_year": y1, "end_year": y2,
                                "year_end_month": None}, m.start(), m.end(), [], ["fiscal_year_end_unspecified"]))
        else:
            fis.append(_fiscal({"fiscal_year": y1, "year_end_month": None}, m.start(), m.end(), [],
                               ["fiscal_year_end_unspecified"]))
    for m in re.finditer(r"(?<![A-Za-z])Q([1-4])\s?(?:FY\s?)?(\d{4})(?!\d)", norm):
        fis.append(_fiscal({"year": int(m.group(2)), "quarter": int(m.group(1)), "basis": "unspecified"},
                           m.start(), m.end(), []))
    for m in re.finditer(r"(?i)fiscal year ended (" + _MONTH_ALT + r")\.? (\d{1,2}), (\d{4})", norm):
        mo = _MONTHS[m.group(1).casefold()]
        fis.append(_fiscal({"fiscal_year": int(m.group(3)), "year_end_month": mo, "year_end_day": int(m.group(2))},
                           m.start(), m.end(), []))
    for m in re.finditer(r"(\d{4})\s?финансов\w+ год|финансов\w+ год\s?(\d{4})", norm, re.I):
        y = int(m.group(1) or m.group(2))
        fis.append(_fiscal({"fiscal_year": y, "year_end_month": None}, m.start(), m.end(), [],
                           ["fiscal_year_end_unspecified"]))
    def covered(a, b):
        return any(not (b <= f["_a"] or a >= f["_b"]) for f in fis)

    # ---- era dates / years
    for m in re.finditer(r"(令和|平成|昭和|民國|民国)(\d{1,3}|元)年(?:(\d{1,2})月(?:(\d{1,2})日)?)?(?!期)", norm):
        if covered(m.start(), m.end()):
            continue
        y, eid = era_year(m.group(1), m.group(2))
        mo = int(m.group(3)) if m.group(3) else None
        d = int(m.group(4)) if m.group(4) else None
        iso = _iso(y, mo, d)
        kind = "era_year" if mo is None else "date"
        out.append(_item(kind, m.start(), m.end(), iso if iso else None, "year" if mo is None else ("day" if d else "month"),
                         [eid], era=eid.split(".")[1], reasons=[] if iso else ["invalid_calendar_date"]))
    for m in re.finditer(r"(?:พ\.ศ\.|ปี)\s?(\d{4})(?!\d)", norm):
        if covered(m.start(), m.end()):
            continue
        y, conv, reasons = _year_be(int(m.group(1)), "th", m.group(0).startswith("พ.ศ."), rules)
        out.append(_item("era_year", m.start(), m.end(), None if y is None else f"{y:04d}", "year", conv, era="buddhist_era",
                         reasons=reasons))
    # ---- CJK dates
    for m in re.finditer(r"(\d{4})年(\d{1,2})月(?:(\d{1,2})[日号號])?(?!期)", norm):
        if covered(m.start(), m.end()) or any(o["_a"] <= m.start() < o["_b"] for o in out):
            continue
        iso = _iso(int(m.group(1)), int(m.group(2)), int(m.group(3)) if m.group(3) else None)
        out.append(_item("date", m.start(), m.end(), iso, "day" if m.group(3) else "month", [],
                         reasons=[] if iso else ["invalid_calendar_date"]))
    for m in re.finditer(r"(\d{4})년\s?(\d{1,2})월\s?(?:(\d{1,2})일)?", norm):
        if covered(m.start(), m.end()):
            continue
        iso = _iso(int(m.group(1)), int(m.group(2)), int(m.group(3)) if m.group(3) else None)
        out.append(_item("date", m.start(), m.end(), iso, "day" if m.group(3) else "month", [],
                         reasons=[] if iso else ["invalid_calendar_date"]))
    for m in re.finditer(r"(\d{4})年(?![度月财財会會第])", norm):
        if covered(m.start(), m.end()) or any(not (m.end() <= o["_a"] or m.start() >= o["_b"]) for o in out):
            continue
        out.append(_item("date", m.start(), m.end(), f"{int(m.group(1)):04d}", "year", []))
    for m in re.finditer(r"(\d{4})년(?!\s?\d{1,2}\s?[월분]|\s?회계|\s?사업)", norm):
        if covered(m.start(), m.end()) or any(not (m.end() <= o["_a"] or m.start() >= o["_b"]) for o in out):
            continue
        out.append(_item("date", m.start(), m.end(), f"{int(m.group(1)):04d}", "year", []))
    # ---- named-month dates (Thai, Indonesian/Malay, Filipino, Russian, Kazakh, Uzbek, English, Vietnamese)
    mon = _MONTH_ALT
    named = [
        (rf"(?i)(\d{{1,2}})\s?({mon})\s?(\d{{4}})", ("d", "m", "y")),
        (rf"(?i)(\d{{1,2}})\s+ng\s+({mon})\s+(\d{{4}})", ("d", "m", "y")),
        (rf"(?i)({mon})\.?\s?(\d{{1,2}}),\s?(\d{{4}})", ("m", "d", "y")),
        (rf"(?i)(\d{{4}})\s?yil\s?(\d{{1,2}})\s?({mon})", ("y", "d", "m")),
        (rf"(?i)(?<![\d\w])({mon})\s?(\d{{4}})(?!\d)", ("m", "y")),
    ]
    for pat, order in named:
        for m in re.finditer(pat, norm):
            if covered(m.start(), m.end()) or any(not (m.end() <= o["_a"] or m.start() >= o["_b"]) for o in out):
                continue
            parts = dict(zip(order, m.groups()))
            mo = _MONTHS[parts["m"].casefold()]
            y0 = int(parts["y"])
            d = int(parts["d"]) if "d" in parts else None
            thai_context = parts["m"].casefold() in {normalize_text(x).casefold() for x in lx.MONTHS_TH}
            y, conv, reasons = _year_be(y0, "th" if thai_context else family, False, rules)
            iso = _iso(y, mo, d) if y is not None else None
            if iso is None and not reasons:
                reasons = ["invalid_calendar_date"]
            out.append(_item("date", m.start(), m.end(), iso, "day" if d else "month", conv, reasons=reasons))
    for m in re.finditer(r"(?i)(?:ngày\s+)?(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", norm):
        if covered(m.start(), m.end()):
            continue
        iso = _iso(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        out.append(_item("date", m.start(), m.end(), iso, "day", [], reasons=[] if iso else ["invalid_calendar_date"]))
    for m in re.finditer(r"(?i)tháng\s+(\d{1,2})\s+năm\s+(\d{4})", norm):
        if covered(m.start(), m.end()) or any(not (m.end() <= o["_a"] or m.start() >= o["_b"]) for o in out):
            continue
        iso = _iso(int(m.group(2)), int(m.group(1)), None)
        out.append(_item("date", m.start(), m.end(), iso, "month", [], reasons=[] if iso else ["invalid_calendar_date"]))
    for m in re.finditer(r"(\d{4})-(\d{2})-(\d{2})(?!\d)", norm):
        iso = _iso(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        out.append(_item("date", m.start(), m.end(), iso, "day", [], reasons=[] if iso else ["invalid_calendar_date"]))
    for m in re.finditer(r"(?<![\d.])(\d{1,2})[./](\d{1,2})[./](\d{4})(?!\d)", norm):
        a1, a2, y0 = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if family in _DAY_FIRST:
            d, mo = a1, a2
        elif a1 > 12 and a2 <= 12:
            d, mo = a1, a2
        elif a2 > 12 and a1 <= 12:
            d, mo = a2, a1
        else:
            out.append(_item("date", m.start(), m.end(), None, "day", [], reasons=["day_month_order_ambiguous"]))
            continue
        iso = _iso(y0, mo, d)
        out.append(_item("date", m.start(), m.end(), iso, "day", [], reasons=[] if iso else ["invalid_calendar_date"]))
    return fis + out


def _dedupe(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items = sorted(items, key=lambda i: (i["_a"], -(i["_b"] - i["_a"])))
    kept: List[Dict[str, Any]] = []
    for it in items:
        if kept and it["_a"] < kept[-1]["_b"] and it["type"] != "amount" and kept[-1]["type"] != "amount":
            continue
        kept.append(it)
    return kept


# ------------------------------------------------------------------ public API
def extract(text: str, language: Optional[str] = None,
            conventions: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Extract amounts, dates, era years, and fiscal periods from ``text``.

    ``language`` (optional) is a tag such as ``"zh-Hans"``, ``"ja"``, ``"th"``,
    ``"id/ms"``, ``"ru"``; when omitted it is identified, and when identification is
    undetermined the language-dependent rules (separators, ``¥``, day-month order)
    flag ambiguity instead of guessing.
    """
    conv = conventions or load_conventions()
    rules = _rules(conv)
    norm, starts, ends = normalize_with_offsets(text)
    if language is None:
        language = identify(text)["language"]
    family = _family(language)
    raw = _amounts(norm, rules, family) + _dates_and_periods(norm, rules, family)
    raw = _dedupe(raw)
    items: List[Dict[str, Any]] = []
    for r in raw:
        s, e = original_span(starts, ends, r["_a"], r["_b"])
        d = {k: v for k, v in r.items() if not k.startswith("_")}
        d.update({"span": text[s:e], "start": s, "end": e, "language": language,
                  "rule_id": f"extract.{r['type']}.v{RULE_VERSION}", "method": "rule"})
        if d["ambiguous"] and r["type"] in ("date", "era_year"):
            d["value"] = None
        items.append(d)
    errors = verify_spans(text, items)
    if errors:
        raise ValueError("; ".join(errors))
    return items


def verify_spans(text: str, items: Sequence[Dict[str, Any]]) -> List[str]:
    """Check ``text[start:end] == span`` for every item; return the errors."""
    errors: List[str] = []
    for i, it in enumerate(items):
        s, e = it.get("start"), it.get("end")
        if not isinstance(s, int) or not isinstance(e, int) or not (0 <= s < e <= len(text)):
            errors.append(f"item {i}: offsets {s}:{e} outside text of length {len(text)}")
        elif text[s:e] != it.get("span"):
            errors.append(f"item {i}: span {it.get('span')!r} does not equal text[{s}:{e}] = {text[s:e]!r}")
    return errors
