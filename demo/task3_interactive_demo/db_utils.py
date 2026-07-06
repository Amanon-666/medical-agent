# -*- coding: utf-8 -*-
"""
可视化平台 SQLite 工具模块。

该模块集中管理只读连接、行读取和数据库路径检查。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def read_json_file(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def count_rows(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def scalar(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> Any:
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def query_dicts(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple[Any, ...] = (),
    limit: int | None = None,
) -> list[dict[str, Any]]:
    if limit is not None and "LIMIT" not in sql.upper():
        sql = f"{sql.rstrip()} LIMIT {int(limit)}"
    return rows_to_dicts(conn.execute(sql, params).fetchall())


def has_table(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name = ? AND type IN ('table', 'view')",
        (table_name,),
    ).fetchone()
    return row is not None
