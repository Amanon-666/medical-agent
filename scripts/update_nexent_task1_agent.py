"""只更新并发布任务一 Nexent 智能体，避免触碰任务二、任务三配置。"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.update_nexent_agents import (
    CONFIG_BASE,
    EMAIL,
    PASSWORD,
    RUNTIME_BASE,
    TASK1_AGENT_ID,
    TASK1_PROMPT,
    _agent_detail,
    _as_tool_list,
    _resolve_agent_id,
    _tool_id,
    _tool_name,
)
from clients.nexent_client import NexentClient


TASK1_TOOLS = [
    "upload_text_to_datamate",
    "inspect_dataset",
    "list_datamate_operators",
    "run_task1_mixed_cleaning",
    "get_task1_mixed_cleaning_status",
]


def main() -> None:
    client = NexentClient(CONFIG_BASE, RUNTIME_BASE, EMAIL, PASSWORD)
    client.login()
    client.scan_tools()
    tools = _as_tool_list(client.list_tools())
    name_to_id = {
        _tool_name(tool): _tool_id(tool)
        for tool in tools
        if _tool_name(tool) and _tool_id(tool) is not None
    }
    missing = [name for name in TASK1_TOOLS if name not in name_to_id]
    if missing:
        raise RuntimeError(f"missing Task 1 tools after scan: {missing}")

    agent_id = _resolve_agent_id(
        client,
        TASK1_AGENT_ID,
        ["medical_data_cleaner", "data_cleaner", "数据清洗", "任务一", "task1"],
    )
    detail = _agent_detail(client, agent_id)
    backup_dir = ROOT / "backups" / f"nexent_task1_agent_{time.strftime('%Y%m%d_%H%M%S')}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    (backup_dir / "agent_detail.json").write_text(
        json.dumps(detail, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tool_ids = sorted(name_to_id[name] for name in TASK1_TOOLS)
    update_result = client.update_agent(
        {
            "agent_id": agent_id,
            "enabled_tool_ids": tool_ids,
            "duty_prompt": TASK1_PROMPT,
            "constraint_prompt": (
                "只能通过已绑定的 MCP 工具完成任务；禁止 python_interpreter；禁止输出 Python/代码块/"
                "函数调用示例/伪代码工具调用；需要执行时第一步必须是真实工具调用；不得编造工具结果。"
            ),
            "few_shots_prompt": "",
            "max_steps": 20,
        }
    )
    publish_result = client.publish_agent(
        agent_id,
        version_name="task1-async-status-v2",
        release_note="Task 1 async status contract and parallel format processing",
    )
    print(
        json.dumps(
            {
                "agent_id": agent_id,
                "previous_version": detail.get("_current_version"),
                "backup": str(backup_dir),
                "tool_ids": tool_ids,
                "update_result": update_result,
                "publish_result": publish_result,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
