"""Workflow builders for securities lending and trading desk quant pipelines.

Provides ready-made pipelines that combine:
  - SQL or synthetic data ingestion
  - Borrow-rate analysis
  - Inventory optimisation
  - ML demand forecasting and anomaly detection
  - Risk monitoring
  - Report synthesis

Quick start::

    from quantsmith.quant.agentic_quant import run_sec_lending_workflow

    # Fully synthetic demo (no database required)
    report = run_sec_lending_workflow()
    print(report)

    # With a real database
    from quantsmith.quant.agentic_quant.sql_data import SQLiteDataSource
    src = SQLiteDataSource("path/to/lending.db")
    report = run_sec_lending_workflow(sql_source=src)
"""

from __future__ import annotations

from typing import Optional, Sequence

from .framework import Agent, AgentPipeline
from .sec_lending import (
    BorrowRateAnalysisAgent,
    InventoryOptimizationAgent,
    SecLendingRiskAgent,
    SecLendingReportAgent,
    SecLendingUniverseAgent,
)
from .ml_agents import (
    AnomalyDetectionAgent,
    BorrowDemandForecastAgent,
)
from .sql_data import SQLDataSource, SQLSecLendingDataAgent


def build_sec_lending_pipeline(
    *,
    sql_source: Optional[SQLDataSource] = None,
    lookback_days: int = 30,
    max_book_size: float = 1e9,
    max_cp_concentration: float = 0.25,
    max_single_name_pct: float = 0.15,
    squeeze_util_threshold: float = 0.85,
    include_ml_forecast: bool = True,
    include_anomaly_detection: bool = True,
) -> AgentPipeline:
    """Construct the full securities lending pipeline without running it.

    Parameters
    ----------
    sql_source:
        An :class:`~quantsmith.quant.agentic_quant.sql_data.SQLDataSource` pointing at your
        lending database.  When *None* the pipeline uses synthetic data so
        you can run the demo without any database.
    lookback_days:
        Days of borrow-rate history to fetch from SQL.
    max_book_size:
        Balance-sheet limit (in USD) for the inventory optimiser.
    max_cp_concentration:
        Maximum fraction of the lending book attributable to a single
        counterparty before a risk flag is raised.
    max_single_name_pct:
        Maximum single-name concentration in the book.
    squeeze_util_threshold:
        Utilisation rate above which a security is flagged as a supply-squeeze
        candidate.
    include_ml_forecast:
        Whether to append the :class:`~quantsmith.quant.agentic_quant.sec_lending.BorrowDemandForecastAgent`.
    include_anomaly_detection:
        Whether to append the :class:`~quantsmith.quant.agentic_quant.ml_agents.AnomalyDetectionAgent`.
    """
    agents: list[Agent] = []

    # 1. Data ingestion (SQL or synthetic)
    if sql_source is not None:
        agents.append(SQLSecLendingDataAgent(sql_source, lookback_days=lookback_days))

    # 2. Build structured lending universe
    agents.append(SecLendingUniverseAgent())

    # 3. Borrow rate analysis
    agents.append(
        BorrowRateAnalysisAgent(squeeze_util_threshold=squeeze_util_threshold)
    )

    # 4. Inventory optimisation
    agents.append(
        InventoryOptimizationAgent(
            max_book_size=max_book_size,
            max_cp_concentration=max_cp_concentration,
        )
    )

    # 5. Counterparty / concentration risk
    agents.append(
        SecLendingRiskAgent(
            max_cp_concentration=max_cp_concentration,
            max_single_name_pct=max_single_name_pct,
        )
    )

    # 6. Optional: ML demand forecast
    if include_ml_forecast:
        agents.append(BorrowDemandForecastAgent())

    # 7. Optional: anomaly detection
    if include_anomaly_detection:
        agents.append(AnomalyDetectionAgent())

    # 8. Report
    agents.append(SecLendingReportAgent())

    return AgentPipeline(agents)


def run_sec_lending_workflow(
    *,
    sql_source: Optional[SQLDataSource] = None,
    lookback_days: int = 30,
    max_book_size: float = 1e9,
    max_cp_concentration: float = 0.25,
    max_single_name_pct: float = 0.15,
    squeeze_util_threshold: float = 0.85,
    include_ml_forecast: bool = True,
    include_anomaly_detection: bool = True,
) -> str:
    """Execute the securities lending pipeline and return the report string.

    All parameters are forwarded to :func:`build_sec_lending_pipeline`.
    """
    pipeline = build_sec_lending_pipeline(
        sql_source=sql_source,
        lookback_days=lookback_days,
        max_book_size=max_book_size,
        max_cp_concentration=max_cp_concentration,
        max_single_name_pct=max_single_name_pct,
        squeeze_util_threshold=squeeze_util_threshold,
        include_ml_forecast=include_ml_forecast,
        include_anomaly_detection=include_anomaly_detection,
    )
    board = pipeline.run()
    return board.get("sec_lending_report", "(no report generated)")


def build_sec_lending_demo_pipeline() -> AgentPipeline:
    """Build the demo pipeline backed by a seeded in-memory SQLite database.

    This is the easiest way to exercise the full SQL → agent → report path
    without any external data dependencies::

        pipeline = build_sec_lending_demo_pipeline()
        board = pipeline.run()
        print(board["sec_lending_report"])
    """
    from .sql_data import SQLiteDataSource

    src = SQLiteDataSource(":memory:")
    src.seed_demo_data()
    return build_sec_lending_pipeline(sql_source=src)


def run_sec_lending_demo() -> str:
    """Run the fully seeded demo and return the report string."""
    pipeline = build_sec_lending_demo_pipeline()
    board = pipeline.run()
    return board.get("sec_lending_report", "(no report generated)")


# ---------------------------------------------------------------------------
# Combined portfolio + sec lending workflow
# ---------------------------------------------------------------------------

def build_combined_quant_pipeline(
    *,
    portfolio_tickers: Sequence[str] = ("AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"),
    target_return: float = 0.12,
    sql_source: Optional[SQLDataSource] = None,
    max_book_size: float = 5e8,
) -> AgentPipeline:
    """Build a combined portfolio + securities lending pipeline.

    This demonstrates how a quant supporting both a trading desk (portfolio
    construction / optimisation) and a securities lending desk (borrow-rate
    analytics, inventory optimisation) can run both workflows through a single
    blackboard pass.

    The pipeline sequence is:
      Data → Signal → Risk → Portfolio → Rebalancing
        → SecLending Universe → Borrow Analysis
        → Inventory Optimisation → Risk → Forecasts
        → Portfolio Report + Sec Lending Report
    """
    from .agents import (
        YahooFinanceDataAgent,
        FactorSignalAgent,
        RiskAgent,
        PortfolioConstructionAgent,
        RiskOverlayAgent,
        ReportAgent,
    )
    from .rebalancing import RebalancingOptimizationAgent

    agents: list[Agent] = []

    # Portfolio side
    try:
        import yfinance  # type: ignore  # noqa: F401
        agents.append(YahooFinanceDataAgent(list(portfolio_tickers)))
    except ImportError:
        from .agents import DataAgent
        agents.append(DataAgent(tickers=list(portfolio_tickers)))

    agents += [
        FactorSignalAgent(),
        RiskAgent(),
        PortfolioConstructionAgent(target_return=target_return),
        RiskOverlayAgent(),
        RebalancingOptimizationAgent(),
        ReportAgent(),
    ]

    # Sec lending side (appended to the same pipeline / blackboard)
    if sql_source is not None:
        agents.append(SQLSecLendingDataAgent(sql_source))

    agents += [
        SecLendingUniverseAgent(),
        BorrowRateAnalysisAgent(),
        InventoryOptimizationAgent(max_book_size=max_book_size),
        SecLendingRiskAgent(),
        BorrowDemandForecastAgent(),
        AnomalyDetectionAgent(),
        SecLendingReportAgent(),
    ]

    return AgentPipeline(agents)
