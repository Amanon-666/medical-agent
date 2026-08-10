"""通过 Nexent 提交任务一，验证首轮不再提前生成完成报告。"""

from __future__ import annotations

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
    started = time.time()
    final_answer = ""
    pre_tool_thinking: list[str] = []
    tool_seen = False
    task1_agent_id = int(_required_env("CCF_TASK1_AGENT_ID"))
    prompt = _required_env("CCF_TASK1_VERIFICATION_PROMPT")
    for event in client.run_agent_stream(task1_agent_id, prompt):
        event_type = str(event.get("type", ""))
        if event_type == "parse":
            tool_seen = True
        elif event_type == "model_output_thinking" and not tool_seen:
            pre_tool_thinking.append(str(event.get("content", "")))
        elif event_type == "final_answer":
            final_answer = str(event.get("content", ""))

    pre_tool_text = "".join(pre_tool_thinking)
    run_ids = re.findall(r"\d{10}_[0-9a-f]{8}", final_answer)
    result = {
        "elapsed_seconds": round(time.time() - started, 3),
        "tool_seen": tool_seen,
        "run_ids": sorted(set(run_ids)),
        "pre_tool_claimed_completion": any(
            marker in pre_tool_text
            for marker in ("清洗完成", "最终交付数据集 ID", "45.82", "f82e3b12-7a4d-4c91-b5f6-8d2e1a9c0b47")
        ),
        "final_answer": final_answer,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if tool_seen and run_ids and not result["pre_tool_claimed_completion"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
