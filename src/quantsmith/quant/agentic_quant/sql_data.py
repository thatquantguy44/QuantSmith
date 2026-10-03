"""SQL data integration layer for quant and securities lending workflows.

Provides a lightweight abstraction over common database backends with
pre-built query templates for securities lending, trading desk analytics,
and general quant data access.  Designed for Python + SQL environments.

Supported backends (add credentials via environment variables):
  - SQLite   (built-in, ideal for local dev/testing)
  - PostgreSQL via psycopg2
  - SQL Server via pyodbc (common in institutional environments)
"""

from __future__ import annotations

import abc
import contextlib
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Sequence

import numpy as np

from .framework import Blackboard


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class SQLDataSource(abc.ABC):
    """Abstract SQL connection interface.  Implement for any backend."""

    @abc.abstractmethod
    def query(self, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        """Execute a SELECT and return rows as a list of dicts."""

    @abc.abstractmethod
    def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        """Execute a non-SELECT statement."""

    @contextlib.contextmanager
    def transaction(self) -> Generator[None, None, None]:
        """Context manager for transactional operations."""
        yield


# ---------------------------------------------------------------------------
# Concrete implementations
# ---------------------------------------------------------------------------

class SQLiteDataSource(SQLDataSource):
    """SQLite-backed source for local development and testing."""

    def __init__(self, database: str = ":memory:") -> None:
        import sqlite3

        self._conn = sqlite3.connect(database, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def query(self, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        cursor = self._conn.execute(sql, params)
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        self._conn.execute(sql, params)
        self._conn.commit()

    @contextlib.contextmanager
    def transaction(self) -> Generator[None, None, None]:
        with self._conn:
            yield

    def seed_demo_data(self) -> None:
        """Create and populate demo tables with synthetic sec-lending data."""
        ddl = [
            """
            CREATE TABLE IF NOT EXISTS borrow_rates (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                as_of_date TEXT    NOT NULL,
                cusip      TEXT    NOT NULL,
                ticker     TEXT    NOT NULL,
                rate_bps   REAL    NOT NULL,   -- borrow fee in basis points
                availability INTEGER NOT NULL, -- shares available
                utilization REAL   NOT NULL    -- 0-1 fraction lent out
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS positions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                as_of_date  TEXT NOT NULL,
                account     TEXT NOT NULL,
                cusip       TEXT NOT NULL,
                ticker      TEXT NOT NULL,
                quantity    INTEGER NOT NULL,
                market_value REAL NOT NULL,
                long_short  TEXT NOT NULL  -- 'L' or 'S'
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS sec_lending_book (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date    TEXT NOT NULL,
                cusip         TEXT NOT NULL,
                ticker        TEXT NOT NULL,
                counterparty  TEXT NOT NULL,
                quantity      INTEGER NOT NULL,
                rate_bps      REAL NOT NULL,
                balance       REAL NOT NULL,   -- collateral / loan balance
                fee_revenue   REAL NOT NULL,   -- accrued daily fee
                status        TEXT NOT NULL    -- 'OPEN' or 'CLOSED'
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS recalls (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                recall_date   TEXT NOT NULL,
                cusip         TEXT NOT NULL,
                ticker        TEXT NOT NULL,
                counterparty  TEXT NOT NULL,
                recall_qty    INTEGER NOT NULL,
                reason        TEXT NOT NULL    -- 'DIVIDEND', 'VOTE', 'SELL', 'RISK'
            )
            """,
        ]
        for stmt in ddl:
            self.execute(stmt)

        # Synthetic securities universe: GC, warm, and hard-to-borrow
        securities = [
            # (cusip, ticker, rate_bps_base, avail_base, util_base)
            ("037833100", "AAPL",  25,   5_000_000, 0.40),
            ("594918104", "MSFT",  20,   4_000_000, 0.35),
            ("02079K305", "GOOGL", 30,   2_000_000, 0.50),
            ("023135106", "AMZN",  28,   3_000_000, 0.45),
            ("67066G104", "NVDA", 120,   1_000_000, 0.75),  # warm
            ("88160R101", "TSLA", 250,     500_000, 0.90),  # hard-to-borrow
            ("532457108", "LLY",   45,   1_500_000, 0.60),
            ("78462F103", "SPY",   10,  10_000_000, 0.20),  # ETF / GC
            ("46625H100", "JPM",   18,   3_500_000, 0.30),
            ("30303M102", "META", 180,     800_000, 0.85),  # hard-to-borrow
        ]

        counterparties = ["GSCO", "MLCO", "BCAP", "CITI", "BARC", "DBAB"]
        rng = np.random.default_rng(42)

        # 30 days of borrow-rate history
        import datetime
        today = datetime.date.today()
        for days_back in range(30, -1, -1):
            date_str = (today - datetime.timedelta(days=days_back)).isoformat()
            for cusip, ticker, rate_base, avail_base, util_base in securities:
                noise = rng.normal(0, 0.05)
                rate = max(5.0, rate_base * (1 + noise))
                avail = max(1000, int(avail_base * rng.uniform(0.85, 1.15)))
                util = float(np.clip(util_base + rng.normal(0, 0.03), 0.05, 0.99))
                self.execute(
                    "INSERT INTO borrow_rates (as_of_date, cusip, ticker, rate_bps, "
                    "availability, utilization) VALUES (?, ?, ?, ?, ?, ?)",
                    (date_str, cusip, ticker, round(rate, 2), avail, round(util, 4)),
                )

        # Current lending book
        today_str = today.isoformat()
        for cusip, ticker, rate_base, avail_base, util_base in securities:
            n_loans = rng.integers(1, 4)
            for _ in range(n_loans):
                cp = str(rng.choice(counterparties))
                qty = int(rng.integers(5_000, 200_000))
                rate = max(5.0, rate_base * rng.uniform(0.95, 1.05))
                price = rng.uniform(50, 800)
                balance = qty * price
                fee = balance * (rate / 10_000) / 252  # one-day accrual
                self.execute(
                    "INSERT INTO sec_lending_book (trade_date, cusip, ticker, "
                    "counterparty, quantity, rate_bps, balance, fee_revenue, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')",
                    (today_str, cusip, ticker, cp, qty, round(rate, 2),
                     round(balance, 2), round(fee, 4)),
                )

        # Some recent recalls
        recall_reasons = ["SELL", "DIVIDEND", "VOTE", "RISK"]
        for _ in range(15):
            sec = securities[int(rng.integers(0, len(securities)))]
            cusip, ticker = sec[0], sec[1]
            days_ago = int(rng.integers(0, 10))
            recall_date = (today - datetime.timedelta(days=days_ago)).isoformat()
            cp = str(rng.choice(counterparties))
            qty = int(rng.integers(1_000, 50_000))
            reason = str(rng.choice(recall_reasons))
            self.execute(
                "INSERT INTO recalls (recall_date, cusip, ticker, counterparty, "
                "recall_qty, reason) VALUES (?, ?, ?, ?, ?, ?)",
                (recall_date, cusip, ticker, cp, qty, reason),
            )


class PostgreSQLDataSource(SQLDataSource):
    """PostgreSQL backend via psycopg2.

    Usage::

        import os
        src = PostgreSQLDataSource(
            host=os.environ["PG_HOST"],
            dbname=os.environ["PG_DB"],
            user=os.environ["PG_USER"],
            password=os.environ["PG_PASS"],
        )
    """

    def __init__(self, **connect_kwargs: Any) -> None:
        try:
            import psycopg2
            import psycopg2.extras
        except ImportError as exc:
            raise RuntimeError("psycopg2 is required for PostgreSQLDataSource") from exc

        self._conn = psycopg2.connect(**connect_kwargs)
        self._extras = psycopg2.extras

    def query(self, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        with self._conn.cursor(cursor_factory=self._extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]

    def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
        self._conn.commit()

    @contextlib.contextmanager
    def transaction(self) -> Generator[None, None, None]:
        try:
            yield
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise


class SQLServerDataSource(SQLDataSource):
    """SQL Server backend via pyodbc (common in institutional environments).

    Usage::

        import os
        src = SQLServerDataSource(
            dsn="DRIVER={ODBC Driver 18 for SQL Server};"
                f"SERVER={os.environ['MSSQL_HOST']};"
                f"DATABASE={os.environ['MSSQL_DB']};"
                "Trusted_Connection=yes;"
        )
    """

    def __init__(self, dsn: str, **connect_kwargs: Any) -> None:
        try:
            import pyodbc
        except ImportError as exc:
            raise RuntimeError("pyodbc is required for SQLServerDataSource") from exc

        self._conn = pyodbc.connect(dsn, **connect_kwargs)

    def query(self, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        cursor = self._conn.execute(sql, params)
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        self._conn.execute(sql, params)
        self._conn.commit()


# ---------------------------------------------------------------------------
# Pre-built query templates
# ---------------------------------------------------------------------------

BORROW_RATE_HISTORY_SQL = """
    SELECT as_of_date, cusip, ticker, rate_bps, availability, utilization
    FROM   borrow_rates
    WHERE  as_of_date >= ?
    ORDER  BY as_of_date, ticker
"""

CURRENT_LENDING_BOOK_SQL = """
    SELECT cusip, ticker, counterparty, quantity, rate_bps,
           balance, fee_revenue, status
    FROM   sec_lending_book
    WHERE  status = 'OPEN'
    ORDER  BY fee_revenue DESC
"""

COUNTERPARTY_EXPOSURE_SQL = """
    SELECT counterparty,
           SUM(balance)   AS total_exposure,
           SUM(fee_revenue) AS daily_fee,
           COUNT(DISTINCT cusip) AS num_positions
    FROM   sec_lending_book
    WHERE  status = 'OPEN'
    GROUP  BY counterparty
    ORDER  BY total_exposure DESC
"""

RECENT_RECALLS_SQL = """
    SELECT recall_date, cusip, ticker, counterparty, recall_qty, reason
    FROM   recalls
    WHERE  recall_date >= ?
    ORDER  BY recall_date DESC
"""

CONCENTRATION_RISK_SQL = """
    SELECT cusip, ticker,
           SUM(balance)     AS total_balance,
           SUM(quantity)    AS total_qty,
           AVG(rate_bps)    AS avg_rate,
           COUNT(DISTINCT counterparty) AS num_counterparties
    FROM   sec_lending_book
    WHERE  status = 'OPEN'
    GROUP  BY cusip, ticker
    ORDER  BY total_balance DESC
"""


# ---------------------------------------------------------------------------
# SQL-backed data agent for the blackboard pipeline
# ---------------------------------------------------------------------------

@dataclass
class SecLendingRawData:
    """Container for raw SQL query results used by downstream agents."""

    borrow_history: List[Dict[str, Any]] = field(default_factory=list)
    lending_book: List[Dict[str, Any]] = field(default_factory=list)
    counterparty_exposure: List[Dict[str, Any]] = field(default_factory=list)
    recent_recalls: List[Dict[str, Any]] = field(default_factory=list)
    concentration: List[Dict[str, Any]] = field(default_factory=list)


class SQLSecLendingDataAgent:
    """Fetches securities lending data from a SQL backend.

    Stores results on the blackboard under ``sec_lending_raw``.

    Parameters
    ----------
    source:
        An :class:`SQLDataSource` instance pointing at your database.
    lookback_days:
        Number of calendar days of borrow-rate history to retrieve.
    """

    def __init__(self, source: SQLDataSource, lookback_days: int = 30) -> None:
        if lookback_days < 1:
            raise ValueError("lookback_days must be at least 1")
        self.name = "sql_sec_lending_data_agent"
        self._source = source
        self._lookback_days = int(lookback_days)

    def run(self, blackboard: Blackboard) -> None:
        import datetime

        cutoff = (
            datetime.date.today() - datetime.timedelta(days=self._lookback_days)
        ).isoformat()

        raw = SecLendingRawData(
            borrow_history=self._source.query(BORROW_RATE_HISTORY_SQL, (cutoff,)),
            lending_book=self._source.query(CURRENT_LENDING_BOOK_SQL),
            counterparty_exposure=self._source.query(COUNTERPARTY_EXPOSURE_SQL),
            recent_recalls=self._source.query(RECENT_RECALLS_SQL, (cutoff,)),
            concentration=self._source.query(CONCENTRATION_RISK_SQL),
        )
        blackboard["sec_lending_raw"] = raw
