"""SQLite write-back target. Spec ``0080`` (T-020, first supported target —
owner decision, 2026-09-24).

A local, gitignored ``.sqlite3`` file, no credentials, no driver beyond the
standard library's own ``sqlite3`` module. Every statement is parameterized;
the table name comes from the contract this writer was built with, never
from a question or a caller-supplied string at call time (SQL-injection-safe
by construction, not by convention).

Idempotency is a real ``INSERT ... ON CONFLICT(record_key) DO NOTHING`` —
not application-level bookkeeping — and reversal is a real tombstone
``UPDATE``, never a ``DELETE``.
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Mapping, Sequence

from .writeback import SCHEMA_COLUMNS, WriteBackContract, WriteBackError

_COLUMN_LIST = ", ".join(SCHEMA_COLUMNS)
_PLACEHOLDERS = ", ".join(f":{c}" for c in SCHEMA_COLUMNS)


_SAFE_IDENT_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _quote_ident(name: str) -> str:
    if not _SAFE_IDENT_RE.match(name):
        raise WriteBackError(f"unsafe table name from contract: {name!r}")
    return f'"{name}"'


class SQLiteWriter:
    """The injected-writer protocol (``writeback.WriteBackWriter``) over
    stdlib ``sqlite3``. The table name is fixed at construction from the
    contract — never taken from a record, a question, or any later call.
    """

    def __init__(self, connection: sqlite3.Connection, contract: WriteBackContract):
        self._conn = connection
        self._table = _quote_ident(f"nl_analytics_writeback_{contract.name}")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        columns_sql = ", ".join(f'"{c}" TEXT' for c in SCHEMA_COLUMNS if c != "record_key")
        self._conn.execute(
            f'CREATE TABLE IF NOT EXISTS {self._table} ("record_key" TEXT PRIMARY KEY, {columns_sql})'
        )
        # A table created before a column joined the schema (``approver_handle``,
        # REQ-023) gains it here; old rows read it as NULL. Columns are only
        # ever added, never dropped or renamed.
        existing = {row[1] for row in self._conn.execute(f"PRAGMA table_info({self._table})")}
        for column in SCHEMA_COLUMNS:
            if column not in existing:
                self._conn.execute(f'ALTER TABLE {self._table} ADD COLUMN "{column}" TEXT')
        self._conn.commit()

    def write(self, records: Sequence[Mapping[str, object]]) -> int:
        cur = self._conn.cursor()
        written = 0
        for r in records:
            cur.execute(
                f"INSERT INTO {self._table} ({_COLUMN_LIST}) VALUES ({_PLACEHOLDERS}) "
                "ON CONFLICT(record_key) DO NOTHING",
                dict(r),
            )
            written += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        self._conn.commit()
        return written

    def reverse(self, run_id: str, reversed_at: int) -> int:
        cur = self._conn.execute(
            f'UPDATE {self._table} SET "reversed_at" = :reversed_at '
            'WHERE "run_id" = :run_id AND "reversed_at" IS NULL',
            {"run_id": run_id, "reversed_at": reversed_at},
        )
        self._conn.commit()
        return cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0

    def read(self, key: str) -> Sequence[Mapping[str, object]]:
        """A ``writeback.PriorInsightReader`` — bind as ``writer.read`` and
        pass it to ``writeback.prior_insights``.

        ``key`` is ``"{metric}|{dim1}|{dim2}..."`` (see
        ``respond.comparison_key``); parsed here into a ``metric`` /
        ``dimensions_json`` match, never interpolated into SQL text.
        """
        parts = key.split("|")
        metric, dims = parts[0], parts[1:]
        cur = self._conn.execute(
            f'SELECT {_COLUMN_LIST} FROM {self._table} WHERE "metric" = :metric AND "dimensions_json" = :dims',
            {"metric": metric, "dims": json.dumps(dims, sort_keys=True)},
        )
        rows = cur.fetchall()
        return [dict(zip(SCHEMA_COLUMNS, row)) for row in rows]


def open_writer(path: str, contract: WriteBackContract) -> SQLiteWriter:
    """Open (creating if needed) the local SQLite file at ``path`` for
    ``contract``. ``path`` is caller-supplied — this module never guesses
    one, and never talks to anything but the file it is given.
    """
    connection = sqlite3.connect(path)
    return SQLiteWriter(connection, contract)
