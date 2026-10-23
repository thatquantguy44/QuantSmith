"""Deterministic workload counters for spec 0116 hardening evidence.

The report is deliberately passive: callers supply observations from a frozen
workload, and this module computes the acceptance counters without touching a
database or clock.  Database time must be excluded by the caller before
``overhead_ms`` is supplied.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

__all__ = ["AssuranceReport", "assess_workload"]


@dataclass(frozen=True)
class AssuranceReport:
    repetitions: int
    deterministic_matches: int
    adversarial_candidates: int
    verifier_rejections: int
    rejection_by_code: Mapping[str, int]
    rejection_rate: float
    executed_queries: int
    identifier_fabrications_executed: int
    overhead_samples_ms: tuple[float, ...]
    overhead_p95_ms: float
    timeout_s: int
    max_repairs: int
    explain_cost_limit: float | None
    observed_explain_cost: float | None
    findings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.findings

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["rejection_by_code"] = dict(sorted(self.rejection_by_code.items()))
        value["overhead_samples_ms"] = list(self.overhead_samples_ms)
        value["findings"] = list(self.findings)
        value["ok"] = self.ok
        return value


def assess_workload(
    *,
    repetitions: int,
    deterministic_matches: int,
    adversarial_candidates: int,
    rejection_by_code: Mapping[str, int],
    executed_queries: int,
    identifier_fabrications_executed: int,
    overhead_ms: Sequence[float],
    timeout_s: int,
    max_repairs: int,
    explain_cost_limit: float | None,
    observed_explain_cost: float | None,
    overhead_limit_ms: float = 15_000,
) -> AssuranceReport:
    """Summarize and gate one frozen synthetic workload."""
    rejected = sum(rejection_by_code.values())
    samples = tuple(float(value) for value in overhead_ms)
    p95 = _percentile(samples, 0.95)
    findings: list[str] = []
    if repetitions < 1 or deterministic_matches != repetitions:
        findings.append("repeated outputs were not deterministic")
    if adversarial_candidates < 1 or rejected != adversarial_candidates:
        findings.append("adversarial verifier rejection rate was below 100%")
    if identifier_fabrications_executed != 0:
        findings.append("an executed query contained a fabricated identifier")
    if not samples or any(value < 0 for value in samples) or p95 > overhead_limit_ms:
        findings.append(f"plugin overhead p95 exceeded {overhead_limit_ms:g} ms or was not recorded")
    if timeout_s < 1:
        findings.append("timeout control was not recorded")
    if max_repairs not in (0, 1, 2):
        findings.append("maximum repair control is outside the approved bound")
    if (explain_cost_limit is not None
            and (observed_explain_cost is None or observed_explain_cost > explain_cost_limit)):
        findings.append("observed EXPLAIN cost is absent or exceeds the configured limit")
    for name, value in {
        "adversarial_candidates": adversarial_candidates,
        "executed_queries": executed_queries,
        "identifier_fabrications_executed": identifier_fabrications_executed,
    }.items():
        if value < 0:
            findings.append(f"{name} cannot be negative")
    rate = rejected / adversarial_candidates if adversarial_candidates > 0 else 0.0
    return AssuranceReport(
        repetitions=repetitions,
        deterministic_matches=deterministic_matches,
        adversarial_candidates=adversarial_candidates,
        verifier_rejections=rejected,
        rejection_by_code=dict(rejection_by_code),
        rejection_rate=rate,
        executed_queries=executed_queries,
        identifier_fabrications_executed=identifier_fabrications_executed,
        overhead_samples_ms=samples,
        overhead_p95_ms=p95,
        timeout_s=timeout_s,
        max_repairs=max_repairs,
        explain_cost_limit=explain_cost_limit,
        observed_explain_cost=observed_explain_cost,
        findings=tuple(findings),
    )


def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]
