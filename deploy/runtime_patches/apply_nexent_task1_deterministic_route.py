"""为 Nexent 任务一请求增加可审计的确定性工具路由。"""

from pathlib import Path


RUNTIME_ROOTS = (
    Path("/opt/backend/.venv/lib/python3.10/site-packages/nexent"),
    Path("/opt/sdk/nexent"),
)
ROUTE_MARKER = "TASK1_DETERMINISTIC_ROUTE"
ROUTE_VERSION_MARKER = "TASK1_DETERMINISTIC_ROUTE_V3_BEGIN"
ROUTE_VERSION_BEGIN = "        # TASK1_DETERMINISTIC_ROUTE_V3_BEGIN\n"
OLD_V2_ROUTE_BEGIN = "        # TASK1_DETERMINISTIC_ROUTE_V2_BEGIN\n"
OLD_ROUTE_BEGIN = "        # Route Task 1 dataset operations from the user's quoted identifier before model planning.\n"
ROUTE_END = "        if additional_args is not None:\n"


def patch_core(path: Path) -> bool:
    """向指定 Nexent 运行时入口写入幂等路由补丁。"""
    text = path.read_text(encoding="utf-8")
    if ROUTE_VERSION_MARKER in text and "wait=True)\\nprint(result)\\n" in text:
        return False

    if "import json\n" not in text:
        raise RuntimeError(f"json import not found: {path}")
    if "import re\n" not in text:
        text = text.replace("import json\n", "import json\nimport re\n", 1)

    marker = "        self.task = task\n"
    insert = r"""        # TASK1_DETERMINISTIC_ROUTE_V3_BEGIN
        # Route Task 1 dataset operations from the user's quoted identifier before model planning.
        if "run_task1_mixed_cleaning" in self.tools or "inspect_dataset" in self.tools:
            quoted_values = re.findall(r'["“‘《]([^"”’》]{2,120})["”’》]', task)
            dataset_name = next(
                (
                    value.strip()
                    for value in quoted_values
                    if "数据集" in value
                    or "dataset" in value.lower()
                    or re.fullmatch(r"[0-9a-fA-F-]{36}", value.strip())
                ),
                None,
            )
            wants_cleaning = (
                any(flag in task.lower() for flag in ("清洗", "clean"))
                and not any(flag in task for flag in ("不清洗", "不要清洗", "未执行清洗"))
            )
            wants_inspection = any(
                flag in task.lower()
                for flag in ("只探查", "只查看", "只检查", "inspect only")
            )
            if dataset_name and wants_cleaning and "run_task1_mixed_cleaning" in self.tools:
                dataset_literal = json.dumps(dataset_name, ensure_ascii=False)
                task_name_literal = json.dumps(f"{dataset_name}_清洗任务", ensure_ascii=False)
                self.task = (
                    "[TASK1_DETERMINISTIC_ROUTE_V3] Your next response must contain only executable Python code "
                    "for the exact call below. Do not write a plan, result, metric, dataset ID, or completion claim "
                    "before executing it. Do not call inspect_dataset:\n"
                    f"result = run_task1_mixed_cleaning(dataset_id={dataset_literal}, "
                    f"task_name={task_name_literal}, wait=True)\nprint(result)\n"
                    "Do not answer until this call returns. After execution, report only its actual status, "
                    "final dataset, quality evidence, and performance; never invent IDs or metrics.\n"
                    f"Original user request: {task}"
                )
            elif dataset_name and wants_inspection and "inspect_dataset" in self.tools:
                dataset_literal = json.dumps(dataset_name, ensure_ascii=False)
                self.task = (
                    "[TASK1_DETERMINISTIC_ROUTE] Execute only this exact call, then answer from its return:\n"
                    f"result = inspect_dataset(dataset_id={dataset_literal})\nprint(result)\n"
                    f"Original user request: {task}"
                )
        # TASK1_DETERMINISTIC_ROUTE_V3_END
"""
    if ROUTE_VERSION_BEGIN in text:
        start = text.index(ROUTE_VERSION_BEGIN)
        end = text.index(ROUTE_END, start)
        text = text[:start] + insert + text[end:]
    elif OLD_V2_ROUTE_BEGIN in text:
        start = text.index(OLD_V2_ROUTE_BEGIN)
        end = text.index(ROUTE_END, start)
        text = text[:start] + insert + text[end:]
    elif OLD_ROUTE_BEGIN in text:
        start = text.index(OLD_ROUTE_BEGIN)
        end = text.index(ROUTE_END, start)
        text = text[:start] + insert + text[end:]
    else:
        if marker not in text:
            raise RuntimeError(f"task marker not found: {path}")
        text = text.replace(marker, marker + insert, 1)
    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    patched = []
    for root in RUNTIME_ROOTS:
        path = root / "core/agents/core_agent.py"
        if path.exists() and patch_core(path):
            patched.append(str(path))

    if not any(root.exists() for root in RUNTIME_ROOTS):
        raise RuntimeError("No Nexent runtime package root was found")
    print("patched:" if patched else "already patched", *patched, sep="\n")


if __name__ == "__main__":
    main()
