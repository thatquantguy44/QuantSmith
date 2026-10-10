"""Acceptance tests for spec 0111 — change-safe data engineering.

Each test is named for the acceptance criterion it covers (see
``specs/0111-change-safe-data-engineering/tasks.md``). Standard-library only.
"""

from __future__ import annotations

import random
import threading

import pytest

from quantsmith.pipelines.pipeline_fleet import FleetConfig, Pool
from quantsmith.pipelines.provenance import (
    BitemporalStore,
    DatasetVersion,
    LineageGraph,
    TransformRun,
)
from quantsmith.pipelines.reprocessing import (
    Restatement,
    compare,
    execute_plan,
    max_changed_fraction,
    plan_reprocessing,
    swap,
)
from quantsmith.pipelines.schema_evolution import (
    Field,
    Schema,
    check,
    compatibility,
    detect_drift,
    evolve_rows,
    first_violation,
)
from quantsmith.pipelines.streaming_cdc import (
    ChangeEvent,
    TimedEvent,
    apply_cdc,
    record_revisions,
    window_aggregate,
)

# ---------------------------------------------------------------------------
# AC-001 — CDC is idempotent and order-safe
# ---------------------------------------------------------------------------


def cdc_stream():
    return [
        ChangeEvent("AAA", "insert", 1, {"px": 100.0, "qty": 10}),
        ChangeEvent("BBB", "insert", 1, {"px": 50.0, "qty": 5}),
        ChangeEvent("AAA", "update", 2, {"px": 101.0}),
        ChangeEvent("BBB", "delete", 2),
        ChangeEvent("AAA", "update", 3, {"qty": 12}),
    ]


def test_cdc_idempotent_and_order_safe_AC_001():
    state, rep = apply_cdc(cdc_stream())
    assert state.rows == {"AAA": {"px": 101.0, "qty": 12}}
    assert state.deleted == {"BBB": 2}
    assert (rep.applied, rep.duplicates, rep.stale, rep.deletes) == (5, 0, 0, 1)

    # Replaying the whole stream (at-least-once delivery) changes nothing: the
    # last-applied events are duplicates, the earlier ones are stale.
    state2, rep2 = apply_cdc(cdc_stream(), state)
    assert state2.rows == {"AAA": {"px": 101.0, "qty": 12}}
    assert rep2.applied == 0 and rep2.duplicates + rep2.stale == 5

    # A stale update arriving late never overwrites a newer one.
    _, rep3 = apply_cdc([ChangeEvent("AAA", "update", 2, {"px": 1.0})], state2)
    assert rep3.stale == 1 and state2.rows["AAA"]["px"] == 101.0
    # A stale insert cannot resurrect a deleted key.
    apply_cdc([ChangeEvent("BBB", "insert", 1, {"px": 1.0})], state2)
    assert "BBB" not in state2.rows
    with pytest.raises(ValueError, match="unknown CDC op"):
        apply_cdc([ChangeEvent("X", "upsert", 1)])


def test_full_image_cdc_converges_in_any_order_AC_001():
    # With full row images (Debezium-style after-images), any arrival order with
    # any number of replays converges to the same table.
    full = [
        ChangeEvent("AAA", "insert", 1, {"px": 100.0, "qty": 10}),
        ChangeEvent("BBB", "insert", 1, {"px": 50.0, "qty": 5}),
        ChangeEvent("AAA", "update", 2, {"px": 101.0, "qty": 10}),
        ChangeEvent("BBB", "delete", 2),
        ChangeEvent("AAA", "update", 3, {"px": 101.0, "qty": 12}),
        ChangeEvent("CCC", "insert", 4, {"px": 9.0, "qty": 1}),
    ]
    expected = apply_cdc(full)[0]
    for seed in range(50):
        events = full * 3
        random.Random(seed).shuffle(events)
        got = apply_cdc(events)[0]
        assert got.rows == expected.rows == {
            "AAA": {"px": 101.0, "qty": 12}, "CCC": {"px": 9.0, "qty": 1}}
        assert got.applied_seq == expected.applied_seq
        assert got.deleted == {"BBB": 2}


# ---------------------------------------------------------------------------
# AC-002 / AC-003 — watermarked windows, late data, restatements
# ---------------------------------------------------------------------------


def trades():
    # (event_time, arrival_time, value): 5-second windows, 2s allowed lateness.
    return [
        TimedEvent(1, 1.1, 10), TimedEvent(3, 3.2, 20), TimedEvent(6, 6.1, 5),
        TimedEvent(4, 6.5, 1),    # late-ish but within lateness (watermark 4)
        TimedEvent(8, 8.1, 7),    # watermark 6 -> window [0,5) final
        TimedEvent(2, 9.0, 100),  # window [0,5) already emitted -> late
        TimedEvent(12, 12.2, 3),  # watermark 10 -> window [5,10) final
    ]


def test_windows_emit_on_watermark_and_account_for_late_AC_002():
    run = window_aggregate(trades(), size=5, allowed_lateness=2)
    first = run.results[0]
    assert (first.start, first.end, first.value, first.count, first.revision) == (0, 5, 31, 3, 1)
    assert first.known_at == 8.1  # emitted when the watermark passed 5, not before
    assert [(r.start, r.value) for r in run.results] == [(0, 31), (5, 12)]
    assert [e.value for e in run.late] == [100]  # side output, not dropped
    assert run.open_windows == (("", 10),)
    # Every input event is in exactly one place.
    counted = sum(r.count for r in run.results) + len(run.late) + 1  # +1 open window event
    assert counted == len(trades())

    flushed = window_aggregate(trades(), 5, 2, flush=True)
    assert flushed.open_windows == () and flushed.results[-1].start == 10

    with pytest.raises(ValueError):
        window_aggregate(trades(), 0, 2)
    with pytest.raises(ValueError):
        window_aggregate(trades(), 5, 2, late_policy="drop")


def test_restatements_are_bitemporal_AC_003():
    run = window_aggregate(trades(), size=5, allowed_lateness=2, late_policy="restate")
    w0 = [r for r in run.results if r.start == 0]
    assert [(r.value, r.revision, r.known_at) for r in w0] == [(31, 1, 8.1), (131, 2, 9.0)]
    assert run.final()[("", 0)].value == 131 and run.late == ()

    store = BitemporalStore()
    assert record_revisions(run, store, "vwap", "feed:trades") == 3
    # A backtest deciding at t=8.5 sees the first print; after 9.0, the restatement.
    assert store.value_as_of("vwap:", 0, 8.5) == 31
    assert store.value_as_of("vwap:", 0, 9.5) == 131
    assert store.value_as_of("vwap:", 0, 8.0) is None  # not final yet at 8.0
    assert [f.value for f in store.revisions("vwap:", 0)] == [31, 131]


# ---------------------------------------------------------------------------
# AC-004 / AC-005 / AC-006 — schema evolution and drift
# ---------------------------------------------------------------------------

V1 = Schema("prices", "1", (
    Field("ticker", "string"),
    Field("close", "float"),
    Field("volume", "int"),
    Field("exchange", "string", nullable=True),
))


def test_change_classification_AC_004():
    v2 = Schema("prices", "2", (
        Field("ticker", "string"),
        Field("close", "double"),              # widened
        Field("volume", "string"),             # changed
        Field("currency", "string", default="USD"),  # added with default
        Field("venue", "string"),              # added, required, no default
    ))
    by = {c.field: c for c in compatibility(V1, v2).changes}
    assert by["close"].kind == "type_widened"
    assert (by["close"].breaks_backward, by["close"].breaks_forward) == (False, True)
    assert by["volume"].kind == "type_changed"
    assert by["volume"].breaks_backward and by["volume"].breaks_forward
    assert by["currency"].kind == "added" and not by["currency"].breaks_backward
    assert by["venue"].breaks_backward and not by["venue"].breaks_forward
    assert by["exchange"].kind == "removed" and not by["exchange"].breaks_forward  # was nullable

    tightened = Schema("prices", "3", tuple(
        Field(f.name, f.type, nullable=False) for f in V1.fields))
    by = {c.field: c for c in compatibility(V1, tightened).changes}
    assert by["exchange"].kind == "nullability_tightened" and by["exchange"].breaks_backward


def test_mode_enforcement_and_backward_reads_AC_005():
    safe = Schema("prices", "2", V1.fields + (Field("currency", "string", default="USD"),))
    assert check(V1, safe, "full") == []
    widened = Schema("prices", "3", (
        Field("ticker", "string"), Field("close", "double"), Field("volume", "long"),
        Field("exchange", "string", nullable=True)))
    assert check(V1, widened, "backward") == []
    assert len(check(V1, widened, "forward")) == 2
    breaking = Schema("prices", "4", V1.fields + (Field("venue", "string"),))
    assert check(V1, breaking, "backward") == [
        "venue: added (string) breaks backward compatibility"]
    assert first_violation([V1, safe, breaking], "backward")[0] == 2
    assert first_violation([V1, safe], "full") is None
    with pytest.raises(ValueError, match="unknown compatibility mode"):
        check(V1, safe, "loose")

    old_rows = [{"ticker": "AAA", "close": 101, "volume": 10, "exchange": None}]
    assert evolve_rows(V1, safe, old_rows) == [
        {"ticker": "AAA", "close": 101.0, "volume": 10, "exchange": None, "currency": "USD"}]
    with pytest.raises(ValueError, match="not backward compatible"):
        evolve_rows(V1, breaking, old_rows)
    with pytest.raises(ValueError, match="duplicate fields"):
        Schema("x", "1", (Field("a", "int"), Field("a", "int")))


def test_drift_detection_AC_006():
    rows = [
        {"ticker": "AAA", "close": 101.5, "volume": 10, "exchange": "XNYS"},
        {"ticker": "BBB", "close": "n/a", "volume": 5, "exchange": None},   # type
        {"ticker": None, "close": 50.0, "volume": True},                   # null, bool
        {"close": 1.0, "volume": 1, "mic": "XNAS"},                         # missing, unknown
    ]
    rep = detect_drift(V1, rows)
    assert not rep.clean and rep.rows == 4
    assert rep.type_mismatches == {"close": 1, "volume": 1}
    assert rep.null_violations == {"ticker": 1}
    assert rep.missing_required == {"ticker": 1}
    assert rep.unknown_columns == {"mic": 1}
    assert "unknown column 'mic': 1/4 rows" in rep.findings()
    assert detect_drift(V1, rows[:1]).clean


# ---------------------------------------------------------------------------
# AC-007 / AC-008 / AC-009 — reprocessing after a restatement
# ---------------------------------------------------------------------------


class Warehouse:
    """A toy versioned store: rows by version ref, plus the transforms."""

    def __init__(self):
        self.data = {}
        self.calls = []
        self.lock = threading.Lock()

    def put(self, dv, rows):
        self.data[dv.ref] = rows

    def recompute(self, run, inputs):
        with self.lock:
            self.calls.append(run.run_id)
        if run.transform == "fail":
            raise RuntimeError("boom")
        if run.transform == "to_usd":
            px = {r["t"]: r["px"] for r in self.data[inputs["prices"].ref]}
            fx = self.data[inputs["fx"].ref][0]["rate"]
            return {"prices_usd": [{"t": t, "px": px[t] * fx} for t in sorted(px)]}
        if run.transform == "signal":
            usd = self.data[inputs["prices_usd"].ref]
            return {"signal": [{"t": r["t"], "s": round(r["px"] / 100, 6)} for r in usd]}
        if run.transform == "volume_stats":
            vol = self.data[inputs["volumes"].ref]
            return {"vol_stats": [{"n": len(vol)}]}
        raise AssertionError(run.transform)


def build_lineage(transform_signal="signal"):
    wh = Warehouse()
    g = LineageGraph()

    def src(name, version, rows, source_id):
        dv = DatasetVersion.of(name, version, rows)
        g.register_source(dv, source_id, "2026-10-01T22:00:00Z")
        wh.put(dv, rows)
        return dv

    prices = src("prices", "d1", [{"t": "AAA", "px": 100.0}, {"t": "BBB", "px": 50.0}], "vendor")
    fx = src("fx", "d1", [{"rate": 1.1}], "ecb")
    volumes = src("volumes", "d1", [{"t": "AAA", "v": 1}], "vendor")

    def run(run_id, transform, inputs, out_name):
        produced = wh.recompute(
            TransformRun(run_id, transform, "git:1", inputs, ()),
            {dv.dataset: dv for dv in inputs})[out_name]
        out = DatasetVersion.of(out_name, "v1", produced)
        g.record_run(TransformRun(run_id, transform, "git:1", inputs, (out,)))
        wh.put(out, produced)
        return out

    usd = run("r_usd", "to_usd", (prices, fx), "prices_usd")
    sig = run("r_sig", transform_signal, (usd,), "signal")
    stats = run("r_vol", "volume_stats", (volumes,), "vol_stats")
    wh.calls.clear()
    return wh, g, prices, fx, usd, sig, stats


def restate_prices(wh, g, prices, new_rows):
    new = DatasetVersion.of("prices", "d1r", new_rows)
    g.register_source(new, "vendor", "2026-10-02T09:00:00Z")
    wh.put(new, new_rows)
    return Restatement(prices, new)


def test_plan_covers_exactly_the_downstream_AC_007():
    wh, g, prices, fx, _usd, _sig, _stats = build_lineage()
    r = restate_prices(wh, g, prices, [{"t": "AAA", "px": 102.0}, {"t": "BBB", "px": 50.0}])
    plan = plan_reprocessing(g, [r])
    assert [p.run_id for p in plan.reruns] == ["r_usd", "r_sig"]  # not r_vol
    assert plan.reruns[1].depends_on == ("r_usd",)
    assert plan.affected == ("prices_usd@v1", "signal@v1")

    with pytest.raises(ValueError, match="not registered"):
        plan_reprocessing(g, [Restatement(prices, DatasetVersion("prices", "x", "sha256:0"))])
    with pytest.raises(ValueError, match="nothing to reprocess"):
        plan_reprocessing(g, [])
    with pytest.raises(ValueError, match="changes dataset"):
        plan_reprocessing(g, [Restatement(prices, fx)])


def test_execute_writes_new_versions_with_lineage_AC_008():
    wh, g, prices, _fx, usd, sig, _stats = build_lineage()
    r = restate_prices(wh, g, prices, [{"t": "AAA", "px": 102.0}, {"t": "BBB", "px": 50.0}])
    plan = plan_reprocessing(g, [r])
    res = execute_plan(
        g, plan, wh.recompute, "restate1",
        config=FleetConfig(max_concurrent=2, pools=(Pool("warehouse", 1),)),
        pools_for=lambda run: {"warehouse": 1}, persist=wh.put,
    )
    assert res.ok
    assert wh.calls == ["r_usd", "r_sig"]
    new_usd, new_sig = res.superseded[usd.ref], res.superseded[sig.ref]
    assert new_usd.ref == "prices_usd@v1+restate1" and new_sig.ref == "signal@v1+restate1"
    assert res.rows[new_usd.ref][0]["px"] == pytest.approx(112.2)
    # Lineage of the new signal traces to the restated source, not the old one.
    tr = g.trace(new_sig)
    assert [s.version.ref for s in tr.sources] == ["fx@d1", "prices@d1r"]
    assert [x.run_id for x in tr.runs] == ["r_usd@restate1", "r_sig@restate1"]
    # Old versions are untouched (immutable); rollback stays possible.
    assert usd.ref in g.versions and wh.data[usd.ref][0]["px"] == pytest.approx(110.0)
    with pytest.raises(ValueError, match="tag"):
        execute_plan(g, plan, wh.recompute, "bad+tag")


def test_failure_isolation_AC_008():
    wh, g, prices, _fx, _usd, _sig, _stats = build_lineage(transform_signal="signal")
    r = restate_prices(wh, g, prices, [{"t": "AAA", "px": 1.0}, {"t": "BBB", "px": 1.0}])
    plan = plan_reprocessing(g, [r])
    g.runs["r_usd"] = TransformRun("r_usd", "fail", "git:1", g.runs["r_usd"].inputs,
                                   g.runs["r_usd"].outputs)
    res = execute_plan(g, plan, wh.recompute, "attempt1")
    assert not res.ok
    assert res.manifest.status_of("r_usd") == "failed"
    assert res.manifest.status_of("r_sig") == "upstream_failed"
    assert "signal@v1+attempt1" not in g.versions


def test_compare_and_atomic_swap_AC_009():
    wh, g, prices, _fx, usd, sig, stats = build_lineage()
    r = restate_prices(wh, g, prices, [{"t": "AAA", "px": 102.0}, {"t": "BBB", "px": 50.0}])
    res = execute_plan(g, plan_reprocessing(g, [r]), wh.recompute, "restate1", persist=wh.put)
    diffs = {
        ds: compare(ds, wh.data[old.ref], res.rows[res.superseded[old.ref].ref], key=("t",))
        for ds, old in (("prices_usd", usd), ("signal", sig))
    }
    assert (diffs["signal"].changed, diffs["signal"].unchanged) == (1, 1)
    assert diffs["prices_usd"].max_abs_change["px"] == pytest.approx(2.2)

    pointers = {"prices": prices.ref, "prices_usd": usd.ref, "signal": sig.ref,
                "vol_stats": stats.ref}
    tight = swap(pointers, res, diffs, max_changed_fraction(0.25))
    assert not tight.swapped and tight.pointers == pointers  # nothing moved
    assert any("gate failed" in b for b in tight.blocked)

    ok = swap(pointers, res, diffs, max_changed_fraction(0.6))
    assert ok.swapped
    assert ok.pointers == {"prices": "prices@d1r", "prices_usd": "prices_usd@v1+restate1",
                           "signal": "signal@v1+restate1", "vol_stats": stats.ref}
    assert ok.previous == pointers  # rollback target

    missing = swap(pointers, res, {"prices_usd": diffs["prices_usd"]}, max_changed_fraction(1))
    assert not missing.swapped and any("no comparison" in b for b in missing.blocked)

    with pytest.raises(ValueError, match="duplicate key"):
        compare("x", [{"t": 1}, {"t": 1}], [], key=("t",))


def test_failed_run_blocks_swap_AC_009():
    wh, g, prices, _fx, usd, sig, _stats = build_lineage()
    r = restate_prices(wh, g, prices, [{"t": "AAA", "px": 1.0}, {"t": "BBB", "px": 1.0}])
    plan = plan_reprocessing(g, [r])
    g.runs["r_sig"] = TransformRun("r_sig", "fail", "git:1", g.runs["r_sig"].inputs,
                                   g.runs["r_sig"].outputs)
    res = execute_plan(g, plan, wh.recompute, "restate1", persist=wh.put)
    out = swap({"prices": prices.ref, "prices_usd": usd.ref, "signal": sig.ref}, res, {},
               max_changed_fraction(1.0))
    assert not out.swapped and "reprocessing incomplete: r_sig" in out.blocked[0]
