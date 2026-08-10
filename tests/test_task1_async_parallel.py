import json
import threading
from pathlib import Path

from deploy.runtime_patches.apply_nexent_task1_deterministic_route import patch_core
from mcp_server.task1.execution import run_parallel_group_jobs, should_start_background_job
from mcp_server.task1 import status as task1_status
from scripts.update_nexent_agents import TASK1_PROMPT


def test_nonblocking_task_always_starts_background_job():
    assert should_start_background_job(wait=False) is True
    assert should_start_background_job(wait=True) is False


def test_task1_agent_prompt_waits_for_final_result():
    assert "wait 必须设为 true" in TASK1_PROMPT
    assert "同一次调用中返回最终数据集和质量结果" in TASK1_PROMPT
    assert "正常任务一路径必须等待工具返回 success 后" in TASK1_PROMPT


def test_format_groups_execute_concurrently(monkeypatch):
    monkeypatch.setenv("CCF_TASK1_PARALLEL_GROUPS", "2")
    barrier = threading.Barrier(2, timeout=1)

    def worker(group):
        barrier.wait()
        return f"done-{group}"

    completed = []
    results = run_parallel_group_jobs(
        ["text", "csv"],
        worker,
        lambda group, _result, count, total: completed.append((group, count, total)),
    )

    assert results == {"text": "done-text", "csv": "done-csv"}
    assert sorted(count for _group, count, _total in completed) == [1, 2]


def test_status_updates_preserve_submission_details(monkeypatch, tmp_path):
    monkeypatch.setattr(task1_status, "TASK1_ASYNC_STATUS_ROOT", tmp_path)
    task1_status.write_task1_async_status(
        "run-1",
        {"status": "async_started", "operators_plan": {"text": ["Cleaner"]}},
    )
    task1_status.update_task1_async_status(
        "run-1",
        {"status": "running", "stage": "cleaning_groups"},
    )

    payload = json.loads((tmp_path / "run-1" / "status.json").read_text(encoding="utf-8"))
    assert payload["operators_plan"] == {"text": ["Cleaner"]}
    assert payload["status"] == "running"
    assert payload["stage"] == "cleaning_groups"
    assert payload["run_id"] == "run-1"


def test_nexent_route_uses_synchronous_call(tmp_path):
    core = tmp_path / "core_agent.py"
    core.write_text(
        "import json\n"
        "class Agent:\n"
        "    def run(self, task, additional_args=None):\n"
        "        self.task = task\n"
        "        # Route Task 1 dataset operations from the user's quoted identifier before model planning.\n"
        "        if True:\n"
        "            self.task = '[TASK1_DETERMINISTIC_ROUTE] wait=True'\n"
        "        if additional_args is not None:\n"
        "            pass\n",
        encoding="utf-8",
    )

    assert patch_core(core) is True
    patched = core.read_text(encoding="utf-8")
    assert "TASK1_DETERMINISTIC_ROUTE_V3_BEGIN" in patched
    assert "wait=True" in patched
    assert "wait=False" not in patched
    assert "Do not answer until this call returns" in patched
    assert "never invent IDs or metrics" in patched
    assert patch_core(core) is False


def test_nexent_route_upgrades_v2_without_duplicate_routes(tmp_path):
    core = tmp_path / "core_agent_v2.py"
    core.write_text(
        "import json\n"
        "import re\n"
        "class Agent:\n"
        "    def run(self, task, additional_args=None):\n"
        "        self.task = task\n"
        "        # TASK1_DETERMINISTIC_ROUTE_V2_BEGIN\n"
        "        self.task = '[TASK1_DETERMINISTIC_ROUTE_V2] wait=False'\n"
        "        # TASK1_DETERMINISTIC_ROUTE_V2_END\n"
        "        if additional_args is not None:\n"
        "            pass\n",
        encoding="utf-8",
    )

    assert patch_core(core) is True
    patched = core.read_text(encoding="utf-8")
    assert patched.count("TASK1_DETERMINISTIC_ROUTE_V3_BEGIN") == 1
    assert "TASK1_DETERMINISTIC_ROUTE_V2_BEGIN" not in patched
    assert "wait=True" in patched
    assert "wait=False" not in patched
    assert patch_core(core) is False
