"""Edge-case engine for Python functions (spec 0097).

Given a function and its type hints, build boundary values per parameter, call the function with
one parameter at a time set to each edge value (the rest at a typical value), and report what it
did. It cannot know the *right* answer, so it looks for things that are wrong whatever the answer
is: an exception on a value that is valid for the declared type, a non-finite result from finite
inputs, a mutated argument, a call that does not finish. It can also emit a pytest file that pins
today's behaviour (a characterization test) for you to review.

Run it only on code you own or are authorised to test: it calls the function in this process.
POSIX only (SIGALRM timeouts, main thread).
"""

from __future__ import annotations

import copy
import datetime as dt
import decimal
import inspect
import math
import signal
import typing
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

CRASH_LIKE = (ZeroDivisionError, IndexError, KeyError, AttributeError, RecursionError, MemoryError, OverflowError,
              UnicodeError, AssertionError, NotImplementedError)


@dataclass(frozen=True)
class EdgeValue:
    label: str
    value: Any
    why: str
    valid_for_type: bool = True


def _ints() -> List[EdgeValue]:
    return [EdgeValue("zero", 0, "identity and divide-by-zero boundary"), EdgeValue("one", 1, "smallest positive"),
            EdgeValue("minus_one", -1, "smallest negative; indexing from the end"),
            EdgeValue("int32_max", 2**31 - 1, "32-bit overflow boundary"), EdgeValue("int32_min", -2**31, "32-bit underflow boundary"),
            EdgeValue("int64_max", 2**63 - 1, "64-bit overflow boundary"), EdgeValue("int64_min", -2**63, "64-bit underflow boundary"),
            EdgeValue("beyond_int64", 2**64, "beyond fixed-width integers")]


def _floats() -> List[EdgeValue]:
    return [EdgeValue("zero", 0.0, "identity and divide-by-zero boundary"), EdgeValue("neg_zero", -0.0, "sign of zero"),
            EdgeValue("nan", math.nan, "NaN compares unequal to itself"), EdgeValue("inf", math.inf, "positive infinity"),
            EdgeValue("neg_inf", -math.inf, "negative infinity"), EdgeValue("max", 1.7976931348623157e308, "overflow on arithmetic"),
            EdgeValue("tiny", 5e-324, "denormal: underflow and precision loss"), EdgeValue("epsilon", 2.220446049250313e-16, "smallest step near 1"),
            EdgeValue("negative", -1.5, "ordinary negative")]


def _strs() -> List[EdgeValue]:
    return [EdgeValue("empty", "", "empty input"), EdgeValue("space", " ", "whitespace only"), EdgeValue("newline", "\n", "line separator"),
            EdgeValue("nul", "a\x00b", "embedded NUL"), EdgeValue("unicode", "naïve café 日本語 🙂", "non-ASCII and emoji"),
            EdgeValue("combining", "é", "combining character: len differs from glyph count"),
            EdgeValue("rtl", "‮abc", "right-to-left override"), EdgeValue("zero_width", "a​b", "zero-width space"),
            EdgeValue("long", "x" * 10_000, "length stress"), EdgeValue("quote", "\"'; --", "quote and delimiter characters")]


def _bytes() -> List[EdgeValue]:
    return [EdgeValue("empty", b"", "empty input"), EdgeValue("nul", b"\x00", "NUL byte"), EdgeValue("high", b"\xff\xfe", "invalid UTF-8"),
            EdgeValue("long", b"x" * 10_000, "length stress")]


def _bools() -> List[EdgeValue]:
    return [EdgeValue("true", True, "truthy"), EdgeValue("false", False, "falsy")]


def _dates() -> List[EdgeValue]:
    return [EdgeValue("epoch", dt.date(1970, 1, 1), "Unix epoch"), EdgeValue("leap_day", dt.date(2024, 2, 29), "leap day"),
            EdgeValue("century_non_leap", dt.date(1900, 3, 1), "1900 is not a leap year"), EdgeValue("min", dt.date.min, "date.min"),
            EdgeValue("max", dt.date.max, "date.max: adding a day overflows"), EdgeValue("month_end", dt.date(2023, 1, 31), "month-end arithmetic")]


def _datetimes() -> List[EdgeValue]:
    utc = dt.timezone.utc
    return [EdgeValue("epoch_utc", dt.datetime(1970, 1, 1, tzinfo=utc), "aware epoch"), EdgeValue("naive", dt.datetime(2024, 6, 1, 12, 0), "naive vs aware mixing"),
            EdgeValue("leap_second_edge", dt.datetime(2024, 12, 31, 23, 59, 59, 999999, tzinfo=utc), "last microsecond of a year"),
            EdgeValue("min", dt.datetime.min, "datetime.min"), EdgeValue("max", dt.datetime.max, "datetime.max"),
            EdgeValue("offset", dt.datetime(2024, 3, 10, 2, 30, tzinfo=dt.timezone(dt.timedelta(hours=-5, minutes=-30))), "non-whole-hour offset")]


def _decimals() -> List[EdgeValue]:
    D = decimal.Decimal
    return [EdgeValue("zero", D("0"), "zero"), EdgeValue("neg_zero", D("-0"), "negative zero"), EdgeValue("tiny", D("1E-28"), "precision limit"),
            EdgeValue("huge", D("1E+28"), "magnitude"), EdgeValue("nan", D("NaN"), "NaN"), EdgeValue("inf", D("Infinity"), "infinity")]


def _none() -> List[EdgeValue]:
    return [EdgeValue("none", None, "absent value")]


CATALOGS: Dict[Any, Callable[[], List[EdgeValue]]] = {int: _ints, float: _floats, str: _strs, bytes: _bytes, bool: _bools,
                                                      dt.date: _dates, dt.datetime: _datetimes, decimal.Decimal: _decimals}
TYPICAL: Dict[Any, Any] = {int: 3, float: 1.5, str: "abc", bytes: b"abc", bool: True, dt.date: dt.date(2024, 6, 15),
                           dt.datetime: dt.datetime(2024, 6, 15, 12, 0, tzinfo=dt.timezone.utc), decimal.Decimal: decimal.Decimal("1.5"),
                           list: [1, 2, 3], dict: {"a": 1}, tuple: (1, 2, 3), set: {1, 2, 3}}


def _container(origin: Any, args: Tuple[Any, ...]) -> List[EdgeValue]:
    inner = args[0] if args else int
    typical = TYPICAL.get(inner, 3)
    if origin in (list, typing.Sequence, typing.List):
        big = [typical] * 10_000
        return [EdgeValue("empty", [], "empty collection"), EdgeValue("single", [typical], "one element"),
                EdgeValue("duplicates", [typical, typical, typical], "repeated elements"), EdgeValue("large", big, "size stress"),
                EdgeValue("with_none", [typical, None], "None among elements", valid_for_type=False)]
    if origin in (dict, typing.Mapping):
        return [EdgeValue("empty", {}, "empty mapping"), EdgeValue("single", {"k": typical}, "one entry"),
                EdgeValue("many", {str(i): typical for i in range(2_000)}, "size stress")]
    if origin in (tuple,):
        return [EdgeValue("empty", (), "empty tuple"), EdgeValue("single", (typical,), "one element")]
    if origin in (set, frozenset):
        return [EdgeValue("empty", set(), "empty set"), EdgeValue("single", {typical}, "one element")]
    return []


def edge_values(hint: Any) -> List[EdgeValue]:
    """Boundary values for a type hint. Unknown hints return [] (the caller reports 'no catalog')."""
    if hint is inspect.Parameter.empty or hint is Any:
        return []
    origin, args = typing.get_origin(hint), typing.get_args(hint)
    if origin is typing.Union or (hasattr(typing, "UnionType") and origin is getattr(__import__("types"), "UnionType", None)):
        out: List[EdgeValue] = []
        for a in args:
            out += _none() if a is type(None) else edge_values(a)
        seen, uniq = set(), []
        for e in out:
            if (e.label, repr(e.value)) not in seen:
                seen.add((e.label, repr(e.value)))
                uniq.append(e)
        return uniq
    if hint in CATALOGS:
        return CATALOGS[hint]()
    if origin is not None:
        return _container(origin, args)
    if hint in (list, dict, tuple, set):
        return _container(hint, ())
    return []


def typical_value(hint: Any) -> Any:
    origin, args = typing.get_origin(hint), typing.get_args(hint)
    if origin is typing.Union:
        non_none = [a for a in args if a is not type(None)]
        return typical_value(non_none[0]) if non_none else None
    if hint in TYPICAL:
        return copy.deepcopy(TYPICAL[hint])
    if origin in (list, typing.Sequence):
        return [typical_value(args[0]) if args else 3] * 3
    if origin in (dict, typing.Mapping):
        return {"a": typical_value(args[1]) if len(args) > 1 else 1}
    if origin is tuple:
        return tuple(typical_value(a) for a in args if a is not Ellipsis) or (1, 2, 3)
    if origin in (set, frozenset):
        return {typical_value(args[0]) if args else 1}
    return 3


class _Timeout(Exception):
    pass


def _alarm(_signum: int, _frame: Any) -> None:
    raise _Timeout()


@dataclass
class Outcome:
    case_id: str
    param: str
    label: str
    why: str
    valid_for_type: bool
    kind: str                          # returned | raised | timeout
    result_repr: str = ""
    exception: str = ""
    message: str = ""
    duration_s: float = 0.0
    flags: List[str] = field(default_factory=list)


def _call(fn: Callable[..., Any], kwargs: Dict[str, Any], timeout_s: float) -> Tuple[str, Any, float]:
    import time
    old = signal.signal(signal.SIGALRM, _alarm)
    start = time.monotonic()
    try:
        signal.setitimer(signal.ITIMER_REAL, timeout_s)
        try:
            return "returned", fn(**kwargs), time.monotonic() - start
        except _Timeout:
            return "timeout", None, time.monotonic() - start
        except BaseException as exc:                                   # noqa: BLE001 - report every failure mode
            return "raised", exc, time.monotonic() - start
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def _finite(x: Any) -> bool:
    if isinstance(x, float):
        return math.isfinite(x)
    if isinstance(x, decimal.Decimal):
        return x.is_finite()
    if isinstance(x, (list, tuple, set)):
        return all(_finite(i) for i in x)
    return True


def probe_function(fn: Callable[..., Any], allowed_exceptions: Sequence[type] = (), baseline: Optional[Mapping[str, Any]] = None,
                   extra_edges: Optional[Mapping[str, Sequence[EdgeValue]]] = None, timeout_s: float = 2.0,
                   max_cases: int = 400) -> Dict[str, Any]:
    """Call ``fn`` with one parameter at a time at each edge value. Returns outcomes and findings.

    ``allowed_exceptions`` are the exceptions the function is *documented* to raise on bad input. An
    exception on a value valid for the declared type that is not allowed is a finding; so is any
    crash-like exception (ZeroDivisionError, IndexError, ...), a call that times out, a non-finite
    result from finite inputs, and an argument that the call mutated.
    """
    sig = inspect.signature(fn)
    hints = typing.get_type_hints(fn) if hasattr(fn, "__annotations__") else {}
    params = [p for p in sig.parameters.values() if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)]
    base: Dict[str, Any] = {}
    for p in params:
        if baseline and p.name in baseline:
            base[p.name] = copy.deepcopy(baseline[p.name])
        elif p.default is not inspect.Parameter.empty:
            base[p.name] = copy.deepcopy(p.default)
        else:
            base[p.name] = typical_value(hints.get(p.name, p.annotation))
    outcomes: List[Outcome] = []
    no_catalog: List[str] = []
    n = 0
    for p in params:
        hint = hints.get(p.name, p.annotation)
        edges = list(edge_values(hint)) + list((extra_edges or {}).get(p.name, ()))
        if not edges:
            no_catalog.append(p.name)
            continue
        for e in edges:
            if n >= max_cases:
                break
            n += 1
            kwargs = copy.deepcopy(base)
            kwargs[p.name] = copy.deepcopy(e.value)
            before = copy.deepcopy(kwargs)
            kind, res, dur = _call(fn, kwargs, timeout_s)
            o = Outcome(case_id=f"{p.name}={e.label}", param=p.name, label=e.label, why=e.why, valid_for_type=e.valid_for_type,
                        kind=kind, duration_s=round(dur, 4))
            if kind == "returned":
                o.result_repr = repr(res)[:200]
                if isinstance(res, float) and not math.isfinite(res) and all(_finite(v) for v in before.values()):
                    o.flags.append("non_finite_result_from_finite_inputs")
                elif isinstance(res, decimal.Decimal) and not res.is_finite() and all(_finite(v) for v in before.values()):
                    o.flags.append("non_finite_result_from_finite_inputs")
            elif kind == "raised":
                o.exception, o.message = type(res).__name__, str(res)[:200]
                if not isinstance(res, tuple(allowed_exceptions)):
                    if isinstance(res, CRASH_LIKE):
                        o.flags.append("crash_like_exception")
                    elif e.valid_for_type:
                        o.flags.append("exception_on_valid_input")
            else:
                o.flags.append("timeout")
            if kwargs != before and not any(isinstance(v, float) and math.isnan(v) for v in before.values()):
                o.flags.append("mutated_its_input")
            outcomes.append(o)
    findings = [o for o in outcomes if o.flags]
    return {"function": getattr(fn, "__qualname__", repr(fn)), "baseline": {k: repr(v)[:80] for k, v in base.items()},
            "cases": len(outcomes), "outcomes": [o.__dict__ for o in outcomes], "findings": [o.__dict__ for o in findings],
            "no_catalog_for": no_catalog,
            "note": "edge cases find crashes and contract violations, not wrong answers; an empty findings list is not proof of correctness"}


def to_literal(value: Any) -> str:
    """A Python expression that rebuilds ``value`` (NaN, infinities, dates, decimals handled)."""
    if isinstance(value, float):
        if math.isnan(value):
            return 'float("nan")'
        if math.isinf(value):
            return 'float("inf")' if value > 0 else 'float("-inf")'
        return "-0.0" if value == 0 and math.copysign(1, value) < 0 else repr(value)
    if isinstance(value, decimal.Decimal):
        return f'decimal.Decimal("{value}")'
    if isinstance(value, dt.datetime):
        tz = ", tzinfo=" + ("datetime.timezone.utc" if value.tzinfo == dt.timezone.utc else f"datetime.timezone(datetime.timedelta(seconds={int(value.utcoffset().total_seconds())}))") if value.tzinfo else ""
        return f"datetime.datetime({value.year}, {value.month}, {value.day}, {value.hour}, {value.minute}, {value.second}, {value.microsecond}{tz})"
    if isinstance(value, dt.date):
        return f"datetime.date({value.year}, {value.month}, {value.day})"
    if isinstance(value, (list, tuple, set, dict)):
        if isinstance(value, dict):
            return "{" + ", ".join(f"{to_literal(k)}: {to_literal(v)}" for k, v in value.items()) + "}"
        inner = ", ".join(to_literal(v) for v in value)
        return {list: f"[{inner}]", tuple: f"({inner}{',' if len(value) == 1 else ''})", set: f"{{{inner}}}" if value else "set()"}[type(value)]
    return repr(value)


def generate_pytest_source(module: str, function: str, probe: Mapping[str, Any], fn: Callable[..., Any],
                           extra_edges: Optional[Mapping[str, Sequence[EdgeValue]]] = None) -> str:
    """A pytest file that pins today's behaviour for every probed case. It is a characterization test:
    it records what the function does now, so a later change is noticed. It does not assert correctness;
    review every case, and delete or fix the ones that pin a bug."""
    sig = inspect.signature(fn)
    hints = typing.get_type_hints(fn)
    params = [p.name for p in sig.parameters.values() if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)]
    base = {}
    for name in params:
        base[name] = fn_default(sig, name, hints)
    by_param: Dict[str, Dict[str, EdgeValue]] = {}
    for name in params:
        by_param[name] = {e.label: e for e in list(edge_values(hints.get(name, sig.parameters[name].annotation))) + list((extra_edges or {}).get(name, ()))}
    lines = ['"""Characterization tests generated by quantsmith.test_engineering (spec 0097).', "",
             f"They pin the CURRENT behaviour of {module}.{function} at boundary values. They do not assert that", 
             'the behaviour is correct. Review every case; fix the code or delete the case if it pins a bug."""', "",
             "import datetime", "import decimal", "import math", "", "import pytest", "", f"from {module} import {function}", "", "",
             "def _same(a, b):", "    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):", "        return True",
             "    return a == b", "", "", "CASES = ["]
    for o in probe["outcomes"]:
        e = by_param[o["param"]][o["label"]]
        kwargs = dict(base)
        kwargs[o["param"]] = e.value
        kw = "{" + ", ".join(f"{k!r}: {to_literal(v)}" for k, v in kwargs.items()) + "}"
        if o["kind"] == "raised":
            expect = f'("raises", {o["exception"]!r})'
        elif o["kind"] == "returned":
            try:
                real = fn(**copy.deepcopy(kwargs))
                expect = f'("returns", {to_literal(real)})'
            except BaseException:                                       # noqa: BLE001
                continue
        else:
            continue
        lines.append(f"    ({o['case_id']!r}, {kw}, {expect}),")
    lines += ["]", "", "", '@pytest.mark.parametrize("case_id,kwargs,expected", CASES, ids=[c[0] for c in CASES])',
              "def test_pinned_behaviour(case_id, kwargs, expected):", "    kind, value = expected",
              '    if kind == "raises":', "        with pytest.raises(Exception) as info:", f"            {function}(**kwargs)",
              "        assert type(info.value).__name__ == value", "    else:", f"        assert _same({function}(**kwargs), value)", ""]
    return "\n".join(lines)


def fn_default(sig: inspect.Signature, name: str, hints: Mapping[str, Any]) -> Any:
    p = sig.parameters[name]
    if p.default is not inspect.Parameter.empty:
        return p.default
    return typical_value(hints.get(name, p.annotation))
