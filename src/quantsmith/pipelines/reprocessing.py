"""Reference runtime for spec 0111 — backfill and reprocessing after a restatement.

A vendor restates a file. Every table, feature, and signal built from it is now
wrong, and the fix has three failure modes: recomputing too little (stale
downstream), recomputing too much (wasted compute, needless churn), and swapping
results in piecemeal so readers see half-old, half-new data. This module plans,
executes, compares, and publishes a reprocessing as one unit:

* ``plan_reprocessing`` uses the ``0102`` lineage graph to find exactly the runs
  downstream of the restated versions, in dependency order.
* ``execute_plan`` re-runs them under ``0101`` fleet limits, writing **new**
  immutable versions (``<old version>+<tag>``) and recording their lineage; the
  old versions stay untouched, so nothing is lost and rollback is a pointer move.
* ``compare`` diffs old against new output by key.
* ``swap`` moves every published pointer at once, or none, and only when the
  run succeeded and every diff passes its gate; it returns the previous pointers
  for rollback.

Guarantees held by construction:

* REQ-007 / AC-007 — the plan contains every run downstream of a restated version
  and nothing else, ordered so no run precedes a run it reads from.
* REQ-008 / AC-008 — re-runs read the restated version (or a re-run's new output)
  wherever the original read the old one; outputs are new versions with recorded
  lineage; a failure marks its dependents ``upstream_failed`` and the run not ok.
* REQ-009 / AC-009 — publication is all-or-nothing: a failed run or a failed gate
  swaps nothing; a swap returns the previous pointers.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from .pipeline_fleet import Fleet, FleetConfig, FleetJob, FleetManifest, run_fleet
from .provenance import DatasetVersion, LineageGraph, TransformRun, content_hash

Rows = List[Dict[str, Any]]
# recompute(run, inputs) -> {output dataset name: rows}; inputs maps dataset name
# to the version the re-run must read.
Recompute = Callable[[TransformRun, Dict[str, DatasetVersion]], Mapping[str, Rows]]


@dataclass(frozen=True)
class Restatement:
    old: DatasetVersion
    new: DatasetVersion


@dataclass(frozen=True)
class PlannedRerun:
    run_id: str  # the original run being re-executed
    depends_on: Tuple[str, ...]  # original run ids in the plan it reads from


@dataclass(frozen=True)
class ReprocessPlan:
    restatements: Tuple[Restatement, ...]
    reruns: Tuple[PlannedRerun, ...]  # dependency order
    affected: Tuple[str, ...]  # old version refs that will be superseded


def plan_reprocessing(
    graph: LineageGraph, restatements: Sequence[Restatement]
) -> ReprocessPlan:
    if not restatements:
        raise ValueError("nothing to reprocess")
    for r in restatements:
        for dv in (r.old, r.new):
            known = graph.versions.get(dv.ref)
            if known is None or known.content_hash != dv.content_hash:
                raise ValueError(f"{dv.ref} is not registered in the lineage graph")
        if r.old.dataset != r.new.dataset:
            raise ValueError(f"restatement changes dataset: {r.old.ref} -> {r.new.ref}")
        if r.old.content_hash == r.new.content_hash:
            raise ValueError(f"{r.new.ref} has the same content as {r.old.ref}")

    runs: Set[str] = set()
    stack = [r.old.ref for r in restatements]
    seen: Set[str] = set()
    while stack:
        ref = stack.pop()
        if ref in seen:
            continue
        seen.add(ref)
        for run_id in graph.consumers.get(ref, []):
            runs.add(run_id)
            for dv in graph.runs[run_id].outputs:
                stack.append(dv.ref)

    deps: Dict[str, Tuple[str, ...]] = {}
    for run_id in runs:
        ups = {graph.produced_by.get(dv.ref) for dv in graph.runs[run_id].inputs}
        deps[run_id] = tuple(sorted(u for u in ups if u in runs))
    order: List[str] = []
    done: Set[str] = set()
    pending = sorted(runs)
    while pending:
        ready = [r for r in pending if all(d in done for d in deps[r])]
        if not ready:  # pragma: no cover - lineage is acyclic by construction
            raise ValueError("cycle in lineage")
        for r in ready:
            order.append(r)
            done.add(r)
        pending = [r for r in pending if r not in done]
    affected = sorted(dv.ref for r in runs for dv in graph.runs[r].outputs)
    return ReprocessPlan(tuple(restatements), tuple(PlannedRerun(r, deps[r]) for r in order),
                         tuple(affected))


@dataclass(frozen=True)
class ReprocessResult:
    tag: str
    superseded: Dict[str, DatasetVersion]  # old version ref -> new version
    rows: Dict[str, Rows]  # new version ref -> rows
    manifest: FleetManifest

    @property
    def ok(self) -> bool:
        return self.manifest.ok()


def execute_plan(
    graph: LineageGraph,
    plan: ReprocessPlan,
    recompute: Recompute,
    tag: str,
    config: Optional[FleetConfig] = None,
    pools_for: Optional[Callable[[TransformRun], Mapping[str, int]]] = None,
    persist: Optional[Callable[[DatasetVersion, Rows], None]] = None,
) -> ReprocessResult:
    """Re-run the plan under fleet limits, recording new versions and lineage.

    ``persist(version, rows)`` is called for each new output as soon as it is
    recorded, before any dependent re-run starts, so ``recompute`` can read it.
    """
    if not tag or "@" in tag or "+" in tag:
        raise ValueError("tag must be non-empty and contain no '@' or '+'")
    lock = threading.Lock()
    superseded: Dict[str, DatasetVersion] = {r.old.ref: r.new for r in plan.restatements}
    rows_out: Dict[str, Rows] = {}

    def job(run_id: str) -> Callable[[], None]:
        def fn() -> None:
            orig = graph.runs[run_id]
            with lock:
                inputs = {dv.dataset: superseded.get(dv.ref, dv) for dv in orig.inputs}
            produced = recompute(orig, dict(inputs))
            new_outputs = []
            for dv in orig.outputs:
                if dv.dataset not in produced:
                    raise ValueError(f"recompute for '{run_id}' did not produce '{dv.dataset}'")
                rows = [dict(r) for r in produced[dv.dataset]]
                new_outputs.append((dv, DatasetVersion(dv.dataset, f"{dv.version}+{tag}",
                                                       content_hash(rows)), rows))
            with lock:
                graph.record_run(TransformRun(
                    run_id=f"{run_id}@{tag}",
                    transform=orig.transform,
                    code_version=orig.code_version,
                    inputs=tuple(inputs[dv.dataset] for dv in orig.inputs),
                    outputs=tuple(n for _, n, _ in new_outputs),
                    params=orig.params,
                    column_map=orig.column_map,
                ))
                for old, new, rows in new_outputs:
                    if persist is not None:
                        persist(new, rows)
                    superseded[old.ref] = new
                    rows_out[new.ref] = rows
        return fn

    jobs = [
        FleetJob(
            name=p.run_id,
            fn=job(p.run_id),
            deps=p.depends_on,
            pools=dict(pools_for(graph.runs[p.run_id])) if pools_for else {},
        )
        for p in plan.reruns
    ]
    manifest = run_fleet(Fleet(jobs, config or FleetConfig(max_concurrent=4)))
    return ReprocessResult(tag, dict(superseded), rows_out, manifest)


# ---------------------------------------------------------------------------
# Compare and swap — REQ-009
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Diff:
    dataset: str
    added: int
    removed: int
    changed: int
    unchanged: int
    max_abs_change: Dict[str, float] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return self.added + self.removed + self.changed + self.unchanged

    @property
    def changed_fraction(self) -> float:
        return (self.added + self.removed + self.changed) / self.total if self.total else 0.0


def compare(dataset: str, old: Sequence[Mapping[str, Any]], new: Sequence[Mapping[str, Any]],
            key: Sequence[str]) -> Diff:
    """Row-level diff by ``key`` columns, with the largest numeric change per column."""
    def index(rows: Sequence[Mapping[str, Any]]) -> Dict[Tuple[Any, ...], Mapping[str, Any]]:
        out: Dict[Tuple[Any, ...], Mapping[str, Any]] = {}
        for r in rows:
            k = tuple(r.get(c) for c in key)
            if k in out:
                raise ValueError(f"{dataset}: duplicate key {k}")
            out[k] = r
        return out

    a, b = index(old), index(new)
    changed = unchanged = 0
    max_abs: Dict[str, float] = {}
    for k in a.keys() & b.keys():
        if dict(a[k]) == dict(b[k]):
            unchanged += 1
            continue
        changed += 1
        for col in set(a[k]) | set(b[k]):
            x, y = a[k].get(col), b[k].get(col)
            if isinstance(x, (int, float)) and isinstance(y, (int, float)) \
                    and not isinstance(x, bool) and not isinstance(y, bool):
                max_abs[col] = max(max_abs.get(col, 0.0), abs(float(y) - float(x)))
    return Diff(dataset, len(b.keys() - a.keys()), len(a.keys() - b.keys()), changed,
                unchanged, {c: max_abs[c] for c in sorted(max_abs)})


Gate = Callable[[Diff], bool]


def max_changed_fraction(limit: float) -> Gate:
    """Gate: accept when at most ``limit`` of rows were added, removed, or changed."""
    return lambda d: d.changed_fraction <= limit


@dataclass(frozen=True)
class SwapOutcome:
    swapped: bool
    pointers: Dict[str, str]  # dataset -> published version ref after the call
    previous: Dict[str, str]  # pointers before the call (rollback target)
    blocked: Tuple[str, ...] = ()


def swap(
    pointers: Mapping[str, str],
    result: ReprocessResult,
    diffs: Mapping[str, Diff],
    gate: Gate,
) -> SwapOutcome:
    """Publish every superseding version at once, or nothing.

    ``pointers`` maps dataset name to the published version ref (a view, alias, or
    table pointer). Only datasets whose published ref was superseded move.
    """
    previous = dict(pointers)
    blocked: List[str] = []
    if not result.ok:
        failed = [r.name for r in result.manifest.results if r.status != "ok"]
        blocked.append(f"reprocessing incomplete: {', '.join(failed)}")
    moves: Dict[str, str] = {}
    for dataset, ref in pointers.items():
        new = result.superseded.get(ref)
        if new is None:
            continue
        diff = diffs.get(dataset)
        if diff is None and new.ref in result.rows:
            blocked.append(f"{dataset}: no comparison for {ref} -> {new.ref}")
        elif diff is not None and not gate(diff):
            blocked.append(f"{dataset}: gate failed ({diff.changed_fraction:.1%} rows changed)")
        moves[dataset] = new.ref
    if blocked:
        return SwapOutcome(False, previous, previous, tuple(blocked))
    updated = dict(previous)
    updated.update(moves)
    return SwapOutcome(True, updated, previous)
