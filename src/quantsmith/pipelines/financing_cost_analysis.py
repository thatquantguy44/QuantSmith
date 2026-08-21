"""Reference pipeline for spec 0028 — financing cost analysis.

This module makes the ``0028-financing-cost-analysis`` spec *executable*. It is a
deterministic, standard-library-only implementation of the
``financing_cost_analysis`` agent's job: decompose the all-in cost of carry for a
book of financed positions (borrow fee, short rebate, repo/funding, margin),
restate returns net of that cost, flag a backtest that understates financing,
quantify the financing spread's sensitivity to rate shocks, and surface capacity
limits from scarce or expensive financing.

It continues the securities-financing chain — ``0022`` asset-class mechanics →
``0023`` securities lending → **``0028`` financing cost analysis** → backtest/risk
— and reconciles with ``0023``'s borrow-rate classification (GC/WARM/HTB) without
importing its runtime, which depends on ``numpy``: this module stays
dependency-free by accepting plain values (rate, classification) rather than a
``BorrowSecurity`` object.

Guarantees held by construction:

* REQ-001 / AC-001 — the all-in cost of carry is decomposed by leg (borrow fee,
  rebate, funding, margin), each computed on an explicit ACT/360 day-count basis.
* REQ-002 / AC-002 — a gross return is restated net of the aggregate financing
  cost, with the drag reported, not just the net number.
* REQ-003 / AC-003 — a backtest's reported financing cost is checked against the
  computed all-in cost and flagged when it understates it beyond tolerance.
* REQ-004 / AC-004 — the financing spread's sensitivity to a uniform rate shock is
  quantified by re-decomposing under the shock, not assumed linear.
* REQ-005 / AC-005 — capacity findings are keyed by borrow classification
  (GC/WARM/HTB), flagging where requested notional exceeds available.
* NFR-001 / AC-006 — a financing leg whose rate was "known" after its position's
  period ended is flagged as a look-ahead risk.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Sequence, Tuple

_DAY_COUNT_BASIS = 360.0
_LEG_KINDS = ("borrow_fee", "rebate", "funding", "margin")


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _days_between(start: str, end: str) -> int:
    days = (_parse_date(end) - _parse_date(start)).days
    if days < 0:
        raise ValueError(f"period_end {end} is before period_start {start}")
    return days


@dataclass(frozen=True)
class FinancingLeg:
    """One financing cost/credit component, with the date its rate was known.

    ``kind`` is one of ``borrow_fee``, ``rebate``, ``funding``, ``margin``.
    ``rebate`` is income (netted against cost), the other three are cost.
    """

    kind: str
    rate_bps: float
    rate_asof: str  # ISO date the rate was known as of (point-in-time)

    def __post_init__(self) -> None:
        if self.kind not in _LEG_KINDS:
            raise ValueError(f"unknown leg kind {self.kind!r}; must be one of {_LEG_KINDS}")
        if self.rate_bps < 0:
            raise ValueError("rate_bps must be non-negative; sign is handled by leg kind")


@dataclass(frozen=True)
class FinancedPosition:
    """A position that carries one or more financing legs over a period."""

    position_id: str
    side: str  # "long" | "short"
    notional: float
    period_start: str
    period_end: str
    legs: Tuple[FinancingLeg, ...]
    classification: str | None = None  # GC | WARM | HTB (short borrow; ties to 0023)

    def __post_init__(self) -> None:
        if self.side not in ("long", "short"):
            raise ValueError(f"side must be 'long' or 'short', got {self.side!r}")
        if self.notional <= 0:
            raise ValueError("notional must be positive")
        _days_between(self.period_start, self.period_end)  # validates ordering

    @property
    def days(self) -> int:
        return _days_between(self.period_start, self.period_end)


@dataclass(frozen=True)
class CostDecomposition:
    """Per-position all-in cost of carry, one leg at a time."""

    position_id: str
    days: int
    borrow_fee_cost: float
    rebate_income: float
    funding_cost: float
    margin_cost: float

    @property
    def net_financing_cost(self) -> float:
        return self.borrow_fee_cost - self.rebate_income + self.funding_cost + self.margin_cost


def _leg_cost(position: FinancedPosition, kind: str) -> float:
    total = 0.0
    for leg in position.legs:
        if leg.kind == kind:
            total += position.notional * (leg.rate_bps / 10_000.0) * (position.days / _DAY_COUNT_BASIS)
    return total


def decompose(positions: Sequence[FinancedPosition]) -> List[CostDecomposition]:
    """Per-position all-in cost-of-carry decomposition."""
    return [
        CostDecomposition(
            position_id=p.position_id,
            days=p.days,
            borrow_fee_cost=_leg_cost(p, "borrow_fee"),
            rebate_income=_leg_cost(p, "rebate"),
            funding_cost=_leg_cost(p, "funding"),
            margin_cost=_leg_cost(p, "margin"),
        )
        for p in positions
    ]


@dataclass(frozen=True)
class FinancingAwareReturns:
    """A gross return restated net of aggregate financing cost."""

    gross_return: float
    financing_cost: float
    net_return: float

    @property
    def drag(self) -> float:
        return self.gross_return - self.net_return


def financing_aware_returns(
    gross_return: float, decompositions: Sequence[CostDecomposition]
) -> FinancingAwareReturns:
    """Restate a gross return net of every position's net financing cost."""
    total_cost = sum(d.net_financing_cost for d in decompositions)
    return FinancingAwareReturns(
        gross_return=gross_return, financing_cost=total_cost, net_return=gross_return - total_cost
    )


def flag_understated_backtest(
    reported_cost: float, computed_cost: float, tolerance: float = 0.0
) -> List[str]:
    """Flags when a backtest's reported financing cost understates the all-in cost."""
    shortfall = computed_cost - reported_cost
    if shortfall > tolerance:
        return [
            f"backtest reports {reported_cost:.2f} financing cost but the all-in computed "
            f"cost is {computed_cost:.2f} -- understated by {shortfall:.2f}"
        ]
    return []


def spread_sensitivity(
    positions: Sequence[FinancedPosition],
    shocks_bps: Sequence[float] = (-100.0, -50.0, 0.0, 50.0, 100.0),
) -> Dict[float, float]:
    """Net financing cost under a uniform rate shock to borrow_fee/funding legs.

    Rebate and margin legs are held fixed; a rate shock is what actually moves
    what a short pays to borrow and what a levered long pays to fund.
    """
    results: Dict[float, float] = {}
    for shock in shocks_bps:
        shocked = [
            FinancedPosition(
                position_id=p.position_id,
                side=p.side,
                notional=p.notional,
                period_start=p.period_start,
                period_end=p.period_end,
                classification=p.classification,
                legs=tuple(
                    FinancingLeg(kind=leg.kind, rate_bps=max(0.0, leg.rate_bps + shock), rate_asof=leg.rate_asof)
                    if leg.kind in ("borrow_fee", "funding")
                    else leg
                    for leg in p.legs
                ),
            )
            for p in positions
        ]
        results[shock] = sum(d.net_financing_cost for d in decompose(shocked))
    return results


@dataclass(frozen=True)
class CapacityFinding:
    """Whether a short book's requested notional exceeds available borrow, by class."""

    classification: str
    requested_notional: float
    available_notional: float
    constrained: bool


def capacity_limit(
    positions: Sequence[FinancedPosition],
    available_notional_by_classification: Dict[str, float],
) -> List[CapacityFinding]:
    """Capacity findings keyed by borrow classification (GC/WARM/HTB)."""
    requested: Dict[str, float] = {}
    for p in positions:
        if p.side == "short" and p.classification:
            requested[p.classification] = requested.get(p.classification, 0.0) + p.notional
    return [
        CapacityFinding(
            classification=classification,
            requested_notional=requested_notional,
            available_notional=available_notional_by_classification.get(classification, float("inf")),
            constrained=requested_notional > available_notional_by_classification.get(classification, float("inf")),
        )
        for classification, requested_notional in requested.items()
    ]


def check_point_in_time(positions: Sequence[FinancedPosition]) -> List[str]:
    """Flags a financing leg whose rate was known after its position's period ended."""
    findings = []
    for p in positions:
        period_end = _parse_date(p.period_end)
        for leg in p.legs:
            if _parse_date(leg.rate_asof) > period_end:
                findings.append(
                    f"{p.position_id}: {leg.kind} rate_asof {leg.rate_asof} is after "
                    f"period_end {p.period_end} -- look-ahead risk"
                )
    return findings


def position_from_borrow_rate(
    *,
    position_id: str,
    rate_bps: float,
    classification: str,
    notional: float,
    period_start: str,
    period_end: str,
    rate_asof: str,
    rebate_rate_bps: float = 0.0,
) -> FinancedPosition:
    """Build a short ``FinancedPosition`` from securities-lending-style borrow terms.

    Accepts plain values (``rate_bps``/``classification``) rather than importing
    ``quantsmith.quant.agentic_quant.sec_lending.BorrowSecurity`` directly, so this
    dependency-free module never pulls in ``numpy`` transitively. A caller already
    holding a ``BorrowSecurity`` (spec ``0023``) passes its ``rate_bps`` and
    ``classification`` fields through.
    """
    legs = [FinancingLeg(kind="borrow_fee", rate_bps=rate_bps, rate_asof=rate_asof)]
    if rebate_rate_bps:
        legs.append(FinancingLeg(kind="rebate", rate_bps=rebate_rate_bps, rate_asof=rate_asof))
    return FinancedPosition(
        position_id=position_id,
        side="short",
        notional=notional,
        period_start=period_start,
        period_end=period_end,
        legs=tuple(legs),
        classification=classification,
    )
