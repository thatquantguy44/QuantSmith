"""Reference runtime for spec 0101 — concurrent pipeline fleet.

``0011`` runs *one* pipeline correctly. This module runs *hundreds* of them at once
without overrunning the shared things they compete for: warehouse connections,
vendor API rate limits, cluster slots, and the sink tables two pipelines must never
write at the same time. It is standard-library only and has three surfaces that
share one admission policy, so the plan, the run, and the exported orchestrator
config cannot disagree:

* ``simulate`` — a deterministic capacity plan (makespan, queue wait, per-pool
  utilization, and which limit is the bottleneck) from estimated durations.
* ``run_fleet`` — real concurrent execution on a thread pool, admitted under the same
  limits, with bounded retries and dependent isolation.
* ``to_dagster`` / ``to_mage`` — the same limits rendered as Dagster and Mage
  concurrency configuration, with every lossy mapping reported, never dropped.

Guarantees held by construction:

* REQ-001 / AC-001 — a fleet is validated at construction: unique names, known
  dependencies, no cycles, declared pools, and slot demands that fit their pool (a
  job that could never be admitted is rejected, not left to hang).
* REQ-002 / NFR-001 / AC-002 — admission is all-or-nothing against the global limit,
  every pool the job needs, and its mutual-exclusion key. No hold-and-wait, so no
  deadlock; in-use never exceeds a limit.
* REQ-003 / AC-003 — ready jobs are ordered by priority then submission order; a job
  overtaken ``max_bypass`` times jumps the queue and blocks later jobs until it
  is admitted (no starvation).
* REQ-004 / AC-004 — retries are bounded and re-enter admission, so a retry storm
  cannot exceed a limit; a permanent failure marks its transitive dependents
  ``upstream_failed`` and leaves unrelated pipelines running.
* REQ-005 / NFR-002 / AC-005 — ``simulate`` is deterministic and attributes queue wait
  to the constraint that caused it.
* REQ-006 / AC-006 — ``stagger_offsets`` spreads start times deterministically so
  hundreds of schedules do not fire on the same second.
* REQ-007 / NFR-003 / AC-007 — exporters emit Dagster and Mage config plus an explicit
  ``warnings`` list for anything the target cannot enforce natively.
"""

from __future__ import annotations

import hashlib
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple

JobFn = Callable[[], object]

STATUS_OK = "ok"
STATUS_FAILED = "failed"
STATUS_UPSTREAM_FAILED = "upstream_failed"

# Tag namespace used when limits are rendered as orchestrator run tags.
TAG_PREFIX = "quantsmith"


# ---------------------------------------------------------------------------
# Declarations — REQ-001
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Pool:
    """A named, shared capacity: e.g. ``warehouse`` (8 connections)."""

    name: str
    limit: int


@dataclass(frozen=True)
class FleetJob:
    """One pipeline run in the fleet.

    ``pools`` maps pool name to the slots this job holds while it runs.
    ``concurrency_key`` is a mutual-exclusion key (typically the sink table or
    ``table:partition``): two jobs sharing a key never run at the same time.
    ``est_seconds`` is used only by ``simulate``.
    """

    name: str
    fn: Optional[JobFn] = None
    deps: Tuple[str, ...] = ()
    pools: Mapping[str, int] = field(default_factory=dict)
    concurrency_key: Optional[str] = None
    priority: int = 0
    max_attempts: int = 1
    est_seconds: float = 1.0
    owner: str = ""


@dataclass(frozen=True)
class FleetConfig:
    max_concurrent: int
    pools: Tuple[Pool, ...] = ()
    max_bypass: int = 50


class Fleet:
    """A validated set of jobs plus the limits they run under."""

    def __init__(self, jobs: Sequence[FleetJob], config: FleetConfig) -> None:
        if config.max_concurrent < 1:
            raise ValueError("max_concurrent must be >= 1")
        if config.max_bypass < 1:
            raise ValueError("max_bypass must be >= 1")
        self.config = config
        self.pools: Dict[str, Pool] = {}
        for p in config.pools:
            if p.name in self.pools:
                raise ValueError(f"duplicate pool '{p.name}'")
            if p.limit < 1:
                raise ValueError(f"pool '{p.name}' limit must be >= 1")
            self.pools[p.name] = p

        self.jobs: Dict[str, FleetJob] = {}
        self.index: Dict[str, int] = {}
        for i, job in enumerate(jobs):
            if job.name in self.jobs:
                raise ValueError(f"duplicate job '{job.name}'")
            if job.max_attempts < 1:
                raise ValueError(f"job '{job.name}' max_attempts must be >= 1")
            if job.est_seconds <= 0:
                raise ValueError(f"job '{job.name}' est_seconds must be > 0")
            for pool, slots in job.pools.items():
                if pool not in self.pools:
                    raise ValueError(f"job '{job.name}' uses undeclared pool '{pool}'")
                if not 1 <= slots <= self.pools[pool].limit:
                    raise ValueError(
                        f"job '{job.name}' needs {slots} slot(s) of pool '{pool}' "
                        f"(limit {self.pools[pool].limit}); it could never be admitted"
                    )
            self.jobs[job.name] = job
            self.index[job.name] = i
        for job in self.jobs.values():
            for d in job.deps:
                if d not in self.jobs:
                    raise ValueError(f"job '{job.name}' depends on unknown job '{d}'")
        self.order = self._toposort()
        self.dependents: Dict[str, List[str]] = {n: [] for n in self.jobs}
        for job in self.jobs.values():
            for d in job.deps:
                self.dependents[d].append(job.name)

    def _toposort(self) -> List[str]:
        indegree = {n: len(j.deps) for n, j in self.jobs.items()}
        ready = sorted((n for n, d in indegree.items() if d == 0), key=self.index.get)
        children: Dict[str, List[str]] = {n: [] for n in self.jobs}
        for job in self.jobs.values():
            for d in job.deps:
                children[d].append(job.name)
        order: List[str] = []
        while ready:
            n = ready.pop(0)
            order.append(n)
            for m in children[n]:
                indegree[m] -= 1
                if indegree[m] == 0:
                    ready.append(m)
            ready.sort(key=self.index.get)
        if len(order) != len(self.jobs):
            raise ValueError("fleet has a dependency cycle")
        return order

    def sort_key(self, name: str) -> Tuple[int, int]:
        return (-self.jobs[name].priority, self.index[name])


# ---------------------------------------------------------------------------
# Admission — REQ-002 / REQ-003 (shared by simulate and run_fleet)
# ---------------------------------------------------------------------------


class _Admission:
    """All-or-nothing slot accounting. Never holds a partial reservation."""

    def __init__(self, fleet: Fleet) -> None:
        self.fleet = fleet
        self.running = 0
        self.in_use: Dict[str, int] = {p: 0 for p in fleet.pools}
        self.keys: Set[str] = set()
        self.peak_running = 0
        self.peak_pools: Dict[str, int] = {p: 0 for p in fleet.pools}

    def blocker(self, job: FleetJob) -> Optional[str]:
        """The first constraint preventing admission, or ``None`` if it fits."""
        if self.running >= self.fleet.config.max_concurrent:
            return "global"
        for pool, slots in sorted(job.pools.items()):
            if self.in_use[pool] + slots > self.fleet.pools[pool].limit:
                return f"pool:{pool}"
        if job.concurrency_key is not None and job.concurrency_key in self.keys:
            return f"key:{job.concurrency_key}"
        return None

    def acquire(self, job: FleetJob) -> None:
        self.running += 1
        self.peak_running = max(self.peak_running, self.running)
        for pool, slots in job.pools.items():
            self.in_use[pool] += slots
            self.peak_pools[pool] = max(self.peak_pools[pool], self.in_use[pool])
        if job.concurrency_key is not None:
            self.keys.add(job.concurrency_key)

    def release(self, job: FleetJob) -> None:
        self.running -= 1
        for pool, slots in job.pools.items():
            self.in_use[pool] -= slots
        if job.concurrency_key is not None:
            self.keys.discard(job.concurrency_key)


def _select(
    fleet: Fleet, adm: _Admission, ready: List[str], bypassed: Dict[str, int]
) -> Tuple[List[str], Dict[str, str]]:
    """Pick the ready jobs to admit now, in order; return them and the blockers.

    Jobs that do not fit are skipped so later jobs can use idle capacity, and each
    skipped job counts how often it is overtaken that way. A job overtaken
    ``max_bypass`` times is *starved*: it moves to the front of the order and,
    while it still does not fit, nothing behind it is admitted, so capacity drains
    toward it (aging guard against starvation by smaller jobs).
    """
    limit = fleet.config.max_bypass

    def key(name: str) -> Tuple[bool, int, int]:
        return (bypassed.get(name, 0) < limit,) + fleet.sort_key(name)

    admitted: List[str] = []
    blocked: Dict[str, str] = {}
    for name in sorted(ready, key=key):
        job = fleet.jobs[name]
        reason = adm.blocker(job)
        if reason is not None:
            blocked[name] = reason
            if reason == "global" or bypassed.get(name, 0) >= limit:
                break  # nothing else may fit / starved job reserves capacity
            continue
        if any(bypassed.get(w, 0) >= limit for w in blocked):
            break
        adm.acquire(job)
        admitted.append(name)
        for w in blocked:
            bypassed[w] = bypassed.get(w, 0) + 1
    for name in admitted:
        ready.remove(name)
        bypassed.pop(name, None)
    return admitted, blocked


# ---------------------------------------------------------------------------
# Simulation (capacity plan) — REQ-005
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlannedRun:
    name: str
    start: float
    end: float
    queue_wait: float


@dataclass(frozen=True)
class SchedulePlan:
    runs: Tuple[PlannedRun, ...]
    makespan: float
    lower_bound: float
    critical_path: float
    peak_running: int
    peak_pools: Dict[str, int]
    pool_utilization: Dict[str, float]
    wait_by_constraint: Dict[str, float]

    def bottleneck(self) -> Optional[str]:
        """The constraint that accounts for the most queue wait, if any."""
        if not self.wait_by_constraint:
            return None
        return max(sorted(self.wait_by_constraint), key=self.wait_by_constraint.get)

    def efficiency(self) -> float:
        """``lower_bound / makespan`` — 1.0 means no schedule could finish sooner."""
        return self.lower_bound / self.makespan if self.makespan else 1.0


def simulate(fleet: Fleet) -> SchedulePlan:
    """Deterministic discrete-event plan using each job's ``est_seconds``."""
    adm = _Admission(fleet)
    remaining_deps = {n: set(j.deps) for n, j in fleet.jobs.items()}
    ready = [n for n in fleet.order if not remaining_deps[n]]
    ready_at = {n: 0.0 for n in ready}
    bypassed: Dict[str, int] = {}
    running: List[Tuple[float, int, str]] = []  # (end, index, name)
    starts: Dict[str, float] = {}
    runs: List[PlannedRun] = []
    wait_by: Dict[str, float] = {}
    busy: Dict[str, float] = {p: 0.0 for p in fleet.pools}
    now = 0.0

    while ready or running:
        admitted, blocked = _select(fleet, adm, ready, bypassed)
        for name in admitted:
            starts[name] = now
            job = fleet.jobs[name]
            running.append((now + job.est_seconds, fleet.index[name], name))
            for pool, slots in job.pools.items():
                busy[pool] += slots * job.est_seconds
        if not running:  # pragma: no cover - construction guarantees progress
            raise RuntimeError("no job admissible; fleet limits are inconsistent")
        running.sort()
        next_t = running[0][0]
        # Time-weighted attribution: every waiting job charges its blocker.
        full = adm.running >= fleet.config.max_concurrent
        unreached = "global" if full else "starvation_guard"
        for name in ready:
            reason = blocked.get(name, unreached)
            wait_by[reason] = wait_by.get(reason, 0.0) + (next_t - now)
        now = next_t
        while running and running[0][0] == now:
            _, _, name = running.pop(0)
            adm.release(fleet.jobs[name])
            runs.append(PlannedRun(name, starts[name], now, starts[name] - ready_at[name]))
            for child in fleet.dependents[name]:
                remaining_deps[child].discard(name)
                if not remaining_deps[child]:
                    ready.append(child)
                    ready_at[child] = now

    makespan = now
    finish: Dict[str, float] = {}
    for n in fleet.order:
        j = fleet.jobs[n]
        finish[n] = max((finish[d] for d in j.deps), default=0.0) + j.est_seconds
    critical = max(finish.values(), default=0.0)
    total = sum(j.est_seconds for j in fleet.jobs.values())
    bounds = [critical, total / fleet.config.max_concurrent]
    bounds += [busy[p] / fleet.pools[p].limit for p in fleet.pools]
    util = {
        p: (busy[p] / (fleet.pools[p].limit * makespan) if makespan else 0.0)
        for p in sorted(fleet.pools)
    }
    return SchedulePlan(
        runs=tuple(sorted(runs, key=lambda r: (r.start, fleet.index[r.name]))),
        makespan=makespan,
        lower_bound=max(bounds),
        critical_path=critical,
        peak_running=adm.peak_running,
        peak_pools=dict(adm.peak_pools),
        pool_utilization=util,
        wait_by_constraint={k: wait_by[k] for k in sorted(wait_by) if wait_by[k] > 0},
    )


# ---------------------------------------------------------------------------
# Execution — REQ-002 / REQ-004
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JobResult:
    name: str
    status: str
    attempts: int
    error_type: Optional[str] = None  # class name only; messages may hold secrets


@dataclass(frozen=True)
class FleetManifest:
    results: Tuple[JobResult, ...]
    admission_order: Tuple[str, ...]
    peak_running: int
    peak_pools: Dict[str, int]
    max_concurrent: int
    pool_limits: Dict[str, int]

    def status_of(self, name: str) -> Optional[str]:
        for r in self.results:
            if r.name == name:
                return r.status
        return None

    def ok(self) -> bool:
        return all(r.status == STATUS_OK for r in self.results)

    def within_limits(self) -> bool:
        return self.peak_running <= self.max_concurrent and all(
            self.peak_pools[p] <= self.pool_limits[p] for p in self.pool_limits
        )

    def counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for r in self.results:
            out[r.status] = out.get(r.status, 0) + 1
        return dict(sorted(out.items()))


def run_fleet(fleet: Fleet, max_workers: Optional[int] = None) -> FleetManifest:
    """Run every job concurrently under the fleet's limits.

    A single coordinator owns admission (no shared mutable state in workers); the
    thread pool only executes job functions. A job with no ``fn`` is a no-op.
    """
    adm = _Admission(fleet)
    remaining_deps = {n: set(j.deps) for n, j in fleet.jobs.items()}
    ready = [n for n in fleet.order if not remaining_deps[n]]
    bypassed: Dict[str, int] = {}
    attempts: Dict[str, int] = {n: 0 for n in fleet.jobs}
    results: Dict[str, JobResult] = {}
    order: List[str] = []
    workers = max_workers or fleet.config.max_concurrent

    def _cascade(name: str) -> None:
        stack = list(fleet.dependents[name])
        while stack:
            child = stack.pop()
            if child in results:
                continue
            results[child] = JobResult(child, STATUS_UPSTREAM_FAILED, 0)
            stack.extend(fleet.dependents[child])

    with ThreadPoolExecutor(max_workers=workers) as pool:
        inflight: Dict[Future, str] = {}
        while ready or inflight:
            ready[:] = [n for n in ready if n not in results]
            admitted, _ = _select(fleet, adm, ready, bypassed)
            for name in admitted:
                attempts[name] += 1
                order.append(name)
                fn = fleet.jobs[name].fn or (lambda: None)
                inflight[pool.submit(fn)] = name
            if not inflight:
                break
            done, _ = wait(list(inflight), return_when=FIRST_COMPLETED)
            for fut in sorted(done, key=lambda f: fleet.index[inflight[f]]):
                name = inflight.pop(fut)
                job = fleet.jobs[name]
                adm.release(job)
                exc = fut.exception()
                if exc is None:
                    results[name] = JobResult(name, STATUS_OK, attempts[name])
                    for child in fleet.dependents[name]:
                        remaining_deps[child].discard(name)
                        if not remaining_deps[child]:
                            ready.append(child)
                elif attempts[name] < job.max_attempts:
                    ready.append(name)  # retry re-enters admission
                else:
                    results[name] = JobResult(
                        name, STATUS_FAILED, attempts[name], type(exc).__name__
                    )
                    _cascade(name)

    return FleetManifest(
        results=tuple(results[n] for n in fleet.order if n in results),
        admission_order=tuple(order),
        peak_running=adm.peak_running,
        peak_pools=dict(adm.peak_pools),
        max_concurrent=fleet.config.max_concurrent,
        pool_limits={p: fleet.pools[p].limit for p in fleet.pools},
    )


# ---------------------------------------------------------------------------
# Schedule staggering — REQ-006
# ---------------------------------------------------------------------------


def stagger_offsets(names: Sequence[str], window_seconds: int) -> Dict[str, int]:
    """Deterministic per-pipeline start offsets in ``[0, window_seconds)``.

    Hash-based, so an offset depends only on the pipeline name: adding or removing
    a pipeline never moves the others (no schedule churn on deploy).
    """
    if window_seconds < 1:
        raise ValueError("window_seconds must be >= 1")
    out: Dict[str, int] = {}
    for n in names:
        digest = hashlib.sha256(n.encode("utf-8")).digest()
        out[n] = int.from_bytes(digest[:8], "big") % window_seconds
    return out


# ---------------------------------------------------------------------------
# Orchestrator exporters — REQ-007
# ---------------------------------------------------------------------------


def _pool_tag(pool: str) -> str:
    return f"{TAG_PREFIX}/pool/{pool}"


def _key_tag() -> str:
    return f"{TAG_PREFIX}/concurrency_key"


def _shared_keys(fleet: Fleet) -> Dict[str, List[str]]:
    by_key: Dict[str, List[str]] = {}
    for n in fleet.order:
        k = fleet.jobs[n].concurrency_key
        if k is not None:
            by_key.setdefault(k, []).append(n)
    return by_key


def _dep_warning(fleet: Fleet, target: str, how: str) -> List[str]:
    n = sum(len(j.deps) for j in fleet.jobs.values())
    if not n:
        return []
    return [
        (
            f"{n} cross-pipeline dependency edge(s) are not expressed by {target} "
            f"concurrency config; express them as {how}."
        )
    ]


def to_dagster(fleet: Fleet) -> Dict[str, object]:
    """Render fleet limits as Dagster run-queue concurrency configuration.

    Limits become run-level ``tag_concurrency_limits`` under
    ``concurrency.runs``; each job gets the run tags that count against them, plus
    ``dagster/priority`` and ``dagster/max_retries``. The ``dagster_yaml`` value
    belongs in the instance's ``dagster.yaml``. Verify key names against the
    Dagster version you run.
    """
    limits: List[Dict[str, object]] = [
        {"key": _pool_tag(p), "limit": fleet.pools[p].limit} for p in sorted(fleet.pools)
    ]
    if any(j.concurrency_key for j in fleet.jobs.values()):
        limits.append(
            {"key": _key_tag(), "value": {"applyLimitPerUniqueValue": True}, "limit": 1}
        )
    warnings: List[str] = []
    jobs: Dict[str, Dict[str, object]] = {}
    for n in fleet.order:
        job = fleet.jobs[n]
        tags: Dict[str, str] = {"dagster/priority": str(job.priority)}
        for pool, slots in sorted(job.pools.items()):
            tags[_pool_tag(pool)] = "1"
            if slots > 1:
                warnings.append(
                    f"job '{n}' holds {slots} slots of pool '{pool}'; Dagster run tag "
                    f"limits count 1 per run, so it is under-counted."
                )
        if job.concurrency_key is not None:
            tags[_key_tag()] = job.concurrency_key
        if job.owner:
            tags[f"{TAG_PREFIX}/owner"] = job.owner
        if job.max_attempts > 1:
            tags["dagster/max_retries"] = str(job.max_attempts - 1)
        jobs[n] = {"tags": tags}
    warnings += _dep_warning(fleet, "Dagster", "asset dependencies or run-status sensors")
    return {
        "target": "dagster",
        "dagster_yaml": {
            "concurrency": {
                "runs": {
                    "max_concurrent_runs": fleet.config.max_concurrent,
                    "tag_concurrency_limits": limits,
                },
            },
            # Retried runs are new queued runs: they count against the same limits.
            "run_retries": {"enabled": any(j.max_attempts > 1 for j in fleet.jobs.values())},
        },
        "jobs": jobs,
        "warnings": warnings,
    }


def to_mage(fleet: Fleet) -> Dict[str, object]:
    """Render fleet limits as Mage project and per-pipeline concurrency config.

    Mage limits concurrency per project (``queue_config.concurrency``) and per
    pipeline (``concurrency_config``). It has no named shared pools, cross-pipeline
    mutual exclusion, or run priority, so those are reported in ``warnings`` with
    the mitigation, not silently dropped. Verify key names against your Mage version.
    """
    warnings: List[str] = []
    if fleet.pools:
        warnings.append(
            "Mage has no shared named pools ("
            + ", ".join(sorted(fleet.pools))
            + "); enforce them by dispatching Mage runs through run_fleet admission, "
            "or by splitting pipelines across projects/executors sized to the pool."
        )
    pipelines: Dict[str, Dict[str, object]] = {}
    for key, members in sorted(_shared_keys(fleet).items()):
        if len(members) > 1:
            warnings.append(
                f"concurrency key '{key}' is shared by {len(members)} pipelines "
                f"({', '.join(members)}); Mage cannot exclude across pipelines."
            )
    if len({j.priority for j in fleet.jobs.values()}) > 1:
        warnings.append("Mage has no run priority; job priorities are not enforced.")
    for n in fleet.order:
        job = fleet.jobs[n]
        cfg: Dict[str, object] = {"on_pipeline_run_limit_reached": "wait"}
        if job.concurrency_key is not None:
            # One run at a time across all triggers of this pipeline.
            cfg["pipeline_run_limit_all_triggers"] = 1
        meta: Dict[str, object] = {"concurrency_config": cfg}
        if job.max_attempts > 1:
            meta["retry_config"] = {"retries": job.max_attempts - 1}
        pipelines[n] = meta
    if any(j.max_attempts > 1 for j in fleet.jobs.values()):
        warnings.append(
            "Mage retry_config retries blocks inside the run, so a retrying run keeps "
            "its queue slot; size queue_config.concurrency for retry hold time."
        )
    warnings += _dep_warning(
        fleet, "Mage", "triggers that start the downstream pipeline on upstream success"
    )
    return {
        "target": "mage",
        "project_metadata": {
            "queue_config": {"concurrency": fleet.config.max_concurrent},
        },
        "pipelines": pipelines,
        "warnings": warnings,
    }
