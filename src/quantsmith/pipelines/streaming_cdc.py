"""Reference runtime for spec 0111 — streaming and change-data-capture correctness.

Two places a quant data pipeline silently goes wrong when data arrives as a
stream rather than a nightly file:

1. **Change data capture (CDC).** A connector delivers insert/update/delete events
   at least once, and not always in order. Applying them naively double-counts
   replays and lets a stale update overwrite a newer one. ``apply_cdc`` applies an
   event only if its source sequence (LSN, offset, version) is newer than the last
   one applied for that key, so replays and stale events are counted, not applied.
2. **Event-time windows.** A bar or aggregate for 10:00-10:05 must not be
   finalized while 10:03 prints can still arrive, and a print that arrives after
   finalization must not vanish. ``window_aggregate`` finalizes a window when the
   watermark (max event time seen minus allowed lateness) passes its end; a later
   event goes to a side output or produces a numbered restatement — never a silent
   drop. Restatements can be recorded in the ``0102`` bitemporal store so a
   backtest sees the first print as of then and the restatement only after.

Guarantees held by construction:

* REQ-001 / AC-001 — applying the same event stream twice, or any replay of it, is
  a no-op; an event older than the key's applied sequence never overwrites it;
  deletes are tombstones that also carry a sequence. With full row images (the
  usual connector after-image), any arrival order converges to the same table;
  partial updates are merged onto the current row and so are only order-safe
  when each key's events arrive in sequence order.
* REQ-002 / AC-002 — a window is emitted once its end is behind the watermark and
  never before; every late event is accounted for (side output or restatement).
* REQ-003 / AC-003 — window revisions carry the knowledge time at which they were
  emitted and can be written to a ``BitemporalStore``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from .provenance import BitemporalStore

OPS = ("insert", "update", "delete")


# ---------------------------------------------------------------------------
# Change data capture — REQ-001
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChangeEvent:
    key: str
    op: str  # insert | update | delete
    seq: int  # source sequence: LSN / offset / row version, monotonic per key
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class CdcState:
    """The materialized table plus the last applied sequence per key."""

    rows: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    applied_seq: Dict[str, int] = field(default_factory=dict)
    deleted: Dict[str, int] = field(default_factory=dict)  # tombstones: key -> seq


@dataclass(frozen=True)
class CdcReport:
    applied: int
    duplicates: int  # same seq already applied (replay)
    stale: int  # older seq than applied (out-of-order)
    deletes: int


def apply_cdc(
    events: Sequence[ChangeEvent], state: Optional[CdcState] = None
) -> Tuple[CdcState, CdcReport]:
    """Apply events idempotently and order-safely; returns the state and a report."""
    state = state if state is not None else CdcState()
    applied = duplicates = stale = deletes = 0
    for ev in events:
        if ev.op not in OPS:
            raise ValueError(f"unknown CDC op '{ev.op}' for key '{ev.key}'")
        last = state.applied_seq.get(ev.key)
        if last is not None and ev.seq == last:
            duplicates += 1
            continue
        if last is not None and ev.seq < last:
            stale += 1
            continue
        state.applied_seq[ev.key] = ev.seq
        applied += 1
        if ev.op == "delete":
            state.rows.pop(ev.key, None)
            state.deleted[ev.key] = ev.seq
            deletes += 1
        else:
            state.deleted.pop(ev.key, None)
            if ev.op == "update" and ev.key in state.rows:
                merged = dict(state.rows[ev.key])
                merged.update(ev.payload)
                state.rows[ev.key] = merged
            else:
                state.rows[ev.key] = dict(ev.payload)
    return state, CdcReport(applied, duplicates, stale, deletes)


# ---------------------------------------------------------------------------
# Event-time windows with watermarks — REQ-002 / REQ-003
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TimedEvent:
    event_time: float  # when it happened (e.g. trade time, epoch seconds)
    arrival_time: float  # when we received it (knowledge time)
    value: float
    key: str = ""


@dataclass(frozen=True)
class WindowResult:
    key: str
    start: float
    end: float
    value: float
    count: int
    revision: int  # 1 = first emission; >1 = restatement
    known_at: float  # arrival time of the event whose processing emitted this


@dataclass(frozen=True)
class WindowRun:
    results: Tuple[WindowResult, ...]
    late: Tuple[TimedEvent, ...]  # side output (late_policy="side_output")
    open_windows: Tuple[Tuple[str, float], ...]  # (key, start) not yet final at end of input
    watermark: float

    def final(self) -> Dict[Tuple[str, float], WindowResult]:
        """Latest revision per (key, window start)."""
        out: Dict[Tuple[str, float], WindowResult] = {}
        for r in self.results:
            out[(r.key, r.start)] = r
        return out


Agg = Callable[[Sequence[float]], float]


def window_aggregate(
    events: Sequence[TimedEvent],
    size: float,
    allowed_lateness: float,
    agg: Agg = sum,
    late_policy: str = "side_output",
    flush: bool = False,
) -> WindowRun:
    """Tumbling event-time windows of ``size``, processed in arrival order.

    A window ``[start, start+size)`` is emitted when the watermark reaches its end.
    ``late_policy="side_output"`` routes an event for an emitted window to ``late``;
    ``"restate"`` re-emits that window with ``revision + 1``. ``flush=True`` emits
    the still-open windows at the end of input (bounded replay), otherwise they
    are reported in ``open_windows``.
    """
    if size <= 0 or allowed_lateness < 0:
        raise ValueError("size must be > 0 and allowed_lateness >= 0")
    if late_policy not in ("side_output", "restate"):
        raise ValueError("late_policy must be 'side_output' or 'restate'")
    buckets: Dict[Tuple[str, float], List[float]] = {}
    revision: Dict[Tuple[str, float], int] = {}
    results: List[WindowResult] = []
    late: List[TimedEvent] = []
    max_event = float("-inf")

    def start_of(t: float) -> float:
        return (t // size) * size

    def emit(wk: Tuple[str, float], known_at: float) -> None:
        revision[wk] = revision.get(wk, 0) + 1
        vals = buckets[wk]
        results.append(WindowResult(wk[0], wk[1], wk[1] + size, float(agg(vals)),
                                    len(vals), revision[wk], known_at))

    ordered = sorted(enumerate(events), key=lambda iv: (iv[1].arrival_time, iv[0]))
    for _, ev in ordered:
        wk = (ev.key, start_of(ev.event_time))
        if wk in revision:  # window already emitted -> late
            if late_policy == "side_output":
                late.append(ev)
            else:
                buckets[wk].append(ev.value)
                emit(wk, ev.arrival_time)
            continue
        buckets.setdefault(wk, []).append(ev.value)
        max_event = max(max_event, ev.event_time)
        watermark = max_event - allowed_lateness
        for ready in sorted(k for k in buckets if k not in revision and k[1] + size <= watermark):
            emit(ready, ev.arrival_time)

    watermark = max_event - allowed_lateness
    pending = sorted(k for k in buckets if k not in revision)
    if flush:
        last_arrival = max((e.arrival_time for e in events), default=0.0)
        for wk in pending:
            emit(wk, last_arrival)
        pending = []
    return WindowRun(tuple(results), tuple(late), tuple(pending), watermark)


def record_revisions(run: WindowRun, store: BitemporalStore, prefix: str, source: str) -> int:
    """Write every window revision into a bitemporal store (valid = window start).

    Revisions are written in knowledge-time order, so the store's no-backdating
    rule holds; a backtest reading ``as_of(..., known_at=t)`` sees the first print
    until the restatement was known.
    """
    # Several revisions of one window known at the same instant collapse to the
    # last one: the store rejects contradictory facts recorded at the same time.
    latest: Dict[Tuple[str, float, float], WindowResult] = {}
    for r in run.results:
        latest[(r.key, r.start, r.known_at)] = r
    n = 0
    for r in sorted(latest.values(), key=lambda r: (r.known_at, r.key, r.start)):
        store.record(f"{prefix}:{r.key}", r.value, r.start, r.known_at, source, valid_to=r.end)
        n += 1
    return n
