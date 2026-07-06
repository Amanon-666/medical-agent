# -*- coding: utf-8 -*-
"""
任务二知识图谱构建 MCP 工具。
"""

from __future__ import annotations

from mcp_server.task2.pipeline_service import run_kg_pipeline_service
from mcp_server.tools import mcp


@mcp.tool
def run_task2_kg_pipeline(
    dataset_id: str = "",
    task_name: str = "",
    max_records: int = 0,
    dry_run: bool = False,
    persist: bool = True,
    refresh_analytics: bool = True,
    backend: str = "offline",
) -> dict:
    """基于 DataMate 数据集执行任务二知识图谱构建。"""
    return run_kg_pipeline_service(
        dataset_id=dataset_id,
        task_name=task_name,
        max_records=max_records,
        dry_run=dry_run,
        persist=persist,
        refresh_analytics=refresh_analytics,
        backend=backend,
    )

