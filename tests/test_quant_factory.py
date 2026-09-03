"""Tests for quant_factory.py — spec 0061.

One test per acceptance criterion (AC-001 through AC-013).
All tests use in-memory fixtures; ledger tests write to a tempfile.
No mocking, no network, no imports from other src/quantsmith modules.
"""

import json
import tempfile
from pathlib import Path

import pytest

from quantsmith.pipelines.quant_factory import (
    ConvergenceGate,
    FactoryDecision,
    FactoryError,
    FactoryRunner,
    FactorySpec,
    LaneResult,
    LaneSpec,
    score_lane,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _gate(
    min_sharpe: float = 0.8,
    max_drawdown: float = -0.15,
    min_annual_return: float = 0.05,
    n_best: int = 1,
    pass_threshold: float = 0.6,
) -> ConvergenceGate:
    return ConvergenceGate(
        min_sharpe=min_sharpe,
        max_drawdown=max_drawdown,
        min_annual_return=min_annual_return,
        n_best=n_best,
        pass_threshold=pass_threshold,
    )


def _lane_spec(lane_id: str = "lane_a") -> LaneSpec:
    return LaneSpec(
        lane_id=lane_id,
        hypothesis=f"hypothesis for {lane_id}",
        feature_set=("f1", "f2"),
        model_tag="ridge",
        backtest_config={},
    )


def _good_result(lane_id: str = "lane_a") -> LaneResult:
    return LaneResult(
        lane_id=lane_id,
        status="gate_pending",
        sharpe=1.4,
        max_drawdown=-0.08,
        annual_return=0.12,
        gate_score=None,
        leakage_flags=(),
        elapsed_seconds=5.0,
        error=None,
    )


def _bad_result(lane_id: str = "lane_b") -> LaneResult:
    return LaneResult(
        lane_id=lane_id,
        status="gate_pending",
        sharpe=0.2,
        max_drawdown=-0.35,
        annual_return=0.01,
        gate_score=None,
        leakage_flags=(),
        elapsed_seconds=3.0,
        error=None,
    )


def _make_spec(
    convergence_mode: str = "best_of_n",
    gate: ConvergenceGate = None,
    lane_ids: tuple = ("lane_a", "lane_b"),
    ledger_path: Path = None,
) -> FactorySpec:
    gate = gate or _gate()
    ledger_path = ledger_path or Path(tempfile.mktemp(suffix=".jsonl"))
    return FactorySpec(
        run_id="run_test",
        convergence_mode=convergence_mode,
        gate=gate,
        lanes=tuple(_lane_spec(lid) for lid in lane_ids),
        seed=42,
        ledger_path=ledger_path,
    )


# ---------------------------------------------------------------------------
# AC-001: score_lane returns [0, 1] for valid metrics
# ---------------------------------------------------------------------------

def test_score_lane_valid_metrics_in_unit_range_AC_001():
    gate = _gate(min_sharpe=0.8, max_drawdown=-0.15, min_annual_return=0.05)
    result = _good_result()
    score = score_lane(result, gate)
    assert 0.0 <= score <= 1.0
    assert score > 0.0, "a clearly above-threshold result should score > 0"


# ---------------------------------------------------------------------------
# AC-002: leakage flag → score 0.0
# ---------------------------------------------------------------------------

def test_score_lane_leakage_flag_scores_zero_AC_002():
    gate = _gate()
    result = LaneResult(
        lane_id="lane_a", status="gate_pending",
        sharpe=1.5, max_drawdown=-0.05, annual_return=0.20,
        gate_score=None, leakage_flags=("feature_peek",),
        elapsed_seconds=1.0, error=None,
    )
    assert score_lane(result, gate) == 0.0


# ---------------------------------------------------------------------------
# AC-003: error set → score 0.0
# ---------------------------------------------------------------------------

def test_score_lane_error_set_scores_zero_AC_003():
    gate = _gate()
    result = LaneResult(
        lane_id="lane_a", status="gate_pending",
        sharpe=1.5, max_drawdown=-0.05, annual_return=0.20,
        gate_score=None, leakage_flags=(),
        elapsed_seconds=1.0, error="training diverged",
    )
    assert score_lane(result, gate) == 0.0


# ---------------------------------------------------------------------------
# AC-004: best_of_n approves higher scorer, rejects lower
# ---------------------------------------------------------------------------

def test_best_of_n_approves_higher_scorer_AC_004(tmp_path):
    spec = _make_spec("best_of_n", ledger_path=tmp_path / "ledger.jsonl")
    results = [_good_result("lane_a"), _bad_result("lane_b")]
    runner = FactoryRunner()
    decision = runner.run(spec, results)

    assert decision.decision == "approved"
    assert decision.approved_lanes == ("lane_a",)
    statuses = {r.lane_id: r.status for r in decision.lane_results}
    assert statuses["lane_a"] == "approved"
    assert statuses["lane_b"] == "rejected"


# ---------------------------------------------------------------------------
# AC-005: best_of_n all below threshold → failed, no approved lanes
# ---------------------------------------------------------------------------

def test_best_of_n_all_below_threshold_fails_AC_005(tmp_path):
    spec = _make_spec(
        "best_of_n",
        gate=_gate(pass_threshold=0.99),
        ledger_path=tmp_path / "ledger.jsonl",
    )
    results = [_bad_result("lane_a"), _bad_result("lane_b")]
    runner = FactoryRunner()
    decision = runner.run(spec, results)

    assert decision.decision == "failed"
    assert decision.approved_lanes == ()


# ---------------------------------------------------------------------------
# AC-006: all_required both pass → approved, both in approved_lanes
# ---------------------------------------------------------------------------

def test_all_required_both_pass_approved_AC_006(tmp_path):
    spec = _make_spec(
        "all_required",
        gate=_gate(pass_threshold=0.01),
        ledger_path=tmp_path / "ledger.jsonl",
    )
    results = [_good_result("lane_a"), _good_result("lane_b")]
    runner = FactoryRunner()
    decision = runner.run(spec, results)

    assert decision.decision == "approved"
    assert set(decision.approved_lanes) == {"lane_a", "lane_b"}


# ---------------------------------------------------------------------------
# AC-007: all_required with a leakage flag → failed
# ---------------------------------------------------------------------------

def test_all_required_leakage_flag_fails_run_AC_007(tmp_path):
    spec = _make_spec(
        "all_required",
        gate=_gate(pass_threshold=0.01),
        ledger_path=tmp_path / "ledger.jsonl",
    )
    leaky = LaneResult(
        lane_id="lane_b", status="gate_pending",
        sharpe=1.5, max_drawdown=-0.05, annual_return=0.20,
        gate_score=None, leakage_flags=("future_data",),
        elapsed_seconds=2.0, error=None,
    )
    results = [_good_result("lane_a"), leaky]
    runner = FactoryRunner()
    decision = runner.run(spec, results)

    assert decision.decision == "failed"
    assert decision.approved_lanes == ()


# ---------------------------------------------------------------------------
# AC-008: first_to_pass second lane wins, third is skipped
# ---------------------------------------------------------------------------

def test_first_to_pass_second_lane_wins_third_skipped_AC_008(tmp_path):
    spec = _make_spec(
        "first_to_pass",
        gate=_gate(pass_threshold=0.5),
        lane_ids=("lane_a", "lane_b", "lane_c"),
        ledger_path=tmp_path / "ledger.jsonl",
    )
    # lane_a fails, lane_b passes, lane_c would pass but is skipped
    results = [
        _bad_result("lane_a"),
        _good_result("lane_b"),
        _good_result("lane_c"),
    ]
    runner = FactoryRunner()
    decision = runner.run(spec, results)

    assert decision.decision == "approved"
    assert decision.approved_lanes == ("lane_b",)
    statuses = {r.lane_id: r.status for r in decision.lane_results}
    assert statuses["lane_a"] == "rejected"
    assert statuses["lane_b"] == "approved"
    assert statuses["lane_c"] == "skipped"


# ---------------------------------------------------------------------------
# AC-009: first_to_pass none pass → failed, empty approved_lanes
# ---------------------------------------------------------------------------

def test_first_to_pass_none_pass_fails_AC_009(tmp_path):
    spec = _make_spec(
        "first_to_pass",
        gate=_gate(pass_threshold=0.99),
        lane_ids=("lane_a", "lane_b", "lane_c"),
        ledger_path=tmp_path / "ledger.jsonl",
    )
    results = [_bad_result("lane_a"), _bad_result("lane_b"), _bad_result("lane_c")]
    runner = FactoryRunner()
    decision = runner.run(spec, results)

    assert decision.decision == "failed"
    assert decision.approved_lanes == ()


# ---------------------------------------------------------------------------
# AC-010: ledger entry written with required fields
# ---------------------------------------------------------------------------

def test_ledger_entry_written_with_required_fields_AC_010(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    spec = _make_spec("best_of_n", ledger_path=ledger)
    runner = FactoryRunner()
    runner.run(spec, [_good_result("lane_a"), _bad_result("lane_b")])

    assert ledger.exists()
    with ledger.open() as fh:
        entry = json.loads(fh.readline())

    assert entry["run_id"] == "run_test"
    assert "timestamp" in entry
    assert entry["convergence_mode"] == "best_of_n"
    assert "gate" in entry
    assert "decision" in entry
    assert "approved_lanes" in entry
    assert "lane_summaries" in entry
    assert len(entry["lane_summaries"]) == 2
    # Each lane summary must have required keys
    for summary in entry["lane_summaries"]:
        assert "lane_id" in summary
        assert "status" in summary
        assert "gate_score" in summary
        assert "leakage_flags" in summary
        assert "error" in summary
        assert "elapsed_seconds" in summary


# ---------------------------------------------------------------------------
# AC-011: duplicate lane_id in spec raises FactoryError
# ---------------------------------------------------------------------------

def test_duplicate_lane_id_raises_factory_error_AC_011(tmp_path):
    gate = _gate()
    spec = FactorySpec(
        run_id="run_dup",
        convergence_mode="best_of_n",
        gate=gate,
        lanes=(_lane_spec("lane_a"), _lane_spec("lane_a")),
        seed=0,
        ledger_path=tmp_path / "ledger.jsonl",
    )
    runner = FactoryRunner()
    with pytest.raises(FactoryError, match="duplicate"):
        runner.run(spec, [])


# ---------------------------------------------------------------------------
# AC-012: unknown lane_id in result raises FactoryError
# ---------------------------------------------------------------------------

def test_unknown_lane_id_in_result_raises_factory_error_AC_012(tmp_path):
    spec = _make_spec(ledger_path=tmp_path / "ledger.jsonl")
    unknown = LaneResult(
        lane_id="lane_z", status="gate_pending",
        sharpe=1.0, max_drawdown=-0.1, annual_return=0.1,
        gate_score=None, leakage_flags=(), elapsed_seconds=1.0, error=None,
    )
    runner = FactoryRunner()
    with pytest.raises(FactoryError, match="lane_z"):
        runner.run(spec, [_good_result("lane_a"), unknown])


# ---------------------------------------------------------------------------
# AC-013: deterministic — same inputs produce same decision and ledger entry
# ---------------------------------------------------------------------------

def test_deterministic_same_inputs_same_decision_AC_013(tmp_path):
    results = [_good_result("lane_a"), _bad_result("lane_b")]

    ledger_1 = tmp_path / "ledger_1.jsonl"
    ledger_2 = tmp_path / "ledger_2.jsonl"

    spec_1 = _make_spec(ledger_path=ledger_1)
    spec_2 = _make_spec(ledger_path=ledger_2)

    runner = FactoryRunner()
    d1 = runner.run(spec_1, results)
    d2 = runner.run(spec_2, results)

    assert d1.decision == d2.decision
    assert d1.approved_lanes == d2.approved_lanes
    assert len(d1.lane_results) == len(d2.lane_results)
    for r1, r2 in zip(d1.lane_results, d2.lane_results):
        assert r1.lane_id == r2.lane_id
        assert r1.status == r2.status
        assert r1.gate_score == r2.gate_score

    entry_1 = json.loads(ledger_1.read_text().strip())
    entry_2 = json.loads(ledger_2.read_text().strip())
    # Same except timestamp
    for key in ("run_id", "convergence_mode", "gate", "decision", "approved_lanes"):
        assert entry_1[key] == entry_2[key], f"mismatch on {key}"
    for s1, s2 in zip(entry_1["lane_summaries"], entry_2["lane_summaries"]):
        assert s1["lane_id"] == s2["lane_id"]
        assert s1["status"] == s2["status"]
        assert s1["gate_score"] == s2["gate_score"]


# ---------------------------------------------------------------------------
# Extra edge cases (supporting spec invariants)
# ---------------------------------------------------------------------------

def test_score_lane_none_sharpe_scores_zero():
    gate = _gate()
    result = LaneResult(
        lane_id="lane_a", status="gate_pending",
        sharpe=None, max_drawdown=-0.08, annual_return=0.12,
        gate_score=None, leakage_flags=(), elapsed_seconds=1.0, error=None,
    )
    assert score_lane(result, gate) == 0.0


def test_convergence_gate_zero_pass_threshold_raises():
    with pytest.raises(FactoryError, match="pass_threshold"):
        ConvergenceGate(
            min_sharpe=0.8, max_drawdown=-0.15, min_annual_return=0.05,
            n_best=1, pass_threshold=0.0,
        )


def test_convergence_gate_negative_n_best_raises():
    with pytest.raises(FactoryError, match="n_best"):
        ConvergenceGate(
            min_sharpe=0.8, max_drawdown=-0.15, min_annual_return=0.05,
            n_best=0, pass_threshold=0.5,
        )


def test_best_of_n_returns_top_n(tmp_path):
    spec = _make_spec(
        "best_of_n",
        gate=_gate(n_best=2, pass_threshold=0.01),
        lane_ids=("lane_a", "lane_b", "lane_c"),
        ledger_path=tmp_path / "ledger.jsonl",
    )
    results = [_good_result("lane_a"), _good_result("lane_b"), _good_result("lane_c")]
    decision = FactoryRunner().run(spec, results)

    assert decision.decision == "approved"
    assert len(decision.approved_lanes) == 2
