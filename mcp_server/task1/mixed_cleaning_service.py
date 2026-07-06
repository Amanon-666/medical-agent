"""
任务一混合格式清洗编排服务。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from mcp_server.config import DATASET_VOLUME
from mcp_server.datamate.resolver import _task2_resolve_datamate_dataset
from mcp_server.task1.chains import (
    task1_mixed_chain_descriptions as _task1_mixed_chain_descriptions,
    task1_mixed_chain_map as _task1_mixed_chain_map,
)
from mcp_server.task1.datasets import (
    TASK1_FILE_GROUPS,
    classify_source_file,
    count_source_file_groups,
    datamate_dataset_host_path,
)
from mcp_server.task1.evidence import summarize_cleaning_evidence
from mcp_server.task1.status import (
    task1_async_status_path as _task1_async_status_path,
    write_task1_async_status as _write_task1_async_status,
)


ROOT = Path(__file__).resolve().parents[2]
_DATASET_VOLUME = DATASET_VOLUME


def run_task1_mixed_cleaning_service(
    dataset_id: str,
    task_name: str = "",
    wait: bool = False,
    async_file_threshold: int = 50,
) -> dict:
    """执行任务一混合格式数据集清洗编排。

    Use this tool when a DataMate dataset contains mixed txt/csv/json files or
    when the user asks for Task 1 final delivery. The tool does not rely on the
    agent to guess a single chain. It performs:

    dataset_id can be a DataMate UUID or the exact dataset name from the UI. If
    the user gives a near-match name with a unique timestamp suffix, the shared
    DataMate dataset resolver will resolve it before reading files.

    1. inspect source files and group them by file type
    2. create per-type temporary DataMate datasets
    3. run the appropriate cleaning chain:
       - txt: deterministic text cleaning + MedicalTermNormalizer + LLMNoiseFilter
       - csv: TableColumnCleaner, preserving CSV
       - json/jsonl: JsonFieldCleaner, preserving JSON/JSONL
    4. collect cleaned source-format outputs
    5. register one final Task 1 delivery dataset
    6. register DataMate quality tags, lineage, and statistics

    For large datasets this tool starts an async background job by default and
    returns immediately with run_id, source grouping and operators_plan. Call
    get_task1_mixed_cleaning_status(run_id) later to fetch progress/result.

    Set wait=True only for small datasets or explicit blocking tests.
    Synchronous return includes the source grouping, per-type task IDs, final
    delivery dataset ID/name, and quality totals. This is the recommended path
    for mixed-format Task 1 datasets. Unified JSONL conversion is intentionally
    not a default Task 1 step; use it at Task 2 entry or when explicitly requested.
    """
    import json as _json
    import subprocess as _sp
    import time as _time
    import uuid as _uuid
    from pathlib import Path as _Path

    from mcp_server.task1.runtime_helpers.datamate_ops import register_dataset, run_sudo  # noqa: E402
    from mcp_server.task1.runtime_helpers.quality_eval import evaluate_file, summarize  # noqa: E402
    from mcp_server.task1.runtime_helpers.governance import register_governance  # noqa: E402
    from mcp_server.task1.runtime_helpers.preserved_pipeline import (  # noqa: E402
        collect_outputs,
        merge_numbered_text_chunks,
        run_pipeline,
        register_final_delivery,
        check_db_health,
        postprocess_structured_outputs,
        restore_structured_output_suffix,
    )
    from mcp_server.task1.preserved_cleanup import cleanup_preserved_files  # noqa: E402

    DATASET_VOL = _DATASET_VOLUME
    did = (dataset_id or "").strip()
    if not did:
        return {"status": "error", "error": "dataset_id is required"}
    try:
        resolved_dataset, resolution_candidates = _task2_resolve_datamate_dataset(did)
        requested_identifier = did
        did = resolved_dataset["id"]
        source_name = resolved_dataset["name"]
    except Exception as exc:
        return {"status": "error", "error": str(exc), "requested_identifier": did}

    def _psql(sql: str) -> list[list[str]]:
        completed = _sp.run(
            [
                "docker",
                "exec",
                "-i",
                "datamate-database",
                "psql",
                "-U",
                "postgres",
                "-d",
                "datamate",
                "-t",
                "-A",
                "-F",
                "\t",
            ],
            input=sql,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
        return [line.split("\t") for line in completed.stdout.splitlines() if "\t" in line]

    try:
        started_at = _time.time()
        did_sql = did.replace("'", "''")
        rows = _psql(
            "select file_name, coalesce(file_path, ''), coalesce(file_type, '') from t_dm_dataset_files "
            f"where dataset_id='{did_sql}' and status in ('ACTIVE','COMPLETED') "
            "order by file_name;"
        )
        if not rows:
            return {"status": "error", "error": f"dataset has no active files: {did}"}

        chain_map = _task1_mixed_chain_map()
        chain_descriptions = _task1_mixed_chain_descriptions()
        type_counts, unsupported_preview = count_source_file_groups(rows)

        effective_threshold = max(1, int(async_file_threshold or 50))
        if not wait and len(rows) > effective_threshold:
            run_id = f"{int(_time.time())}_{_uuid.uuid4().hex[:8]}"
            status_payload = {
                "status": "queued",
                "message": (
                    "大数据集清洗已切换为后台异步执行，避免 Nexent 对话界面长时间阻塞。"
                    "请稍后调用 get_task1_mixed_cleaning_status(run_id) 查看进度和最终结果。"
                ),
                "source_dataset": {
                    "id": did,
                    "name": source_name,
                    "requested_identifier": requested_identifier,
                    "resolved_by": resolved_dataset.get("resolved_by", ""),
                    "resolution_candidates": resolution_candidates[:5],
                    "file_count": len(rows),
                    "type_counts": type_counts,
                },
                "operators_plan": {
                    group: {
                        "operators": chain_map[group],
                        "description": chain_descriptions[group],
                        "file_count": type_counts.get(group, 0),
                    }
                    for group in TASK1_FILE_GROUPS
                    if type_counts.get(group, 0)
                },
                "unsupported_files_preview": unsupported_preview[:20],
                "query_tool": "get_task1_mixed_cleaning_status",
                "next_action": f"get_task1_mixed_cleaning_status(run_id='{run_id}')",
            }
            _write_task1_async_status(run_id, status_payload)
            worker_module = "mcp_server.task1.async_worker"
            log_path = _task1_async_status_path(run_id).with_suffix(".log")
            with log_path.open("a", encoding="utf-8") as log:
                subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        worker_module,
                        "--dataset-id",
                        did,
                        "--task-name",
                        task_name or f"任务一混合清洗异步_{run_id}",
                        "--run-id",
                        run_id,
                    ],
                    cwd=str(ROOT),
                    stdout=log,
                    stderr=log,
                    start_new_session=True,
                )
            status_payload["status"] = "async_started"
            status_payload["log_path"] = str(log_path)
            _write_task1_async_status(run_id, status_payload)
            return status_payload

        stamp = f"{int(_time.time())}_{_uuid.uuid4().hex[:8]}"
        work_dir = ROOT / "data" / "task1_mixed_agent_runs" / stamp
        raw_dir = work_dir / "raw"
        outputs_dir = work_dir / "outputs"
        raw_dir.mkdir(parents=True, exist_ok=True)

        grouped: dict[str, list[tuple[_Path, str]]] = {group: [] for group in TASK1_FILE_GROUPS}
        unsupported: list[str] = []

        for fname, file_path, ftype in rows:
            group, out_type = classify_source_file(fname, ftype)
            if not group or not out_type:
                unsupported.append(fname)
                continue

            local_path = raw_dir / group / fname
            local_path.parent.mkdir(parents=True, exist_ok=True)
            cp = run_sudo(["cp", datamate_dataset_host_path(DATASET_VOL, did, fname, file_path), str(local_path)])
            if cp.returncode != 0:
                raise RuntimeError(cp.stderr.strip() or cp.stdout.strip())
            grouped[group].append((local_path, out_type))

        if not any(grouped.values()):
            return {"status": "error", "error": "no supported txt/csv/json files found", "unsupported": unsupported}
        missing_chains = sorted(group for group, files in grouped.items() if files and group not in chain_map)
        if missing_chains:
            return {
                "status": "error",
                "error": f"missing Task 1 cleaning chain for file groups: {missing_chains}",
                "source_groups": {k: [path.name for path, _ in v] for k, v in grouped.items()},
                "unsupported_files": unsupported,
            }

        requested_name = "".join(
            ch if ch.isalnum() or ch in "_-一-鿿" else "_"
            for ch in (task_name or "").strip()
        )
        if requested_name and not re.search(r"[A-Za-z0-9\u4e00-\u9fff]", requested_name):
            requested_name = ""
        def _dm_name(value: str, fallback: str, max_len: int = 60) -> str:
            cleaned = "".join(
                ch if ch.isalnum() or ch in "_-一-鿿" else "_"
                for ch in (value or "").strip()
            ).strip("_")
            cleaned = cleaned or fallback
            return cleaned[:max_len]

    # DataMate 的 t_clean_task.src_dataset_name 字段长度为 64。
    # 清洗任务会把临时子集名称写入该字段，因此生成名称需要主动截断。
        short_prefix = _dm_name(requested_name, "任务一", 18)
        final_dataset_name = (
            f"{requested_name}_最终数据集_{int(_time.time())}"
            if requested_name
            else f"任务一_最终清洗结果_保持源格式_{int(_time.time())}"
        )

        subset_datasets = {}
        for group, files in grouped.items():
            if files:
                group_name = {"text": "文本", "csv": "表格", "json": "JSON", "jsonl": "JSONL"}[group]
                subset_name = _dm_name(
                    f"{short_prefix}_{group_name}子集_{stamp[-8:]}",
                    f"任务一_{group_name}子集_{stamp[-8:]}",
                    60,
                )
                subset_datasets[group] = register_dataset(
                    subset_name,
                    files,
                    "txt" if group == "text" else group,
                    description=f"任务一混合清洗临时子数据集，来源：{source_name}",
                )

        outputs_dir.mkdir(parents=True, exist_ok=True)

        task_results = {}
        reports = {}
        evidence_by_group = {}
        total_records = 0
        for group in TASK1_FILE_GROUPS:
            dataset = subset_datasets.get(group)
            if not dataset:
                continue
            result = run_pipeline(dataset, chain_map[group], group)
            paths = collect_outputs(result["dest_dataset_id"], outputs_dir, group, set())
            if group == "text":
                paths = merge_numbered_text_chunks(paths)
            if group in {"json", "jsonl"}:
                paths = restore_structured_output_suffix(paths, group)
            postprocess_report = {}
            if group in {"json", "jsonl"}:
                postprocess_report = postprocess_structured_outputs(paths)
            artifact_cleanup_report = cleanup_preserved_files(paths)
            file_reports = [evaluate_file(path) for path in paths]
            report = summarize(file_reports, min_records=1)
            if not report["pass"]:
                raise AssertionError(
                    f"{group} output quality failed: "
                    f"{_json.dumps(report.get('totals', {}), ensure_ascii=False)}"
                )
            reports[group] = report["totals"]
            evidence_by_group[group] = summarize_cleaning_evidence(
                [path for path, _out_type in grouped[group]],
                paths,
            )
            total_records += int(report["totals"].get("records", 0) or 0)
            task_results[group] = {
                "task_id": result["task_id"],
                "dest_dataset_id": result["dest_dataset_id"],
                "operators": chain_map[group],
                "outputs": [str(path) for path in paths],
                "artifact_cleanup": artifact_cleanup_report,
                "postprocess": postprocess_report,
                "cleaning_evidence": evidence_by_group[group],
            }

        delivery_dataset = register_final_delivery(
            outputs_dir,
            final_dataset_name,
        )
        db_health = check_db_health()
        elapsed_seconds = round(_time.time() - started_at, 2)
        throughput = round(total_records / elapsed_seconds, 4) if elapsed_seconds > 0 else float(total_records)

        source_mixed_dataset = {
            "id": did,
            "name": source_name,
            "requested_identifier": requested_identifier,
            "resolved_by": resolved_dataset.get("resolved_by", ""),
            "resolution_candidates": resolution_candidates[:5],
            "format": "mixed",
            "files": [row[0] for row in rows],
        }
        summary = {
            "pass": True,
            "status": "success",
            "work_dir": str(work_dir),
            "source_mixed_dataset": source_mixed_dataset,
            "source_groups": {k: [path.name for path, _ in v] for k, v in grouped.items()},
            "unsupported_files": unsupported,
            "operators_plan": {
                group: {
                    "operators": chain_map[group],
                    "description": chain_descriptions[group],
                    "file_count": len(grouped.get(group, [])),
                }
                for group in TASK1_FILE_GROUPS
                if grouped.get(group)
            },
            "subset_datasets": subset_datasets,
            "task_results": task_results,
            "delivery_dataset": delivery_dataset,
            "delivery_report": {"files": len([p for p in outputs_dir.glob('*') if p.is_file()])},
            "reports": reports,
            "actual_cleaning_evidence": evidence_by_group,
            "performance": {
                "elapsed_seconds": elapsed_seconds,
                "processed_records": total_records,
                "processed_files": len([p for p in outputs_dir.glob('*') if p.is_file()]),
                "throughput_records_per_second": throughput,
                "metric_scope": "Task 1 mixed cleaning final outputs",
            },
            "db_health": db_health,
        }
        report_path = work_dir / "test_report.json"
        report_path.write_text(_json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        summary["governance_metadata"] = register_governance(report_path)
        report_path.write_text(_json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        summary["explanation"] = (
            "Mixed dataset was split by file type, cleaned with per-type chains, "
            "then collected into one final Task 1 delivery dataset that preserves "
            "the cleaned source formats. JSONL conversion is left to Task 2 or an "
            "explicit user instruction."
        )
        return summary
    except Exception as e:
        return {"status": "error", "error": str(e)[:2000]}
