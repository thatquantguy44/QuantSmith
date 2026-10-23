"""Build the SYNTHETIC executable SFMeridian database for spec 0116.

The main SQLite file implements the ``main`` objects in
``catalog/fixture_db.catalog.json``. A deterministic sibling database is
attached as schema ``lending`` for that catalog's two namespaced objects.
Use :func:`connect` to reopen the pair. No random values, wall clock, real
security identifiers, counterparties, positions, or query text are used.

Disclosure: ``plugins/sfmeridian/fixtures/README.md``.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

BUSINESS_DATES = ("2026-10-21", "2026-10-22")

COUNTERPARTIES = (
    ("CP-A", "tier-1"),
    ("CP-B", "tier-2"),
    ("CP-C", "tier-3"),
)

LOANS = (
    ("LOAN-A-A", "SEC-A", "CP-A", "2026-10-21", 100, 1000.5, "OPEN"),
    ("LOAN-A-B", "SEC-A", "CP-B", "2026-10-21", 50, 500.5, "OPEN"),
    ("LOAN-B-B", "SEC-B", "CP-B", "2026-10-21", 200, 4000.5, "OPEN"),
    ("LOAN-C-C", "SEC-C", "CP-C", "2026-10-21", 80, 2400.5, "OPEN"),
    ("LOAN-A-A", "SEC-A", "CP-A", "2026-10-22", 120, 1200.5, "OPEN"),
    ("LOAN-A-B", "SEC-A", "CP-B", "2026-10-22", 60, 600.5, "CLOSED"),
    ("LOAN-B-B", "SEC-B", "CP-B", "2026-10-22", 180, 3600.5, "OPEN"),
    ("LOAN-C-C", "SEC-C", "CP-C", "2026-10-22", 100, 3000.5, "OPEN"),
)

INVENTORY = (
    ("SEC-A", "2026-10-21", 300, 3000.0),
    ("SEC-B", "2026-10-21", 400, 8000.0),
    ("SEC-C", "2026-10-21", 200, 6000.0),
    ("SEC-A", "2026-10-22", 300, 3000.0),
    ("SEC-B", "2026-10-22", 400, 8000.0),
    ("SEC-C", "2026-10-22", 250, 7500.0),
)

RATES = (
    ("SEC-A", "2026-10-21", 25.0, "GC"),
    ("SEC-B", "2026-10-21", 120.0, "WARM"),
    ("SEC-C", "2026-10-21", 500.0, "HTB"),
    ("SEC-A", "2026-10-22", 25.0, "GC"),
    ("SEC-B", "2026-10-22", 250.0, "HTB"),
    ("SEC-C", "2026-10-22", 450.0, "HTB"),
)

REVENUE = (
    ("LOAN-A-A", "SEC-A", "2026-10-21", "FUND-1", 7.0, 0.8),
    ("LOAN-B-B", "SEC-B", "2026-10-21", "FUND-2", 20.0, 0.75),
    ("LOAN-C-C", "SEC-C", "2026-10-21", "FUND-1", 30.0, 0.6),
    ("LOAN-A-A", "SEC-A", "2026-10-22", "FUND-1", 8.0, 0.8),
    ("LOAN-B-B", "SEC-B", "2026-10-22", "FUND-2", 25.0, 0.75),
    ("LOAN-C-C", "SEC-C", "2026-10-22", "FUND-1", 35.0, 0.6),
)

COLLATERAL = (
    ("LOAN-A-A", "2026-10-21", 1050.525),
    ("LOAN-A-B", "2026-10-21", 525.525),
    ("LOAN-B-B", "2026-10-21", 4120.515),
    ("LOAN-C-C", "2026-10-21", 2520.525),
    ("LOAN-A-A", "2026-10-22", 1260.525),
    ("LOAN-A-B", "2026-10-22", 630.525),
    ("LOAN-B-B", "2026-10-22", 3708.515),
    ("LOAN-C-C", "2026-10-22", 3150.525),
)

RECALLS = (
    ("RECALL-1", "CP-A", "SEC-A", "2026-10-20", 20, "client_sale", "OPEN"),
    ("RECALL-2", "CP-B", "SEC-B", "2026-10-22", 30, "sale", "OPEN"),
    ("RECALL-3", "CP-B", "SEC-C", "2026-10-23", 40, "vote", "OPEN"),
    ("RECALL-4", "CP-C", "SEC-C", "2026-10-21", 10, None, "CLOSED"),
)


def lending_path(path: Path) -> Path:
    """Return the deterministic attached-database path for ``path``."""
    path = Path(path)
    return path.with_name(f"{path.stem}.lending{path.suffix}")


def connect(path: Path, *, query_only: bool = True) -> sqlite3.Connection:
    """Open the fixture and attach its ``lending`` schema."""
    path = Path(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("ATTACH DATABASE ? AS lending", (str(lending_path(path)),))
    if query_only:
        conn.execute("PRAGMA query_only = ON")
    return conn


def _remove(path: Path) -> None:
    if path.exists():
        path.unlink()


def build(path: Path) -> dict[str, Any]:
    """Build both database files and return their deterministic manifest."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    attached = lending_path(path)
    _remove(path)
    _remove(attached)

    conn = sqlite3.connect(path)
    conn.execute("ATTACH DATABASE ? AS lending", (str(attached),))
    conn.executescript("""
        CREATE TABLE main.sec_lending_book (
            loan_id TEXT NOT NULL,
            security_id TEXT NOT NULL,
            counterparty_id TEXT NOT NULL,
            business_date DATE NOT NULL,
            on_loan_qty INTEGER NOT NULL,
            on_loan_value NUMERIC NOT NULL,
            status TEXT NOT NULL,
            PRIMARY KEY (loan_id, business_date)
        );
        CREATE TABLE main.lendable_inventory (
            security_id TEXT NOT NULL,
            business_date DATE NOT NULL,
            lendable_qty INTEGER NOT NULL,
            lendable_value NUMERIC NOT NULL,
            PRIMARY KEY (security_id, business_date)
        );
        CREATE TABLE main.borrow_rates (
            security_id TEXT NOT NULL,
            business_date DATE NOT NULL,
            fee_bps NUMERIC,
            borrow_category TEXT NOT NULL,
            PRIMARY KEY (security_id, business_date)
        );
        CREATE TABLE main.program_revenue (
            loan_id TEXT NOT NULL,
            security_id TEXT NOT NULL,
            business_date DATE NOT NULL,
            fund_id TEXT NOT NULL,
            fee_income NUMERIC NOT NULL,
            owner_split NUMERIC NOT NULL,
            PRIMARY KEY (loan_id, business_date)
        );
        CREATE TABLE main.collateral (
            loan_id TEXT NOT NULL,
            business_date DATE NOT NULL,
            collateral_value NUMERIC NOT NULL,
            PRIMARY KEY (loan_id, business_date)
        );
        CREATE TABLE main.counterparties (
            counterparty_id TEXT NOT NULL PRIMARY KEY,
            credit_tier TEXT
        );
        CREATE TABLE lending.recalls (
            recall_id TEXT NOT NULL PRIMARY KEY,
            counterparty_id TEXT NOT NULL,
            security_id TEXT NOT NULL,
            recall_date DATE NOT NULL,
            recall_qty INTEGER NOT NULL,
            reason TEXT,
            status TEXT NOT NULL
        );
        CREATE TABLE lending.counterparties (
            counterparty_id TEXT NOT NULL PRIMARY KEY,
            credit_tier TEXT
        );
    """)
    conn.executemany("INSERT INTO main.sec_lending_book VALUES (?, ?, ?, ?, ?, ?, ?)", LOANS)
    conn.executemany("INSERT INTO main.lendable_inventory VALUES (?, ?, ?, ?)", INVENTORY)
    conn.executemany("INSERT INTO main.borrow_rates VALUES (?, ?, ?, ?)", RATES)
    conn.executemany("INSERT INTO main.program_revenue VALUES (?, ?, ?, ?, ?, ?)", REVENUE)
    conn.executemany("INSERT INTO main.collateral VALUES (?, ?, ?)", COLLATERAL)
    conn.executemany("INSERT INTO main.counterparties VALUES (?, ?)", COUNTERPARTIES)
    conn.executemany("INSERT INTO lending.recalls VALUES (?, ?, ?, ?, ?, ?, ?)", RECALLS)
    conn.executemany("INSERT INTO lending.counterparties VALUES (?, ?)", COUNTERPARTIES)
    conn.commit()
    digest = logical_digest(conn)
    counts = row_counts(conn)
    conn.close()
    return {"logical_sha256": digest, "row_counts": counts}


def row_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Return row counts for every declared object."""
    out: dict[str, int] = {}
    for schema, name in _tables(conn):
        out[f"{schema}.{name}"] = int(conn.execute(
            f'SELECT COUNT(*) FROM "{schema}"."{name}"').fetchone()[0])
    return out


def logical_digest(conn: sqlite3.Connection) -> str:
    """Hash declared schemas and rows, excluding SQLite file metadata."""
    payload: list[dict[str, Any]] = []
    for schema, name in _tables(conn):
        columns = [tuple(row) for row in conn.execute(f'PRAGMA "{schema}".table_info("{name}")')]
        order = ", ".join(f'"{row[1]}"' for row in columns)
        rows = [list(row) for row in conn.execute(
            f'SELECT * FROM "{schema}"."{name}" ORDER BY {order}')]
        payload.append({"object": f"{schema}.{name}", "columns": columns, "rows": rows})
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _tables(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for schema in ("main", "lending"):
        rows = conn.execute(
            f'SELECT name FROM "{schema}".sqlite_master '
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        out.extend((schema, str(row[0])) for row in rows)
    return out


if __name__ == "__main__":
    print(json.dumps(build(Path(sys.argv[1])), sort_keys=True, indent=2))
