"""Acceptance tests for spec 0101 — concurrent pipeline fleet.

Each test is named for the acceptance criterion it covers (see
``specs/0101-concurrent-pipeline-fleet/tasks.md``). Standard-library only.
"""

from __future__ import annotations

import threading
import time

import pytest

from quantsmith.pipelines.pipeline_fleet import (
    Fleet,
    FleetConfig,
    FleetJob,
    Pool,
    run_fleet,
    simulate,
    stagger_offsets,
    to_dagster,
    to_mage,
)


class Gauge:
    """Counts what is *actually* running inside job functions, per resource."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.now: dict = {}
        self.peak: dict = {}
        self.keys_live: set = set()
        self.key_overlap = False

    def job(self, resources, key=None, sleep=0.002, fail_times=0):
        calls = {"n": 0}

        def fn():
            with self.lock:
                calls["n"] += 1
                attempt = calls["n"]
                for r in resources:
                    self.now[r] = self.now.get(r, 0) + 1
                    self.peak[r] = max(self.peak.get(r, 0), self.now[r])
                if key is not None:
                    if key in self.keys_live:
                        self.key_overlap = True
                    self.keys_live.add(key)
            try:
                time.sleep(sleep)
                if attempt <= fail_times:
                    raise ConnectionError("transient")
            finally:
                with self.lock:
                    for r in resources:
                        self.now[r] -= 1
                    if key is not None:
                        self.keys_live.discard(key)

        return fn


def big_fleet(gauge: Gauge, n: int = 300) -> Fleet:
    """Hundreds of pipelines over a warehouse, a vendor API, and shared sinks."""
    jobs = []
    for i in range(n):
        pools = {"warehouse": 1}
        res = ["global", "warehouse"]
        if i % 3 == 0:
            pools["vendor_api"] = 1
            res.append("vendor_api")
        key = f"sink_{i % 10}"
        jobs.append(
            FleetJob(
                name=f"p{i:03d}",
                fn=gauge.job(res, key=key),
                pools=pools,
                concurrency_key=key,
                priority=i % 4,
                est_seconds=1.0 + (i % 5),
            )
        )
    return Fleet(
        jobs,
        FleetConfig(
            max_concurrent=32,
            pools=(Pool("warehouse", 12), Pool("vendor_api", 4)),
        ),
    )


# AC-001 ---------------------------------------------------------------------


def test_construction_validation_AC_001():
    cfg = FleetConfig(max_concurrent=4, pools=(Pool("db", 2),))
    with pytest.raises(ValueError, match="duplicate job"):
        Fleet([FleetJob("a"), FleetJob("a")], cfg)
    with pytest.raises(ValueError, match="unknown job"):
        Fleet([FleetJob("a", deps=("ghost",))], cfg)
    with pytest.raises(ValueError, match="cycle"):
        Fleet([FleetJob("a", deps=("b",)), FleetJob("b", deps=("a",))], cfg)
    with pytest.raises(ValueError, match="undeclared pool"):
        Fleet([FleetJob("a", pools={"api": 1})], cfg)
    with pytest.raises(ValueError, match="never be admitted"):
        Fleet([FleetJob("a", pools={"db": 3})], cfg)
    with pytest.raises(ValueError, match="max_concurrent"):
        Fleet([FleetJob("a")], FleetConfig(max_concurrent=0))
    fleet = Fleet([FleetJob("b", deps=("a",)), FleetJob("a")], cfg)
    assert fleet.order == ["a", "b"]


# AC-002 ---------------------------------------------------------------------


def test_limits_hold_under_hundreds_of_pipelines_AC_002():
    gauge = Gauge()
    fleet = big_fleet(gauge)
    manifest = run_fleet(fleet)
    assert manifest.ok()
    assert len(manifest.results) == 300
    assert manifest.within_limits()
    # Independent evidence from inside the job functions themselves.
    assert gauge.peak["global"] <= 32
    assert gauge.peak["warehouse"] <= 12
    assert gauge.peak["vendor_api"] <= 4
    assert not gauge.key_overlap
    # Real concurrency actually happened (not a serial run in disguise).
    assert manifest.peak_running > 1


def test_slot_weights_respected_AC_002():
    gauge = Gauge()
    jobs = [
        FleetJob(f"heavy{i}", fn=gauge.job(["heavy"]), pools={"db": 3}) for i in range(6)
    ]
    fleet = Fleet(jobs, FleetConfig(max_concurrent=10, pools=(Pool("db", 4),)))
    manifest = run_fleet(fleet)
    assert manifest.ok()
    assert manifest.peak_pools["db"] <= 4
    assert gauge.peak["heavy"] == 1  # 3 + 3 > 4: never two at once


# AC-003 ---------------------------------------------------------------------


def test_priority_order_AC_003():
    jobs = [FleetJob(f"low{i}", priority=0) for i in range(3)]
    jobs += [FleetJob(f"high{i}", priority=5) for i in range(3)]
    fleet = Fleet(jobs, FleetConfig(max_concurrent=1))
    manifest = run_fleet(fleet)
    assert manifest.admission_order == (
        "high0", "high1", "high2", "low0", "low1", "low2",
    )


def test_no_starvation_of_wide_job_AC_003():
    # A wide job needs the whole pool; a stream of equal-priority narrow jobs
    # behind it keeps at least one slot busy, overtaking it every time.
    def fleet(max_bypass):
        jobs = [FleetJob("first", pools={"db": 1}, est_seconds=1.0)]
        jobs.append(FleetJob("wide", pools={"db": 2}, est_seconds=1.0))
        jobs += [
            FleetJob(f"n{i:02d}", pools={"db": 1}, est_seconds=1.25 + (i % 3) * 0.5)
            for i in range(40)
        ]
        return Fleet(
            jobs,
            FleetConfig(max_concurrent=4, pools=(Pool("db", 2),), max_bypass=max_bypass),
        )

    def wide_start(plan):
        return next(r for r in plan.runs if r.name == "wide").start

    starved = simulate(fleet(10_000))
    guarded = simulate(fleet(3))
    assert wide_start(starved) == max(r.start for r in starved.runs)  # ran last
    assert wide_start(guarded) <= 5.0
    assert guarded.peak_pools["db"] <= 2


# AC-004 ---------------------------------------------------------------------


def test_retries_and_failure_isolation_AC_004():
    gauge = Gauge()
    calls = {"n": 0}

    def always_fails():
        calls["n"] += 1
        raise RuntimeError("password=hunter2")  # message must not be recorded

    jobs = [
        FleetJob("flaky", fn=gauge.job(["x"], fail_times=2), max_attempts=3),
        FleetJob("broken", fn=always_fails, max_attempts=2),
        FleetJob("child", deps=("broken",)),
        FleetJob("grandchild", deps=("child",)),
        FleetJob("unrelated"),
    ]
    manifest = run_fleet(Fleet(jobs, FleetConfig(max_concurrent=2)))
    by = {r.name: r for r in manifest.results}
    assert by["flaky"].status == "ok" and by["flaky"].attempts == 3
    assert by["broken"].status == "failed" and by["broken"].attempts == 2
    assert calls["n"] == 2
    assert by["broken"].error_type == "RuntimeError"
    assert "hunter2" not in repr(manifest)
    assert by["child"].status == "upstream_failed"
    assert by["grandchild"].status == "upstream_failed"
    assert by["unrelated"].status == "ok"
    assert not manifest.ok()


def test_retries_stay_within_limits_AC_004():
    gauge = Gauge()
    jobs = [
        FleetJob(f"r{i}", fn=gauge.job(["api"], fail_times=1), pools={"api": 1},
                 max_attempts=2)
        for i in range(30)
    ]
    manifest = run_fleet(Fleet(jobs, FleetConfig(max_concurrent=16, pools=(Pool("api", 3),))))
    assert manifest.ok()
    assert gauge.peak["api"] <= 3


def test_dependencies_respected_AC_004():
    seen = []
    lock = threading.Lock()

    def rec(name):
        def fn():
            with lock:
                seen.append(name)
        return fn

    jobs = [
        FleetJob("mart", fn=rec("mart"), deps=("stage_a", "stage_b")),
        FleetJob("stage_a", fn=rec("stage_a"), deps=("raw",)),
        FleetJob("stage_b", fn=rec("stage_b"), deps=("raw",)),
        FleetJob("raw", fn=rec("raw")),
    ]
    manifest = run_fleet(Fleet(jobs, FleetConfig(max_concurrent=8)))
    assert manifest.ok()
    assert seen[0] == "raw" and seen[-1] == "mart"


# AC-005 ---------------------------------------------------------------------


def test_simulation_deterministic_and_attributed_AC_005():
    a = simulate(big_fleet(Gauge()))
    b = simulate(big_fleet(Gauge()))
    assert a == b
    assert len(a.runs) == 300
    assert a.peak_running <= 32
    assert a.peak_pools["warehouse"] <= 12 and a.peak_pools["vendor_api"] <= 4
    assert a.makespan >= a.lower_bound > 0
    assert 0 < a.efficiency() <= 1
    assert a.bottleneck() is not None
    assert all(0 <= u <= 1 for u in a.pool_utilization.values())


def test_simulation_names_the_bottleneck_AC_005():
    jobs = [FleetJob(f"j{i}", pools={"api": 1}, est_seconds=2.0) for i in range(20)]
    fleet = Fleet(jobs, FleetConfig(max_concurrent=20, pools=(Pool("api", 2),)))
    plan = simulate(fleet)
    assert plan.bottleneck() == "pool:api"
    assert plan.makespan == pytest.approx(20.0)
    assert plan.lower_bound == pytest.approx(20.0)
    assert plan.pool_utilization["api"] == pytest.approx(1.0)


# AC-006 ---------------------------------------------------------------------


def test_stagger_offsets_AC_006():
    names = [f"pipeline_{i}" for i in range(500)]
    offsets = stagger_offsets(names, 900)
    assert all(0 <= v < 900 for v in offsets.values())
    assert offsets == stagger_offsets(names, 900)
    # Stable under fleet changes: removing pipelines does not move the others.
    assert stagger_offsets(names[:10], 900) == {n: offsets[n] for n in names[:10]}
    # Spread: no single second carries more than a handful of starts.
    per_second: dict = {}
    for v in offsets.values():
        per_second[v] = per_second.get(v, 0) + 1
    assert max(per_second.values()) <= 6
    with pytest.raises(ValueError):
        stagger_offsets(names, 0)


# AC-007 ---------------------------------------------------------------------


def test_dagster_export_AC_007():
    jobs = [
        FleetJob("load", pools={"warehouse": 1}, concurrency_key="fct_trades",
                 priority=3, max_attempts=3, owner="data-eng"),
        FleetJob("heavy", pools={"warehouse": 2}, deps=("load",)),
    ]
    fleet = Fleet(jobs, FleetConfig(max_concurrent=50, pools=(Pool("warehouse", 8),)))
    out = to_dagster(fleet)
    runs = out["dagster_yaml"]["concurrency"]["runs"]
    assert runs["max_concurrent_runs"] == 50
    assert {"key": "quantsmith/pool/warehouse", "limit": 8} in runs["tag_concurrency_limits"]
    assert {
        "key": "quantsmith/concurrency_key",
        "value": {"applyLimitPerUniqueValue": True},
        "limit": 1,
    } in runs["tag_concurrency_limits"]
    tags = out["jobs"]["load"]["tags"]
    assert tags["dagster/priority"] == "3"
    assert tags["dagster/max_retries"] == "2"
    assert tags["quantsmith/concurrency_key"] == "fct_trades"
    assert out["dagster_yaml"]["run_retries"]["enabled"] is True
    joined = " ".join(out["warnings"])
    assert "heavy" in joined and "under-counted" in joined
    assert "dependency" in joined


def test_mage_export_AC_007():
    jobs = [
        FleetJob("a", pools={"warehouse": 1}, concurrency_key="t1", priority=1),
        FleetJob("b", concurrency_key="t1", max_attempts=2),
        FleetJob("c", deps=("a",)),
    ]
    fleet = Fleet(jobs, FleetConfig(max_concurrent=20, pools=(Pool("warehouse", 8),)))
    out = to_mage(fleet)
    assert out["project_metadata"]["queue_config"]["concurrency"] == 20
    cfg = out["pipelines"]["a"]["concurrency_config"]
    assert cfg["pipeline_run_limit_all_triggers"] == 1
    assert cfg["on_pipeline_run_limit_reached"] == "wait"
    assert "pipeline_run_limit_all_triggers" not in out["pipelines"]["c"]["concurrency_config"]
    assert out["pipelines"]["b"]["retry_config"] == {"retries": 1}
    joined = " ".join(out["warnings"])
    for expected in ("warehouse", "'t1' is shared", "priority", "dependency", "retry"):
        assert expected in joined
