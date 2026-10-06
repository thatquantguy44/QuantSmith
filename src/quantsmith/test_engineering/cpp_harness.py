"""C++ boundary-value harness with sanitizers (spec 0097).

From a function signature and the header that declares it, generate a small standalone program that
calls the function at boundary values (integer limits, NaN and infinities, empty and huge strings, a
null ``const char*``, empty and large vectors), compile it with AddressSanitizer and
UndefinedBehaviorSanitizer, and run **each case in its own process**. One case crashing, hanging, or
tripping a sanitizer therefore cannot hide the others, and every finding is tied to a case.

Supported parameter types: bool, char, signed and unsigned integers (``int``, ``long``, ``long long``,
``size_t``, ``int8_t`` ... ``uint64_t``), ``float``, ``double``, ``std::string``, ``const char*``,
``std::vector<int>``, ``std::vector<double>``, with optional ``const`` and ``&``. Anything else is
reported as unsupported rather than guessed. Only compile and run code you own or are authorised to
test: this builds and executes it.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .report import ToolMissing
from .runners import run_command
from .sanitizers import parse_sanitizer_output

INT_TYPES = {"int": ("INT_MIN", "INT_MAX"), "unsigned": ("0u", "UINT_MAX"), "unsigned int": ("0u", "UINT_MAX"),
             "long": ("LONG_MIN", "LONG_MAX"), "unsigned long": ("0ul", "ULONG_MAX"), "long long": ("LLONG_MIN", "LLONG_MAX"),
             "unsigned long long": ("0ull", "ULLONG_MAX"), "short": ("SHRT_MIN", "SHRT_MAX"), "unsigned short": ("0", "USHRT_MAX"),
             "size_t": ("0", "SIZE_MAX"), "std::size_t": ("0", "SIZE_MAX"), "int8_t": ("INT8_MIN", "INT8_MAX"),
             "uint8_t": ("0", "UINT8_MAX"), "int16_t": ("INT16_MIN", "INT16_MAX"), "uint16_t": ("0", "UINT16_MAX"),
             "int32_t": ("INT32_MIN", "INT32_MAX"), "uint32_t": ("0", "UINT32_MAX"), "int64_t": ("INT64_MIN", "INT64_MAX"),
             "uint64_t": ("0", "UINT64_MAX"), "std::int32_t": ("INT32_MIN", "INT32_MAX"), "std::int64_t": ("INT64_MIN", "INT64_MAX"),
             "std::uint32_t": ("0", "UINT32_MAX"), "std::uint64_t": ("0", "UINT64_MAX"), "char": ("CHAR_MIN", "CHAR_MAX")}
FLOAT_TYPES = {"float", "double"}
SIGNATURE = re.compile(r"^\s*(?P<ret>[\w:<>\s\*&,]+?)\s+(?P<name>[A-Za-z_]\w*)\s*\((?P<params>.*)\)\s*(?:const)?\s*;?\s*$", re.DOTALL)


@dataclass(frozen=True)
class CppParam:
    type: str          # normalised, no const/&
    name: str
    raw: str


class UnsupportedSignature(ValueError):
    pass


def _norm_type(t: str) -> str:
    t = re.sub(r"\bconst\b", "", t)
    t = t.replace("&", "").replace("std::vector<int >", "std::vector<int>")
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s*\*\s*", "*", t)
    return t


def parse_signature(sig: str) -> tuple[str, str, list[CppParam]]:
    """``(return_type, name, params)`` for a simple free-function declaration."""
    m = SIGNATURE.match(sig.strip())
    if not m:
        raise UnsupportedSignature(f"cannot parse signature: {sig!r}")
    ret, name, raw_params = " ".join(m.group("ret").split()), m.group("name"), m.group("params").strip()
    params: list[CppParam] = []
    if raw_params and raw_params != "void":
        depth, cur, parts = 0, "", []
        for ch in raw_params:
            depth += ch == "<"
            depth -= ch == ">"
            if ch == "," and depth == 0:
                parts.append(cur)
                cur = ""
            else:
                cur += ch
        parts.append(cur)
        for i, p in enumerate(parts):
            p = " ".join(p.split())
            mm = re.match(r"^(?P<t>.+?)(?:\s+(?P<n>[A-Za-z_]\w*))?$", p)
            t = _norm_type(mm.group("t") if mm else p)
            if mm and mm.group("n") and re.search(r"[\w>&\*]$", mm.group("t")) is None:
                t = _norm_type(p)
            name_ = mm.group("n") if mm and mm.group("n") and _norm_type(mm.group("t")) in _supported_types() else f"arg{i}"
            if name_ == f"arg{i}":
                t = _norm_type(re.sub(r"\s+[A-Za-z_]\w*$", "", p)) if re.search(r"\s[A-Za-z_]\w*$", p) and _norm_type(re.sub(r"\s+[A-Za-z_]\w*$", "", p)) in _supported_types() else _norm_type(p)
            params.append(CppParam(type=t, name=name_, raw=p))
    for p in params:
        if p.type not in _supported_types():
            raise UnsupportedSignature(f"unsupported parameter type {p.type!r} in {sig!r}")
    return ret, name, params


def _supported_types() -> set:
    return set(INT_TYPES) | FLOAT_TYPES | {"bool", "std::string", "const char*", "char*", "std::vector<int>", "std::vector<double>"}


def cpp_edge_values(t: str) -> list[tuple[str, str, str]]:
    """``(label, C++ expression, why)`` boundary values for a normalised type."""
    if t in INT_TYPES:
        lo, hi = INT_TYPES[t]
        vals = [("zero", f"static_cast<{t}>(0)", "zero"), ("one", f"static_cast<{t}>(1)", "smallest positive"),
                ("min", f"static_cast<{t}>({lo})", "type minimum"), ("max", f"static_cast<{t}>({hi})", "type maximum")]
        if not lo.startswith("0"):
            vals.append(("minus_one", f"static_cast<{t}>(-1)", "negative one; wraps for unsigned"))
        vals.append(("max_minus_one", f"static_cast<{t}>(static_cast<{t}>({hi}) - 1)", "just below the maximum"))
        return vals
    if t in FLOAT_TYPES:
        return [("zero", f"static_cast<{t}>(0)", "zero"), ("neg_zero", f"static_cast<{t}>(-0.0)", "sign of zero"),
                ("nan", f"std::numeric_limits<{t}>::quiet_NaN()", "NaN"), ("inf", f"std::numeric_limits<{t}>::infinity()", "infinity"),
                ("neg_inf", f"-std::numeric_limits<{t}>::infinity()", "negative infinity"),
                ("max", f"std::numeric_limits<{t}>::max()", "overflow on arithmetic"), ("lowest", f"std::numeric_limits<{t}>::lowest()", "most negative"),
                ("denorm_min", f"std::numeric_limits<{t}>::denorm_min()", "denormal"), ("epsilon", f"std::numeric_limits<{t}>::epsilon()", "step near 1")]
    if t == "bool":
        return [("true", "true", "truthy"), ("false", "false", "falsy")]
    if t == "std::string":
        return [("empty", 'std::string("")', "empty"), ("space", 'std::string(" ")', "whitespace"), ("embedded_nul", 'std::string("a\\0b", 3)', "embedded NUL"),
                ("utf8", 'std::string("na\\xc3\\xafve caf\\xc3\\xa9")', "non-ASCII UTF-8"), ("invalid_utf8", 'std::string("\\xff\\xfe")', "invalid UTF-8"),
                ("long", "std::string(100000, 'x')", "length stress"), ("digits_overflow", 'std::string("99999999999999999999999999")', "numeric text beyond int range")]
    if t in ("const char*", "char*"):
        return [("null", "static_cast<const char*>(nullptr)", "null pointer"), ("empty", 'static_cast<const char*>("")', "empty C string")]
    if t == "std::vector<int>":
        return [("empty", "std::vector<int>{}", "empty"), ("single", "std::vector<int>{0}", "one element"),
                ("extremes", "std::vector<int>{INT_MIN, INT_MAX}", "overflow when summed"), ("large", "std::vector<int>(100000, 1)", "size stress")]
    if t == "std::vector<double>":
        return [("empty", "std::vector<double>{}", "empty"), ("nan", "std::vector<double>{std::numeric_limits<double>::quiet_NaN()}", "NaN element"),
                ("infs", "std::vector<double>{std::numeric_limits<double>::infinity(), -std::numeric_limits<double>::infinity()}", "opposite infinities")]
    return []


def _typical(t: str) -> str:
    if t in INT_TYPES:
        return f"static_cast<{t}>(3)"
    return {"float": "1.5f", "double": "1.5", "bool": "true", "std::string": 'std::string("abc")', "const char*": 'static_cast<const char*>("abc")',
            "char*": 'static_cast<const char*>("abc")', "std::vector<int>": "std::vector<int>{1, 2, 3}",
            "std::vector<double>": "std::vector<double>{1.5, 2.5}"}[t]


def build_cases(params: Sequence[CppParam]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for i, p in enumerate(params):
        for label, expr, why in cpp_edge_values(p.type):
            args = [_typical(q.type) for q in params]
            args[i] = expr
            cases.append({"id": len(cases), "param": p.name, "label": label, "why": why, "args": args})
    return cases


def generate_harness(header: str, ret: str, name: str, params: Sequence[CppParam], cases: Sequence[dict[str, Any]]) -> str:
    """A standalone program: ``./harness <case-index>`` runs one case and prints ``OK <result>`` or ``EXC <what>``."""
    lines = ["#include <climits>", "#include <cstdint>", "#include <cstdlib>", "#include <cstddef>", "#include <iostream>", "#include <limits>",
             "#include <string>", "#include <vector>", "#include <exception>", f'#include "{header}"', "",
             "template <typename T> void show(const T& v) { std::cout << v; }",
             "template <typename T> void show(const std::vector<T>& v) { std::cout << \"vec[\" << v.size() << \"]\"; }",
             "inline void show(bool b) { std::cout << (b ? \"true\" : \"false\"); }", "",
             "int main(int argc, char** argv) {", "  if (argc < 2) { std::cerr << \"usage: harness <case>\\n\"; return 2; }",
             "  const int which = std::atoi(argv[1]);", "  try {", "    switch (which) {"]
    for c in cases:
        call = f"{name}({', '.join(c['args'])})"
        if ret == "void":
            lines.append(f"      case {c['id']}: {call}; std::cout << \"OK void\\n\"; break;")
        else:
            lines.append(f"      case {c['id']}: {{ auto r = {call}; std::cout << \"OK \"; show(r); std::cout << \"\\n\"; break; }}")
    lines += ["      default: std::cerr << \"no such case\\n\"; return 2;", "    }", "  } catch (const std::exception& e) {",
              "    std::cout << \"EXC \" << e.what() << \"\\n\"; return 0;", "  } catch (...) { std::cout << \"EXC unknown\\n\"; return 0; }",
              "  return 0;", "}", ""]
    return "\n".join(lines)


_SANITIZER_PROBES: dict[tuple[str, tuple[str, ...], str], dict[str, Any]] = {}


def _sanitizer_probe(cxx: str, sanitizers: Sequence[str], std: str) -> dict[str, Any]:
    """Can ``cxx`` build *and run* a trivial program with these sanitizers? Cached per compiler, sanitizers and standard.

    A compiler can be installed yet unable to link the sanitizer runtime (a ``clang++`` without compiler-rt), so
    "a compiler exists" does not mean "the boundary probe can run".
    """
    key = (cxx, tuple(sanitizers), std)
    if key not in _SANITIZER_PROBES:
        with tempfile.TemporaryDirectory(prefix="qte-san-") as tmp:
            src, binary = Path(tmp) / "probe.cpp", Path(tmp) / "probe"
            src.write_text("int main() { return 0; }\n", encoding="utf-8")
            build = run_command([cxx, f"-std={std}", f"-fsanitize={','.join(sanitizers)}", str(src), "-o", str(binary)], tmp, 60.0)
            if build.returncode != 0:
                result = {"compiler": cxx, "usable": False, "error": build.stderr.strip()[-400:] or f"exit {build.returncode}"}
            else:
                run = run_command([str(binary)], tmp, 10.0, {"ASAN_OPTIONS": "detect_leaks=0"})
                result = {"compiler": cxx, "usable": run.returncode == 0, "error": "" if run.returncode == 0 else run.stderr.strip()[-400:] or f"exit {run.returncode}"}
        _SANITIZER_PROBES[key] = result
    return _SANITIZER_PROBES[key]


def find_sanitizer_compiler(sanitizers: Sequence[str] = ("address", "undefined"), std: str = "c++17") -> tuple[str | None, list[dict[str, Any]]]:
    """The first installed compiler (``clang++``, then ``g++``) that can build and run a program with ``sanitizers``.

    Returns ``(path or None, tried)`` where ``tried`` says for each installed compiler whether it was usable and, if not, why.
    """
    tried = [_sanitizer_probe(path, sanitizers, std) for path in (shutil.which(name) for name in ("clang++", "g++")) if path]
    usable = next((t["compiler"] for t in tried if t["usable"]), None)
    return usable, tried


def probe_cpp(header: str, signature: str, include_dirs: Sequence[str] = (), sources: Sequence[str] = (), cwd: str | Path = ".",
              compiler: str | None = None, std: str = "c++17", timeout_s: float = 10.0, extra_flags: Sequence[str] = (),
              sanitizers: Sequence[str] = ("address", "undefined"), max_cases: int = 300) -> dict[str, Any]:
    """Compile with sanitizers and run each boundary case in its own process. Returns outcomes and findings.

    Without ``compiler=``, the first installed compiler that can build and run a sanitizer program is used, so a ``clang++`` that
    cannot link the sanitizer runtime does not hide a working ``g++``. With ``compiler=``, exactly that compiler is used.
    If no installed compiler works, the first one is still tried so the real compile error is reported (``built: false``).
    """
    tried: list[dict[str, Any]] = []
    if compiler:
        cxx: str | None = compiler
    else:
        cxx, tried = find_sanitizer_compiler(sanitizers, std)
        cxx = cxx or shutil.which("clang++") or shutil.which("g++")
    if not cxx:
        raise ToolMissing("no C++ compiler found (install clang++ or g++)")
    ret, name, params = parse_signature(signature)
    cases = build_cases(params)[:max_cases]
    cwd = Path(cwd).resolve()
    with tempfile.TemporaryDirectory(prefix="qte-cpp-") as tmp:
        src = Path(tmp) / "harness.cpp"
        src.write_text(generate_harness(header, ret, name, params, cases), encoding="utf-8")
        binary = Path(tmp) / "harness"
        san = ",".join(sanitizers)
        argv = [cxx, f"-std={std}", "-g", "-O1", "-fno-omit-frame-pointer", f"-fsanitize={san}", "-fno-sanitize-recover=undefined",
                *(f"-I{d}" for d in include_dirs), f"-I{cwd}", *extra_flags, str(src), *[str(Path(s)) for s in sources], "-o", str(binary)]
        build = run_command(argv, cwd, 180.0)
        if build.returncode != 0:
            return {"function": name, "signature": signature, "built": False, "compiler": cxx, "compile_errors": build.stderr[-4000:], "cases": 0,
                    "outcomes": [], "findings": [], "compilers_tried": tried,
                    "note": "the harness did not compile; check the header path, include dirs, and signature"
                            + ("" if not tried or any(t["usable"] for t in tried) else
                               "; no installed compiler can build a sanitizer program (see compilers_tried), so install the compiler's sanitizer runtime")}
        outcomes: list[dict[str, Any]] = []
        for c in cases:
            run = run_command([str(binary), str(c["id"])], cwd, timeout_s, {"ASAN_OPTIONS": "detect_leaks=0:abort_on_error=0", "UBSAN_OPTIONS": "print_stacktrace=1"})
            findings = parse_sanitizer_output(run.stderr)
            if run.timed_out:
                status = "timeout"
            elif findings:
                status = "sanitizer"
            elif run.returncode is not None and run.returncode < 0:
                status = "crash"
            elif run.returncode not in (0, None):
                status = "nonzero_exit"
            elif run.stdout.startswith("EXC"):
                status = "exception"
            else:
                status = "ok"
            outcomes.append({"case_id": c["id"], "param": c["param"], "label": c["label"], "why": c["why"], "status": status,
                             "returncode": run.returncode, "stdout": run.stdout.strip()[:200], "sanitizer": findings})
    findings = [o for o in outcomes if o["status"] in ("sanitizer", "crash", "timeout", "nonzero_exit")]
    return {"function": name, "signature": signature, "built": True, "compiler": cxx, "sanitizers": list(sanitizers), "cases": len(outcomes),
            "outcomes": outcomes, "findings": findings, "compilers_tried": tried,
            "note": "boundary values find undefined behaviour and crashes, not wrong answers; an empty findings list is not proof of correctness"}
