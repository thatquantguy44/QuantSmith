"""Evidence registry, coverage ledger, findings, and the research session.

Spec ``0121`` REQ-009 (POC AC-02, AC-05). Every number a run reports lives in
an evidence record with a deterministic ID; every finding and recommendation
cites evidence IDs; every applicable analysis family has a ledger entry.
Timing fields are kept out of evidence so frozen inputs reproduce evidence
IDs and artifact hashes exactly.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

__all__ = ["FAMILIES", "STATUSES", "CoverageLedger", "EvidenceRegistry", "Finding", "ResearchSession"]

#: Analysis families, in the order the policy works through them (POC §3).
FAMILIES = ("intake", "schema", "univariate", "duplicates_grain", "missingness", "temporal", "domain_rules",
            "numeric", "categorical", "relationships", "segments", "target", "availability", "reference",
            "charts", "recommendations")
STATUSES = ("pending", "completed", "blocked", "skipped", "budget_exhausted")
_VOLATILE = ("elapsed_seconds",)


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def _strip(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip(v) for k, v in value.items() if k not in _VOLATILE}
    if isinstance(value, list):
        return [_strip(v) for v in value]
    return value


class EvidenceRegistry:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}

    def add(self, tool: str, *, summary: str, value: dict[str, Any], scope: str, method: str,
            provenance: Sequence[dict[str, Any]] = (), denominator: Any | None = None,
            exclusions: str | None = None, warnings: Sequence[str] = ()) -> str:
        body = {"tool": tool, "summary": summary, "value": value, "scope": scope, "method": method,
                "denominator": denominator, "exclusions": exclusions, "warnings": list(warnings),
                "queries": [_strip(p) for p in provenance]}
        evidence_id = "E-" + hashlib.sha256(canonical(body).encode()).hexdigest()[:10]
        self.records[evidence_id] = {"evidence_id": evidence_id, **body}
        return evidence_id

    def get(self, evidence_id: str) -> dict[str, Any]:
        return self.records[evidence_id]

    def as_list(self) -> list[dict[str, Any]]:
        return [self.records[k] for k in sorted(self.records)]


class CoverageLedger:
    def __init__(self) -> None:
        self.entries: dict[str, dict[str, Any]] = {f: {"family": f, "status": "pending", "reason": None,
                                                       "evidence_ids": []} for f in FAMILIES}

    def set(self, family: str, status: str, reason: str | None = None, evidence_ids: Sequence[str] = ()) -> None:
        if family not in self.entries or status not in STATUSES:
            raise ValueError(f"bad coverage entry {family}/{status}")
        entry = self.entries[family]
        # A family that already completed is not downgraded by a later follow-up.
        if entry["status"] == "completed" and status != "completed":
            entry["evidence_ids"] = sorted(set(entry["evidence_ids"]) | set(evidence_ids))
            return
        entry.update(status=status, reason=reason)
        entry["evidence_ids"] = sorted(set(entry["evidence_ids"]) | set(evidence_ids))

    def pending(self) -> list[str]:
        return [f for f, e in self.entries.items() if e["status"] == "pending"]

    def close(self, stop_reason: str) -> None:
        """At the end of a run every pending family gets an honest status."""
        for family in self.pending():
            if stop_reason == "budget_exhausted":
                self.set(family, "budget_exhausted", "the run stopped at a budget before this family ran")
            else:
                self.set(family, "skipped", f"not reached (stop reason: {stop_reason})")

    def as_list(self) -> list[dict[str, Any]]:
        return [self.entries[f] for f in FAMILIES]


@dataclass
class Finding:
    finding_id: str
    family: str
    kind: str
    severity: str                    # blocker | material | exploratory | limitation
    observation: str
    evidence_ids: list[str]
    scope: str
    counts: dict[str, Any] = field(default_factory=dict)
    hypothesis: str | None = None
    columns: list[str] = field(default_factory=list)
    follow_up: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"finding_id": self.finding_id, "family": self.family, "kind": self.kind, "severity": self.severity,
                "observation": self.observation, "hypothesis": self.hypothesis, "evidence_ids": self.evidence_ids,
                "scope": self.scope, "counts": self.counts, "columns": self.columns, "follow_up": self.follow_up}


class ResearchSession:
    """Run-scoped state shared by the ``research.*`` tools through the tool context."""

    def __init__(self, *, dataset: Any, context: Any, executor: Any, budget: Any, config_hash: str) -> None:
        self.dataset = dataset
        self.context = context
        self.executor = executor
        self.budget = budget
        self.config_hash = config_hash
        self.evidence = EvidenceRegistry()
        self.ledger = CoverageLedger()
        self.findings: list[Finding] = []
        self.facts: dict[str, Any] = {}       # tool results later tools and the policy consult
        self.charts: list[dict[str, Any]] = []
        self.recommendations: list[dict[str, Any]] = []
        self.limitations: list[str] = []
        self.tool_calls: list[dict[str, Any]] = []
        self.stop_reason: str | None = None
        self.bundle_dir: str | None = None

    def add_finding(self, **kw: Any) -> Finding:
        f = Finding(finding_id=f"F-{len(self.findings) + 1:03d}", **kw)
        self.findings.append(f)
        return f

    def limitation(self, text: str) -> None:
        if text not in self.limitations:
            self.limitations.append(text)
