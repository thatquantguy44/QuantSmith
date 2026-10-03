"""JUnit and GoogleTest XML parsing (pytest, CTest, GoogleTest, Catch2/doctest JUnit reporters).

The parser reads test output written by the user's own test tools. It uses the standard library
``xml.etree`` (which does not resolve external entities) and refuses input over ``MAX_BYTES`` so a
hostile or runaway file cannot exhaust memory.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import List

from .report import ERROR, FAILED, PASSED, SKIPPED, TestResult

MAX_BYTES = 20 * 1024 * 1024


def parse_junit(xml_text: str) -> List[TestResult]:
    """Parse JUnit/xUnit/GoogleTest-style XML into results (document order)."""
    if len(xml_text.encode("utf-8", "ignore")) > MAX_BYTES:
        raise ValueError(f"XML report exceeds {MAX_BYTES} bytes; refusing to parse")
    if not xml_text.strip():
        return []
    root = ET.fromstring(xml_text)
    out: List[TestResult] = []
    for case in root.iter("testcase"):
        cls, name = case.get("classname") or "", case.get("name") or ""
        ident = f"{cls}::{name}" if cls else name
        try:
            duration = float(case.get("time") or 0.0)
        except ValueError:
            duration = 0.0
        status, message = PASSED, ""
        failure, error, skipped = case.find("failure"), case.find("error"), case.find("skipped")
        if error is not None:
            status, message = ERROR, (error.get("message") or (error.text or "")).strip()
        elif failure is not None:
            status, message = FAILED, (failure.get("message") or (failure.text or "")).strip()
        elif skipped is not None:
            status, message = SKIPPED, (skipped.get("message") or "").strip()
        elif case.get("status") in ("notrun", "disabled") or case.get("result") in ("skipped", "suppressed"):
            status = SKIPPED
        elif case.get("status") == "fail":                      # CTest's attribute form
            status = FAILED
        out.append(TestResult(id=ident, status=status, duration_s=duration, message=message[:2000],
                              file=case.get("file") or ""))
    return out
