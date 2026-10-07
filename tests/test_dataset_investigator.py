"""Acceptance tests for spec 0099 — Dataset Investigator.

Each test names the acceptance criterion it proves. Most run against one shared
investigation of a synthetic dataset with planted structure
(``quantsmith.dataset_investigator.synthetic``): a 5.7× international fraud
rate, an overnight window where volume falls 62% while fraud volume is flat, a
dated shift in ``amount``, informative missingness in ``device_id``, and a
correlated pair. Rejection criteria are proved by tampering with a copy and
showing the validator or the reproduction actually fails it.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

for _mod in ("sklearn", "pyarrow", "pydantic", "yaml", "matplotlib", "scipy", "pandas"):
    pytest.importorskip(_mod, reason="needs the `investigator` extra")

import numpy as np
import pandas as pd
from scipy import stats

from quantsmith.dataset_investigator import synthetic
from quantsmith.dataset_investigator.analysis import findings as F
from quantsmith.dataset_investigator.analysis import hypotheses as H
from quantsmith.dataset_investigator.analysis import planner as PL
from quantsmith.dataset_investigator.analysis.loading import (
    LoadError,
    file_sha256,
    load_dataset,
)
from quantsmith.dataset_investigator.analysis.models import (
    Config,
    Finding,
    Hypothesis,
    Question,
    Weights,
)
from quantsmith.dataset_investigator.analysis.pipeline import (
    EXIT_MISMATCH,
    EXIT_OK,
    EXIT_WRONG_DATA,
    investigate,
    reproduce,
    rerun,
    start,
)
from quantsmith.dataset_investigator.analysis.registry import (
    TOOL_REGISTRY,
    ToolError,
    execute,
)
from quantsmith.dataset_investigator.analysis.report import (
    SECTIONS,
    key_findings,
)
from quantsmith.dataset_investigator.analysis.roles import infer_columns
from quantsmith.dataset_investigator.analysis.validator import (
    ground,
    validate,
)
from quantsmith.dataset_investigator.context import ROLES
from quantsmith.dataset_investigator.context import build as build_context
from quantsmith.dataset_investigator.export import (
    ANALYSIS_DIR,
    build_package,
    runtime_module_hashes,
)

ROOT = Path(__file__).resolve().parents[1]
PKG_SRC = ROOT / "src" / "quantsmith" / "dataset_investigator"
WORKFLOW = ROOT / ".claude" / "workflows" / "dataset-investigator.js"


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    d = tmp_path_factory.mktemp("dataset_investigator")
    data = d / "tx.csv"
    synthetic.transactions().to_csv(data, index=False)
    out = d / "run"
    state = investigate(str(data), Config(as_of="2026-12-31"), out, created_at="2026-10-07T00:00:00Z")
    pkg = build_package(state, out)
    df, _ = load_dataset(str(data))
    return SimpleNamespace(dir=d, data=data, out=out, state=state, pkg=pkg, df=df)


def _result(state, tool, **params):
    for e in state.executions:
        if e.tool == tool and all(e.params.get(k) == v for k, v in params.items()):
            return state.results[e.execution_id]
    raise AssertionError(f"no execution of {tool} with {params}")


def _by_kind(state, kind, **subject):
    return [f for f in state.findings if f.kind == kind and all(f.subject.get(k) == v for k, v in subject.items())]


# --- AC-001: loaders and fingerprints -------------------------------------------------


def test_ac001_loaders_and_fingerprints(tmp_path, monkeypatch):
    """AC-001: CSV, Parquet, pandas (and Polars when installed) give one profile and content hash."""
    df = synthetic.transactions(2_000)
    csv, parquet = tmp_path / "t.csv", tmp_path / "t.parquet"
    df.to_csv(csv, index=False)
    df.to_parquet(parquet, index=False)
    loaded = {"csv": load_dataset(str(csv)), "parquet": load_dataset(str(parquet)), "pandas": load_dataset(df)}
    try:
        import polars as pl
        loaded["polars"] = load_dataset(pl.from_pandas(df))
    except ImportError:
        pass
    hashes = {k: info.content_sha256 for k, (_, info) in loaded.items()}
    assert len(set(hashes.values())) == 1, hashes
    profiles = {k: [c.model_dump() for c in infer_columns(frame)] for k, (frame, _) in loaded.items()}
    assert all(p == profiles["csv"] for p in profiles.values())
    assert loaded["csv"][1].file_sha256 == hashlib.sha256(csv.read_bytes()).hexdigest()
    assert loaded["parquet"][1].file_sha256 == file_sha256(parquet)
    assert loaded["pandas"][1].file_sha256 is None
    assert loaded["csv"][1].rows == 2_000 and loaded["csv"][1].columns == df.shape[1]

    with pytest.raises(LoadError, match="CSV"):
        load_dataset(str(tmp_path / "t.xlsx").replace("xlsx", "csv") if False else _touch(tmp_path / "t.xlsx"))
    monkeypatch.setitem(sys.modules, "pyarrow", None)
    with pytest.raises(LoadError, match="investigator"):
        load_dataset(str(parquet))


def _touch(path: Path) -> str:
    path.write_bytes(b"x")
    return str(path)


# --- AC-002: semantic roles ---------------------------------------------------------------


def test_ac002_semantic_roles(run):
    """AC-002: roles are inferred with evidence; an integer row number is an identifier; overrides win."""
    roles = run.state.roles()
    expected = {"transaction_id": "identifier", "customer_id": "entity_identifier", "transaction_date": "timestamp",
                "amount": "continuous_numeric", "country": "categorical", "device_id": "categorical",
                "note": "free_text", "is_fraud": "binary_target"}
    assert {k: roles[k] for k in expected} == expected
    assert all(c.evidence.get("rule") for c in run.state.columns)

    df = synthetic.transactions(3_000)
    df.insert(0, "row_no", range(len(df)))
    _, st = start(df, Config(roles={"country": "free_text"}))
    r = st.roles()
    assert r["row_no"] == "identifier"
    assert r["country"] == "free_text" and next(c for c in st.columns if c.name == "country").overridden
    st.plan = PL.plan(df, st)
    numeric_calls = [pa for pa in st.plan.analyses if pa.tool in ("analyze_distributions", "calculate_correlations")]
    ctx = H.tool_context(st)
    for pa in numeric_calls:
        res = execute(pa.tool, df, pa.params, ctx, input_fingerprint="x")[1]
        assert "row_no" not in json.dumps(res)
    with pytest.raises(ToolError, match="identifier"):
        execute("analyze_distributions", df, {"columns": ["row_no"]}, ctx, input_fingerprint="x")


# --- AC-003: planner -------------------------------------------------------------------------


def test_ac003_planner_rules_and_model_plan_validation():
    """AC-003: each planning rule fires with a reason; sampling records its seed; unknown analyses are rejected."""
    df = synthetic.transactions(2_000)
    _, st = start(df, Config(sample_threshold=1_000, expensive_sample=500))
    plan = PL.plan(df, st)
    planned = {pa.analysis for pa in plan.analyses}
    assert {"target_balance", "entity_concentration", "temporal_drift", "period_patterns", "target_relationships"} <= planned
    anomaly = next(pa for pa in plan.analyses if pa.analysis == "anomaly_detection")
    assert "sampled to 500 rows (seed 42)" in anomaly.reason
    rec, _ = execute("detect_multivariate_outliers", df, {"method": "mahalanobis"}, H.tool_context(st),
                     input_fingerprint="x", sample_threshold=1_000, expensive_sample=500)
    assert rec.sampled_rows == 500

    bare = df.drop(columns=["transaction_date", "is_fraud", "customer_id"])
    _, st2 = start(bare, Config())
    plan2 = PL.plan(bare, st2)
    skipped = {s.analysis: s.reason for s in plan2.skipped}
    assert skipped["temporal_drift"] == "no timestamp column detected or supplied"
    assert "no binary target" in skipped["target_relationships"]
    assert skipped["target_balance"] == "no target column detected or supplied"
    assert skipped["entity_concentration"] == "no entity identifier columns"
    assert not any(TOOL_REGISTRY[pa.tool].category == "temporal" for pa in plan2.analyses)

    assert PL.validate_plan({"analyses": ["data_quality", "correlations"]}) == ["profile", "data_quality", "correlations"]
    for bad in (["data_quality", "write_back"], ["profile", "profile"], "data_quality"):
        with pytest.raises(PL.PlanError):
            PL.validate_plan(bad)


# --- AC-004 / AC-005: quality and distributions ---------------------------------------------


def test_ac004_quality_defects_counted():
    """AC-004: every planted defect is reported with its exact count."""
    df = synthetic.quality_defects()
    st_df, st = start(df, Config(as_of="2026-12-31"))
    ctx = H.tool_context(st)
    run_ = lambda tool, **p: execute(tool, st_df, p, ctx, input_fingerprint="x")[1]
    dup = run_("analyze_duplicates", id_columns=["order_id"])
    assert dup["duplicate_rows"] == 2
    assert dup["identifiers"][0]["duplicate_rows"] == 6 and dup["identifiers"][0]["ids_repeated"] == 3
    q = run_("analyze_column_quality", as_of="2026-12-31")
    assert [c["column"] for c in q["constant"]] == ["region"]
    assert [c["column"] for c in q["near_constant"]] == ["channel"]
    assert q["negative_in_nonnegative"] == [{"column": "amount", "negative": 3, "negative_pct": 3 / 202}]
    assert q["timestamp_issues"][0]["after_as_of"] == 2
    mixed = {c["column"]: c for c in q["mixed_types"]}
    assert mixed["code"]["non_numeric"] == int(st_df["code"].astype(str).str.startswith("X").sum()) == 51
    miss = run_("analyze_missingness")
    assert all(c["missing"] == 0 for c in miss["columns"])


def test_ac005_distributions_match_reference(run):
    """AC-005: numeric statistics match numpy/scipy within 1e-9; category counts sum to the non-missing count."""
    res = _result(run.state, "analyze_distributions")
    for col in ("amount", "balance", "velocity_24h"):
        x = run.df[col].dropna().to_numpy(dtype="float64")
        got = next(c for c in res["columns"] if c["column"] == col)
        ref = {"mean": x.mean(), "median": np.median(x), "std": x.std(ddof=1), "var": x.var(ddof=1),
               "p01": np.quantile(x, 0.01), "p99": np.quantile(x, 0.99), "min": x.min(), "max": x.max(),
               "skew": stats.skew(x, bias=False), "kurtosis": stats.kurtosis(x, fisher=True, bias=False)}
        for k, v in ref.items():
            assert got[k] == pytest.approx(v, rel=1e-9, abs=1e-9), (col, k)
    cats = _result(run.state, "analyze_categories")
    for c in cats["columns"]:
        assert sum(t["count"] for t in c["top"]) + c["other_count"] == c["n"] == int(run.df[c["column"]].notna().sum())


# --- AC-006 / AC-007 / AC-008: relationships, anomalies, temporal ----------------------------


def test_ac006_relationships_and_segments(run):
    """AC-006: target rates match hand counts; Pearson/Spearman match scipy; MI is deterministic."""
    res = _result(run.state, "compare_target_rates", by="region")
    df = run.df
    for g in res["groups"]:
        part = df[df["region"] == g["group"]]
        assert g["n"] == len(part) and g["positives"] == int(part["is_fraud"].sum())
        assert g["rate"] == pytest.approx(part["is_fraud"].mean())
    assert res["extreme"]["group"] == "international" and res["reference"]["group"] == "domestic"
    assert res["extreme_ratio"] == pytest.approx(res["extreme"]["rate"] / res["reference"]["rate"])
    assert 4.5 < res["extreme_ratio"] < 7.5  # planted 5.7×
    corr = _result(run.state, "calculate_correlations")
    pair = next(p for p in corr["pairs"] if {p["a"], p["b"]} == {"amount", "balance"})
    assert pair["pearson"] == pytest.approx(stats.pearsonr(df.amount, df.balance)[0], abs=1e-12)
    assert pair["spearman"] == pytest.approx(stats.spearmanr(df.amount, df.balance)[0], abs=1e-9)
    ctx = H.tool_context(run.state)
    mi = [execute("mutual_information", df, {"target": "is_fraud"}, ctx, input_fingerprint="x")[0].result_sha256
          for _ in range(2)]
    assert mi[0] == mi[1]


def test_ac007_anomalies():
    """AC-007: robust z and Mahalanobis recover planted outliers; IF and LOF flag them; all are seed-stable."""
    from quantsmith.dataset_investigator.analysis.anomalies import outlier_flags

    rng = np.random.default_rng(1)
    n = 2_000
    a = rng.normal(0, 1, n)
    df = pd.DataFrame({"a": a, "b": a * 0.9 + rng.normal(0, 0.3, n), "c": rng.normal(10, 2, n)})
    joint = np.arange(40)                        # off the a–b relationship: each value is ordinary on its own
    df.loc[joint, "a"] = np.where(joint % 2, 1, -1) * rng.uniform(2, 3.5, 40)
    df.loc[joint, "b"] = -df.loc[joint, "a"] * 0.9 + rng.normal(0, 0.2, 40)
    single = np.arange(40, 60)                   # univariate outliers in c
    df.loc[single, "c"] = rng.uniform(40, 80, 20)
    _, st = start(df, Config())
    ctx = H.tool_context(st)
    z = execute("detect_outliers", df, {}, ctx, input_fingerprint="x")[1]
    assert next(c for c in z["columns"] if c["column"] == "c")["outliers"] >= len(single)
    A = df[["a", "b", "c"]].to_numpy()
    planted = np.concatenate([joint, single])
    for method, floor in (("mahalanobis", 0.95), ("isolation_forest", 0.75), ("lof", 0.9)):
        flags, _ = outlier_flags(A, method, seed=42, contamination=0.04)
        recall = flags[planted].mean()
        assert recall >= floor, (method, recall)
        again, _ = outlier_flags(A, method, seed=42, contamination=0.04)
        assert (flags == again).all(), method
    res = [execute("detect_multivariate_outliers", df, {"method": m}, ctx, input_fingerprint="x")[1] for m in ("isolation_forest", "lof")]
    assert all(r["outliers"] == round(0.01 * n) for r in res)  # the recorded contamination share


def test_ac008_temporal_shift(run):
    """AC-008: KS and PSI flag the planted amount shift near its date; no timestamp means no temporal tool."""
    res = _result(run.state, "detect_distribution_shift", column="amount")
    assert res["ks"] >= 0.1 and res["psi"] >= 0.1 and res["p_value"] < 0.05
    planted = synthetic.START + pd.Timedelta(days=synthetic.SHIFT_DAY)
    assert abs(pd.Timestamp(res["breakpoint"]) - planted) <= pd.Timedelta(days=7)
    assert _by_kind(run.state, "distribution_shift", column="amount")[0].status == "VALIDATED"
    df = synthetic.transactions(2_000).drop(columns=["transaction_date"])
    st = investigate(df, Config(), None, figures=False)
    assert not any(TOOL_REGISTRY[e.tool].category == "temporal" for e in st.executions)


# --- AC-009: ranking ------------------------------------------------------------------------------


def test_ac009_ranking_and_bh(run):
    """AC-009: order follows I with recorded components; weights reorder as computed; BH over all tests."""
    st = copy.deepcopy(run.state)
    live = [f for f in st.findings if f.merged_into is None]
    for f in live:
        s = f.score
        w = st.config.weights
        assert s.I == pytest.approx((w.M * s.M + w.S * s.S + w.P * s.P + w.A * s.A) / (w.M + w.S + w.P + w.A), abs=1e-6)
    keys = key_findings(st)
    assert [f.score.I for f in keys] == sorted((f.score.I for f in keys), reverse=True)
    assert 5 <= len(keys) <= 15

    st.config.weights = Weights(M=0, S=0, P=1, A=0)
    F.score(st)
    by_prev = sorted(st.findings, key=lambda f: (-f.prevalence, f.key))
    assert [f.key for f in F.ranked(st.findings)] == [f.key for f in by_prev]

    tests = F.all_tests(run.state)
    adjusted = F.benjamini_hochberg(tests)
    p = sorted(tests.values())
    m = len(p)
    manual = [min(1.0, min(p[j] * m / (j + 1) for j in range(i, m))) for i in range(m)]
    assert sorted(adjusted.values()) == pytest.approx(manual)
    for f in run.state.findings:
        if f.test:
            assert f.p_adjusted == pytest.approx(adjusted[f.test])
    assert F.benjamini_hochberg({"a": 0.01, "b": 0.04, "c": 0.03}) == pytest.approx({"a": 0.03, "b": 0.04, "c": 0.04})


# --- AC-010 / AC-011: hypothesis loop and questions ------------------------------------------------


def test_ac010_hypothesis_loop_rejects_denominator_effect(run):
    """AC-010: 'fraud volume rises overnight' is rejected; the denominator effect is supported; caps hold."""
    hs = {h.template: h for h in run.state.hypotheses}
    vol, den = hs["window_volume"], hs["window_denominator"]
    assert vol.status == "rejected" and vol.evidence["positives_ratio"] < 1.2
    assert den.status == "supported" and den.parent == vol.hypothesis_id and den.round == vol.round + 1
    assert den.evidence["volume_ratio"] == pytest.approx(synthetic.OVERNIGHT_WEIGHT, abs=0.05)
    window = _result(run.state, "compare_window_counts")
    assert window["window"] == list(synthetic.OVERNIGHT)
    assert window["rate_window"] > 1.5 * window["rate_rest"]  # the tempting reading the loop rejected

    df = synthetic.transactions(30_000)
    one_round = investigate(df, Config(max_rounds=1), None, figures=False)
    assert all(h.round == 1 for h in one_round.hypotheses)
    assert not any(h.template == "window_denominator" for h in one_round.hypotheses)
    capped = investigate(df, Config(max_tool_calls=2), None, figures=False)
    assert sum(1 for e in capped.executions if e.origin == "hypothesis") <= 2
    assert any(h.status == "untested" for h in capped.hypotheses)
    assert any("cap" in n for n in capped.notes)


def test_ac011_research_questions(run):
    """AC-011: 5–10 questions, each linked to a finding or hypothesis and to a registered tool or marked."""
    qs = run.state.questions
    assert 5 <= len(qs) <= 10
    keys = {f.key for f in run.state.findings}
    ids = {h.hypothesis_id for h in run.state.hypotheses}
    for q in qs:
        assert (set(q.from_findings) & keys) or (set(q.from_hypotheses) & ids), q
        assert (q.tool in TOOL_REGISTRY) != q.needs_new_tool, q
    assert len({q.text for q in qs}) == len(qs)


# --- AC-012: validator ----------------------------------------------------------------------------


def test_ac012_validator_statuses(run):
    """AC-012: unbacked number, causal wording, tampered evidence → REJECTED; small n → WEAK; duplicate → merged."""
    st = copy.deepcopy(run.state)
    base = next(f for f in st.findings if f.kind == "target_rate_gap" and f.subject["by"] == "region")
    def variant(suffix, **changes):
        f = base.model_copy(deep=True)
        f.key = base.key + suffix
        for k, v in changes.items():
            setattr(f, k, v)
        st.findings.append(f)
        return f.key
    unbacked = variant("#unbacked", claim=base.claim.replace("(", "(99.9% vs ", 1))
    causal = variant("#causal", claim=base.claim.rstrip(".") + ", because international cards are riskier.")
    tampered = variant("#tampered", evidence={**base.evidence, "ratio": base.evidence["ratio"] * 2})
    # A genuine duplicate: the same comparison through a second, differently parameterized execution.
    rec, res = execute("compare_target_rates", run.df, {"target": "is_fraud", "by": "region", "bins": 3},
                       H.tool_context(st), input_fingerprint=st.dataset.content_sha256)
    st.executions.append(rec)
    st.results[rec.execution_id] = res
    dup = F.derive(rec, res, st)[0]
    st.findings.append(dup)
    validate(st, run.df)
    by = {f.key: f for f in st.findings}
    assert by[unbacked].status == "REJECTED" and "99.9%" in " ".join(by[unbacked].issues)
    assert by[causal].status == "REJECTED" and "because" in " ".join(by[causal].issues)
    assert by[tampered].status == "REJECTED" and any("reproduce" in i for i in by[tampered].issues)
    pair = [by[base.key], by[dup.key]]
    assert sorted(f.merged_into is None for f in pair) == [False, True]  # exactly one survives
    survivor = next(f for f in pair if f.merged_into is None)
    assert next(f for f in pair if f.merged_into).merged_into == survivor.finding_id
    assert survivor.status == "VALIDATED"
    shown = {f.key for f in key_findings(st)}
    assert not shown & {unbacked, causal, tampered} and len(shown & {base.key, dup.key}) == 1

    small_only = copy.deepcopy(run.state)
    f = next(x for x in small_only.findings if x.key == base.key)
    f.n = 5
    validate(small_only, run.df)
    assert next(x for x in small_only.findings if x.key == base.key).status == "WEAK_EVIDENCE"

    assert ground("rate 6.27× (7.46% vs 1.19%)", [{"ratio": 6.2729, "a": 0.0746269, "b": 0.0118966}]) == []
    assert ground("rate 6.4×", [{"ratio": 6.2729}]) == ["6.4"]
    assert ground("`secret_col` is high", [{}], ["amount"]) == ["`secret_col`"]


# --- AC-013: report ---------------------------------------------------------------------------------


def test_ac013_report_structure_and_schemas(run):
    """AC-013: sections in the declared order; findings.json and hypotheses.json validate against the models."""
    md = (run.out / "report" / "investigation_report.md").read_text(encoding="utf-8")
    heads = [line[3:] for line in md.splitlines() if line.startswith("## ")]
    assert heads[: len(SECTIONS)] == list(SECTIONS)
    fj = json.loads((run.out / "report" / "findings.json").read_text(encoding="utf-8"))
    hj = json.loads((run.out / "report" / "hypotheses.json").read_text(encoding="utf-8"))
    assert [Finding.model_validate(f).finding_id for f in fj["findings"]]
    assert all(Hypothesis.model_validate(h) for h in hj["hypotheses"])
    assert all(Question.model_validate(q) for q in hj["questions"])
    for f in key_findings(run.state):
        assert f.finding_id in md and f"dataset-investigator reproduce {f.finding_id}" in md
    figures = list((run.out / "report" / "figures").glob("*.png"))
    assert figures and all(p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n" for p in figures)


# --- AC-014 / AC-015 / AC-016: package, reproduce, rerun ---------------------------------------------


def _pkg_env(run):
    return {**os.environ, "PYTHONPATH": str(run.pkg), "DATASET_ANALYSIS_DATA": str(run.data)}


def test_ac014_exported_package_is_what_ran(run):
    """AC-014: modules are byte-identical to the runtime's; every finding is in the manifest; package tests pass."""
    m = json.loads((run.pkg / "manifest.json").read_text(encoding="utf-8"))
    assert m["modules"] == runtime_module_hashes()
    for rel in m["modules"]:
        assert (run.pkg / rel).read_bytes() == (ANALYSIS_DIR / Path(rel).name).read_bytes()
    reported = {f.finding_id for f in run.state.findings if f.merged_into is None}
    assert reported == set(m["findings"])
    for f in key_findings(run.state):
        e = m["findings"][f.finding_id]
        assert e["function"] == f.function and e["params"] == f.params and e["evidence"] == f.evidence
    for name in ("pyproject.toml", "README.md", "requirements.lock", "configs/investigation.yaml",
                 "examples/reproduce_analysis.py", "tests/test_quality.py", "tests/test_relationships.py",
                 "tests/test_pipeline.py", "expected/findings.json", "expected/hypotheses.json"):
        assert (run.pkg / name).is_file(), name
    r = subprocess.run(check=False, args=[sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(run.pkg / "tests")],
                       cwd=run.dir, env=_pkg_env(run), capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    assert " passed" in r.stdout and "skipped" not in r.stdout


def test_ac015_reproduce_finding_cli(run, tmp_path):
    """AC-015: each finding reproduces (exit 0); a modified dataset exits 4; tampered evidence exits 3."""
    m = json.loads((run.pkg / "manifest.json").read_text(encoding="utf-8"))
    for fid in m["findings"]:
        out = reproduce(m, fid, str(run.data))
        assert out.code == EXIT_OK, "\n".join(out.lines)
    fid = key_findings(run.state)[0].finding_id
    cli = [sys.executable, "-m", "dataset_analysis.cli", "reproduce", fid, "--data", str(run.data)]
    r = subprocess.run(check=False, args=cli, cwd=run.dir, env=_pkg_env(run), capture_output=True, text=True, timeout=300)
    assert r.returncode == EXIT_OK and "Finding successfully reproduced." in r.stdout and f"Reproducing Finding {fid}" in r.stdout
    other = tmp_path / "other.csv"
    pd.read_csv(run.data).iloc[1:].to_csv(other, index=False)
    r = subprocess.run(check=False, args=cli[:-1] + [str(other)], cwd=run.dir, env=_pkg_env(run), capture_output=True, text=True, timeout=300)
    assert r.returncode == EXIT_WRONG_DATA, r.stdout
    tampered = copy.deepcopy(m)
    entry = tampered["findings"][fid]
    k = next(k for k, v in entry["evidence"].items() if isinstance(v, float))
    entry["evidence"][k] = entry["evidence"][k] * 1.01 + 1e-3
    mp = tmp_path / "manifest.json"
    mp.write_text(json.dumps(tampered), encoding="utf-8")
    r = subprocess.run(check=False, args=cli + ["--manifest", str(mp)], cwd=run.dir, env=_pkg_env(run), capture_output=True, text=True, timeout=300)
    assert r.returncode == EXIT_MISMATCH and k in r.stdout


def test_ac016_rerun_without_model_is_identical(run, tmp_path):
    """AC-016: a model-free rerun from the runtime and from the package gives byte-identical outputs."""
    again = tmp_path / "again"
    st = investigate(str(run.data), Config(as_of="2026-12-31"), again, created_at="2026-10-08T09:00:00Z")
    build_package(st, again)
    for rel in ("report/findings.json", "report/hypotheses.json", "analysis_package/manifest.json"):
        assert (again / rel).read_bytes() == (run.out / rel).read_bytes(), rel
    out = rerun(run.pkg, str(run.data), tmp_path / "pkg_rerun")
    assert out.code == EXIT_OK, "\n".join(out.lines)


def test_ac017_run_metadata_fields(run):
    """AC-017: run_metadata.yaml records every REQ-015 field."""
    import yaml

    meta = yaml.safe_load((run.out / "run_metadata.yaml").read_text(encoding="utf-8"))
    for key in ("run_id", "python", "libraries", "random_seed", "dataset", "created_at", "analyses", "configuration"):
        assert meta.get(key) is not None, key
    assert meta["dataset"]["sha256"] == file_sha256(run.data)
    assert meta["dataset"]["rows"] == 30_000 and meta["dataset"]["columns"] == 11
    assert {"numpy", "pandas", "scipy", "scikit-learn"} <= set(meta["libraries"])
    a = meta["analyses"][0]
    assert {"function", "module", "version", "params", "execution_id"} <= set(a)
    assert meta["random_seed"] == 42 and meta["created_at"] == "2026-10-07T00:00:00Z"


# --- AC-018: on-demand entry points -----------------------------------------------------------------


def _cli(*args, cwd):
    return subprocess.run(check=False, args=[sys.executable, "-m", "quantsmith.dataset_investigator.cli", *args], cwd=cwd,
                          capture_output=True, text=True, timeout=600,
                          env={**os.environ, "PYTHONPATH": str(ROOT / "src")})


def test_ac018_on_demand_entry_points(tmp_path):
    """AC-018: the command runs end to end and step by step; the workflow is well formed; the agent contract exists."""
    data = tmp_path / "small.csv"
    synthetic.transactions(4_000).to_csv(data, index=False)
    r = _cli("analyze", str(data), "--out", str(tmp_path / "a"), "--no-figures", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert Path(out["package"], "manifest.json").is_file() and Path(out["report"]).is_file()

    run_dir = str(tmp_path / "steps")
    p = json.loads(_cli("profile", str(data), "--out", run_dir, "--context", "planner", cwd=tmp_path).stdout)
    assert p["context"]["role"] == "planner" and p["context"]["deterministic_plan"]
    r = _cli("run-plan", run_dir, "--templates", "--context", "investigator", cwd=tmp_path)
    ctx = json.loads(r.stdout)["context"]
    # Step output passes through an executor agent: one compact line, the static catalog printed separately.
    assert r.stdout.count("\n") == 1 and "tools" not in ctx
    tools = json.loads(_cli("catalog", cwd=tmp_path).stdout)["tools"]
    assert "stratified_target_rates" in {t["name"] for t in tools}
    gap = next(f for f in ctx["findings"] if f["kind"] == "target_rate_gap")
    proposal = {"hypotheses": [
        {"statement": f"The `{gap['subject']['by']}` gap persists within `velocity_24h` bands.", "from_findings": [gap["key"]],
         "tool": "stratified_target_rates", "prediction": "MH ratio ≥ 1.5",
         "params": {"target": "is_fraud", "by": gap["subject"]["by"], "strata": "velocity_24h",
                    "exposed": gap["subject"]["exposed"], "reference": gap["subject"]["reference"]},
         "decision_rule": {"supported": [{"path": "mh_rate_ratio", "op": ">=", "value": 1.5}],
                           "rejected": [{"path": "mh_rate_ratio", "op": "<", "value": 1.2}]}},
        {"statement": "Run my own code.", "from_findings": [], "tool": "exec_python", "params": {},
         "prediction": "", "decision_rule": {"supported": [], "rejected": []}},
        {"statement": "Fraud is 42.42% higher.", "from_findings": [gap["key"]], "tool": "compare_target_rates",
         "params": {"target": "is_fraud", "by": "region"}, "prediction": "",
         "decision_rule": {"supported": [{"path": "extreme_ratio", "op": ">", "value": 1}], "rejected": []}},
    ]}
    r = subprocess.run(check=False, args=[sys.executable, "-m", "quantsmith.dataset_investigator.cli", "hypotheses", run_dir, "--add", "-"],
                       input=json.dumps(proposal), cwd=tmp_path, capture_output=True, text=True, timeout=600,
                       env={**os.environ, "PYTHONPATH": str(ROOT / "src")})
    tested = json.loads(r.stdout)["tested"]
    assert [h["status"] for h in tested][1:] == ["invalid", "invalid"]
    assert tested[0]["status"] in ("supported", "rejected", "inconclusive")
    assert "unregistered tool" in tested[1]["explanation"] and "42.42%" in tested[2]["explanation"]
    assert _cli("validate", run_dir, cwd=tmp_path).returncode == 0
    bad = subprocess.run(check=False, args=[sys.executable, "-m", "quantsmith.dataset_investigator.cli", "report", run_dir, "--narrative", "-"],
                         input="Fraud is 97.3% international.", cwd=tmp_path, capture_output=True, text=True,
                         env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, timeout=600)
    assert bad.returncode == 5 and "97.3%" in bad.stdout
    good = _cli("report", run_dir, "--export", "--no-figures", cwd=tmp_path)
    assert good.returncode == 0 and Path(json.loads(good.stdout)["package"], "manifest.json").is_file()

    src = WORKFLOW.read_text(encoding="utf-8")
    meta = re.search(r"export const meta = \{(.*?)\n\}\n", src, re.DOTALL).group(1)
    assert "name: 'dataset-investigator'" in meta
    meta_phases = re.findall(r"\{ title: '([^']+)'", meta)
    called = re.findall(r"\bphase\('([^']+)'\)", src)
    assert meta_phases == called
    assert not re.search(r"Date\.now|Math\.random|new Date\(\)", src)
    commands = re.findall(r"`\$\{CLI\} ([a-z-]+)", src)
    assert set(commands) <= {"profile", "catalog", "run-plan", "hypotheses", "validate", "report"}
    assert "quantsmith-dataset-investigator" in src and "exactly the one shell" in src
    reasoning = re.findall(r"agent\(\s*'You are the (planner|investigator|validation reviewer|report writer)", src)
    assert set(reasoning) == {"planner", "investigator", "validation reviewer", "report writer"}

    agent = ROOT / "agents" / "analytics" / "dataset_investigator"
    for name in ("prompt.md", "README.md", "instructions.md", "tasks.md"):
        assert (agent / name).is_file()
    assert "## Spec-Driven Role" in (agent / "instructions.md").read_text(encoding="utf-8")
    assert "analytics/dataset_investigator/" in (ROOT / "agents" / "README.md").read_text(encoding="utf-8")


# --- AC-019 / AC-020: data handling and scope safety ---------------------------------------------------


def test_ac019_model_context_has_no_rows_or_pii(tmp_path):
    """AC-019: no sentinel or PII value reaches a model context or an artifact; small groups are never shown."""
    df = synthetic.transactions(6_000, sentinel=True)
    data = tmp_path / "s.csv"
    df.to_csv(data, index=False)
    out = tmp_path / "run"
    st = investigate(str(data), Config(pii=["customer_id", "country"]), out, figures=False)
    build_package(st, out)
    pii_values = set(df["customer_id"]) | set(df["country"])
    contexts = json.dumps([build_context(st, role) for role in ROLES])
    texts = [contexts] + [p.read_text(encoding="utf-8") for p in out.rglob("*") if p.suffix in (".json", ".md", ".yaml")]
    for text in texts:
        assert synthetic.SENTINEL not in text
        hits = [v for v in pii_values if re.search(rf"(?<![A-Za-z0-9]){re.escape(v)}(?![A-Za-z0-9])", text)]
        assert not hits, hits[:5]
    for e in st.executions:
        res = st.results[e.execution_id]
        for g in res.get("groups", []) + res.get("strata", []):
            assert g.get("n", g.get("n_exposed", st.config.min_cell)) >= st.config.min_cell
    with pytest.raises(ToolError, match="PII"):
        execute("compare_target_rates", df, {"target": "is_fraud", "by": "country"}, H.tool_context(st), input_fingerprint="x")


FORBIDDEN = (r"\beval\(", r"\bexec\(", r"\.to_sql\(", r"\.fillna\(", r"SimpleImputer", r"\binplace=True",
             r"Regressor\(", r"Classifier\(", r"LogisticRegression", r"\.drop_duplicates\(", r"open\([^)]*['\"]w")


def test_ac020_read_only_and_confined(run, tmp_path):
    """AC-020: the source is unchanged, nothing is written outside the run directory, and no forbidden call exists."""
    data = tmp_path / "src.csv"
    synthetic.transactions(3_000).to_csv(data, index=False)
    before_hash = file_sha256(data)
    before = {p for p in tmp_path.rglob("*")}
    investigate(str(data), Config(), tmp_path / "out", figures=False)
    assert file_sha256(data) == before_hash
    created = {p for p in tmp_path.rglob("*")} - before
    assert created and all(tmp_path / "out" in p.parents or p == tmp_path / "out" for p in created)
    allowed_writers = {"report.py", "pipeline.py", "metadata.py", "export.py", "cli.py"}
    for path in sorted(PKG_SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for pat in FORBIDDEN:
            if pat.startswith(r"open\(") and path.name in allowed_writers:
                continue
            assert not re.search(pat, text), f"{path.name}: {pat}"
        if path.name != "anomalies.py":
            assert ".fit(" not in text and "fit_predict" not in text, path.name


# --- AC-021 / AC-022: performance and imports -----------------------------------------------------------


def test_ac021_benchmark_1m_rows():
    """AC-021: the deterministic pass over 1,000,000 rows × 20 columns completes in under 120 s.

    A fixed calibration workload measures the runner first, so a genuinely
    under-provisioned runner is skipped with a recorded reason rather than
    failing on wall-clock noise it cannot control (the same convention as 0080's AC-021).
    """
    calibration_start = time.perf_counter()
    sum(i * i for i in range(2_000_000))
    calibration = time.perf_counter() - calibration_start
    if calibration > 0.5:
        pytest.skip(f"runner under-provisioned for a timing benchmark (calibration took {calibration:.2f}s)")
    df = synthetic.wide(1_000_000)
    assert df.shape == (1_000_000, 20)
    started = time.perf_counter()
    st = investigate(df, Config(), None, figures=False)
    elapsed = time.perf_counter() - started
    assert st.findings and st.hypotheses
    assert any(e.sampled_rows for e in st.executions)
    assert elapsed < 120, f"deterministic pass over 1M × 20 took {elapsed:.1f}s (NFR-003 budget: 120 s)"


ALLOWED_IMPORTS = {"numpy", "pandas", "scipy", "sklearn", "pyarrow", "pydantic", "yaml", "matplotlib", "quantsmith"}


def test_ac022_imports():
    """AC-022: only stdlib, the investigator extra, and own modules; quantsmith does not import the investigator."""
    stdlib = set(sys.stdlib_module_names)
    for path in sorted(PKG_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                root = name.split(".")[0]
                assert root in stdlib or root in ALLOWED_IMPORTS, f"{path.name}: {name}"
                if path.parent.name == "analysis":
                    assert root != "quantsmith", f"{path.name} must stay self-contained: {name}"
    assert "polars" not in "".join(p.read_text(encoding="utf-8") for p in PKG_SRC.rglob("*.py")).replace(
        '"polars"', "").replace("Polars", "").replace("polars.DataFrame", "")
    probe = "import quantsmith, sys; print(any(m.startswith('quantsmith.dataset_investigator') for m in sys.modules))"
    r = subprocess.run(check=False, args=[sys.executable, "-c", probe], capture_output=True, text=True,
                       env={**os.environ, "PYTHONPATH": str(ROOT / "src")})
    assert r.stdout.strip() == "False", r.stderr


# --- Regressions found by running real data (IBM Telco churn; UCI Occupancy) ------------------------


def _telco_like(n=4_000, seed=5):
    """A small table with the shapes the real Telco churn data has: a protective contract, a numeric-as-text
    column with blanks, and one 'No internet service' group repeated across several add-on columns."""
    rng = np.random.default_rng(seed)
    contract = rng.choice(["Month-to-month", "One year", "Two year"], size=n, p=[0.55, 0.2, 0.25])
    tenure = np.where(contract == "Two year", rng.integers(30, 72, n), rng.integers(0, 40, n))
    internet = rng.choice(["Fiber optic", "DSL", "No"], size=n, p=[0.45, 0.35, 0.2])
    base = np.select([contract == "Month-to-month", contract == "One year"], [0.40, 0.12], 0.03)
    base = base * np.where(internet == "No", 0.25, 1.0) * np.where(tenure < 12, 1.3, 1.0)
    churn = np.where(rng.random(n) < np.clip(base, 0, 1), "Yes", "No")
    monthly = np.round(np.where(internet == "No", 20, 70) + rng.normal(0, 8, n), 2)
    total = (monthly * np.maximum(tenure, 1)).round(2).astype(str).astype(object)
    total[:5] = " "                                   # blanks, as in the real TotalCharges
    df = pd.DataFrame({"customerID": [f"{i:04d}-AB{i % 97:02d}" for i in range(n)], "Contract": contract,
                       "tenure": tenure, "InternetService": internet, "MonthlyCharges": monthly,
                       "TotalCharges": total, "Churn": churn})
    for addon in ("OnlineSecurity", "TechSupport", "OnlineBackup"):
        df[addon] = np.where(internet == "No", "No internet service", rng.choice(["Yes", "No"], size=n))
    return df


@pytest.fixture(scope="module")
def telco_like():
    df = _telco_like()
    return df, investigate(df, Config(), None, figures=False)


def test_ac002_numbers_stored_as_text_are_numeric(telco_like):
    """AC-002 regression: a numeric column with a few blank strings is numeric, with the blanks counted."""
    _df, st = telco_like
    col = next(c for c in st.columns if c.name == "TotalCharges")
    assert col.role == "continuous_numeric" and col.evidence["non_numeric_entries"] == 5
    assert any(f.kind == "mixed_types" and f.subject["column"] == "TotalCharges" and f.evidence["non_numeric"] == 5
               for f in st.findings)


def test_ac010_protective_gap_tested_in_its_own_direction(telco_like):
    """AC-010 regression: a gap where the group has a lower rate is stated high-to-low and its stratified
    test passes when the gap persists, instead of being rejected for not exceeding 1.5."""
    _, st = telco_like
    gap = next(f for f in st.findings if f.kind == "target_rate_gap" and f.subject["by"] == "Contract")
    assert gap.subject["exposed"] == "Month-to-month" and gap.subject["reference"] == "Two year"
    assert gap.evidence["ratio_high_to_low"] > 5 and "Month-to-month` is" in gap.claim
    h = next(h for h in st.hypotheses if h.template == "gap_stratified" and h.params["by"] == "Contract")
    assert h.status == "supported", h.explanation
    banded = [h for h in st.hypotheses if h.template == "gap_stratified" and h.params["by"] in ("tenure", "MonthlyCharges")]
    assert banded and all(h.evidence.get("mh_strength") is not None for h in banded), [h.explanation for h in banded]


def test_ac012_same_rows_through_another_column_are_merged(telco_like):
    """AC-012 regression: gaps whose group is the same rows seen through another column merge into one."""
    _, st = telco_like
    gaps = [f for f in st.findings if f.kind == "target_rate_gap" and
            ("No internet service" in (f.subject["exposed"], f.subject["reference"]) or f.subject["by"] == "InternetService")]
    survivors = [f for f in gaps if f.merged_into is None and f.status != "REJECTED"]
    assert len(gaps) >= 3 and len(survivors) == 1, [(f.finding_id, f.merged_into) for f in gaps]
    tested = {h.params.get("by") for h in st.hypotheses if h.template == "gap_stratified"}
    assert len(tested & {"OnlineSecurity", "TechSupport", "OnlineBackup", "InternetService"}) <= 1


def test_ac007_regimes_are_not_called_outliers():
    """AC-007 regression: a mixture flagged far beyond the expected share is reported as regimes, not outliers."""
    rng = np.random.default_rng(2)
    n = 3_000
    on = rng.random(n) < 0.25
    df = pd.DataFrame({"light": np.where(on, rng.normal(450, 40, n), rng.normal(5, 2, n)),
                       "co2": np.where(on, rng.normal(900, 80, n), rng.normal(450, 20, n)),
                       "temp": rng.normal(21, 0.5, n)})
    st = investigate(df, Config(), None, figures=False)
    kinds = {f.kind for f in st.findings}
    assert "multivariate_regimes" in kinds and "multivariate_outliers" not in kinds
    f = next(f for f in st.findings if f.kind == "multivariate_regimes")
    assert "more than one regime" in f.claim and f.status == "VALIDATED"


def test_ac013_small_values_keep_their_digits():
    """AC-013 regression: tiny values print with significant figures, and the claim stays grounded."""
    assert F.num(0.0033612) == "0.00336" and F.num(21.6612) == "21.66" and F.num(1037.23) == "1,037.23"
    assert ground(f"mean {F.num(0.0033612)} vs {F.num(0.0045601)}", [{"a": 0.0033612, "b": 0.0045601}]) == []


def test_ac003_planner_names_candidate_targets():
    """AC-003 regression: with no target, the plan says which two-valued columns could be one."""
    df = pd.DataFrame({"temp": np.random.default_rng(0).normal(size=500), "Occupancy": np.arange(500) % 2})
    _, st = start(df, Config())
    plan = PL.plan(df, st)
    reason = next(s.reason for s in plan.skipped if s.analysis == "target_balance")
    assert "Occupancy" in reason and "--target" in reason
