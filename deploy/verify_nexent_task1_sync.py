"""运行态验证：任务一正常对话应在同一次调用中返回最终结果。"""

from __future__ import annotations

from collections import Counter
import json
import os
import re
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clients.nexent_client import NexentClient
from scripts.runtime_env import load_runtime_env


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"missing required runtime variable: {name}")
    return value


def main() -> int:
    load_runtime_env(ROOT)
    client = NexentClient(
        _required_env("CCF_NEXENT_CONFIG_BASE"),
        _required_env("CCF_NEXENT_RUNTIME_BASE"),
        _required_env("CCF_NEXENT_EMAIL"),
        _required_env("CCF_NEXENT_PASSWORD"),
    )
    agent_id = int(_required_env("CCF_TASK1_AGENT_ID"))
    prompt = os.environ.get(
        "CCF_TASK1_SYNC_VERIFICATION_PROMPT",
        '请检查并清洗数据集“糖尿病全流程混合演示数据集”，执行任务一并汇报最终结果。',
    )

    started = time.time()
    event_types: list[str] = []
    final_answer = ""
    for event in client.run_agent_stream(agent_id, prompt):
        event_type = str(event.get("type", ""))
        if event_type:
            event_types.append(event_type)
        if event_type == "final_answer":
            final_answer = str(event.get("content", ""))

    event_counts = Counter(event_types)
    result = {
        "agent_id": agent_id,
        "elapsed_seconds": round(time.time() - started, 3),
        "event_type_counts": dict(event_counts),
        "tool_event_seen": any(item in event_counts for item in ("parse", "tool_call")),
        "final_answer_present": bool(final_answer.strip()),
        "async_status_exposed": any(
            marker in final_answer
            for marker in ("async_started", "后台处理中", "稍后使用以下调用查询", "get_task1_mixed_cleaning_status(run_id")
        ),
        "final_dataset_evidence_present": any(
            marker in final_answer
            for marker in ("delivery_dataset", "最终数据集", "最终交付", "数据集 ID")
        ),
        "success_evidence_present": bool(re.search(r"success|成功", final_answer, re.IGNORECASE)),
        "final_answer": final_answer,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    passed = (
        result["tool_event_seen"]
        and result["final_answer_present"]
        and not result["async_status_exposed"]
        and result["final_dataset_evidence_present"]
        and result["success_evidence_present"]
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
