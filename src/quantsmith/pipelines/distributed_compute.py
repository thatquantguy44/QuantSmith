"""Reference runtime for spec 0112 — distributed compute planning and determinism.

Shared by the ``tooling/spark`` and ``tooling/ray_dask`` agents. Three problems
recur in distributed quant workloads (Spark, Dask, Ray Data):

1. **Partition sizing.** Too few partitions spill to disk and stall; too many drown
   the scheduler in tiny tasks. ``plan_partitions`` sizes from bytes and a target.
2. **Skew.** One hot key (a mega-cap ticker, a default account, a null) lands in
   one partition and the whole job waits on it. Repartitioning cannot split a
   single key; salting can. ``skew_report`` finds partition imbalance and the keys
   no repartition can fix; ``salting_plan`` sizes per-key salt factors and shows
   the balance they buy.
3. **Determinism.** Results that depend on partitioning or task order make a
   backtest irreproducible. ``lint_determinism`` flags the usual culprits in
   PySpark and Dask code. It is a line-based heuristic: it reports suspects for a
   human to confirm, and cannot see ordering established elsewhere.

Partition assignment uses SHA-256 of the key, not the engine's hash (Spark uses
Murmur3); balance statistics are representative, exact partition ids are not.

Guarantees held by construction:

* REQ-005 / AC-005 — partition counts honor the target size and bounds; skew is
  measured as max/median partition load and every key larger than a fair
  partition share is reported as needing salting.
* REQ-006 / AC-006 — a salting plan never raises the max partition load, splits
  each hot key into enough salts to fit a fair share, and is deterministic.
* REQ-007 / AC-007 — the lint reports line, rule, and reason for every match, and
  suppresses a match when the same line shows the fix (seed, orderBy).
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

MiB = 1024 * 1024


def plan_partitions(total_bytes: int, target_bytes: int = 128 * MiB,
                    min_partitions: int = 1, max_partitions: Optional[int] = None) -> int:
    """Partitions needed so each holds about ``target_bytes`` (bounded)."""
    if total_bytes < 0 or target_bytes <= 0 or min_partitions < 1:
        raise ValueError("total_bytes >= 0, target_bytes > 0, min_partitions >= 1")
    n = max(min_partitions, math.ceil(total_bytes / target_bytes))
    if max_partitions is not None:
        if max_partitions < min_partitions:
            raise ValueError("max_partitions < min_partitions")
        n = min(n, max_partitions)
    return n


def partition_of(key: str, n: int) -> int:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % n


def _median(xs: Sequence[float]) -> float:
    s = sorted(xs)
    m = len(s) // 2
    return float(s[m]) if len(s) % 2 else (s[m - 1] + s[m]) / 2.0


@dataclass(frozen=True)
class SkewReport:
    loads: Tuple[int, ...]
    max_load: int
    median_load: float
    skew_ratio: float  # max / median (inf if median is 0 and max > 0)
    hot_keys: Tuple[Tuple[str, int], ...]  # keys larger than a fair partition share

    @property
    def skewed(self) -> bool:
        return bool(self.hot_keys) or self.skew_ratio > 2.0


def _loads(counts: Mapping[str, int], n: int) -> List[int]:
    loads = [0] * n
    for k, c in counts.items():
        loads[partition_of(k, n)] += c
    return loads


def skew_report(key_counts: Mapping[str, int], n_partitions: int) -> SkewReport:
    if n_partitions < 1:
        raise ValueError("n_partitions must be >= 1")
    if any(c < 0 for c in key_counts.values()):
        raise ValueError("key counts must be non-negative")
    loads = _loads(key_counts, n_partitions)
    total = sum(loads)
    fair = total / n_partitions if n_partitions else 0
    med = _median(loads)
    mx = max(loads) if loads else 0
    ratio = (mx / med) if med else (math.inf if mx else 1.0)
    hot = tuple(sorted(((k, c) for k, c in key_counts.items() if fair and c > fair),
                       key=lambda kc: (-kc[1], kc[0])))
    return SkewReport(tuple(loads), mx, med, ratio, hot)


@dataclass(frozen=True)
class SaltingPlan:
    factors: Dict[str, int]  # hot key -> number of salts
    before: SkewReport
    after: SkewReport


def salting_plan(key_counts: Mapping[str, int], n_partitions: int) -> SaltingPlan:
    """Split each hot key into ``ceil(count / fair_share)`` salted sub-keys.

    Salted sub-keys are ``"<key>#<i>"`` with the count divided evenly; the join or
    aggregation side must replicate (join) or re-aggregate (group-by) accordingly.
    """
    before = skew_report(key_counts, n_partitions)
    total = sum(key_counts.values())
    fair = total / n_partitions if n_partitions else 0
    factors: Dict[str, int] = {}
    salted: Dict[str, int] = {}
    for k, c in key_counts.items():
        if fair and c > fair:
            f = min(n_partitions, math.ceil(c / fair))
            factors[k] = f
            base, extra = divmod(c, f)
            for i in range(f):
                salted[f"{k}#{i}"] = base + (1 if i < extra else 0)
        else:
            salted[k] = c
    after = skew_report(salted, n_partitions)
    if after.max_load > before.max_load:  # never make it worse
        return SaltingPlan({}, before, before)
    return SaltingPlan(dict(sorted(factors.items())), before, after)


# ---------------------------------------------------------------------------
# Determinism lint — REQ-007
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LintFinding:
    line: int
    rule: str
    message: str
    code: str


# (rule, pattern, message, suppressed-if-line-matches)
RULES: Tuple[Tuple[str, str, str, Optional[str]], ...] = (
    ("monotonic_id", r"monotonically_increasing_id\s*\(",
     "ids depend on partitioning; use a deterministic key or row_number over a total order",
     None),
    ("unseeded_random", r"\b(rand|randn)\s*\(\s*\)",
     "random column without a seed", None),
    ("unseeded_sample", r"\.sample\s*\(",
     "sample without a seed", r"seed\s*=|random_state\s*="),
    ("window_without_order", r"Window\s*\.\s*partitionBy\s*\(",
     "window without orderBy: row_number/first/lag results are arbitrary", r"orderBy"),
    ("order_dependent_agg", r"\b(first|last)\s*\(",
     "first/last depend on row order unless the input is totally ordered", r"orderBy|sort"),
    ("collect_order", r"\bcollect_(list|set)\s*\(",
     "collect_list/collect_set order is not guaranteed; sort the result (array_sort)",
     r"array_sort|sort_array"),
    ("dedup_arbitrary_row", r"\.(dropDuplicates|drop_duplicates)\s*\(",
     "which duplicate survives is partition-dependent; dedup with an ordered window",
     None),
    ("limit_without_order", r"\.limit\s*\(",
     "limit without orderBy returns arbitrary rows", r"orderBy|sort"),
    ("wall_clock", (r"current_timestamp\s*\(|current_date\s*\(|datetime\.now\s*\(|"
                    r"date\.today\s*\(|pd\.Timestamp\.now\s*\("),
     "reads the wall clock; pass the as-of time as a parameter", None),
)


def lint_determinism(code: str) -> List[LintFinding]:
    """Flag partition- or order-dependent constructs, line by line."""
    out: List[LintFinding] = []
    for i, line in enumerate(code.splitlines(), start=1):
        stripped = line.split("#", 1)[0]
        for rule, pattern, message, fix in RULES:
            if re.search(pattern, stripped) and not (fix and re.search(fix, stripped)):
                out.append(LintFinding(i, rule, message, line.strip()))
    return out
