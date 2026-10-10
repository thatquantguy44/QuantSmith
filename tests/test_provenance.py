"""Acceptance tests for spec 0102 — lineage and bitemporal provenance.

Each test is named for the acceptance criterion it covers (see
``specs/0102-lineage-bitemporal-provenance/tasks.md``). Standard-library only.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest

from quantsmith.pipelines.provenance import (
    BitemporalStore,
    DatasetVersion,
    LineageGraph,
    TransformRun,
    content_hash,
    lookahead_violations,
)

D = dt.date
T = dt.datetime

PRICES = [{"ticker": "AAA", "date": "2026-10-01", "close": 101.5}]
FX = [{"pair": "EURUSD", "date": "2026-10-01", "rate": 1.08}]
PRICES_USD = [{"ticker": "AAA", "date": "2026-10-01", "close_usd": 101.5}]
SIGNAL = [{"ticker": "AAA", "date": "2026-10-01", "score": 0.4}]


def build_graph():
    g = LineageGraph()
    prices = DatasetVersion.of("vendor_prices", "2026-10-01", PRICES)
    fx = DatasetVersion.of("fx_rates", "2026-10-01", FX)
    g.register_source(prices, "vendor_eod", "2026-10-01T22:05:00Z", license="internal-only")
    g.register_source(fx, "ecb_fx", "2026-10-01T16:30:00Z")
    usd = DatasetVersion.of("prices_usd", "v1", PRICES_USD)
    g.record_run(
        TransformRun(
            run_id="r1",
            transform="convert_to_usd",
            code_version="git:abc123",
            inputs=(prices, fx),
            outputs=(usd,),
            params={"base": "USD"},
            column_map={
                ("prices_usd", "close_usd"): (("vendor_prices", "close"), ("fx_rates", "rate")),
                ("prices_usd", "ticker"): (("vendor_prices", "ticker"),),
            },
        )
    )
    signal = DatasetVersion.of("momentum_signal", "v1", SIGNAL)
    g.record_run(
        TransformRun(
            run_id="r2",
            transform="momentum",
            code_version="git:def456",
            inputs=(usd,),
            outputs=(signal,),
            params={"lookback": 20},
            column_map={("momentum_signal", "ticker"): (("prices_usd", "ticker"),)},
        )
    )
    return g, prices, fx, usd, signal


# AC-001 ---------------------------------------------------------------------


def test_content_hash_and_immutability_AC_001():
    a = [{"x": 1, "y": "b"}]
    b = [{"y": "b", "x": 1}]
    assert content_hash(a) == content_hash(b)
    assert content_hash(a) != content_hash([{"x": 2, "y": "b"}])
    assert content_hash(a).startswith("sha256:")

    g = LineageGraph()
    v = DatasetVersion.of("d", "v1", a)
    g.register_source(v, "src", "2026-10-01")
    with pytest.raises(ValueError, match="immutable"):
        g.register_source(DatasetVersion.of("d", "v1", [{"x": 9}]), "src", "2026-10-02")
    with pytest.raises(ValueError, match="already has a producer"):
        g.register_source(v, "src", "2026-10-02")


# AC-002 ---------------------------------------------------------------------


def test_run_validation_AC_002():
    g, prices, _fx, usd, _ = build_graph()
    ghost = DatasetVersion.of("ghost", "v1", [])
    new = DatasetVersion.of("out", "v1", [{"a": 1}])
    with pytest.raises(ValueError, match="unknown input"):
        g.record_run(TransformRun("r9", "t", "git:1", (ghost,), (new,)))
    with pytest.raises(ValueError, match="duplicate run id"):
        g.record_run(TransformRun("r1", "t", "git:1", (prices,), (new,)))
    with pytest.raises(ValueError, match="already has a producer"):
        g.record_run(TransformRun("r9", "t", "git:1", (prices,), (usd,)))
    with pytest.raises(ValueError, match="no code_version"):
        g.record_run(TransformRun("r9", "t", "", (prices,), (new,)))
    with pytest.raises(ValueError, match="stale hash"):
        stale = DatasetVersion("vendor_prices", "2026-10-01", "sha256:0")
        g.record_run(TransformRun("r9", "t", "git:1", (stale,), (new,)))
    with pytest.raises(ValueError, match="not an input"):
        g.record_run(
            TransformRun("r9", "t", "git:1", (prices,), (new,),
                         column_map={("out", "a"): (("fx_rates", "rate"),)})
        )
    with pytest.raises(ValueError, match="not serializable"):
        g.record_run(TransformRun("r9", "t", "git:1", (prices,), (new,), params={"f": object()}))
    # Nothing half-recorded after the failures.
    assert "out@v1" not in g.versions


# AC-003 ---------------------------------------------------------------------


def test_trace_impact_and_column_lineage_AC_003():
    g, _prices, fx, usd, signal = build_graph()
    tr = g.trace(signal)
    assert [s.source_id for s in tr.sources] == ["ecb_fx", "vendor_eod"]
    assert [r.run_id for r in tr.runs] == ["r1", "r2"]  # upstream first

    assert g.impact(fx) == ("momentum_signal@v1", "prices_usd@v1")
    assert g.impact(signal) == ()

    col = g.trace_column(usd, "close_usd")
    assert col.sources == (
        ("fx_rates@2026-10-01", "rate"),
        ("vendor_prices@2026-10-01", "close"),
    )
    assert col.gaps == ()
    assert g.trace_column(signal, "ticker").sources == (("vendor_prices@2026-10-01", "ticker"),)
    gap = g.trace_column(signal, "score")
    assert gap.sources == ()
    assert "declares no column lineage" in gap.gaps[0]


# AC-004 ---------------------------------------------------------------------


def test_verify_and_cite_AC_004():
    g, _prices, _fx, usd, signal = build_graph()
    assert g.verify(usd, PRICES_USD)
    tampered = [dict(PRICES_USD[0], close_usd=999.0)]
    assert not g.verify(usd, tampered)
    cite = g.cite(signal)
    assert cite.startswith("momentum_signal@v1 [sha256:")
    assert "vendor_eod (vendor_prices@2026-10-01, retrieved 2026-10-01T22:05:00Z)" in cite
    assert "ecb_fx" in cite


# AC-005 ---------------------------------------------------------------------


def test_openlineage_event_AC_005():
    g, *_ = build_graph()
    ev = g.to_openlineage(g.runs["r1"], namespace="quant", event_time="2026-10-01T23:00:00Z")
    assert ev["eventType"] == "COMPLETE"
    assert ev["run"]["runId"] == "r1"
    assert ev["job"] == {"namespace": "quant", "name": "convert_to_usd"}
    assert ev["run"]["facets"]["quantsmith"]["code_version"] == "git:abc123"
    assert [i["name"] for i in ev["inputs"]] == ["vendor_prices", "fx_rates"]
    out = ev["outputs"][0]
    assert out["facets"]["version"] == {"datasetVersion": "v1"}
    fields = out["facets"]["columnLineage"]["fields"]
    assert {f["name"] for f in fields["close_usd"]["inputFields"]} == {"vendor_prices", "fx_rates"}
    json.dumps(ev)  # serializable as emitted


# AC-006 ---------------------------------------------------------------------


def test_bitemporal_append_only_AC_006():
    s = BitemporalStore()
    s.record("gdp", 100.0, D(2026, 7, 1), T(2026, 7, 30), "bea:advance", valid_to=D(2026, 10, 1))
    with pytest.raises(ValueError, match="backdated"):
        s.record("gdp", 101.0, D(2026, 7, 1), T(2026, 7, 29), "bea:late")
    with pytest.raises(ValueError, match="contradictory"):
        s.record("gdp", 99.0, D(2026, 8, 1), T(2026, 7, 30), "bea:other")
    with pytest.raises(ValueError, match="before valid_to"):
        s.record("gdp", 1.0, D(2026, 7, 1), T(2026, 8, 1), "x", valid_to=D(2026, 7, 1))
    with pytest.raises(ValueError, match="source"):
        s.record("gdp", 1.0, D(2026, 7, 1), T(2026, 8, 1), "")
    # Same value restated at the same instant is not a contradiction.
    s.record("gdp", 100.0, D(2026, 7, 1), T(2026, 7, 30), "bea:mirror", valid_to=D(2026, 10, 1))
    assert len(s.facts) == 2


# AC-007 ---------------------------------------------------------------------


def test_as_of_revisions_and_retraction_AC_007():
    s = BitemporalStore()
    q3 = D(2026, 7, 1)
    s.record("gdp", 100.0, q3, T(2026, 7, 30), "bea:advance", valid_to=D(2026, 10, 1))
    s.record("gdp", 102.0, q3, T(2026, 8, 28), "bea:second", valid_to=D(2026, 10, 1))
    s.record("cpi", 3.1, q3, T(2026, 8, 28), "bls:cpi")
    s.record("gdp", 101.0, q3, T(2026, 9, 25), "bea:third", valid_to=D(2026, 10, 1))

    mid_q = D(2026, 8, 15)
    assert s.as_of("gdp", mid_q, T(2026, 7, 1)) is None  # not yet known
    assert s.value_as_of("gdp", mid_q, T(2026, 8, 1)) == 100.0
    assert s.value_as_of("gdp", mid_q, T(2026, 9, 1)) == 102.0
    assert s.value_as_of("gdp", mid_q, T(2026, 10, 1)) == 101.0
    assert s.value_as_of("gdp", D(2026, 10, 1), T(2026, 10, 1), default="n/a") == "n/a"

    snap = s.snapshot(mid_q, T(2026, 8, 1))
    assert set(snap) == {"gdp"}  # cpi was not known yet
    assert set(s.snapshot(mid_q, T(2026, 9, 1))) == {"cpi", "gdp"}

    assert [f.value for f in s.revisions("gdp", mid_q)] == [100.0, 102.0, 101.0]

    s.retract("cpi", q3, T(2026, 10, 2), "bls:withdrawn")
    assert s.as_of("cpi", mid_q, T(2026, 10, 3)) is None
    assert s.value_as_of("cpi", mid_q, T(2026, 9, 1)) == 3.1  # history intact


# AC-008 ---------------------------------------------------------------------


def test_lookahead_violations_AC_008():
    s = BitemporalStore()
    a = s.record("eps", 1.0, D(2026, 6, 30), T(2026, 7, 20), "filing:10q")
    b = s.record("eps", 1.2, D(2026, 6, 30), T(2026, 8, 5), "filing:10q-a")
    decision = T(2026, 8, 1)
    known = s.as_of("eps", D(2026, 6, 30), decision)
    assert known is a
    assert lookahead_violations([known], decision) == []
    # Using the latest restatement in a backtest dated before it existed is leakage.
    latest = s.as_of("eps", D(2026, 6, 30), T(2026, 12, 31))
    assert lookahead_violations([latest], decision) == [b]
