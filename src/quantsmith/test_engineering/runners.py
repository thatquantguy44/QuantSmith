"""Safe command execution and test-runner adapters (pytest, CTest, GoogleTest binaries, plain binaries).

Safety rules: arguments are always a list (never a shell string), every run has a timeout, the whole
process group is killed on timeout, and output is capped. Commands run in the caller's own working
directory with the caller's own code: point this only at code you own or are authorised to test.
POSIX only (process-group kill).
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import List, Mapping, Optional, Sequence

from .junit import parse_junit
from .report import CommandResult, RunReport, ToolMissing

MAX_OUTPUT = 200_000
PYTEST_EXIT = {0: "all tests passed", 1: "some tests failed", 2: "interrupted", 3: "internal error",
               4: "usage error", 5: "no tests collected"}


def run_command(argv: Sequence[str], cwd: str | Path, timeout_s: float = 300.0,
                env_extra: Optional[Mapping[str, str]] = None, max_output: int = MAX_OUTPUT) -> CommandResult:
    """Run ``argv`` without a shell. The whole process group is killed on timeout; output is capped."""
    if isinstance(argv, str):
        raise TypeError("argv must be a list of strings, not a shell string")
    env = dict(os.environ)
    env.update(env_extra or {})
    start = time.monotonic()
    proc = subprocess.Popen(list(argv), cwd=str(cwd), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, errors="replace", start_new_session=True)
    timed_out = False
    try:
        out, err = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        out, err = proc.communicate()
    truncated = len(out) > max_output or len(err) > max_output
    return CommandResult(argv=list(argv), cwd=str(cwd), returncode=None if timed_out else proc.returncode,
                         duration_s=round(time.monotonic() - start, 4), timed_out=timed_out,
                         stdout=out[:max_output], stderr=err[:max_output], truncated=truncated)


def require_tool(name: str, hint: str = "") -> str:
    path = shutil.which(name)
    if not path:
        raise ToolMissing(f"{name} is not installed or not on PATH. {hint}".strip())
    return path


def run_pytest(cwd: str | Path, args: Sequence[str] = (), timeout_s: float = 600.0, python: Optional[str] = None,
               env_extra: Optional[Mapping[str, str]] = None, ids: Optional[Sequence[str]] = None) -> RunReport:
    """Run pytest in ``cwd`` and report per-test results from its JUnit XML.

    ``ids`` (node ids) run in the order given. Zero collected tests is reported as ``no_tests``, never as a pass.
    """
    py = python or sys.executable
    with tempfile.TemporaryDirectory(prefix="qte-") as tmp:
        xml_path = Path(tmp) / "junit.xml"
        argv = [py, "-m", "pytest", "-p", "no:cacheprovider", "-q", "--tb=short", f"--junitxml={xml_path}", *args, *(ids or [])]
        cmd = run_command(argv, cwd, timeout_s, env_extra)
        results = []
        notes: List[str] = []
        if xml_path.is_file():
            results = parse_junit(xml_path.read_text(encoding="utf-8", errors="replace"))
        if cmd.returncode in PYTEST_EXIT and cmd.returncode not in (0, 1):
            notes.append(f"pytest exit {cmd.returncode}: {PYTEST_EXIT[cmd.returncode]}")
        if not results and not cmd.timed_out:
            notes.append("no per-test results were produced; read stderr/stdout (a collection error looks like this)")
        if cmd.timed_out:
            notes.append(f"timed out after {timeout_s}s; the process group was killed")
    return RunReport(tool="pytest", command=cmd, results=results, notes=notes)


def run_ctest(build_dir: str | Path, args: Sequence[str] = (), timeout_s: float = 900.0,
              env_extra: Optional[Mapping[str, str]] = None) -> RunReport:
    """Run CTest in an already-built ``build_dir`` and parse its JUnit output. Needs ``ctest`` (part of CMake)."""
    ctest = require_tool("ctest", "Install CMake (for example `brew install cmake`).")
    build = Path(build_dir)
    with tempfile.TemporaryDirectory(prefix="qte-") as tmp:
        xml_path = Path(tmp) / "ctest-junit.xml"
        cmd = run_command([ctest, "--output-on-failure", "--output-junit", str(xml_path), *args], build, timeout_s, env_extra)
        results = parse_junit(xml_path.read_text(encoding="utf-8", errors="replace")) if xml_path.is_file() else []
    notes = [] if results else ["ctest produced no JUnit results (is the project built, and are tests registered with add_test?)"]
    return RunReport(tool="ctest", command=cmd, results=results, notes=notes)


def run_gtest_binary(binary: str | Path, cwd: str | Path, filter_: str = "*", shuffle_seed: Optional[int] = None,
                     repeat: int = 1, timeout_s: float = 600.0, env_extra: Optional[Mapping[str, str]] = None) -> RunReport:
    """Run a GoogleTest binary directly with XML output; optional shuffle with a reproducible seed."""
    with tempfile.TemporaryDirectory(prefix="qte-") as tmp:
        xml_path = Path(tmp) / "gtest.xml"
        argv = [str(binary), f"--gtest_output=xml:{xml_path}", f"--gtest_filter={filter_}", f"--gtest_repeat={repeat}"]
        if shuffle_seed is not None:
            argv += ["--gtest_shuffle", f"--gtest_random_seed={shuffle_seed}"]
        cmd = run_command(argv, cwd, timeout_s, env_extra)
        results = parse_junit(xml_path.read_text(encoding="utf-8", errors="replace")) if xml_path.is_file() else []
    notes = [f"shuffled with --gtest_random_seed={shuffle_seed}"] if shuffle_seed is not None else []
    if not results:
        notes.append("no GoogleTest XML was produced; the binary may have crashed before reporting")
    return RunReport(tool="gtest", command=cmd, results=results, notes=notes)
