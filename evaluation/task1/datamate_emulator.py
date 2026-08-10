# -*- coding: utf-8 -*-
"""任务一的本地 DataMate 调用仿真层。

这个模块有两个边界：

1. 自定义算子使用项目中实际的 operators/*/process.py；
2. DataMate 的 Mapper 基类、任务提交、状态查询和结果查询使用本地仿真。

因此报告可以验证“算子本身和编排协议是否能跑通”，但不能把这里的耗时、
任务状态或 HTTP 行为当作线上 DataMate 的性能与服务证明。
"""

from __future__ import annotations

import importlib.util
import os
import sys
import time
import types
from pathlib import Path
from typing import Any, Callable


class _SilentLogger:
    """避免本地评测被算子日志淹没。"""

    def __getattr__(self, _name: str):
        return lambda *_args, **_kwargs: None


class _MapperShim:
    """只实现当前自定义算子用到的 DataMate Mapper 接口。"""

    def __init__(self, *_args, **kwargs):
        self.text_key = kwargs.get("textKey", "text")
        self.filename_key = kwargs.get("filenameKey", "file_name")
        self.filepath_key = kwargs.get("filepathKey", "file_path")
        self.filetype_key = kwargs.get("filetypeKey", "file_type")
        self.data_key = kwargs.get("dataKey", "data")

    def read_file_first(self, sample: dict[str, Any]) -> dict[str, Any]:
        if self.text_key not in sample or sample.get(self.text_key) is None:
            path = sample.get(self.filepath_key)
            if path:
                sample[self.text_key] = Path(path).read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            else:
                sample[self.text_key] = ""
        return sample


def _install_runtime_shims() -> None:
    """安装算子导入所需的最小 DataMate/loguru 模块。"""

    datamate = types.ModuleType("datamate")
    core = types.ModuleType("datamate.core")
    base_op = types.ModuleType("datamate.core.base_op")
    base_op.Mapper = _MapperShim
    core.base_op = base_op
    datamate.core = core
    sys.modules["datamate"] = datamate
    sys.modules["datamate.core"] = core
    sys.modules["datamate.core.base_op"] = base_op

    loguru = types.ModuleType("loguru")
    loguru.logger = _SilentLogger()
    sys.modules["loguru"] = loguru


def _install_package_aliases() -> None:
    """安装算子源码中使用的 ops.user.* 导入路径。"""

    packages = [
        "ops",
        "ops.user",
        "ops.user.llm_noise_filter",
        "ops.user.medical_term_normalizer",
    ]
    for name in packages:
        module = types.ModuleType(name)
        module.__path__ = []
        sys.modules[name] = module


def _load_module(alias: str, path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(alias, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load operator module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    parent_name, _, child_name = alias.rpartition(".")
    if parent_name and parent_name in sys.modules:
        setattr(sys.modules[parent_name], child_name, module)
    return module


class OperatorRuntime:
    """加载实际自定义算子，并提供四种文件格式的本地执行入口。"""

    def __init__(
        self,
        project_root: Path,
        knowledge_base_dir: Path,
        runtime_dir: Path,
        *,
        noise_teacher: Callable[[str], str] | None = None,
    ):
        self.project_root = project_root
        self.knowledge_base_dir = knowledge_base_dir
        self.runtime_dir = runtime_dir
        self.noise_teacher = noise_teacher
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

        # noise_logger 在导入时读取该变量，必须在加载算子前指向本地评测目录。
        os.environ["NOISE_DB_PATH"] = str(self.runtime_dir / "noise_log.db")
        _install_runtime_shims()
        _install_package_aliases()
        self._load_dependencies()
        self._load_operators()
        self._build_instances()

    def _load_dependencies(self) -> None:
        operator_root = self.project_root / "operators"
        _load_module(
            "ops.user.llm_noise_filter.noise_logger",
            operator_root / "llm_noise_filter" / "noise_logger.py",
        )
        _load_module(
            "ops.user.llm_noise_filter.noise_rule_engine",
            operator_root / "llm_noise_filter" / "noise_rule_engine.py",
        )
        self.structured_utils = _load_module(
            "ops.user.llm_noise_filter.structured_clean_utils",
            operator_root / "llm_noise_filter" / "structured_clean_utils.py",
        )
        _load_module(
            "ops.user.medical_term_normalizer.medical_abbrev",
            operator_root / "medical_term_normalizer" / "medical_abbrev.py",
        )

    def _load_operators(self) -> None:
        operator_root = self.project_root / "operators"
        self.operator_modules = {
            "emoji": _load_module(
                "eval_task1_emoji_cleaner",
                operator_root / "emoji_cleaner" / "process.py",
            ),
            "term": _load_module(
                "eval_task1_medical_term_normalizer",
                operator_root / "medical_term_normalizer" / "process.py",
            ),
            "noise": _load_module(
                "eval_task1_llm_noise_filter",
                operator_root / "llm_noise_filter" / "process.py",
            ),
            "table": _load_module(
                "eval_task1_table_column_cleaner",
                operator_root / "table_column_cleaner" / "process.py",
            ),
            "json": _load_module(
                "eval_task1_json_field_cleaner",
                operator_root / "json_field_cleaner" / "process.py",
            ),
        }

    def _build_instances(self) -> None:
        term_kb = str(self.knowledge_base_dir / "term_kb.db")
        noise_kb = str(self.knowledge_base_dir / "noise_kb.db")
        self.operators = {
            "emoji": self.operator_modules["emoji"].EmojiCleaner(),
            "term": self.operator_modules["term"].MedicalTermNormalizer(
                termKbPath=term_kb,
                apiKey="",
                timeoutSeconds=1,
            ),
            "noise": self.operator_modules["noise"].LLMNoiseFilter(
                kbPath=noise_kb,
                apiKey="",
                timeoutSeconds=1,
            ),
            "table": self.operator_modules["table"].TableColumnCleaner(
                termKbPath=term_kb,
                noiseKbPath=noise_kb,
            ),
            "json": self.operator_modules["json"].JsonFieldCleaner(
                termKbPath=term_kb,
                noiseKbPath=noise_kb,
            ),
        }

        # 本地评测不访问任何外部模型。保留算子原有“未知缩写触发兜底”的判断，
        # 但把网络调用替换成原文返回；未知缩写是否需要真实 LLM 评测另行验证。
        self.operators["term"]._call_llm = lambda text: text
        self.operators["noise"]._call_llm = self.noise_teacher or (lambda text: text)

    def _sample(
        self,
        file_name: str,
        file_path: Path,
        file_format: str,
        text: str,
        case_id: str,
    ) -> dict[str, Any]:
        return {
            "instance_id": case_id,
            "file_name": file_name,
            "file_path": str(file_path),
            "file_type": file_format,
            "text": text,
            "data": text.encode("utf-8"),
        }

    def process(
        self,
        *,
        case_id: str,
        file_name: str,
        file_path: Path,
        file_format: str,
        output_path: Path,
    ) -> dict[str, Any]:
        """按任务一的源格式路由执行，并把结果落盘。"""

        started = time.perf_counter()
        raw_text = file_path.read_text(encoding="utf-8", errors="replace")
        sample = self._sample(file_name, file_path, file_format, raw_text, case_id)

        if file_format == "txt":
            sample = self.operators["emoji"].execute(sample)
            # 这些是 DataMate 内置基础算子的本地等价调用；项目自定义算子
            # 仍然使用上面的实际 process.py。
            sample["text"] = self.structured_utils.deterministic_field_clean(
                sample["text"],
                rule_engine=None,
                remove_noise=False,
            )
            sample = self.operators["term"].execute(sample)
            sample = self.operators["noise"].execute(sample)
            executed = [
                "EmojiCleaner(actual_operator)",
                "DataMate基础字符/HTML/URL清洗(emulated)",
                "MedicalTermNormalizer(actual_operator)",
                "LLMNoiseFilter(actual_operator, no-network fallback)",
            ]
        elif file_format == "csv":
            sample = self.operators["table"].execute(sample)
            executed = ["TableColumnCleaner(actual_operator)"]
        elif file_format in {"json", "jsonl"}:
            sample = self.operators["json"].execute(sample)
            executed = ["JsonFieldCleaner(actual_operator)"]
        else:
            raise ValueError(f"unsupported local evaluation format: {file_format}")

        output_text = str(sample.get("text", ""))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text, encoding="utf-8")
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        return {
            "case_id": case_id,
            "file_name": file_name,
            "file_format": file_format,
            "output_path": str(output_path),
            "status": "COMPLETED",
            "elapsed_ms": elapsed_ms,
            "operators_executed": executed,
            "emulated": True,
            "llm_network_calls": 0,
        }


class LocalDataMateEmulator:
    """复现任务一所需的 DataMate 数据集/任务/结果调用顺序。"""

    def __init__(self, runtime: OperatorRuntime, output_dir: Path):
        self.runtime = runtime
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.datasets: dict[str, dict[str, Any]] = {}
        self.tasks: dict[str, dict[str, Any]] = {}
        self.trace: list[dict[str, Any]] = []

    def register_dataset(self, cases: list[Any], input_dir: Path) -> dict[str, Any]:
        dataset_id = f"local-eval-dataset-{len(self.datasets) + 1:04d}"
        files = [
            {
                "case_id": case.case_id,
                "file_name": case.file_name,
                "file_type": case.file_format,
                "file_path": str(input_dir / case.file_name),
            }
            for case in cases
        ]
        dataset = {
            "id": dataset_id,
            "name": "task1-local-gold-corpus",
            "files": files,
            "emulated": True,
        }
        self.datasets[dataset_id] = dataset
        self.trace.append(
            {
                "sequence": len(self.trace) + 1,
                "method": "POST",
                "operation": "dataset.register",
                "endpoint": "/api/dm/datasets/register",
                "dataset_id": dataset_id,
                "file_count": len(files),
                "emulated": True,
            }
        )
        return dataset

    def submit_cleaning_task(self, dataset_id: str) -> dict[str, Any]:
        if dataset_id not in self.datasets:
            raise KeyError(f"unknown local dataset: {dataset_id}")
        task_id = f"local-eval-task-{len(self.tasks) + 1:04d}"
        task = {
            "id": task_id,
            "dataset_id": dataset_id,
            "status": "SUBMITTED",
            "files": [],
            "emulated": True,
        }
        self.tasks[task_id] = task
        self.trace.append(
            {
                "sequence": len(self.trace) + 1,
                "method": "POST",
                "operation": "cleaning_task.submit",
                "endpoint": "/api/cleaning/tasks",
                "task_id": task_id,
                "dataset_id": dataset_id,
                "emulated": True,
            }
        )
        return {"task_id": task_id, "status": task["status"], "emulated": True}

    def get_task_status(self, task_id: str) -> dict[str, Any]:
        task = self.tasks[task_id]
        self.trace.append(
            {
                "sequence": len(self.trace) + 1,
                "method": "GET",
                "operation": "cleaning_task.status",
                "endpoint": f"/api/cleaning/tasks/{task_id}",
                "task_id": task_id,
                "status": task["status"],
                "emulated": True,
            }
        )
        return {
            "task_id": task_id,
            "status": task["status"],
            "file_count": len(task["files"]),
            "emulated": True,
        }

    def execute_task(self, task_id: str) -> dict[str, Any]:
        task = self.tasks[task_id]
        dataset = self.datasets[task["dataset_id"]]
        task["status"] = "RUNNING"
        self.get_task_status(task_id)
        records = []
        for item in dataset["files"]:
            output_path = self.output_dir / item["file_name"]
            try:
                records.append(
                    self.runtime.process(
                        case_id=item["case_id"],
                        file_name=item["file_name"],
                        file_path=Path(item["file_path"]),
                        file_format=item["file_type"],
                        output_path=output_path,
                    )
                )
            except Exception as exc:
                records.append(
                    {
                        "case_id": item["case_id"],
                        "file_name": item["file_name"],
                        "file_format": item["file_type"],
                        "output_path": str(output_path),
                        "status": "FAILED",
                        "error": f"{type(exc).__name__}: {exc}",
                        "elapsed_ms": None,
                        "emulated": True,
                        "llm_network_calls": 0,
                    }
                )
        task["files"] = records
        task["status"] = (
            "COMPLETED"
            if records and all(item["status"] == "COMPLETED" for item in records)
            else "PARTIAL_SUCCESS"
        )
        self.get_task_status(task_id)
        return self.get_task_result(task_id)

    def get_task_result(self, task_id: str) -> dict[str, Any]:
        task = self.tasks[task_id]
        self.trace.append(
            {
                "sequence": len(self.trace) + 1,
                "method": "GET",
                "operation": "cleaning_task.result",
                "endpoint": f"/api/cleaning/tasks/{task_id}/result",
                "task_id": task_id,
                "status": task["status"],
                "file_count": len(task["files"]),
                "emulated": True,
            }
        )
        return {
            "task_id": task_id,
            "status": task["status"],
            "files": list(task["files"]),
            "emulated": True,
            "trace": list(self.trace),
        }
