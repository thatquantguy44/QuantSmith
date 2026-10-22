"""File intake checks carried over from the Dataset Intake Investigator POC.

Spec ``0121`` REQ-001 (POC AC-01). Behaviour is the POC's
``investigator.investigate``: CSV, TSV, or flat JSON; contract columns and
inferred types, business key, inclusive ranges, ISO date columns; malformed
rows, duplicate rows, IQR flags, future dates; status ``blocked``,
``review``, or ``passed_configured_checks``. Changes from the POC: the as-of
date is required (no wall-clock default), and the module is a pure function
used as the ``intake`` family of a research run. The POC's folder watcher is
not carried over (``0121`` non-goals).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import statistics
from datetime import date
from typing import Any

__all__ = [
    "MAX_BYTES",
    "MAX_COLUMNS",
    "MAX_ROWS",
    "NULLS",
    "investigate",
    "iso_date",
    "loader_source",
    "missing",
    "numeric",
    "parse",
    "profile",
]

NULLS = {"", "null", "none", "na", "n/a", "nan"}
MAX_ROWS = 50000
MAX_COLUMNS = 200
MAX_BYTES = 2_000_000


def missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip().lower() in NULLS)


def numeric(value: Any) -> float | None:
    if isinstance(value, bool) or missing(value):
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def iso_date(value: Any) -> date | None:
    """ISO calendar dates only; ambiguous regional dates are never guessed."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def parse(raw: bytes, suffix: str) -> tuple[list[str], list[dict[str, Any]], list[int]]:
    if len(raw) > MAX_BYTES:
        raise ValueError("File exceeds 2 MB limit")
    text = raw.decode("utf-8-sig")
    if suffix in {".csv", ".tsv"}:
        rows = csv.reader(io.StringIO(text, newline=""), delimiter="\t" if suffix == ".tsv" else ",")
        headers = next(rows, [])
        if not headers or any(not h.strip() for h in headers) or len(headers) != len(set(headers)):
            raise ValueError("Headers must be nonempty and unique")
        records: list[dict[str, Any]] = []
        malformed: list[int] = []
        for line, row in enumerate(rows, 2):
            if line - 1 > MAX_ROWS:
                raise ValueError("Row limit exceeded")
            if len(row) != len(headers):
                malformed.append(line)
            else:
                records.append(dict(zip(headers, row)))
    elif suffix == ".json":
        records = json.loads(text)
        if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
            raise ValueError("JSON must be an array of flat objects")
        if len(records) > MAX_ROWS:
            raise ValueError("Row limit exceeded")
        headers = list(dict.fromkeys(k for r in records for k in r))
        malformed = []
        if any(isinstance(v, (dict, list)) for r in records for v in r.values()):
            raise ValueError("Nested JSON is unsupported")
    else:
        raise ValueError("Supported formats: CSV, TSV, flat JSON array")
    if len(headers) > MAX_COLUMNS:
        raise ValueError("Column limit exceeded")
    return headers, records, malformed


def profile(headers: list[str], records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for h in headers:
        values = [r.get(h) for r in records]
        present = [v for v in values if not missing(v)]
        nums = [numeric(v) for v in present]
        dates = [iso_date(v) for v in present]
        kind = ("empty" if not present else "boolean" if all(isinstance(v, bool) for v in present)
                else "numeric" if all(v is not None for v in nums)
                else "iso_date" if all(v is not None for v in dates) else "text_or_mixed")
        item: dict[str, Any] = {"type": kind, "missing": len(values) - len(present),
                                    "distinct_nonmissing": len({json.dumps(v, sort_keys=True) for v in present})}
        if kind == "numeric":
            item.update(min=min(nums), max=max(nums), mean=statistics.mean(nums))
            if len(nums) >= 4:
                q1, _, q3 = statistics.quantiles(nums, n=4, method="inclusive")
                iqr = q3 - q1
                item["iqr_outlier_count"] = sum(v < q1 - 1.5 * iqr or v > q3 + 1.5 * iqr for v in nums)
                item["outlier_note"] = "Heuristic only; no values removed"
        output[h] = item
    return output


def investigate(name: str, raw: bytes, contract: dict[str, Any] | None, as_of: str) -> dict[str, Any]:
    """The POC intake investigation of one file's bytes (pure; no files written)."""
    contract = contract or {}
    as_of_d = date.fromisoformat(as_of)
    trace: list[str] = []
    findings: list[dict[str, str]] = []
    suffix = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    result: dict[str, Any] = {"file": name, "sha256": hashlib.sha256(raw).hexdigest(), "policy": "deterministic-v1",
                                  "as_of": as_of, "contract": contract, "trace": trace, "findings": findings}

    def flag(severity: str, check: str, detail: str) -> None:
        findings.append({"severity": severity, "check": check, "detail": detail})
    try:
        trace.append("parse_structure")
        headers, records, malformed = parse(raw, suffix)
        result.update(rows=len(records), columns=headers, malformed_row_numbers=malformed)
        if malformed:
            flag("blocker", "row_width", f"{len(malformed)} malformed rows excluded from profiling")
        if not records:
            flag("blocker", "empty_dataset", "No valid data rows")
        trace.append("profile_columns")
        profiles = profile(headers, records)
        result["profile"] = profiles
        duplicates = len(records) - len({json.dumps(r, sort_keys=True) for r in records})
        result["duplicate_rows"] = duplicates
        if duplicates:
            flag("warning", "duplicate_rows", f"{duplicates} repeated rows; business significance unknown")
        for h, item in profiles.items():
            if item["missing"]:
                flag("warning", "missing_values", f'{h}: {item["missing"]} missing')
            if item.get("iqr_outlier_count", 0):
                flag("warning", "numeric_outliers",
                     f'{h}: {item["iqr_outlier_count"]} IQR flags; investigate, do not auto-remove')
        trace.append("check_contract_and_grain")
        for h, kind in contract.get("columns", {}).items():
            if h not in profiles:
                flag("blocker", "required_column", f"Missing column: {h}")
            elif profiles[h]["type"] != kind:
                flag("blocker", "column_type", f'{h}: expected {kind}, observed {profiles[h]["type"]}')
        keys = contract.get("key", [])
        if keys:
            if any(h not in headers for h in keys):
                flag("blocker", "grain", "Configured key columns absent")
            else:
                missing_keys = sum(any(missing(r.get(h)) for h in keys) for r in records)
                identities = [json.dumps([r.get(h) for h in keys]) for r in records]
                repeated_keys = len(identities) - len(set(identities))
                result["grain"] = {"key": keys, "missing_key_rows": missing_keys, "repeated_key_rows": repeated_keys}
                if missing_keys or repeated_keys:
                    flag("blocker", "grain", f"{missing_keys} missing-key rows; {repeated_keys} repeated-key rows")
        else:
            result["candidate_single_column_keys"] = [h for h, p in profiles.items() if records and not p["missing"]
                                                      and p["distinct_nonmissing"] == len(records)]
            flag("warning", "grain_unconfirmed", "No business key configured; unique columns are candidates only")
        for h, limits in contract.get("ranges", {}).items():
            if h not in headers:
                flag("blocker", "range_column", f"Configured range column absent: {h}")
                continue
            invalid = out = 0
            for r in records:
                v = numeric(r.get(h))
                if v is None:
                    invalid += not missing(r.get(h))
                else:
                    out += ("min" in limits and v < limits["min"]) or ("max" in limits and v > limits["max"])
            if invalid or out:
                flag("blocker", "range", f"{h}: {invalid} nonnumeric values, {out} outside configured bounds")
        trace.append("investigate_dates")
        configured = contract.get("date_columns", [])
        date_cols = set(configured) | {h for h, p in profiles.items() if p["type"] == "iso_date"}
        result["dates"] = {}
        for h in sorted(date_cols):
            if h not in headers:
                flag("blocker", "date_column", f"Configured date column absent: {h}")
                continue
            parsed = [iso_date(r.get(h)) for r in records]
            invalid = sum(not missing(r.get(h)) and d is None for r, d in zip(records, parsed))
            valid = [d for d in parsed if d is not None]
            result["dates"][h] = {"invalid": invalid, "missing": sum(missing(r.get(h)) for r in records),
                                      "min": min(valid).isoformat() if valid else None,
                                      "max": max(valid).isoformat() if valid else None,
                                      "future_count": sum(d > as_of_d for d in valid)}
            if invalid:
                flag("blocker" if h in configured else "warning", "date_parse", f"{h}: {invalid} non-ISO dates")
            if any(d > as_of_d for d in valid):
                flag("warning", "future_dates", f"{h}: future calendar dates; may be valid scheduled events")
        trace.append("finish")
        result["status"] = ("blocked" if any(f["severity"] == "blocker" for f in findings)
                            else "review" if findings else "passed_configured_checks")
    except (ValueError, UnicodeError, csv.Error) as exc:
        flag("blocker", "parse_failure", str(exc))
        result["status"] = "blocked"
    return result


def loader_source(sha256: str, suffix: str) -> str:
    """The POC's generated loader: fixed code plus repr-encoded constants."""
    return ("from pathlib import Path\nimport hashlib\nfrom sfmeridian.research.intake import parse\n\n"
            f"EXPECTED_SHA256 = {sha256!r}\nSUFFIX = {suffix!r}\n\n"
            "def load_dataset(path):\n    raw = Path(path).read_bytes()\n"
            "    if hashlib.sha256(raw).hexdigest() != EXPECTED_SHA256:\n"
            "        raise ValueError(\"Input differs from investigated snapshot\")\n"
            "    headers, records, malformed = parse(raw, SUFFIX)\n"
            "    if malformed:\n        raise ValueError(\"Malformed rows: refusing silent data loss\")\n"
            "    return headers, records\n")
