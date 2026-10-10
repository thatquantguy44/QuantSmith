"""Reference runtime for spec 0102 — lineage and bitemporal provenance.

Two questions every number in a quant report must answer, and that the SDK could
only answer per-dataset (``0045`` for FRED vintages) or by convention (``0025``
citations):

1. **Where did this come from?** ``LineageGraph`` records content-hashed dataset
   versions, the sources they were pulled from, and the transform runs (code
   version, parameters) that produced them — at dataset and column level. It can
   trace any version back to its sources, list everything downstream of a
   restated input, verify that rows still match their recorded hash, emit a
   citation, and export OpenLineage-shaped run events.
2. **What did we know, and when?** ``BitemporalStore`` keeps every fact on two
   timelines — *valid time* (when it is true in the world) and *knowledge time*
   (when we recorded it). Corrections append; nothing is overwritten. ``as_of``
   answers "the value for date V as known at time K", so a backtest can only see
   what was known at decision time.

Guarantees held by construction:

* REQ-001 / AC-001 — ``content_hash`` is canonical (key order and row
  serialization do not change it); a dataset version is immutable: one producer,
  one hash.
* REQ-002 / AC-002 — a run is recorded only if every input is a registered source
  or a previously produced version, its outputs are new, and its column map names
  only its own inputs and outputs (no orphan outputs, no cycles).
* REQ-003 / AC-003 — ``trace`` returns every upstream source and run; ``impact``
  every downstream version; ``trace_column`` reports unmapped hops as gaps instead
  of guessing.
* REQ-004 / AC-004 — ``verify`` detects rows that no longer match their recorded
  hash; ``cite`` names the version, hash, and sources with retrieval times.
* REQ-005 / AC-005 — ``to_openlineage`` emits a COMPLETE run event with dataset
  version and column-lineage facets.
* REQ-006 / AC-006 — the bitemporal store is append-only with a monotonic
  knowledge clock (no backdated knowledge); contradictory facts recorded at the
  same instant for overlapping validity are rejected.
* REQ-007 / AC-007 — ``as_of`` / ``snapshot`` return the latest knowledge at or
  before ``known_at``; retractions are tombstones; ``revisions`` lists the full
  restatement trail.
* REQ-008 / AC-008 — ``lookahead_violations`` flags any fact used in a decision
  that was recorded after the decision time.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

PRODUCER = "https://github.com/thatquantguy44/QuantSmith"
OPENLINEAGE_SCHEMA = "https://openlineage.io/spec/2-0-2/OpenLineage.json#/definitions/RunEvent"


# ---------------------------------------------------------------------------
# Content hashing & dataset versions — REQ-001
# ---------------------------------------------------------------------------


def content_hash(rows: Sequence[Mapping[str, Any]]) -> str:
    """Canonical SHA-256 of rows: column order inside a row does not matter."""
    canonical = json.dumps(
        list(rows), sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=True
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DatasetVersion:
    dataset: str
    version: str
    content_hash: str

    @property
    def ref(self) -> str:
        return f"{self.dataset}@{self.version}"

    @classmethod
    def of(
        cls, dataset: str, version: str, rows: Sequence[Mapping[str, Any]]
    ) -> "DatasetVersion":
        return cls(dataset, version, content_hash(rows))


@dataclass(frozen=True)
class SourceRecord:
    """An external origin: where a version was pulled from, when, under what licence."""

    version: DatasetVersion
    source_id: str  # a `sources/` catalog id (spec 0027)
    retrieved_at: str
    license: Optional[str] = None


ColumnRef = Tuple[str, str]  # (dataset name, column)


@dataclass(frozen=True)
class TransformRun:
    """One execution that read input versions and wrote output versions.

    ``column_map`` maps an output column ``(dataset, column)`` to the input columns
    it was derived from. Dataset names are unique within a run.
    """

    run_id: str
    transform: str
    code_version: str
    inputs: Tuple[DatasetVersion, ...]
    outputs: Tuple[DatasetVersion, ...]
    params: Mapping[str, Any] = field(default_factory=dict)
    column_map: Mapping[ColumnRef, Tuple[ColumnRef, ...]] = field(default_factory=dict)
    started_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Lineage graph — REQ-002 / REQ-003 / REQ-004 / REQ-005
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Trace:
    sources: Tuple[SourceRecord, ...]
    runs: Tuple[TransformRun, ...]  # upstream first


@dataclass(frozen=True)
class ColumnTrace:
    sources: Tuple[Tuple[str, str], ...]  # (source version ref, column)
    gaps: Tuple[str, ...]  # human-readable unmapped hops


class LineageGraph:
    """Append-only lineage of dataset versions, sources, and transform runs."""

    def __init__(self) -> None:
        self.versions: Dict[str, DatasetVersion] = {}
        self.sources: Dict[str, SourceRecord] = {}
        self.runs: Dict[str, TransformRun] = {}
        self.produced_by: Dict[str, str] = {}  # version ref -> run id
        self.consumers: Dict[str, List[str]] = {}  # version ref -> run ids

    # -- recording ---------------------------------------------------------

    def _claim(self, dv: DatasetVersion) -> None:
        known = self.versions.get(dv.ref)
        if known is not None:
            if known.content_hash != dv.content_hash:
                raise ValueError(
                    f"{dv.ref} is immutable: recorded {known.content_hash}, "
                    f"got {dv.content_hash}; publish a new version instead"
                )
            raise ValueError(f"{dv.ref} already has a producer")
        self.versions[dv.ref] = dv

    def register_source(
        self,
        version: DatasetVersion,
        source_id: str,
        retrieved_at: str,
        license: Optional[str] = None,
    ) -> SourceRecord:
        if not source_id:
            raise ValueError("source_id is required")
        self._claim(version)
        rec = SourceRecord(version, source_id, retrieved_at, license)
        self.sources[version.ref] = rec
        self.consumers.setdefault(version.ref, [])
        return rec

    def record_run(self, run: TransformRun) -> TransformRun:
        if run.run_id in self.runs:
            raise ValueError(f"duplicate run id '{run.run_id}'")
        if not run.outputs:
            raise ValueError(f"run '{run.run_id}' has no outputs")
        if not run.code_version:
            raise ValueError(f"run '{run.run_id}' has no code_version")
        try:
            json.dumps(dict(run.params), sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"run '{run.run_id}' params are not serializable") from exc
        for dv in run.inputs:
            known = self.versions.get(dv.ref)
            if known is None:
                raise ValueError(
                    f"run '{run.run_id}' reads unknown input {dv.ref}; register its "
                    "source or record the run that produced it first"
                )
            if known.content_hash != dv.content_hash:
                raise ValueError(f"run '{run.run_id}' reads {dv.ref} with a stale hash")
        names_in = [dv.dataset for dv in run.inputs]
        names_out = [dv.dataset for dv in run.outputs]
        if len(set(names_in)) != len(names_in) or len(set(names_out)) != len(names_out):
            raise ValueError(f"run '{run.run_id}' names a dataset twice")
        for (out_ds, out_col), srcs in run.column_map.items():
            if out_ds not in names_out:
                raise ValueError(f"column map output '{out_ds}.{out_col}' is not an output")
            for in_ds, in_col in srcs:
                if in_ds not in names_in:
                    raise ValueError(f"column map input '{in_ds}.{in_col}' is not an input")
        for dv in run.outputs:
            if dv.ref in self.versions:
                self._claim(dv)  # raises with the precise reason
        for dv in run.outputs:
            self._claim(dv)
            self.produced_by[dv.ref] = run.run_id
            self.consumers.setdefault(dv.ref, [])
        for dv in run.inputs:
            self.consumers[dv.ref].append(run.run_id)
        self.runs[run.run_id] = run
        return run

    # -- querying ----------------------------------------------------------

    def _get(self, ref: str) -> DatasetVersion:
        if ref not in self.versions:
            raise KeyError(f"unknown dataset version {ref}")
        return self.versions[ref]

    def trace(self, version: DatasetVersion) -> Trace:
        """Every upstream source and run that contributed to ``version``."""
        self._get(version.ref)
        sources: Dict[str, SourceRecord] = {}
        seen_runs: Set[str] = set()
        ordered: List[TransformRun] = []

        def visit(ref: str) -> None:
            if ref in self.sources:
                sources[ref] = self.sources[ref]
                return
            run_id = self.produced_by[ref]
            if run_id in seen_runs:
                return
            run = self.runs[run_id]
            for dv in run.inputs:
                visit(dv.ref)
            seen_runs.add(run_id)
            ordered.append(run)  # post-order: upstream first

        visit(version.ref)
        return Trace(tuple(sources[k] for k in sorted(sources)), tuple(ordered))

    def impact(self, version: DatasetVersion) -> Tuple[str, ...]:
        """Every downstream version that must be recomputed if ``version`` changes."""
        self._get(version.ref)
        out: Set[str] = set()
        stack = [version.ref]
        while stack:
            ref = stack.pop()
            for run_id in self.consumers.get(ref, []):
                for dv in self.runs[run_id].outputs:
                    if dv.ref not in out:
                        out.add(dv.ref)
                        stack.append(dv.ref)
        return tuple(sorted(out))

    def trace_column(self, version: DatasetVersion, column: str) -> ColumnTrace:
        """Source columns behind ``version.column``; unmapped hops are gaps."""
        self._get(version.ref)
        found: Set[Tuple[str, str]] = set()
        gaps: Set[str] = set()
        stack: List[Tuple[str, str]] = [(version.ref, column)]
        seen: Set[Tuple[str, str]] = set()
        while stack:
            ref, col = stack.pop()
            if (ref, col) in seen:
                continue
            seen.add((ref, col))
            if ref in self.sources:
                found.add((ref, col))
                continue
            run = self.runs[self.produced_by[ref]]
            dataset = self.versions[ref].dataset
            srcs = run.column_map.get((dataset, col))
            if srcs is None:
                gaps.add(f"{ref}.{col}: run '{run.run_id}' declares no column lineage")
                continue
            by_name = {dv.dataset: dv.ref for dv in run.inputs}
            for in_ds, in_col in srcs:
                stack.append((by_name[in_ds], in_col))
        return ColumnTrace(tuple(sorted(found)), tuple(sorted(gaps)))

    def verify(self, version: DatasetVersion, rows: Sequence[Mapping[str, Any]]) -> bool:
        """True when ``rows`` still hash to the recorded content hash."""
        return self._get(version.ref).content_hash == content_hash(rows)

    def cite(self, version: DatasetVersion) -> str:
        """A point-of-use citation (``0025``): version, hash, sources and as-of."""
        dv = self._get(version.ref)
        tr = self.trace(dv)
        srcs = "; ".join(
            f"{s.source_id} ({s.version.ref}, retrieved {s.retrieved_at})" for s in tr.sources
        )
        return f"{dv.ref} [{dv.content_hash[:19]}] <- {srcs}"

    def to_openlineage(
        self, run: TransformRun, namespace: str, event_time: str
    ) -> Dict[str, Any]:
        """An OpenLineage-shaped COMPLETE ``RunEvent`` for ``run``."""
        if run.run_id not in self.runs:
            raise KeyError(f"unknown run '{run.run_id}'")

        def ds(dv: DatasetVersion) -> Dict[str, Any]:
            return {
                "namespace": namespace,
                "name": dv.dataset,
                "facets": {"version": {"datasetVersion": dv.version}},
            }

        by_name = {dv.dataset: dv for dv in run.inputs}
        outputs = []
        for dv in run.outputs:
            entry = ds(dv)
            fields = {
                col: {
                    "inputFields": [
                        {"namespace": namespace, "name": by_name[i].dataset, "field": c}
                        for i, c in srcs
                    ]
                }
                for (out_ds, col), srcs in sorted(run.column_map.items())
                if out_ds == dv.dataset
            }
            if fields:
                entry["facets"]["columnLineage"] = {"fields": fields}
            outputs.append(entry)
        return {
            "eventType": "COMPLETE",
            "eventTime": event_time,
            "producer": PRODUCER,
            "schemaURL": OPENLINEAGE_SCHEMA,
            "run": {
                "runId": run.run_id,
                "facets": {
                    "quantsmith": {
                        "code_version": run.code_version,
                        "params": dict(run.params),
                    }
                },
            },
            "job": {"namespace": namespace, "name": run.transform},
            "inputs": [ds(dv) for dv in run.inputs],
            "outputs": outputs,
        }


# ---------------------------------------------------------------------------
# Bitemporal store — REQ-006 / REQ-007 / REQ-008
# ---------------------------------------------------------------------------


class _Retracted:
    def __repr__(self) -> str:
        return "RETRACTED"


RETRACTED = _Retracted()


@dataclass(frozen=True)
class Fact:
    key: str
    value: Any
    valid_from: Any
    valid_to: Optional[Any]  # exclusive; None = open-ended
    recorded_at: Any
    source: str
    seq: int = 0

    def covers(self, valid_at: Any) -> bool:
        return self.valid_from <= valid_at and (self.valid_to is None or valid_at < self.valid_to)

    @property
    def retracted(self) -> bool:
        return self.value is RETRACTED


def _overlaps(a: Fact, b: Fact) -> bool:
    a_end_after_b_start = a.valid_to is None or b.valid_from < a.valid_to
    b_end_after_a_start = b.valid_to is None or a.valid_from < b.valid_to
    return a_end_after_b_start and b_end_after_a_start


class BitemporalStore:
    """Append-only facts on valid time × knowledge time.

    Times may be any mutually comparable type (``date``, ``datetime``, ISO strings
    of one format). Validity intervals are half-open ``[valid_from, valid_to)``.
    """

    def __init__(self) -> None:
        self.facts: List[Fact] = []
        self._by_key: Dict[str, List[Fact]] = {}
        self._clock: Optional[Any] = None

    def record(
        self,
        key: str,
        value: Any,
        valid_from: Any,
        recorded_at: Any,
        source: str,
        valid_to: Optional[Any] = None,
    ) -> Fact:
        if not source:
            raise ValueError("every fact needs a source (dataset version ref or source id)")
        if valid_to is not None and not valid_from < valid_to:
            raise ValueError("valid_from must be before valid_to")
        if self._clock is not None and recorded_at < self._clock:
            raise ValueError(
                f"recorded_at {recorded_at!r} is before the store clock {self._clock!r}; "
                "knowledge cannot be backdated"
            )
        fact = Fact(key, value, valid_from, valid_to, recorded_at, source, len(self.facts))
        for other in self._by_key.get(key, []):
            if (
                other.recorded_at == recorded_at
                and _overlaps(other, fact)
                and other.value != value
            ):
                raise ValueError(
                    f"contradictory facts for '{key}' recorded at the same instant "
                    f"{recorded_at!r} over overlapping validity"
                )
        self.facts.append(fact)
        self._by_key.setdefault(key, []).append(fact)
        self._clock = recorded_at
        return fact

    def retract(
        self,
        key: str,
        valid_from: Any,
        recorded_at: Any,
        source: str,
        valid_to: Optional[Any] = None,
    ) -> Fact:
        """Record that nothing is known to be true for ``key`` over the interval."""
        return self.record(key, RETRACTED, valid_from, recorded_at, source, valid_to)

    def as_of(self, key: str, valid_at: Any, known_at: Any) -> Optional[Fact]:
        """The fact for ``valid_at`` as known at ``known_at`` (latest knowledge wins)."""
        best: Optional[Fact] = None
        for f in self._by_key.get(key, []):
            if (
                f.recorded_at <= known_at
                and f.covers(valid_at)
                and (best is None or (f.recorded_at, f.seq) > (best.recorded_at, best.seq))
            ):
                best = f
        if best is None or best.retracted:
            return None
        return best

    def value_as_of(self, key: str, valid_at: Any, known_at: Any, default: Any = None) -> Any:
        fact = self.as_of(key, valid_at, known_at)
        return default if fact is None else fact.value

    def snapshot(self, valid_at: Any, known_at: Any) -> Dict[str, Fact]:
        out: Dict[str, Fact] = {}
        for key in sorted(self._by_key):
            fact = self.as_of(key, valid_at, known_at)
            if fact is not None:
                out[key] = fact
        return out

    def revisions(self, key: str, valid_at: Any) -> Tuple[Fact, ...]:
        """Every recorded belief about ``key`` at ``valid_at``, in knowledge order."""
        return tuple(
            sorted(
                (f for f in self._by_key.get(key, []) if f.covers(valid_at)),
                key=lambda f: (f.recorded_at, f.seq),
            )
        )


def lookahead_violations(used: Iterable[Fact], decision_time: Any) -> List[Fact]:
    """Facts used for a decision at ``decision_time`` that were not yet known then."""
    return [f for f in used if f.recorded_at > decision_time]
