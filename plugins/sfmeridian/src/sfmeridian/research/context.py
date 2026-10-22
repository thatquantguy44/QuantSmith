"""Research context: what a dataset-research run may assume, and nothing more.

Spec ``0121`` REQ-002. The context says what the dataset is for and what the
adopter knows about it — grain, time column, calendar, timezone, segments,
target, availability columns, column permissions, thresholds, budgets. It is
validated before any query runs. Missing context is never invented: checks
that need it are ``blocked`` or ``skipped`` with the reason.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

__all__ = ["BUDGET_DEFAULTS", "DATASET_KINDS", "ContextError", "ResearchContext", "parse_context"]

DATASET_KINDS = ("loan_book", "lendable_inventory", "borrow_rates", "collateral", "recalls",
                 "program_revenue", "generic")
VIEWPOINTS = ("lender", "beneficial_owner", "agent", "borrower")
FREQUENCIES = ("business_day", "daily", "weekly", "monthly")

#: Proposed starting points from the POC spec (§4) — not universal limits.
BUDGET_DEFAULTS: dict[str, Any] = {
    "max_steps": 60, "max_queries": 80, "max_rows_local": 5000, "max_local_bytes": 2_000_000,
    "max_columns": 200, "max_pairs": 50, "wall_time_seconds": 300, "model_token_limit": 20000,
    "max_groups": 400,
}
_KEYS = {"objective", "dataset_kind", "viewpoint", "business_grain", "grain_probe_columns", "time_column",
         "expected_frequency", "calendar_dates", "timezone", "segments", "target", "feature_availability",
         "exclude_columns", "allowed_analysis_columns", "sensitive_columns", "as_of", "thresholds",
         "column_map", "reference_profile", "budgets", "change_column"}
_THRESHOLDS = {"fee_band_bps", "category_thresholds_bps", "category_labels", "collateral_margin",
               "accrual_tolerance", "status_values", "materiality_missing_rate", "reference_shift",
               "strong_correlation"}
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ContextError(ValueError):
    def __init__(self, problems: Sequence[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = list(problems)


@dataclass(frozen=True)
class ResearchContext:
    objective: str
    dataset_kind: str
    as_of: str
    timezone: str | None
    viewpoint: str | None
    business_grain: tuple[str, ...]
    grain_probe_columns: tuple[str, ...]
    time_column: str | None
    expected_frequency: str | None
    calendar_dates: tuple[str, ...]
    segments: tuple[str, ...]
    target: dict[str, Any]
    feature_availability: dict[str, Any]
    exclude_columns: tuple[str, ...]
    allowed_analysis_columns: tuple[str, ...]
    sensitive_columns: tuple[str, ...]
    thresholds: dict[str, Any]
    column_map: dict[str, str]
    reference_profile: str | None
    change_column: str | None
    budgets: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    def column(self, logical: str) -> str:
        """Physical name of a logical column (rule packs use logical names)."""
        return self.column_map.get(logical, logical)


def _names(value: Any, key: str, problems: list[str]) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(v, str) and _NAME_RE.match(v) for v in value):
        problems.append(f"{key} must be a list of simple column names")
        return ()
    return tuple(value)


def parse_context(data: Mapping[str, Any], dataset_columns: Sequence[str]) -> ResearchContext:
    """Validate ``data`` against the dataset's declared columns; raise on any problem."""
    problems: list[str] = []
    unknown = set(data) - _KEYS
    if unknown:
        problems.append(f"unknown context keys: {', '.join(sorted(unknown))}")
    objective = data.get("objective")
    if not isinstance(objective, str) or not objective.strip():
        problems.append("objective is required")
    kind = data.get("dataset_kind", "generic")
    if kind not in DATASET_KINDS:
        problems.append(f"dataset_kind must be one of {', '.join(DATASET_KINDS)}")
    as_of = data.get("as_of")
    if not isinstance(as_of, str) or not _DATE_RE.match(as_of):
        problems.append("as_of (YYYY-MM-DD) is required: research never reads the wall clock")
    tz = data.get("timezone")
    if tz is not None:
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(tz)
        except Exception:  # noqa: BLE001 — any lookup failure means an unusable zone
            problems.append(f"timezone {tz!r} is not a known IANA zone")
    viewpoint = data.get("viewpoint")
    if viewpoint is not None and viewpoint not in VIEWPOINTS:
        problems.append(f"viewpoint must be one of {', '.join(VIEWPOINTS)}")
    freq = data.get("expected_frequency")
    if freq is not None and freq not in FREQUENCIES:
        problems.append(f"expected_frequency must be one of {', '.join(FREQUENCIES)}")
    calendar = data.get("calendar_dates") or []
    if not isinstance(calendar, list) or not all(isinstance(d, str) and _DATE_RE.match(d) for d in calendar):
        problems.append("calendar_dates must be a list of ISO dates")
        calendar = []

    grain = _names(data.get("business_grain"), "business_grain", problems)
    probe = _names(data.get("grain_probe_columns"), "grain_probe_columns", problems)
    segments = _names(data.get("segments"), "segments", problems)
    exclude = _names(data.get("exclude_columns"), "exclude_columns", problems)
    sensitive = _names(data.get("sensitive_columns"), "sensitive_columns", problems)
    allowed = _names(data.get("allowed_analysis_columns"), "allowed_analysis_columns", problems)
    time_column = data.get("time_column")
    change_column = data.get("change_column")

    column_map = data.get("column_map") or {}
    if not isinstance(column_map, dict) or not all(isinstance(k, str) and isinstance(v, str) and _NAME_RE.match(v)
                                                   for k, v in column_map.items()):
        problems.append("column_map maps logical names to simple column names")
        column_map = {}
    thresholds = data.get("thresholds") or {}
    if not isinstance(thresholds, dict):
        problems.append("thresholds must be a mapping")
        thresholds = {}
    for key in set(thresholds) - _THRESHOLDS:
        problems.append(f"unknown threshold {key!r}")
    target = data.get("target") or {}
    availability = data.get("feature_availability") or {}
    for name, block, keys in (("target", target, {"column", "prediction_horizon", "available_at_column"}),
                              ("feature_availability", availability,
                               {"event_time_column", "available_at_column", "naive_timezone"})):
        if not isinstance(block, dict) or set(block) - keys:
            problems.append(f"{name} accepts only {', '.join(sorted(keys))}")
    budgets = dict(BUDGET_DEFAULTS)
    given = data.get("budgets") or {}
    if not isinstance(given, dict):
        problems.append("budgets must be a mapping")
        given = {}
    for key, value in given.items():
        if key not in BUDGET_DEFAULTS:
            problems.append(f"unknown budget {key!r}")
        elif not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            problems.append(f"budget {key} must be positive")
        else:
            budgets[key] = value

    columns = set(dataset_columns)
    referenced: dict[str, Sequence[str]] = {
        "business_grain": grain, "grain_probe_columns": probe, "segments": segments,
        "exclude_columns": exclude, "sensitive_columns": sensitive, "allowed_analysis_columns": allowed,
        "time_column": [time_column] if time_column else [], "change_column": [change_column] if change_column else [],
        "target.column": [target.get("column")] if isinstance(target, dict) and target.get("column") else [],
        "target.available_at_column": [target["available_at_column"]]
        if isinstance(target, dict) and target.get("available_at_column") else [],
        "feature_availability": [v for k, v in (availability.items() if isinstance(availability, dict) else [])
                                 if k.endswith("_column") and v],
    }
    for key, names in referenced.items():
        for name in names:
            if name not in columns:
                problems.append(f"{key} names {name!r}, which is not a declared dataset column")
    # Contradictions: excluded or sensitive columns cannot be keys, segments, or analysis columns.
    blocked_cols = set(exclude)
    for key in ("business_grain", "segments", "allowed_analysis_columns", "time_column", "target.column"):
        clash = blocked_cols.intersection(referenced[key])
        if clash:
            problems.append(f"{key} uses excluded column(s) {', '.join(sorted(clash))}")
    clash = set(sensitive).intersection(segments) | set(sensitive).intersection(allowed)
    if clash:
        problems.append(f"sensitive column(s) {', '.join(sorted(clash))} cannot be segments or analysis columns")
    if problems:
        raise ContextError(problems)
    return ResearchContext(
        objective=objective.strip(), dataset_kind=kind, as_of=as_of, timezone=tz, viewpoint=viewpoint,
        business_grain=grain, grain_probe_columns=probe, time_column=time_column, expected_frequency=freq,
        calendar_dates=tuple(sorted(calendar)), segments=segments, target=dict(target),
        feature_availability=dict(availability), exclude_columns=exclude, allowed_analysis_columns=allowed,
        sensitive_columns=sensitive, thresholds=dict(thresholds), column_map=dict(column_map),
        reference_profile=data.get("reference_profile"), change_column=change_column, budgets=budgets,
        raw=dict(data))
