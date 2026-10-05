"""Common result model for the test-engineering runtime (spec 0097).

Every runner, whatever the language, reports into the same shapes so a Python suite and a C++ suite
can be compared, repeated, and summarised alike. Statuses are deliberately few and honest:
``passed``, ``failed``, ``error`` (the test could not run or crashed), and ``skipped``. A run that
collected no tests is **not** a pass: ``RunReport.verdict`` says ``no_tests``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence

PASSED, FAILED, ERROR, SKIPPED = "passed", "failed", "error", "skipped"
STATUSES = (PASSED, FAILED, ERROR, SKIPPED)


class ToolMissing(RuntimeError):
    """A required external tool (compiler, ctest, coverage, ...) is not installed."""


@dataclass(frozen=True)
class TestResult:
    __test__ = False                                  # not a pytest test class
    id: str
    status: str
    duration_s: float = 0.0
    message: str = ""
    file: str = ""

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"unknown test status {self.status!r}")


def summarize(results: Sequence[TestResult]) -> Dict[str, int]:
    out = {s: 0 for s in STATUSES}
    for r in results:
        out[r.status] += 1
    out["total"] = len(results)
    return out


@dataclass
class CommandResult:
    argv: List[str]
    cwd: str
    returncode: Optional[int]
    duration_s: float
    timed_out: bool = False
    stdout: str = ""
    stderr: str = ""
    truncated: bool = False


@dataclass
class RunReport:
    tool: str
    command: CommandResult
    results: List[TestResult] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    @property
    def summary(self) -> Dict[str, int]:
        return summarize(self.results)

    @property
    def verdict(self) -> str:
        """``passed`` | ``failed`` | ``no_tests`` | ``timeout`` | ``error``. Never ``passed`` on zero tests."""
        if self.command.timed_out:
            return "timeout"
        s = self.summary
        if s["total"] == 0:
            return "error" if self.command.returncode not in (0, 5, None) else "no_tests"
        if s[FAILED] or s[ERROR]:
            return "failed"
        if s[PASSED] == 0:
            return "no_tests"
        return "passed"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["summary"] = self.summary
        d["verdict"] = self.verdict
        return d


def tail(text: str, limit: int = 4000) -> str:
    return text if len(text) <= limit else "...[truncated]...\n" + text[-limit:]
