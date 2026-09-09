"""Securities lending agents for the agentic quant workflow.

Covers the full securities lending lifecycle:
  1. Data structuring from raw SQL results
  2. Borrow-rate analysis (GC / warm / hard-to-borrow classification)
  3. Inventory optimization (LP to maximize fee revenue)
  4. Counterparty and concentration risk
  5. Report synthesis

These agents are designed to plug into the same AgentPipeline / Blackboard
framework used by the existing portfolio-construction workflow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .framework import Blackboard
from .sql_data import SecLendingRawData


# ---------------------------------------------------------------------------
# Domain dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BorrowSecurity:
    """Aggregated view of a single security in the lending market."""

    cusip: str
    ticker: str
    rate_bps: float           # current borrow fee
    availability: int         # shares available to lend
    utilization: float        # fraction currently lent (0-1)
    rate_30d_avg: float       # 30-day average rate
    rate_30d_vol: float       # 30-day rate volatility
    classification: str       # 'GC', 'WARM', 'HTB'


@dataclass(frozen=True)
class LendingPosition:
    """A single open loan in the lending book."""

    cusip: str
    ticker: str
    counterparty: str
    quantity: int
    rate_bps: float
    balance: float
    daily_fee: float


@dataclass(frozen=True)
class CounterpartyRisk:
    """Risk metrics for a single counterparty."""

    counterparty: str
    total_exposure: float
    daily_fee: float
    num_positions: int
    concentration_pct: float  # share of total book


@dataclass
class SecLendingUniverse:
    """Processed securities lending universe used by downstream agents."""

    securities: List[BorrowSecurity] = field(default_factory=list)
    lending_book: List[LendingPosition] = field(default_factory=list)
    counterparty_risks: List[CounterpartyRisk] = field(default_factory=list)
    recall_count: int = 0
    total_book_balance: float = 0.0
    total_daily_fee: float = 0.0


@dataclass(frozen=True)
class OptimizedAllocation:
    """Result of inventory-optimization for a single security.

    ``counterparty`` is always ``None``: this LP allocates by security only
    (see ``InventoryOptimizationAgent``'s docstring) and does not decide
    which counterparty receives a loan -- that assignment, and its
    concentration limit, is ``SecLendingRiskAgent``'s job, checked against
    the actually-booked ``LendingPosition`` entries.
    """

    cusip: str
    ticker: str
    allocated_qty: int
    expected_fee: float
    counterparty: Optional[str] = None


@dataclass
class InventoryOptimizationResult:
    """Full result of the inventory-optimization agent."""

    allocations: List[OptimizedAllocation] = field(default_factory=list)
    total_expected_fee: float = 0.0
    utilization_rate: float = 0.0
    solver_status: str = "not_run"


# ---------------------------------------------------------------------------
# HTB classification thresholds (basis points) and day-count basis
# ---------------------------------------------------------------------------
# Default GC/WARM/HTB cutoffs. These are a stated, overridable model
# assumption (knowledge/short_term_markets: convention.seclend.
# demo_classification_thresholds), not sourced market truth -- see
# specs/0066-securities-lending-model-correction/ (gap D-0063-002). A caller
# who has a real classification policy should pass it to
# SecLendingUniverseAgent rather than relying on these defaults.
_DEFAULT_GC_THRESHOLD_BPS = 50.0      # general collateral: fee <= 50 bps
_DEFAULT_WARM_THRESHOLD_BPS = 200.0   # warm: 50 < fee <= 200 bps
                                        # hard-to-borrow: > 200 bps

# Securities-lending fee/rebate accrual day-count basis. ACT/360, matching
# knowledge/short_term_markets: convention.seclend.borrow_fee_act360_simple
# and convention.seclend.rebate_act360_simple, and financing_cost_analysis.
# py's own _DAY_COUNT_BASIS -- not the /252 trading-day approximation this
# module used before spec 0066 (gap D-0063-003).
_DAY_COUNT_BASIS = 360.0


def _classify(
    rate_bps: float,
    gc_threshold_bps: float = _DEFAULT_GC_THRESHOLD_BPS,
    warm_threshold_bps: float = _DEFAULT_WARM_THRESHOLD_BPS,
) -> str:
    if rate_bps <= gc_threshold_bps:
        return "GC"
    if rate_bps <= warm_threshold_bps:
        return "WARM"
    return "HTB"


# ---------------------------------------------------------------------------
# Agent 1 – Universe construction
# ---------------------------------------------------------------------------

class SecLendingUniverseAgent:
    """Transforms raw SQL results into a structured lending universe.

    Reads ``sec_lending_raw`` from the blackboard and writes
    ``sec_lending_universe``.  If no raw data is present (e.g. when running
    in demo mode without a real database) it generates synthetic data instead.
    """

    def __init__(
        self,
        synthetic_n: int = 10,
        seed: int = 42,
        gc_threshold_bps: float = _DEFAULT_GC_THRESHOLD_BPS,
        warm_threshold_bps: float = _DEFAULT_WARM_THRESHOLD_BPS,
    ) -> None:
        self.name = "sec_lending_universe_agent"
        self._synthetic_n = synthetic_n
        self._seed = seed
        self._gc_threshold_bps = gc_threshold_bps
        self._warm_threshold_bps = warm_threshold_bps

    def _classify(self, rate_bps: float) -> str:
        return _classify(rate_bps, self._gc_threshold_bps, self._warm_threshold_bps)

    # ------------------------------------------------------------------
    def run(self, blackboard: Blackboard) -> None:
        raw: Optional[SecLendingRawData] = blackboard.get("sec_lending_raw")

        if raw is not None and raw.borrow_history:
            universe = self._build_from_raw(raw)
        else:
            universe = self._build_synthetic()

        blackboard["sec_lending_universe"] = universe

    # ------------------------------------------------------------------
    def _build_from_raw(self, raw: SecLendingRawData) -> SecLendingUniverse:
        # Aggregate rate history per security
        history: Dict[str, List[float]] = {}
        latest: Dict[str, Dict[str, Any]] = {}
        for row in raw.borrow_history:
            t = row["ticker"]
            history.setdefault(t, []).append(float(row["rate_bps"]))
            latest[t] = row  # last row wins (sorted by date)

        securities = []
        for ticker, rows in latest.items():
            rates = history.get(ticker, [float(rows["rate_bps"])])
            arr = np.array(rates, dtype=float)
            rate = float(rows["rate_bps"])
            sec = BorrowSecurity(
                cusip=str(rows["cusip"]),
                ticker=ticker,
                rate_bps=rate,
                availability=int(rows["availability"]),
                utilization=float(rows["utilization"]),
                rate_30d_avg=float(arr.mean()),
                rate_30d_vol=float(arr.std(ddof=1)) if len(arr) > 1 else 0.0,
                classification=self._classify(rate),
            )
            securities.append(sec)

        book = [
            LendingPosition(
                cusip=str(r["cusip"]),
                ticker=str(r["ticker"]),
                counterparty=str(r["counterparty"]),
                quantity=int(r["quantity"]),
                rate_bps=float(r["rate_bps"]),
                balance=float(r["balance"]),
                daily_fee=float(r["fee_revenue"]),
            )
            for r in raw.lending_book
        ]

        total_exposure = sum(r.get("total_exposure", 0) for r in raw.counterparty_exposure)
        cp_risks = [
            CounterpartyRisk(
                counterparty=str(r["counterparty"]),
                total_exposure=float(r["total_exposure"]),
                daily_fee=float(r["daily_fee"]),
                num_positions=int(r["num_positions"]),
                concentration_pct=(
                    float(r["total_exposure"]) / total_exposure
                    if total_exposure > 0 else 0.0
                ),
            )
            for r in raw.counterparty_exposure
        ]

        total_balance = sum(p.balance for p in book)
        total_fee = sum(p.daily_fee for p in book)

        return SecLendingUniverse(
            securities=securities,
            lending_book=book,
            counterparty_risks=cp_risks,
            recall_count=len(raw.recent_recalls),
            total_book_balance=total_balance,
            total_daily_fee=total_fee,
        )

    # ------------------------------------------------------------------
    def _build_synthetic(self) -> SecLendingUniverse:
        rng = np.random.default_rng(self._seed)
        tickers = [
            ("037833100", "AAPL",  25,  5_000_000, 0.40),
            ("594918104", "MSFT",  20,  4_000_000, 0.35),
            ("02079K305", "GOOGL", 30,  2_000_000, 0.50),
            ("67066G104", "NVDA", 120,  1_000_000, 0.75),
            ("88160R101", "TSLA", 250,    500_000, 0.90),
            ("532457108", "LLY",   45,  1_500_000, 0.60),
            ("78462F103", "SPY",   10, 10_000_000, 0.20),
            ("46625H100", "JPM",   18,  3_500_000, 0.30),
            ("30303M102", "META", 180,    800_000, 0.85),
            ("023135106", "AMZN",  28,  3_000_000, 0.45),
        ][: self._synthetic_n]

        counterparties = ["GSCO", "MLCO", "BCAP", "CITI", "BARC", "DBAB"]
        securities = []
        book: List[LendingPosition] = []
        cp_totals: Dict[str, float] = {}
        cp_fees: Dict[str, float] = {}
        cp_pos: Dict[str, int] = {}

        for cusip, ticker, rate_base, avail, util_base in tickers:
            rate_history = rng.normal(rate_base, rate_base * 0.05, 30)
            rate_history = np.clip(rate_history, 5, None)
            rate = float(rate_history[-1])

            sec = BorrowSecurity(
                cusip=cusip,
                ticker=ticker,
                rate_bps=rate,
                availability=avail,
                utilization=float(np.clip(util_base + rng.normal(0, 0.03), 0.05, 0.99)),
                rate_30d_avg=float(rate_history.mean()),
                rate_30d_vol=float(rate_history.std(ddof=1)),
                classification=self._classify(rate),
            )
            securities.append(sec)

            # Lending book entries
            n_loans = int(rng.integers(1, 4))
            for _ in range(n_loans):
                cp = str(rng.choice(counterparties))
                qty = int(rng.integers(5_000, 200_000))
                price = float(rng.uniform(50, 800))
                balance = qty * price
                fee = balance * (rate / 10_000) / _DAY_COUNT_BASIS
                book.append(
                    LendingPosition(
                        cusip=cusip,
                        ticker=ticker,
                        counterparty=cp,
                        quantity=qty,
                        rate_bps=rate,
                        balance=balance,
                        daily_fee=fee,
                    )
                )
                cp_totals[cp] = cp_totals.get(cp, 0.0) + balance
                cp_fees[cp] = cp_fees.get(cp, 0.0) + fee
                cp_pos[cp] = cp_pos.get(cp, 0) + 1

        total_balance = sum(p.balance for p in book)
        total_fee = sum(p.daily_fee for p in book)
        cp_risks = [
            CounterpartyRisk(
                counterparty=cp,
                total_exposure=cp_totals[cp],
                daily_fee=cp_fees[cp],
                num_positions=cp_pos[cp],
                concentration_pct=cp_totals[cp] / total_balance if total_balance > 0 else 0.0,
            )
            for cp in cp_totals
        ]
        cp_risks.sort(key=lambda x: x.total_exposure, reverse=True)

        return SecLendingUniverse(
            securities=securities,
            lending_book=book,
            counterparty_risks=cp_risks,
            recall_count=int(rng.integers(3, 15)),
            total_book_balance=total_balance,
            total_daily_fee=total_fee,
        )


# ---------------------------------------------------------------------------
# Agent 2 – Borrow rate analysis
# ---------------------------------------------------------------------------

class BorrowRateAnalysisAgent:
    """Analyses borrow-rate dynamics and identifies opportunities.

    Writes ``borrow_rate_analysis`` to the blackboard with:
      - Classification breakdown (GC / WARM / HTB counts & weights)
      - Securities with elevated rate vs 30-day average (potential shorts)
      - Securities where utilization > threshold (supply squeeze risk)
    """

    def __init__(
        self,
        squeeze_util_threshold: float = 0.85,
        rate_spike_factor: float = 1.30,
    ) -> None:
        if not 0 < squeeze_util_threshold <= 1:
            raise ValueError("squeeze_util_threshold must be in (0, 1]")
        if rate_spike_factor <= 1:
            raise ValueError("rate_spike_factor must be > 1")
        self.name = "borrow_rate_analysis_agent"
        self._squeeze_threshold = squeeze_util_threshold
        self._spike_factor = rate_spike_factor

    def run(self, blackboard: Blackboard) -> None:
        blackboard.require("sec_lending_universe")
        universe: SecLendingUniverse = blackboard["sec_lending_universe"]

        secs = universe.securities
        total = len(secs)

        classification_counts = {"GC": 0, "WARM": 0, "HTB": 0}
        for s in secs:
            classification_counts[s.classification] += 1

        # Rate spikes vs 30d average
        rate_spikes = [
            s for s in secs
            if s.rate_30d_avg > 0 and s.rate_bps >= s.rate_30d_avg * self._spike_factor
        ]

        # Supply squeeze candidates
        squeeze_candidates = [
            s for s in secs if s.utilization >= self._squeeze_threshold
        ]

        # Fee opportunity: HTB / WARM sorted by rate
        fee_opportunities = sorted(
            [s for s in secs if s.classification in ("HTB", "WARM")],
            key=lambda x: x.rate_bps,
            reverse=True,
        )

        analysis = {
            "total_securities": total,
            "classification_counts": classification_counts,
            "rate_spike_securities": [s.ticker for s in rate_spikes],
            "squeeze_candidates": [s.ticker for s in squeeze_candidates],
            "top_fee_opportunities": [
                {"ticker": s.ticker, "rate_bps": s.rate_bps, "class": s.classification}
                for s in fee_opportunities[:5]
            ],
            "weighted_avg_rate": (
                float(
                    np.average(
                        [s.rate_bps for s in secs],
                        weights=[s.availability for s in secs],
                    )
                )
                if secs else 0.0
            ),
        }
        blackboard["borrow_rate_analysis"] = analysis


# ---------------------------------------------------------------------------
# Agent 3 – Inventory optimization (LP)
# ---------------------------------------------------------------------------

class InventoryOptimizationAgent:
    """Maximizes fee revenue subject to a balance-sheet limit.

    Formulation
    -----------
    Variables : x_i  (fraction of available inventory to lend for security i)
    Objective : maximize  sum_i  rate_i * avail_i * price_i * x_i  (fee revenue)
    Constraints:
      - 0 <= x_i <= 1  (can't lend more than available)
      - sum_i  avail_i * price_i * x_i  <= max_book_size  (balance sheet limit)

    Security-level only -- this LP has no counterparty dimension in its
    decision variables (``x`` is indexed by security, not by security x
    counterparty), and the SQL data model
    (:mod:`quantsmith.quant.agentic_quant.sql_data`) carries no
    per-security, per-counterparty demand to allocate against. Earlier
    versions of this docstring and ``max_cp_concentration`` implied a
    per-counterparty constraint that was never actually enforced here; see
    ``specs/0066-securities-lending-model-correction/`` (gap D-0063-004) for
    why that claim was removed rather than answered with fabricated
    per-counterparty demand data. Counterparty concentration remains
    ``SecLendingRiskAgent``'s job, checked against the actually-booked
    ``LendingPosition`` entries after allocation, not predicted here.

    Uses scipy.optimize.linprog when available; falls back to a greedy
    heuristic ranked by fee per unit of inventory.
    """

    def __init__(
        self,
        max_book_size: float = 1e9,
        max_cp_concentration: float = 0.30,
        assumed_price: float = 100.0,
    ) -> None:
        if max_book_size <= 0:
            raise ValueError("max_book_size must be positive")
        if not 0 < max_cp_concentration <= 1:
            raise ValueError("max_cp_concentration must be in (0, 1]")
        self.name = "inventory_optimization_agent"
        self._max_book = max_book_size
        # Accepted, not used: kept only so this agent shares a constructor
        # shape with SecLendingRiskAgent in sec_lending_workflow.py's
        # pipeline wiring. See the class docstring -- this LP has no
        # counterparty dimension to constrain.
        self._max_cp_conc = max_cp_concentration
        self._price = assumed_price

    def run(self, blackboard: Blackboard) -> None:
        blackboard.require("sec_lending_universe")
        universe: SecLendingUniverse = blackboard["sec_lending_universe"]
        secs = universe.securities

        if not secs:
            blackboard["inventory_optimization"] = InventoryOptimizationResult(
                solver_status="no_securities"
            )
            return

        result = self._optimize(secs)
        blackboard["inventory_optimization"] = result

    def _optimize(self, secs: List[BorrowSecurity]) -> InventoryOptimizationResult:
        # Notional value and fee rate per share
        notional = np.array([s.availability * self._price for s in secs], dtype=float)
        fee_per_notional = np.array(
            [s.rate_bps / 10_000 / _DAY_COUNT_BASIS for s in secs], dtype=float
        )

        try:
            from scipy.optimize import linprog  # type: ignore

            # Maximize fee = minimize negative fee
            c = -(notional * fee_per_notional)

            # Balance sheet constraint: sum(notional * x) <= max_book
            A_ub = [notional.tolist()]
            b_ub = [self._max_book]

            bounds = [(0.0, 1.0)] * len(secs)
            res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")

            if res.success:
                x = np.array(res.x)
                status = "optimal"
            else:
                x = self._greedy(notional, fee_per_notional, self._max_book)
                status = "greedy_fallback"

        except ImportError:
            x = self._greedy(notional, fee_per_notional, self._max_book)
            status = "greedy_scipy_missing"

        allocations = []
        total_fee = 0.0
        total_notional = 0.0
        for i, sec in enumerate(secs):
            alloc_qty = int(sec.availability * x[i])
            if alloc_qty == 0:
                continue
            exp_fee = alloc_qty * self._price * fee_per_notional[i]
            allocations.append(
                OptimizedAllocation(
                    cusip=sec.cusip,
                    ticker=sec.ticker,
                    allocated_qty=alloc_qty,
                    expected_fee=exp_fee,
                )
            )
            total_fee += exp_fee
            total_notional += alloc_qty * self._price

        total_avail_notional = float(notional.sum())
        util = total_notional / total_avail_notional if total_avail_notional > 0 else 0.0

        return InventoryOptimizationResult(
            allocations=sorted(allocations, key=lambda a: a.expected_fee, reverse=True),
            total_expected_fee=total_fee,
            utilization_rate=util,
            solver_status=status,
        )

    @staticmethod
    def _greedy(
        notional: np.ndarray, fee_per_notional: np.ndarray, max_book: float
    ) -> np.ndarray:
        """Rank by fee density; allocate greedily up to the balance-sheet cap.

        Used when scipy is unavailable or the LP solve fails, so it must
        respect the same balance-sheet constraint the LP does.
        """
        x = np.zeros(len(notional))
        remaining = max_book
        for i in np.argsort(-fee_per_notional):
            if remaining <= 0 or notional[i] <= 0:
                continue
            x[i] = min(1.0, remaining / notional[i])
            remaining -= notional[i] * x[i]
        return x


# ---------------------------------------------------------------------------
# Agent 4 – Counterparty and concentration risk
# ---------------------------------------------------------------------------

class SecLendingRiskAgent:
    """Evaluates counterparty concentration and single-name exposure limits.

    Flags positions that breach configurable thresholds and writes a
    ``sec_lending_risk`` dict to the blackboard.
    """

    def __init__(
        self,
        max_cp_concentration: float = 0.25,
        max_single_name_pct: float = 0.15,
        htb_alert_pct: float = 0.30,
    ) -> None:
        self.name = "sec_lending_risk_agent"
        self._max_cp = max_cp_concentration
        self._max_sn = max_single_name_pct
        self._htb_alert = htb_alert_pct

    def run(self, blackboard: Blackboard) -> None:
        blackboard.require("sec_lending_universe")
        universe: SecLendingUniverse = blackboard["sec_lending_universe"]

        # Counterparty breaches
        cp_breaches = [
            cp for cp in universe.counterparty_risks
            if cp.concentration_pct > self._max_cp
        ]

        # Single-name concentration from the lending book
        sn_exposure: Dict[str, float] = {}
        for pos in universe.lending_book:
            sn_exposure[pos.ticker] = sn_exposure.get(pos.ticker, 0.0) + pos.balance

        total = universe.total_book_balance
        sn_breaches = [
            {"ticker": t, "pct": v / total}
            for t, v in sn_exposure.items()
            if total > 0 and v / total > self._max_sn
        ]

        # HTB fraction of book
        htb_tickers = {
            s.ticker for s in universe.securities if s.classification == "HTB"
        }
        htb_balance = sum(
            p.balance for p in universe.lending_book if p.ticker in htb_tickers
        )
        htb_pct = htb_balance / total if total > 0 else 0.0
        htb_alert = htb_pct > self._htb_alert

        risk_summary = {
            "counterparty_breaches": [
                {"counterparty": cp.counterparty, "concentration_pct": cp.concentration_pct}
                for cp in cp_breaches
            ],
            "single_name_breaches": sn_breaches,
            "htb_pct_of_book": htb_pct,
            "htb_alert": htb_alert,
            "recall_count": universe.recall_count,
        }
        blackboard["sec_lending_risk"] = risk_summary


# ---------------------------------------------------------------------------
# Agent 5 – Report synthesis
# ---------------------------------------------------------------------------

class SecLendingReportAgent:
    """Synthesises all sec-lending agent outputs into a human-readable report."""

    def __init__(self) -> None:
        self.name = "sec_lending_report_agent"

    def run(self, blackboard: Blackboard) -> None:
        blackboard.require("sec_lending_universe")
        universe: SecLendingUniverse = blackboard["sec_lending_universe"]

        lines: List[str] = []
        lines.append("Securities Lending Workflow Report")
        lines.append("=" * 55)
        lines.append(f"Total book balance:  ${universe.total_book_balance:>15,.0f}")
        lines.append(f"Daily fee revenue:   ${universe.total_daily_fee:>15,.2f}")
        lines.append(
            f"Annualised estimate: ${universe.total_daily_fee * _DAY_COUNT_BASIS:>15,.0f}"
        )
        lines.append(f"Open recalls:        {universe.recall_count}")

        # Borrow rate analysis
        analysis = blackboard.get("borrow_rate_analysis")
        if analysis:
            cc = analysis["classification_counts"]
            lines.append("\nBorrow Classification Breakdown:")
            lines.append(
                f"  GC: {cc.get('GC', 0)} | WARM: {cc.get('WARM', 0)} | HTB: {cc.get('HTB', 0)}"
            )
            lines.append(
                f"  Weighted avg rate: {analysis['weighted_avg_rate']:.1f} bps"
            )
            if analysis["squeeze_candidates"]:
                lines.append(
                    "  Supply squeeze candidates: "
                    + ", ".join(analysis["squeeze_candidates"])
                )
            if analysis["rate_spike_securities"]:
                lines.append(
                    "  Rate spike alerts: "
                    + ", ".join(analysis["rate_spike_securities"])
                )
            if analysis["top_fee_opportunities"]:
                lines.append("  Top fee opportunities (HTB/WARM):")
                for opp in analysis["top_fee_opportunities"]:
                    lines.append(
                        f"    {opp['ticker']:<6} {opp['rate_bps']:.0f} bps  [{opp['class']}]"
                    )

        # Inventory optimisation
        opt: Optional[InventoryOptimizationResult] = blackboard.get("inventory_optimization")
        if opt and opt.allocations:
            lines.append("\nInventory Optimisation (Top 5 by Expected Fee):")
            lines.append(f"  Solver status: {opt.solver_status}")
            lines.append(f"  Inventory utilisation: {opt.utilization_rate:.1%}")
            lines.append(
                f"  Expected daily fee from optimised book: ${opt.total_expected_fee:,.2f}"
            )
            for alloc in opt.allocations[:5]:
                lines.append(
                    f"    {alloc.ticker:<6} qty={alloc.allocated_qty:>9,}  "
                    f"fee=${alloc.expected_fee:>10,.2f}"
                )

        # Counterparty exposure
        if universe.counterparty_risks:
            lines.append("\nCounterparty Exposure (Top 5):")
            for cp in universe.counterparty_risks[:5]:
                lines.append(
                    f"  {cp.counterparty:<6}  exposure=${cp.total_exposure:>12,.0f}  "
                    f"conc={cp.concentration_pct:.1%}  "
                    f"daily_fee=${cp.daily_fee:>8,.2f}"
                )

        # Risk flags
        risk = blackboard.get("sec_lending_risk")
        if risk:
            lines.append("\nRisk Flags:")
            if risk["counterparty_breaches"]:
                lines.append("  [!] Counterparty concentration breaches:")
                for b in risk["counterparty_breaches"]:
                    lines.append(
                        f"      {b['counterparty']} at {b['concentration_pct']:.1%}"
                    )
            if risk["single_name_breaches"]:
                lines.append("  [!] Single-name concentration breaches:")
                for b in risk["single_name_breaches"]:
                    lines.append(f"      {b['ticker']} at {b['pct']:.1%}")
            if risk["htb_alert"]:
                lines.append(
                    f"  [!] HTB exposure elevated: {risk['htb_pct_of_book']:.1%} of book"
                )
            if not any(
                [
                    risk["counterparty_breaches"],
                    risk["single_name_breaches"],
                    risk["htb_alert"],
                ]
            ):
                lines.append("  No risk limit breaches detected.")

        # ML demand forecast (optional)
        forecast = blackboard.get("borrow_demand_forecast")
        if forecast:
            lines.append("\nML Borrow Demand Forecast (next 5 trading days):")
            for item in forecast[:5]:
                lines.append(
                    f"  {item['ticker']:<6} predicted demand: {item['predicted_demand']:,.0f} "
                    f"shares  (confidence: {item.get('confidence', 'N/A')})"
                )

        blackboard["sec_lending_report"] = "\n".join(lines)
