"""通过 Nexent 任务一智能体查询真实后台状态，验证最终答复闭环。"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
import sys
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
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    parser.add_argument("--agent-id", type=int, default=int(_required_env("CCF_TASK1_AGENT_ID")))
    args = parser.parse_args()

    client = NexentClient(
        _required_env("CCF_NEXENT_CONFIG_BASE"),
        _required_env("CCF_NEXENT_RUNTIME_BASE"),
        _required_env("CCF_NEXENT_EMAIL"),
        _required_env("CCF_NEXENT_PASSWORD"),
    )
    final_answer = ""
    event_types: list[str] = []
    for event in client.run_agent_stream(
        args.agent_id,
        f"查询任务一运行编号 {args.run_id} 的真实状态，只能根据状态工具返回回答。",
    ):
        event_type = str(event.get("type", ""))
        if event_type:
            event_types.append(event_type)
        if event_type == "final_answer":
            final_answer = str(event.get("content", ""))

    print(
        json.dumps(
            {
                "agent_id": args.agent_id,
                "run_id": args.run_id,
                "event_type_counts": dict(Counter(event_types)),
                "final_answer": final_answer,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if final_answer and args.run_id in final_answer else 1


if __name__ == "__main__":
    raise SystemExit(main())
