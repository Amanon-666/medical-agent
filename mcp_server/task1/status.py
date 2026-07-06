"""
任务一异步任务状态模块。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


TASK1_ASYNC_STATUS_ROOT = Path("/home/panyushuo/ccf-medical-ai/data/task1_mixed_agent_runs")


def task1_async_status_path(run_id: str) -> Path:
    return TASK1_ASYNC_STATUS_ROOT / run_id / "status.json"


def write_task1_async_status(run_id: str, payload: dict[str, Any]) -> None:
    path = task1_async_status_path(run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
