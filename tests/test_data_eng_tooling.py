"""Acceptance tests for spec 0112 — data-engineering tooling.

Each test is named for the acceptance criterion it covers (see
``specs/0112-data-engineering-tooling/tasks.md``). Standard-library only.
"""

from __future__ import annotations

import json

import pytest

from quantsmith.pipelines.dbt_review import review_manifest, summarize
from quantsmith.pipelines.distributed_compute import (
    MiB,
    lint_determinism,
    plan_partitions,
    salting_plan,
    skew_report,
)
from quantsmith.pipelines.pipeline_fleet import (
    Fleet,
    FleetConfig,
    FleetJob,
    Pool,
    to_airflow,
    to_prefect,
)


def fleet():
    jobs = [
        FleetJob("load_prices", pools={"warehouse": 1}, priority=3, max_attempts=3,
                 owner="data-eng"),
        FleetJob("heavy_backfill", pools={"warehouse": 2, "vendor_api": 1}),
        FleetJob("write_trades", pools={"warehouse": 1}, concurrency_key="fct_trades:2026"),
        FleetJob("signal", deps=("load_prices",), priority=1),
    ]
    return Fleet(jobs, FleetConfig(max_concurrent=40,
                                   pools=(Pool("warehouse", 8), Pool("vendor_api", 2))))


# AC-001 ---------------------------------------------------------------------


def test_airflow_export_AC_001():
    out = to_airflow(fleet())
    json.dumps(out)
    assert out["airflow_cfg"] == {"core": {"parallelism": 40}}
    assert out["pools"]["quantsmith_warehouse"]["slots"] == 8
    assert out["pools"]["quantsmith_vendor_api"]["slots"] == 2
    assert out["pools"]["quantsmith_key_fct_trades_2026"]["slots"] == 1
    assert 'airflow pools set quantsmith_warehouse 8 "QuantSmith fleet pool \'warehouse\'"' \
        in out["cli"]

    lp = out["dags"]["load_prices"]["default_args"]
    assert lp == {"priority_weight": 3, "weight_rule": "absolute", "retries": 2,
                  "pool": "quantsmith_warehouse", "pool_slots": 1, "owner": "data-eng"}
    hb = out["dags"]["heavy_backfill"]["default_args"]
    assert hb["pool"] == "quantsmith_vendor_api" and hb["pool_slots"] == 1  # tightest pool
    wt = out["dags"]["write_trades"]["default_args"]
    assert wt["pool"] == "quantsmith_key_fct_trades_2026"  # correctness first
    joined = " ".join(out["warnings"])
    assert "heavy_backfill" in joined and "'vendor_api' is enforced" in joined
    assert "write_trades" in joined and "only the key" in joined
    assert "dependency edge" in joined


# AC-002 ---------------------------------------------------------------------


def test_prefect_export_AC_002():
    out = to_prefect(fleet())
    json.dumps(out)
    assert out["work_pool"] == {"concurrency_limit": 40}
    gcl = {g["name"]: g["limit"] for g in out["global_concurrency_limits"]}
    assert gcl == {"quantsmith-pool-vendor_api": 2, "quantsmith-pool-warehouse": 8,
                   "quantsmith-key-fct-trades-2026": 1}
    queues = {q["name"]: q["priority"] for q in out["work_queues"]}
    assert queues == {"quantsmith-p3": 1, "quantsmith-p1": 2, "quantsmith-p0": 3}

    lp = out["flows"]["load_prices"]
    assert lp["work_queue"] == "quantsmith-p3" and lp["retries"] == 2
    assert lp["concurrency"] == [{"names": ["quantsmith-pool-warehouse"], "occupy": 1}]
    wt = out["flows"]["write_trades"]["concurrency"]
    assert wt == [{"names": ["quantsmith-key-fct-trades-2026", "quantsmith-pool-warehouse"],
                   "occupy": 1}]  # equal slots: one all-or-nothing call
    hb = out["flows"]["heavy_backfill"]["concurrency"]
    assert [c["names"][0] for c in hb] == ["quantsmith-pool-vendor_api",
                                           "quantsmith-pool-warehouse"]  # name order
    assert [c["occupy"] for c in hb] == [1, 2]
    assert out["flows"]["signal"]["concurrency"] == []
    joined = " ".join(out["warnings"])
    assert "heavy_backfill" in joined and "name order" in joined
    assert "dependency edge" in joined


# AC-003 / AC-004 ------------------------------------------------------------


def manifest():
    def model(name, **kw):
        base = {"resource_type": "model", "fqn": ["proj", "staging", name],
                "path": f"staging/{name}.sql", "config": {"materialized": "view"},
                "meta": {"owner": "data-eng"}, "raw_code": "select 1"}
        base.update(kw)
        return base

    def test(name, model_id, col=None, extra=None):
        t = {"resource_type": "test", "attached_node": model_id,
             "test_metadata": {"name": name, "kwargs": {"column_name": col} if col else {}}}
        t.update(extra or {})
        return t

    return {
        "nodes": {
            "model.proj.stg_prices": model("stg_prices"),
            "test.proj.u1": test("unique", "model.proj.stg_prices", "id"),
            "test.proj.n1": test("not_null", "model.proj.stg_prices", "id"),
            "model.proj.fct_trades": model(
                "fct_trades", fqn=["proj", "marts", "fct_trades"], path="marts/fct_trades.sql",
                meta={},
                config={"materialized": "incremental", "contract": {"enforced": False}},
                raw_code="select * from {{ ref('stg_prices') }} where d = current_date"),
            # A unique test on *another* model must not count for fct_trades.
            "test.proj.u2": test("unique", "model.proj.stg_prices", "px"),
            "model.proj.dim_sec": model(
                "dim_sec", fqn=["proj", "marts", "dim_sec"], path="marts/dim_sec.sql",
                config={"materialized": "incremental", "unique_key": "sec_id",
                        "on_schema_change": "fail", "contract": {"enforced": True}},
                raw_code="select * from x {% if is_incremental() %} where u > 1 {% endif %}"),
            "test.proj.combo": test("unique_combination_of_columns", "model.proj.dim_sec",
                                    extra={"depends_on": {"nodes": ["model.proj.dim_sec"]}}),
            "snapshot.proj.sec_snap": {"resource_type": "snapshot",
                                       "config": {"unique_key": "id", "strategy": "timestamp"}},
        },
        "sources": {
            "source.proj.vendor.prices": {"loaded_at_field": "_loaded_at",
                                          "freshness": {"warn_after": {"count": 1,
                                                                       "period": "day"}}},
            "source.proj.vendor.fx": {"freshness": None},
        },
    }


def test_dbt_review_rules_AC_003():
    findings = review_manifest(manifest())
    by = {(f.node, f.rule) for f in findings}
    ft = "model.proj.fct_trades"
    for rule in ("ownership", "primary_key", "contract", "incremental_unique_key",
                 "incremental_filter", "incremental_schema_change", "wall_clock"):
        assert (ft, rule) in by, rule
    assert not any(f.node == "model.proj.stg_prices" for f in findings)
    assert not any(f.node == "model.proj.dim_sec" for f in findings)  # clean incremental
    assert ("snapshot.proj.sec_snap", "snapshot") in by  # timestamp without updated_at
    fx = [f for f in findings if f.node == "source.proj.vendor.fx"]
    assert len(fx) == 2  # no loaded_at_field, no threshold
    assert not any(f.node == "source.proj.vendor.prices" for f in findings)
    assert findings == sorted(findings, key=lambda f: (f.node, f.rule, f.message))
    errors, warns = summarize(findings)
    assert errors >= 4 and warns >= 4
    wc = next(f for f in findings if f.rule == "wall_clock")
    assert "current_date" in wc.message


def test_tests_attach_to_their_own_model_AC_004():
    m = manifest()
    # Remove stg_prices' not_null: its PK now fails, even though fct_trades has none either.
    del m["nodes"]["test.proj.n1"]
    by = {(f.node, f.rule) for f in review_manifest(m)}
    assert ("model.proj.stg_prices", "primary_key") in by
    # Fallback via depends_on when attached_node is absent (older manifests).
    m = manifest()
    t = m["nodes"]["test.proj.n1"]
    del t["attached_node"]
    t["depends_on"] = {"nodes": ["model.proj.stg_prices"]}
    assert ("model.proj.stg_prices", "primary_key") not in {
        (f.node, f.rule) for f in review_manifest(m)}
    assert review_manifest({}) == []


# AC-005 / AC-006 ------------------------------------------------------------


def test_partition_planning_and_skew_AC_005():
    assert plan_partitions(10 * 1024 * MiB) == 80
    assert plan_partitions(0) == 1
    assert plan_partitions(10 * 1024 * MiB, max_partitions=50) == 50
    assert plan_partitions(1, min_partitions=8) == 8
    with pytest.raises(ValueError):
        plan_partitions(10, target_bytes=0)
    with pytest.raises(ValueError):
        plan_partitions(10, min_partitions=4, max_partitions=2)

    counts = {"AAPL": 5000, "MSFT": 4000, **{f"T{i:03d}": 50 for i in range(200)}}
    rep = skew_report(counts, 32)
    assert rep.skewed and rep.skew_ratio > 10
    assert [k for k, _ in rep.hot_keys] == ["AAPL", "MSFT"]
    assert sum(rep.loads) == sum(counts.values())
    even = skew_report({f"k{i}": 10 for i in range(1000)}, 8)
    assert not even.hot_keys and even.skew_ratio < 1.5
    with pytest.raises(ValueError):
        skew_report(counts, 0)


def test_salting_plan_AC_006():
    counts = {"AAPL": 5000, "MSFT": 4000, **{f"T{i:03d}": 50 for i in range(200)}}
    plan = salting_plan(counts, 32)
    assert set(plan.factors) == {"AAPL", "MSFT"}
    fair = sum(counts.values()) / 32
    assert all(counts[k] / f <= fair for k, f in plan.factors.items())
    assert plan.after.max_load < plan.before.max_load
    assert plan.after.skew_ratio < plan.before.skew_ratio / 3
    assert sum(plan.after.loads) == sum(counts.values())  # nothing lost
    assert salting_plan(counts, 32) == plan  # deterministic
    flat = salting_plan({f"k{i}": 10 for i in range(100)}, 4)
    assert flat.factors == {} and flat.after == flat.before


# AC-007 ---------------------------------------------------------------------


CODE = """\
df = df.withColumn("id", F.monotonically_increasing_id())
w = Window.partitionBy("ticker")
w_ok = Window.partitionBy("ticker").orderBy("ts")
s1 = df.sample(0.1)
s2 = df.sample(0.1, seed=7)
x = F.rand()
y = F.rand(42)
agg = df.groupBy("t").agg(F.first("px"), F.collect_list("px"))
ok = df.groupBy("t").agg(F.array_sort(F.collect_list("px")))
d = df.dropDuplicates(["t"])
top = df.limit(10)
top_ok = df.orderBy("ts").limit(10)
asof = datetime.now()
# F.rand() in a comment is ignored
pdf = ddf.sample(frac=0.1, random_state=0)
"""


def test_determinism_lint_AC_007():
    findings = lint_determinism(CODE)
    got = {(f.line, f.rule) for f in findings}
    assert got == {
        (1, "monotonic_id"), (2, "window_without_order"), (4, "unseeded_sample"),
        (6, "unseeded_random"), (8, "order_dependent_agg"), (8, "collect_order"),
        (10, "dedup_arbitrary_row"), (11, "limit_without_order"), (13, "wall_clock"),
    }
    assert all(f.message and f.code for f in findings)
    assert lint_determinism("df.orderBy('ts').write.parquet(path)\n") == []
