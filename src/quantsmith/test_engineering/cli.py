"""``quantsmith-test-engineering`` command line (spec 0097). Every subcommand prints JSON to stdout.

    detect  [--root .]
    run     --tool pytest|ctest|gtest [--root .] [--build-dir B] [--binary X] [-- extra args]
    edges   --target pkg.mod:func [--root .] [--allow ValueError,...] [--hint name=type] [--write-tests OUT.py]
    cpp     --header lib.hpp --signature "int add(int a, int b)" [--root .] [--include DIR] [--source FILE.cpp]
    mutate  --target path/in/root.py [--root .] [--python PY] [--env K=V] [--max-mutants N] [-- pytest args]
    flaky   --tool pytest|gtest [--root .] [--python PY] [--env K=V] [--runs N] [--shuffles N] [--binary X] [-- pytest args]
    metamorphic --target pkg.mod:func --relation NAME [--param K=V] --input vector:5 [--root .] [--cases N] [--seed N] [--rtol X] [--atol X]   (spec 0098)
    differential --target pkg.mod:func --reference pkg.mod:func --input vector:5 [--root .] [--cases N] [--seed N] [--rtol X] [--atol X]      (spec 0098)

Exit status: 0 = ran, nothing to flag; 1 = findings (failures, survivors, flakiness, sanitizer or probe findings, a violated
relation, disagreeing implementations); 2 = could not run (missing tool, bad input, an edges probe that tested nothing, or a
metamorphic/differential check that was inconclusive or had no cases). Findings are advisory evidence, never proof of correctness.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .report import ToolMissing


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, default=str))


def _split(argv: Sequence[str]) -> tuple:
    argv = list(argv)
    if "--" in argv:
        i = argv.index("--")
        return argv[:i], argv[i + 1:]
    return argv, []


def _env(pairs) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in pairs or ():
        if "=" not in item:
            raise ValueError(f"--env expects KEY=VALUE, got {item!r}")
        k, v = item.split("=", 1)
        out[k] = v
    return out


TYPE_NAMES = {"int": int, "float": float, "str": str, "bytes": bytes, "bool": bool, "list": list, "dict": dict, "tuple": tuple, "set": set}


def _hints(pairs) -> dict[str, type]:
    out: dict[str, type] = {}
    for item in pairs or ():
        name, _, tname = item.partition("=")
        if not name or tname not in TYPE_NAMES:
            raise ValueError(f"--hint expects name=type with type in {sorted(TYPE_NAMES)}, got {item!r}")
        out[name] = TYPE_NAMES[tname]
    return out


def _load_target(root: Path, target: str):
    if ":" not in target:
        raise ValueError("--target must look like package.module:function")
    mod_name, fn_name = target.split(":", 1)
    for p in (root, root / "src"):
        if p.is_dir() and str(p) not in sys.path:
            sys.path.insert(0, str(p))
    module = importlib.import_module(mod_name)
    fn = getattr(module, fn_name, None)
    if not callable(fn):
        raise ValueError(f"{target} is not a callable")  # noqa: TRY004 - main() maps ValueError to bad_input, exit 2
    return mod_name, fn_name, fn


def cmd_detect(a, extra) -> int:
    from .detect import detect_stack
    _emit(detect_stack(Path(a.root)))
    return 0


def cmd_run(a, extra) -> int:
    from . import runners
    root = Path(a.root)
    if a.tool == "pytest":
        rep = runners.run_pytest(root, extra, python=a.python, env_extra=_env(a.env))
    elif a.tool == "ctest":
        rep = runners.run_ctest(Path(a.build_dir or root / "build"), extra)
    else:
        if not a.binary:
            raise ValueError("--binary is required for --tool gtest")
        rep = runners.run_gtest_binary(a.binary, root)
    _emit(rep.to_dict())
    return 0 if rep.verdict == "passed" else 1


def cmd_edges(a, extra) -> int:
    from .edgecases import generate_pytest_source, probe_function
    root = Path(a.root).resolve()
    mod, name, fn = _load_target(root, a.target)
    allowed: list[type] = []
    for exc in filter(None, (a.allow or "").split(",")):
        import builtins
        t = getattr(builtins, exc.strip(), None)
        if not (isinstance(t, type) and issubclass(t, BaseException)):
            raise ValueError(f"--allow: {exc!r} is not a builtin exception")  # noqa: TRY004 - main() maps ValueError to bad_input, exit 2
        allowed.append(t)
    probe = probe_function(fn, allowed_exceptions=allowed, param_types=_hints(a.hint))
    if a.write_tests:
        Path(a.write_tests).write_text(generate_pytest_source(mod, name, probe, fn), encoding="utf-8")
        probe["tests_written"] = a.write_tests
    _emit(probe)
    if probe["status"] == "nothing_probed":
        return 2
    return 1 if probe.get("findings") else 0


def cmd_cpp(a, extra) -> int:
    from .cpp_harness import probe_cpp
    res = probe_cpp(a.header, a.signature, include_dirs=a.include or (), sources=a.source or (), cwd=a.root)
    _emit(res)
    return 2 if not res["built"] else (1 if res["findings"] else 0)


def cmd_mutate(a, extra) -> int:
    from .mutation import run_mutation
    res = run_mutation(a.root, a.target, extra, python=a.python, max_mutants=a.max_mutants, env=_env(a.env))
    _emit(res)
    if res.get("score") is None and res.get("baseline") != "passed":
        return 2
    return 1 if res.get("survived") else 0


def cmd_flaky(a, extra) -> int:
    from . import flaky
    if a.tool == "gtest":
        if not a.binary:
            raise ValueError("--binary is required for --tool gtest")
        res = flaky.check_gtest(a.binary, a.root, runs=a.runs, shuffles=a.shuffles)
    else:
        res = flaky.check_pytest(a.root, extra, runs=a.runs, shuffles=a.shuffles, python=a.python, env=_env(a.env))
    _emit(res)
    return 1 if res["verdict"] == "flakiness_found" else 0


def _finite(obj: Any) -> Any:
    """Replace non-finite floats with strings so the output is standard JSON."""
    import math
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else str(obj)
    if isinstance(obj, dict):
        return {k: _finite(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_finite(v) for v in obj]
    return obj


def _params(pairs) -> dict[str, Any]:
    import ast
    out: dict[str, Any] = {}
    for item in pairs or ():
        key, sep, raw = item.partition("=")
        if not key or not sep:
            raise ValueError(f"--param expects KEY=VALUE, got {item!r}")
        try:
            out[key] = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            out[key] = raw
    return out


def cmd_metamorphic(a, extra) -> int:
    from .metamorphic import RELATIONS, check_relation
    root = Path(a.root).resolve()
    _, _, fn = _load_target(root, a.target)
    if a.relation not in RELATIONS:
        raise ValueError(f"--relation must be one of {sorted(RELATIONS)}, got {a.relation!r}")
    try:
        relation = RELATIONS[a.relation](**_params(a.param))
    except TypeError as exc:
        raise ValueError(f"--param does not fit relation {a.relation!r}: {exc}") from exc
    res = check_relation(fn, relation, spec=a.input, cases=a.cases, seed=a.seed, rtol=a.rtol, atol=a.atol,
                         equal_nan=a.equal_nan, timeout_s=a.timeout)
    res["target"] = a.target
    _emit(_finite(res))
    return {"holds": 0, "violated": 1}.get(res["status"], 2)


def cmd_differential(a, extra) -> int:
    from .differential import compare_implementations
    root = Path(a.root).resolve()
    if a.target == a.reference:
        raise ValueError("--target and --reference must name different functions")
    _, _, fn = _load_target(root, a.target)
    _, _, ref = _load_target(root, a.reference)
    res = compare_implementations({a.target: fn, a.reference: ref}, spec=a.input, cases=a.cases, seed=a.seed, rtol=a.rtol,
                                  atol=a.atol, equal_nan=a.equal_nan, timeout_s=a.timeout, reference=a.reference)
    _emit(_finite(res))
    return {"agree": 0, "disagree": 1}.get(res["status"], 2)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="quantsmith-test-engineering", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("--root", default=".")
        sp.set_defaults(func=fn)
        return sp

    add("detect", cmd_detect, "detect languages, frameworks and test commands")
    sp = add("run", cmd_run, "run a test runner and report per-test results")
    sp.add_argument("--python", help="interpreter of the project under test (default: this one)")
    sp.add_argument("--env", action="append", metavar="KEY=VALUE", help="environment variable for the test run (repeatable)")
    sp.add_argument("--tool", choices=["pytest", "ctest", "gtest"], required=True)
    sp.add_argument("--build-dir")
    sp.add_argument("--binary")
    sp = add("edges", cmd_edges, "probe a Python function at edge values")
    sp.add_argument("--target", required=True)
    sp.add_argument("--allow", help="comma-separated builtin exceptions the function is documented to raise")
    sp.add_argument("--hint", action="append", metavar="NAME=TYPE", help="type for an unannotated parameter (int, float, str, bytes, bool, list, dict, tuple, set)")
    sp.add_argument("--write-tests", help="write characterization tests to this path")
    sp = add("cpp", cmd_cpp, "probe a C++ function with sanitizers")
    sp.add_argument("--header", required=True)
    sp.add_argument("--signature", required=True)
    sp.add_argument("--include", action="append")
    sp.add_argument("--source", action="append")
    sp = add("mutate", cmd_mutate, "mutation-test one Python file")
    sp.add_argument("--python", help="interpreter of the project under test (default: this one)")
    sp.add_argument("--env", action="append", metavar="KEY=VALUE", help="environment variable for the test run (repeatable)")
    sp.add_argument("--target", required=True)
    sp.add_argument("--max-mutants", type=int, default=60)
    sp = add("flaky", cmd_flaky, "rerun, shuffle and reseed to find flaky or order-dependent tests")
    sp.add_argument("--python", help="interpreter of the project under test (default: this one)")
    sp.add_argument("--env", action="append", metavar="KEY=VALUE", help="environment variable for the test run (repeatable)")
    sp.add_argument("--tool", choices=["pytest", "gtest"], default="pytest")
    sp.add_argument("--binary")
    sp.add_argument("--runs", type=int, default=5)
    sp.add_argument("--shuffles", type=int, default=3)
    def numeric(sp):
        sp.add_argument("--input", required=True, help="scalar, vector:N, matrix:RxC or spd:N")
        sp.add_argument("--cases", type=int, default=50)
        sp.add_argument("--seed", type=int, default=0)
        sp.add_argument("--rtol", type=float, default=1e-7)
        sp.add_argument("--atol", type=float, default=1e-9)
        sp.add_argument("--equal-nan", action="store_true")
        sp.add_argument("--timeout", type=float, default=10.0, help="seconds allowed per call")

    sp = add("metamorphic", cmd_metamorphic, "check a metamorphic relation (scaling, translation, permutation, idempotence, monotone, symmetry)")
    sp.add_argument("--target", required=True)
    sp.add_argument("--relation", required=True)
    sp.add_argument("--param", action="append", metavar="KEY=VALUE", help="relation parameter, e.g. degree=2 or kind=equivariant (repeatable)")
    numeric(sp)
    sp = add("differential", cmd_differential, "compare two implementations on shared seeded inputs")
    sp.add_argument("--target", required=True, help="the implementation under test")
    sp.add_argument("--reference", required=True, help="the implementation to compare it with")
    numeric(sp)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    own, extra = _split(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(own)
    try:
        return args.func(args, extra)
    except ToolMissing as exc:
        _emit({"error": "tool_missing", "message": str(exc)})
        return 2
    except (ValueError, ImportError, FileNotFoundError) as exc:
        _emit({"error": "bad_input", "message": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
