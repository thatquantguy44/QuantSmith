"""Line and branch coverage through the ``coverage`` package (an optional dependency).

Coverage says which lines ran, not whether they were checked. It is used here to tell a *surviving*
mutant (a test ran the line and did not notice the change) from an *uncovered* one (no test ran it),
which need different fixes.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from .report import ToolMissing
from .runners import run_command


def coverage_available(python: Optional[str] = None) -> bool:
    """Is ``coverage`` importable by ``python`` (the project's interpreter; default: this one)?"""
    if python is None or python == sys.executable:
        import importlib.util
        return importlib.util.find_spec("coverage") is not None
    return run_command([python, "-c", "import coverage"], Path("."), 30.0).returncode == 0


def run_pytest_with_coverage(cwd: str | Path, source: Sequence[str], args: Sequence[str] = (), timeout_s: float = 900.0,
                             python: Optional[str] = None, env_extra: Optional[dict] = None) -> Dict[str, Any]:
    """Run pytest under ``coverage`` (branch coverage) and return per-file executed and missing lines."""
    if not coverage_available(python):
        raise ToolMissing("the coverage package is not installed (it is in the `dev` extra: pip install -e '.[dev]')")
    py = python or sys.executable
    cwd = Path(cwd)
    with tempfile.TemporaryDirectory(prefix="qte-cov-") as tmp:
        data = Path(tmp) / ".coverage"
        env = dict(env_extra or {})
        env["COVERAGE_FILE"] = str(data)
        run = run_command([py, "-m", "coverage", "run", "--branch", f"--source={','.join(source)}", "-m", "pytest",
                           "-p", "no:cacheprovider", "-q", "--tb=short", *args], cwd, timeout_s, env)
        out_json = Path(tmp) / "cov.json"
        rep = run_command([py, "-m", "coverage", "json", "-o", str(out_json)], cwd, 120.0, env)
        files: Dict[str, Any] = {}
        totals: Dict[str, Any] = {}
        if out_json.is_file():
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            for name, d in payload.get("files", {}).items():
                files[name] = {"executed": d.get("executed_lines", []), "missing": d.get("missing_lines", []),
                               "percent": round(d.get("summary", {}).get("percent_covered", 0.0), 2)}
            totals = payload.get("totals", {})
    return {"returncode": run.returncode, "timed_out": run.timed_out, "files": files,
            "percent_covered": round(totals.get("percent_covered", 0.0), 2) if totals else None,
            "note": "line and branch coverage only shows what ran, not what was checked",
            "report_returncode": rep.returncode}
