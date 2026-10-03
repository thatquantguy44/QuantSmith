"""Narrative and grounding. Spec ``0080`` (REQ-008).

A narrative — whether the deterministic template below or a later LLM
narrator — is only ever as trustworthy as the numbers in it: :func:`ground`
checks every number the text states against the numbers the insight set
actually computed, and rejects the first one it cannot find (RISK-002).
Causal wording ("because", "caused by", …) is flagged separately: a
contributor insight is a decomposition, not a cause (RISK-007).

Standard library only.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from .execute import Result
from .insights import Insight

_NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?%?")

# Decomposition wording ("drove", "contributed") is deliberately not here —
# RISK-007 treats a contributor insight as a decomposition, not a cause.
_CAUSAL_PHRASES = ("because", "caused by", "causes", "due to", "leads to", "led to",
                  "results in", "resulted in", "results from", "resulted from")

_TOLERANCE_ABS = 0.05
_TOLERANCE_REL = 1e-3


@dataclass(frozen=True)
class GroundingReport:
    """The result of checking a narrative against an insight set (REQ-008)."""

    ok: bool
    unbacked_numbers: Tuple[str, ...]
    causal_flags: Tuple[str, ...]


def template_narrative(insights: Sequence[Insight]) -> str:
    """The deterministic default narrative: every insight's statement, in order."""
    return " ".join(i.statement for i in insights)


def _flatten_numbers(value: object, out: set) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        out.add(float(value))
        out.add(float(value) * 100)  # any ratio may be written as a percent (a >100% move included)
    elif isinstance(value, dict):
        for v in value.values():
            _flatten_numbers(v, out)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _flatten_numbers(v, out)


def _allowed_numbers(insights: Sequence[Insight], result: Optional[Result]) -> set:
    allowed: set = set()
    for insight in insights:
        _flatten_numbers(insight.values, allowed)
    if result is not None:
        _flatten_numbers(result.values, allowed)
        _flatten_numbers(list(result.series.keys()), allowed)
        allowed.add(float(result.row_count))
        allowed.add(float(result.as_of))
        if result.latest_period is not None:
            allowed.add(float(result.latest_period))
    return allowed


def _parse_token(token: str) -> float:
    cleaned = token.replace(",", "")
    if cleaned.endswith("%"):
        return float(cleaned[:-1])
    return float(cleaned)


def _is_backed(value: float, allowed: set) -> bool:
    return any(
        abs(value - a) <= max(_TOLERANCE_ABS, abs(a) * _TOLERANCE_REL)
        for a in allowed
    )


def ground(narrative: str, insights: Sequence[Insight], result: Optional[Result] = None) -> GroundingReport:
    """Check ``narrative`` number by number against ``insights`` (and ``result``).

    A number in the text with no backing value anywhere in the insight set
    (within a small rounding tolerance) is unbacked (AC-010). Causal phrases
    are reported but do not by themselves make the report ``ok is False`` —
    callers decide whether a causal flag blocks delivery.
    """
    allowed = _allowed_numbers(insights, result)
    unbacked = []
    for token in _NUMBER_RE.findall(narrative):
        try:
            value = _parse_token(token)
        except ValueError:
            continue
        if not _is_backed(value, allowed):
            unbacked.append(token)

    lowered = narrative.lower()
    causal = tuple(p for p in _CAUSAL_PHRASES if p in lowered)

    return GroundingReport(ok=not unbacked, unbacked_numbers=tuple(unbacked), causal_flags=causal)


# ---------------------------------------------------------------------------
# Caveats (REQ-008, AC-011)
# ---------------------------------------------------------------------------


def default_caveats(
    result: Result,
    *,
    synthetic: bool = False,
    min_sample_rows: int = 10,
    staleness_periods: int = 2,
) -> Tuple[str, ...]:
    """Caveats triggered by the data behind a result, not by its content."""
    caveats = []
    if synthetic:
        caveats.append("This data is synthetic and for demonstration only (see spec 0025).")
    if result.row_count < min_sample_rows:
        caveats.append(f"Small sample: only {result.row_count} row(s) behind this answer.")
    if result.latest_period is not None and (result.as_of - result.latest_period) > staleness_periods:
        caveats.append(
            f"Data may be stale: the latest observed period is {result.latest_period}, "
            f"asked as of {result.as_of}."
        )
    periods = sorted(result.series)
    if len(periods) >= 2:
        counts = [len(result.series[p]) for p in periods]
        if counts[-1] < statistics.median(counts[:-1]):
            caveats.append("The most recent period may be partial (fewer rows than earlier periods).")
    return tuple(caveats)
