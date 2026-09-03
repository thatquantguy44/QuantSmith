"""Quant Model Factory — spec 0061.

Coordinates parallel model-development lanes and converges them at a
shared quality gate, producing an append-only audit ledger.

Usage::

    from quantsmith.pipelines.quant_factory import (
        FactorySpec, LaneSpec, LaneResult, ConvergenceGate,
        FactoryRunner, score_lane,
    )
    from pathlib import Path

    gate = ConvergenceGate(
        min_sharpe=0.8, max_drawdown=-0.15, min_annual_return=0.05,
        n_best=1, pass_threshold=0.6,
    )
    spec = FactorySpec(
        run_id="run_001",
        convergence_mode="best_of_n",
        gate=gate,
        lanes=(
            LaneSpec(lane_id="lane_a", hypothesis="momentum", feature_set=("rsi",),
                     model_tag="ridge", backtest_config={}),
            LaneSpec(lane_id="lane_b", hypothesis="reversion", feature_set=("zscore",),
                     model_tag="ridge", backtest_config={}),
        ),
        seed=42,
        ledger_path=Path("factory_ledger.jsonl"),
    )

    results = [
        LaneResult(lane_id="lane_a", status="gate_pending", sharpe=1.2,
                   max_drawdown=-0.08, annual_return=0.12, gate_score=None,
                   leakage_flags=(), elapsed_seconds=10.0, error=None),
        LaneResult(lane_id="lane_b", status="gate_pending", sharpe=0.5,
                   max_drawdown=-0.22, annual_return=0.03, gate_score=None,
                   leakage_flags=(), elapsed_seconds=8.0, error=None),
    ]

    runner = FactoryRunner()
    decision = runner.run(spec, results)
    # decision.approved_lanes == ("lane_a",)

**Design invariants (spec RISK-001 – RISK-004):**

- ``score_lane`` and the three convergence helpers are pure; no I/O.
- Only ``_append_ledger`` writes to the filesystem (append-only JSONL).
- Duplicate ``lane_id`` or unknown ``lane_id`` in a result → ``FactoryError``
  before any scoring.
- ``ConvergenceGate.pass_threshold`` must be > 0.0 (validated at
  construction); gate params are recorded verbatim in every ledger entry
  so a reviewer can audit any decision from the ledger alone (NFR-004).
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONVERGENCE_MODES = frozenset({"best_of_n", "all_required", "first_to_pass"})

LANE_STATUSES = frozenset({
    "draft", "specified", "running", "gate_pending",
    "approved", "rejected", "skipped", "failed",
})

_EPSILON = 1e-9  # prevents division by zero in score_lane


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConvergenceGate:
    """Gate thresholds applied to every lane's metrics.

    ``pass_threshold`` must be > 0.0 (validated at construction via
    ``__post_init__``).  ``max_drawdown`` uses the negative convention
    (e.g. -0.15 means "no worse than 15% drawdown").
    """

    min_sharpe: float
    max_drawdown: float        # negative convention
    min_annual_return: float
    n_best: int                # used only by best_of_n
    pass_threshold: float      # score >= threshold → approved

    def __post_init__(self) -> None:
        if self.pass_threshold <= 0.0:
            raise FactoryError(
                f"ConvergenceGate.pass_threshold must be > 0.0; got {self.pass_threshold}"
            )
        if self.n_best < 1:
            raise FactoryError(
                f"ConvergenceGate.n_best must be >= 1; got {self.n_best}"
            )


@dataclass(frozen=True)
class LaneSpec:
    """Declaration of a single model-development lane."""

    lane_id: str
    hypothesis: str
    feature_set: Tuple[str, ...]
    model_tag: str
    backtest_config: Dict[str, Any]
    status: str = "draft"

    def __post_init__(self) -> None:
        if self.status not in LANE_STATUSES:
            raise FactoryError(f"LaneSpec.status {self.status!r} not in {LANE_STATUSES}")


@dataclass(frozen=True)
class LaneResult:
    """Result produced by a lane executor for one lane."""

    lane_id: str
    status: str
    sharpe: Optional[float]
    max_drawdown: Optional[float]   # negative convention
    annual_return: Optional[float]
    gate_score: Optional[float]     # set by FactoryRunner after scoring
    leakage_flags: Tuple[str, ...]
    elapsed_seconds: float
    error: Optional[str]

    def __post_init__(self) -> None:
        if self.status not in LANE_STATUSES:
            raise FactoryError(f"LaneResult.status {self.status!r} not in {LANE_STATUSES}")


@dataclass(frozen=True)
class FactorySpec:
    """Full specification for one factory run."""

    run_id: str
    convergence_mode: str
    gate: ConvergenceGate
    lanes: Tuple[LaneSpec, ...]
    seed: int
    ledger_path: Path
    deadline_seconds: float = math.inf

    def __post_init__(self) -> None:
        if self.convergence_mode not in CONVERGENCE_MODES:
            raise FactoryError(
                f"convergence_mode {self.convergence_mode!r} not in {CONVERGENCE_MODES}"
            )
        if not self.lanes:
            raise FactoryError("FactorySpec.lanes must not be empty")


@dataclass(frozen=True)
class FactoryDecision:
    """Output of a single factory run."""

    run_id: str
    decision: str                   # "approved" | "failed"
    approved_lanes: Tuple[str, ...]
    lane_results: Tuple[LaneResult, ...]
    elapsed_seconds: float


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class FactoryError(ValueError):
    """Raised on invalid factory configuration or runtime error."""


# ---------------------------------------------------------------------------
# Scoring — pure, no I/O (REQ-005, NFR-002)
# ---------------------------------------------------------------------------

def score_lane(result: LaneResult, gate: ConvergenceGate) -> float:
    """Return a score in [0, 1] for ``result`` against ``gate``.

    Returns 0.0 if any metric is None, if any leakage flag is set, or if
    ``result.error`` is set.  The three metric components are:

    - sharpe_component  = clip((sharpe)            / max(gate.min_sharpe * 2, ε), 0, 1)
    - dd_component      = clip((drawdown - gate.max_drawdown) / max(abs(gate.max_drawdown), ε), 0, 1)
    - return_component  = clip((ret - gate.min_annual_return) / max(gate.min_annual_return, ε), 0, 1)

    Final score = mean of the three components.
    """
    if result.error or result.leakage_flags:
        return 0.0
    if result.sharpe is None or result.max_drawdown is None or result.annual_return is None:
        return 0.0

    sharpe_component = _clip(
        result.sharpe / max(gate.min_sharpe * 2, _EPSILON), 0.0, 1.0
    )
    dd_component = _clip(
        (result.max_drawdown - gate.max_drawdown) / max(abs(gate.max_drawdown), _EPSILON),
        0.0, 1.0,
    )
    return_component = _clip(
        (result.annual_return - gate.min_annual_return) / max(gate.min_annual_return, _EPSILON),
        0.0, 1.0,
    )

    return (sharpe_component + dd_component + return_component) / 3.0


def _clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


# ---------------------------------------------------------------------------
# Convergence helpers — pure, no I/O (REQ-007 – REQ-009, NFR-002)
# ---------------------------------------------------------------------------

def _converge_best_of_n(
    scored: List[Tuple[LaneResult, float]],
    gate: ConvergenceGate,
    run_id: str,
    elapsed: float,
) -> FactoryDecision:
    """Best-of-N: top ``gate.n_best`` lanes by score that meet pass_threshold."""
    passing = sorted(
        [(r, s) for r, s in scored if s >= gate.pass_threshold],
        key=lambda x: x[1],
        reverse=True,
    )
    top = passing[: gate.n_best]

    approved_ids = tuple(r.lane_id for r, _ in top)
    approved_set = set(approved_ids)

    updated: List[LaneResult] = []
    for result, sc in scored:
        if result.lane_id in approved_set:
            status = "approved"
        else:
            status = "rejected"
        updated.append(_with_score_and_status(result, sc, status))

    decision = "approved" if approved_ids else "failed"
    return FactoryDecision(
        run_id=run_id,
        decision=decision,
        approved_lanes=approved_ids,
        lane_results=tuple(updated),
        elapsed_seconds=elapsed,
    )


def _converge_all_required(
    scored: List[Tuple[LaneResult, float]],
    gate: ConvergenceGate,
    run_id: str,
    elapsed: float,
) -> FactoryDecision:
    """All-required: every lane must meet pass_threshold."""
    failed_any = any(s < gate.pass_threshold for _, s in scored)

    if failed_any:
        updated = tuple(
            _with_score_and_status(r, s, "rejected" if s < gate.pass_threshold else "approved")
            for r, s in scored
        )
        return FactoryDecision(
            run_id=run_id,
            decision="failed",
            approved_lanes=(),
            lane_results=updated,
            elapsed_seconds=elapsed,
        )

    approved_ids = tuple(r.lane_id for r, _ in scored)
    updated = tuple(_with_score_and_status(r, s, "approved") for r, s in scored)
    return FactoryDecision(
        run_id=run_id,
        decision="approved",
        approved_lanes=approved_ids,
        lane_results=updated,
        elapsed_seconds=elapsed,
    )


def _converge_first_to_pass(
    scored: List[Tuple[LaneResult, float]],
    gate: ConvergenceGate,
    run_id: str,
    elapsed: float,
) -> FactoryDecision:
    """First-to-pass: first lane (in supplied order) meeting pass_threshold wins."""
    winner_idx: Optional[int] = None
    for i, (_, s) in enumerate(scored):
        if s >= gate.pass_threshold:
            winner_idx = i
            break

    if winner_idx is None:
        updated = tuple(_with_score_and_status(r, s, "rejected") for r, s in scored)
        return FactoryDecision(
            run_id=run_id,
            decision="failed",
            approved_lanes=(),
            lane_results=updated,
            elapsed_seconds=elapsed,
        )

    updated: List[LaneResult] = []
    for i, (result, sc) in enumerate(scored):
        if i < winner_idx:
            status = "rejected"
        elif i == winner_idx:
            status = "approved"
        else:
            status = "skipped"
        updated.append(_with_score_and_status(result, sc, status))

    approved_id = scored[winner_idx][0].lane_id
    return FactoryDecision(
        run_id=run_id,
        decision="approved",
        approved_lanes=(approved_id,),
        lane_results=tuple(updated),
        elapsed_seconds=elapsed,
    )


def _with_score_and_status(result: LaneResult, score: float, status: str) -> LaneResult:
    return LaneResult(
        lane_id=result.lane_id,
        status=status,
        sharpe=result.sharpe,
        max_drawdown=result.max_drawdown,
        annual_return=result.annual_return,
        gate_score=score,
        leakage_flags=result.leakage_flags,
        elapsed_seconds=result.elapsed_seconds,
        error=result.error,
    )


# ---------------------------------------------------------------------------
# Ledger — the only side effect (REQ-010, NFR-002)
# ---------------------------------------------------------------------------

def _append_ledger(
    path: Path,
    spec: FactorySpec,
    decision: FactoryDecision,
    start_time: float,
) -> None:
    """Append one JSON line to the factory ledger at ``path``.

    Raises ``FactoryError`` on ``OSError`` with the decision embedded in
    the message (RISK-002: the run is not silently lost).
    """
    entry: Dict[str, Any] = {
        "run_id": decision.run_id,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "convergence_mode": spec.convergence_mode,
        "gate": {
            "min_sharpe": spec.gate.min_sharpe,
            "max_drawdown": spec.gate.max_drawdown,
            "min_annual_return": spec.gate.min_annual_return,
            "n_best": spec.gate.n_best,
            "pass_threshold": spec.gate.pass_threshold,
        },
        "lane_summaries": [
            {
                "lane_id": r.lane_id,
                "status": r.status,
                "gate_score": r.gate_score,
                "leakage_flags": list(r.leakage_flags),
                "error": r.error,
                "elapsed_seconds": r.elapsed_seconds,
            }
            for r in decision.lane_results
        ],
        "decision": decision.decision,
        "approved_lanes": list(decision.approved_lanes),
        "elapsed_seconds": decision.elapsed_seconds,
    }

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError as exc:
        raise FactoryError(
            f"ledger write failed ({exc}); decision was: {json.dumps(entry)}"
        ) from exc


# ---------------------------------------------------------------------------
# FactoryRunner — the public entry point (REQ-006, REQ-011)
# ---------------------------------------------------------------------------

class FactoryRunner:
    """Scores lane results and converges them to a ``FactoryDecision``.

    The only public method is ``run``; it is deliberately not a module-level
    function so callers can subclass or inject a mock runner in tests.
    """

    def run(
        self,
        spec: FactorySpec,
        lane_results: Sequence[LaneResult],
    ) -> FactoryDecision:
        """Execute the factory run.

        Steps:
        1. Validate spec (unique lane_ids, non-empty, valid mode).
        2. Validate results (all lane_ids declared in spec).
        3. Score each result.
        4. Apply convergence mode.
        5. Append ledger entry.
        6. Return ``FactoryDecision``.

        Raises ``FactoryError`` on any validation failure or ledger write error.
        """
        start = time.monotonic()

        # --- Validation ---
        if spec.convergence_mode not in CONVERGENCE_MODES:
            raise FactoryError(
                f"unknown convergence_mode {spec.convergence_mode!r}"
            )
        if not spec.lanes:
            raise FactoryError("spec.lanes is empty")

        declared_ids = [lane.lane_id for lane in spec.lanes]
        if len(declared_ids) != len(set(declared_ids)):
            dupes = [lid for lid in declared_ids if declared_ids.count(lid) > 1]
            raise FactoryError(
                f"duplicate lane_id(s) in spec.lanes: {sorted(set(dupes))}"
            )
        declared_set = set(declared_ids)

        for result in lane_results:
            if result.lane_id not in declared_set:
                raise FactoryError(
                    f"LaneResult.lane_id {result.lane_id!r} not declared in spec.lanes"
                )

        # --- Scoring ---
        scored: List[Tuple[LaneResult, float]] = [
            (r, score_lane(r, spec.gate)) for r in lane_results
        ]

        # --- Convergence ---
        elapsed = time.monotonic() - start
        converge_fn = {
            "best_of_n": _converge_best_of_n,
            "all_required": _converge_all_required,
            "first_to_pass": _converge_first_to_pass,
        }[spec.convergence_mode]

        decision = converge_fn(scored, spec.gate, spec.run_id, elapsed)

        # --- Ledger ---
        _append_ledger(spec.ledger_path, spec, decision, start)

        return decision
