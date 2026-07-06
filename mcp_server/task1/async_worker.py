"""任务一混合清洗后台执行入口。"""

from __future__ import annotations

import argparse
import json
import sys

from mcp_server.task1.mixed_cleaning_service import run_task1_mixed_cleaning_service
from mcp_server.task1.status import write_task1_async_status


def main() -> int:
    parser = argparse.ArgumentParser(description="执行任务一混合格式清洗后台任务")
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--task-name", default="")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    write_task1_async_status(
        args.run_id,
        {
            "status": "running",
            "dataset_id": args.dataset_id,
            "task_name": args.task_name,
        },
    )
    result = run_task1_mixed_cleaning_service(
        dataset_id=args.dataset_id,
        task_name=args.task_name,
        wait=True,
    )
    result.setdefault("run_id", args.run_id)
    result.setdefault("status", "success" if result.get("status") not in {"error", "failed"} else "error")
    write_task1_async_status(args.run_id, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())
