from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict

from .contracts import DataArtifact


class SQLIntegrationAgent:
    """SQLite-first SQL integration for local workflow prototyping."""

    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)

    def setup_demo_data(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sales (
                    order_id INTEGER PRIMARY KEY,
                    region TEXT,
                    segment TEXT,
                    sales REAL,
                    profit REAL
                )
                """
            )
            rows = conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
            if rows == 0:
                conn.executemany(
                    "INSERT INTO sales(order_id, region, segment, sales, profit) VALUES (?, ?, ?, ?, ?)",
                    [
                        (1, "East", "Consumer", 1200.0, 240.0),
                        (2, "West", "Corporate", 940.0, 120.0),
                        (3, "South", "Consumer", 720.0, 90.0),
                    ],
                )
            conn.commit()
        finally:
            conn.close()

    def query(self, sql: str) -> DataArtifact:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(sql).fetchall()
            result = [dict(r) for r in rows]
            schema: Dict[str, str] = {}
            if result:
                for k, v in result[0].items():
                    schema[k] = type(v).__name__
            return DataArtifact(rows=result, schema=schema, lineage=[f"sql:{sql}"])
        finally:
            conn.close()
