"""``quantsmith-test-engineering`` command line (spec 0097). Every subcommand prints JSON to stdout.

    detect  [--root .]
    run     --tool pytest|ctest|gtest [--root .] [--build-dir B] [--binary X] [-- extra args]
    edges   --target pkg.mod:func [--root .] [--allow ValueError,...] [--write-tests OUT.py]
    cpp     --header lib.hpp --signature "int add(int a, int b)" [--root .] [--include DIR] [--source FILE.cpp]
    mutate  --target path/in/root.py [--root .] [--max-mutants N] [-- pytest args]
    flaky   --tool pytest|gtest [--root .] [--runs N] [--shuffles N] [--binary X] [-- pytest args]

Exit status: 0 = ran, nothing to flag; 1 = findings (failures, survivors, flakiness, sanitizer or probe findings);
2 = could not run (missing tool, bad input). Findings are advisory evidence, never proof of correctness.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .report import ToolMissing


def _emit(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, default=str))


def _split(argv: Sequence[str]) -> tuple:
    argv = list(argv)
    if "--" in argv:
        i = argv.index("--")
        return argv[:i], argv[i + 1:]
    return argv, []


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
        raise ValueError(f"{target} is not a callable")
    return mod_name, fn_name, fn


def cmd_detect(a, extra) -> int:
    from .detect import detect_stack
    _emit(detect_stack(Path(a.root)))
    return 0


def cmd_run(a, extra) -> int:
    from . import runners
    root = Path(a.root)
    if a.tool == "pytest":
        rep = runners.run_pytest(root, extra)
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
    allowed: List[type] = []
    for exc in filter(None, (a.allow or "").split(",")):
        import builtins
        t = getattr(builtins, exc.strip(), None)
        if not (isinstance(t, type) and issubclass(t, BaseException)):
            raise ValueError(f"--allow: {exc!r} is not a builtin exception")
        allowed.append(t)
    probe = probe_function(fn, allowed_exceptions=allowed)
    if a.write_tests:
        Path(a.write_tests).write_text(generate_pytest_source(mod, name, probe, fn), encoding="utf-8")
        probe["tests_written"] = a.write_tests
    _emit(probe)
    return 1 if probe.get("findings") else 0


def cmd_cpp(a, extra) -> int:
    from .cpp_harness import probe_cpp
    res = probe_cpp(a.header, a.signature, include_dirs=a.include or (), sources=a.source or (), cwd=a.root)
    _emit(res)
    return 2 if not res["built"] else (1 if res["findings"] else 0)


def cmd_mutate(a, extra) -> int:
    from .mutation import run_mutation
    res = run_mutation(a.root, a.target, extra, max_mutants=a.max_mutants)
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
        res = flaky.check_pytest(a.root, extra, runs=a.runs, shuffles=a.shuffles)
    _emit(res)
    return 1 if res["verdict"] == "flakiness_found" else 0


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
    sp.add_argument("--tool", choices=["pytest", "ctest", "gtest"], required=True)
    sp.add_argument("--build-dir")
    sp.add_argument("--binary")
    sp = add("edges", cmd_edges, "probe a Python function at edge values")
    sp.add_argument("--target", required=True)
    sp.add_argument("--allow", help="comma-separated builtin exceptions the function is documented to raise")
    sp.add_argument("--write-tests", help="write characterization tests to this path")
    sp = add("cpp", cmd_cpp, "probe a C++ function with sanitizers")
    sp.add_argument("--header", required=True)
    sp.add_argument("--signature", required=True)
    sp.add_argument("--include", action="append")
    sp.add_argument("--source", action="append")
    sp = add("mutate", cmd_mutate, "mutation-test one Python file")
    sp.add_argument("--target", required=True)
    sp.add_argument("--max-mutants", type=int, default=60)
    sp = add("flaky", cmd_flaky, "rerun, shuffle and reseed to find flaky or order-dependent tests")
    sp.add_argument("--tool", choices=["pytest", "gtest"], default="pytest")
    sp.add_argument("--binary")
    sp.add_argument("--runs", type=int, default=5)
    sp.add_argument("--shuffles", type=int, default=3)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
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
