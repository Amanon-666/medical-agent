"""
可视化平台数据来源维护模块。

该模块提供受保护的数据来源删除能力，用于清理演示环境中的重复来源。
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROTECTED_SOURCE_PREFIXES = (
    "QASystemOnMedicalKG:",
    "CBLUE:",
)


def maintenance_token_configured() -> bool:
    return bool(os.environ.get("CCF_DEMO_DELETE_TOKEN"))


def verify_maintenance_token(token: str | None) -> None:
    expected = os.environ.get("CCF_DEMO_DELETE_TOKEN")
    if not expected:
        raise PermissionError("服务器未配置 CCF_DEMO_DELETE_TOKEN，删除功能未启用。")
    if token != expected:
        raise PermissionError("维护口令不正确，未执行删除。")


def backup_database(db_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = backup_dir / f"{db_path.stem}.{stamp}.bak{db_path.suffix}"
    shutil.copy2(db_path, target)
    return target


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _fetch_source(conn: sqlite3.Connection, source_id: int) -> dict[str, Any] | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT source_id, source_name, source_type, source_path, source_url, record_count, created_at
        FROM kg_sources
        WHERE source_id = ?
        """,
        (source_id,),
    ).fetchone()
    return dict(row) if row else None


def delete_kg_source(
    kg_db: Path,
    analytics_db: Path,
    source_id: int,
    *,
    token: str | None,
    confirm_source_name: str | None,
    force_protected: bool = False,
) -> dict[str, Any]:
    """备份数据库后删除指定知识图谱来源及其关联记录。"""

    verify_maintenance_token(token)
    if source_id <= 0:
        raise ValueError("source_id 必须为正整数。")
    if not kg_db.exists():
        raise FileNotFoundError(f"KG 数据库不存在：{kg_db}")

    backup_dir = kg_db.parent / "backups" / "source_deletion"
    kg_backup = backup_database(kg_db, backup_dir)
    analytics_backup = backup_database(analytics_db, backup_dir) if analytics_db.exists() else None

    with sqlite3.connect(str(kg_db)) as conn:
        if not _table_exists(conn, "kg_sources"):
            raise RuntimeError("KG 数据库缺少 kg_sources 表。")
        source = _fetch_source(conn, source_id)
        if not source:
            return {
                "deleted": False,
                "reason": "source_not_found",
                "source_id": source_id,
                "kg_backup": str(kg_backup),
                "analytics_backup": str(analytics_backup) if analytics_backup else None,
            }
        if confirm_source_name and confirm_source_name != source["source_name"]:
            raise ValueError("确认的来源名称与数据库记录不一致，未执行删除。")
        is_protected = str(source["source_name"]).startswith(PROTECTED_SOURCE_PREFIXES)
        if is_protected and not force_protected:
            raise PermissionError("该来源属于初始基线数据；如确需删除，请勾选强制删除基线来源。")

        counts = {
            "triples": conn.execute("SELECT COUNT(*) FROM kg_triples WHERE source_id=?", (source_id,)).fetchone()[0],
            "quality_issues": conn.execute("SELECT COUNT(*) FROM kg_quality_issues WHERE source_id=?", (source_id,)).fetchone()[0],
            "aliases": conn.execute("SELECT COUNT(*) FROM kg_aliases WHERE source_id=?", (source_id,)).fetchone()[0],
            "source_entities": conn.execute("SELECT COUNT(*) FROM kg_entities WHERE source_id=?", (source_id,)).fetchone()[0],
        }
        conn.execute("DELETE FROM kg_triples WHERE source_id=?", (source_id,))
        conn.execute("DELETE FROM kg_quality_issues WHERE source_id=?", (source_id,))
        conn.execute("DELETE FROM kg_aliases WHERE source_id=?", (source_id,))
        orphan_cursor = conn.execute(
            """
            DELETE FROM kg_entities
            WHERE source_id = ?
              AND entity_id NOT IN (SELECT subject_id FROM kg_triples)
              AND entity_id NOT IN (SELECT object_id FROM kg_triples)
              AND entity_id NOT IN (SELECT entity_id FROM kg_aliases)
            """,
            (source_id,),
        )
        counts["orphan_entities_deleted"] = max(orphan_cursor.rowcount, 0)
        conn.execute("DELETE FROM kg_sources WHERE source_id=?", (source_id,))
        conn.commit()

    refresh_status: dict[str, Any]
    try:
        from kg.build_analytics_v2 import build_from_kg

        stats = build_from_kg(kg_db, analytics_db)
        refresh_status = {"status": "success", "stats": stats}
    except Exception as exc:  # 来源删除已完成，此处只记录分析库刷新失败。
        refresh_status = {"status": "failed", "error": str(exc)}

    return {
        "deleted": True,
        "source": source,
        "deleted_counts": counts,
        "kg_backup": str(kg_backup),
        "analytics_backup": str(analytics_backup) if analytics_backup else None,
        "refresh_analytics": refresh_status,
    }
