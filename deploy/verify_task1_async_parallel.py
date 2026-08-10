"""运行态验证：任务一应快速返回 run_id，并由后台更新最终状态。"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_server.task1.mixed_cleaning_service import run_task1_mixed_cleaning_service


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset")
    parser.add_argument("--task-name", default="任务一异步并发验证")
    args = parser.parse_args()

    started = time.time()
    result = run_task1_mixed_cleaning_service(
        dataset_id=args.dataset,
        task_name=args.task_name,
        wait=False,
    )
    print(
        json.dumps(
            {"return_seconds": round(time.time() - started, 3), "result": result},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.get("status") == "async_started" and result.get("run_id") else 1


if __name__ == "__main__":
    raise SystemExit(main())
