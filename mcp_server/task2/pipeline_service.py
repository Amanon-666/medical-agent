# -*- coding: utf-8 -*-
"""
任务二知识图谱构建服务。
"""

from __future__ import annotations

import time
from collections import Counter

from core.llm_client import LLMClient
from core.medical_extraction_service import extract_medical_knowledge, normalize_backend
from mcp_server.config import KG_DB, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from mcp_server.datamate.resolver import (
    _task2_read_datamate_dataset,
    _task2_resolve_datamate_dataset,
)
from mcp_server.kg.analytics_refresh import refresh_task3_analytics
from mcp_server.kg.persistence import ensure_source, persist_triples
from mcp_server.kg.schema import _task2_ensure_kg_schema
from mcp_server.shared.parsing import parse_files
from mcp_server.shared.sqlite_utils import connect_kg
from mcp_server.task2.reporting import (
    format_stage_duration,
    summarize_analytics_refresh,
    summarize_source_files,
)
from mcp_server.task2.selection import select_balanced_records


_LLM: LLMClient | None = None


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _get_task2_llm() -> LLMClient:
    global _LLM
    if _LLM is None:
        _LLM = LLMClient(base_url=LLM_BASE_URL, model=LLM_MODEL, api_key=LLM_API_KEY or None)
    return _LLM


def _llm_for_backend(backend: str) -> LLMClient | None:
    selected = normalize_backend(backend)
    return _get_task2_llm() if selected in {"llm", "hybrid"} else None


def _backend_label(backend: str) -> str:
    return {
        "offline": "本地知识抽取链",
        "hybrid": "本地抽取增强链",
        "llm": "语义抽取链",
    }.get(backend, "本地知识抽取链")


def run_kg_pipeline_service(
    *,
    dataset_id: str,
    task_name: str = "",
    max_records: int = 0,
    dry_run: bool = False,
    persist: bool = True,
    refresh_analytics: bool = True,
    backend: str = "offline",
) -> dict:
    """执行任务二知识图谱流水线并返回结构化 MCP 结果。"""
    t0 = time.time()
    selected_backend = normalize_backend(backend)
    backend_label = _backend_label(selected_backend)
    progress_log: list[dict] = []
    tool_call_trace: list[dict] = []

    if not dataset_id:
        return {"status": "error", "error": "需要 dataset_id"}

    stage_start = time.time()
    progress_log.append({"step": "resolve", "label": "数据集解析", "status": "running", "time": _now()})
    try:
        ds, _ = _task2_resolve_datamate_dataset(dataset_id)
        progress_log[-1].update(
            {
                "status": "done",
                "dataset_name": ds.get("name", ""),
                "duration_seconds": round(time.time() - stage_start, 4),
            }
        )
    except Exception as exc:
        progress_log[-1].update({"status": "error", "duration_seconds": round(time.time() - stage_start, 4)})
        return {"status": "error", "error": str(exc), "progress_log": progress_log}

    stage_start = time.time()
    progress_log.append({"step": "read_files", "label": "文件读取", "status": "running", "time": _now()})
    try:
        _, files = _task2_read_datamate_dataset(ds["id"])
        progress_log[-1].update(
            {"status": "done", "file_count": len(files), "duration_seconds": round(time.time() - stage_start, 4)}
        )
    except Exception as exc:
        progress_log[-1].update({"status": "error", "duration_seconds": round(time.time() - stage_start, 4)})
        return {"status": "error", "error": str(exc), "progress_log": progress_log}

    if dry_run:
        return {
            "status": "dry_run",
            "backend": selected_backend,
            "backend_label": backend_label,
            "dataset": ds,
            "file_count": len(files),
            "plan": "数据集解析 -> 文件读取 -> 混合格式记录解析 -> 知识抽取 -> 三元组入库 -> 分析库刷新",
            "progress_log": progress_log,
        }

    stage_start = time.time()
    progress_log.append({"step": "parse", "label": "记录解析", "status": "running", "time": _now()})
    records, stats = parse_files(files)
    selected_records = select_balanced_records(records, int(max_records or 0))
    progress_log[-1].update(
        {
            "status": "done",
            "record_count": len(records),
            "selected_record_count": len(selected_records),
            "format_stats": stats,
            "duration_seconds": round(time.time() - stage_start, 4),
        }
    )
    tool_call_trace.append(
        {
            "tool": "parse_files",
            "input_count": len(files),
            "output_count": len(records),
            "selected_count": len(selected_records),
        }
    )

    conn = connect_kg() if persist else None
    if conn:
        _task2_ensure_kg_schema(conn)

    source_id = None
    record_results: list[dict] = []
    generated_triple_count = 0
    inserted_triple_count = 0
    extraction_errors: list[dict] = []
    extraction_elapsed_total = 0.0
    persistence_elapsed_total = 0.0
    llm_degraded_count = 0
    llm = _llm_for_backend(selected_backend)

    stage_start = time.time()
    progress_log.append({"step": "extract", "label": "实体关系三元组生成", "status": "running", "time": _now()})
    for index, record in enumerate(selected_records):
        text = record.get("text", "")
        if not text.strip():
            continue
        try:
            bundle = extract_medical_knowledge(text, backend=selected_backend, kg_db_path=KG_DB, llm=llm)
            extraction_elapsed_total += bundle.elapsed_seconds
            if bundle.llm_error:
                llm_degraded_count += 1

            triples = bundle.triples
            generated_triple_count += len(triples)
            record_result = {
                "record": index,
                "source_file": record.get("source_file", ""),
                "backend": bundle.backend,
                "entities": len(bundle.entities),
                "relations": len(bundle.relations),
                "triples": len(triples),
                "elapsed_seconds": bundle.elapsed_seconds,
            }
            if bundle.llm_error:
                record_result["llm_error"] = bundle.llm_error

            if persist and conn and triples:
                if source_id is None:
                    source_id = ensure_source(conn, ds, len(selected_records))
                persist_start = time.time()
                inserted = persist_triples(conn, triples, record.get("source_file", ""), source_id)
                persistence_elapsed_total += time.time() - persist_start
                record_result["inserted_triples"] = inserted
                inserted_triple_count += inserted

            record_results.append(record_result)
            tool_call_trace.append({"tool": f"record_{index}", **record_result})
        except Exception as exc:
            error = {"record": index, "source_file": record.get("source_file", ""), "error": str(exc)}
            extraction_errors.append(error)
            tool_call_trace.append({"tool": f"record_{index}", **error})

    progress_log[-1].update(
        {
            "status": "partial" if extraction_errors else "done",
            "processed_record_count": len(record_results),
            "error_count": len(extraction_errors),
            "duration_seconds": round(time.time() - stage_start, 4),
        }
    )

    commit_elapsed = 0.0
    if conn:
        commit_start = time.time()
        conn.commit()
        commit_elapsed = time.time() - commit_start
        conn.close()
    progress_log.append(
        {
            "step": "persist",
            "label": "三元组入库",
            "status": "done" if persist else "skipped",
            "inserted_triple_count": inserted_triple_count,
            "duration_seconds": round(persistence_elapsed_total + commit_elapsed, 4),
        }
    )

    analytics_refresh_result = {"status": "skipped", "reason": "refresh_analytics=false"}
    if refresh_analytics:
        stage_start = time.time()
        if inserted_triple_count > 0:
            try:
                analytics_refresh_result = refresh_task3_analytics()
            except Exception as exc:
                analytics_refresh_result = {"status": "error", "error": str(exc)}
        else:
            analytics_refresh_result = {"status": "skipped", "reason": "no newly inserted triples"}
        analytics_refresh_result["duration_seconds"] = round(time.time() - stage_start, 4)
    progress_log.append(
        {
            "step": "refresh_analytics",
            "label": "分析库刷新",
            "status": analytics_refresh_result.get("status", "skipped"),
            "duration_seconds": analytics_refresh_result.get("duration_seconds", 0),
        }
    )

    if extraction_errors and not record_results:
        status = "error"
    elif extraction_errors:
        status = "partial_success"
    else:
        status = "success"
    status_label = {"success": "完成", "partial_success": "部分完成", "error": "失败"}.get(status, status)

    elapsed = round(time.time() - t0, 1)
    processed_records = len(record_results)
    avg_latency = round(extraction_elapsed_total / processed_records, 4) if processed_records else 0.0
    throughput = round(processed_records / extraction_elapsed_total, 4) if extraction_elapsed_total else 0.0
    source_file_summary = summarize_source_files(records, selected_records, record_results)
    analytics_summary = summarize_analytics_refresh(analytics_refresh_result)
    source_format_summary = dict(Counter(item.get("source_format", "unknown") for item in records))

    return {
        "status": status,
        "error": "all records failed during extraction or persistence" if status == "error" else "",
        "elapsed_seconds": elapsed,
        "backend": selected_backend,
        "backend_label": backend_label,
        "dataset": {"id": ds["id"], "name": ds.get("name", "")},
        "file_count": len(files),
        "record_count": len(records),
        "selected_record_count": len(selected_records),
        "source_format_summary": source_format_summary,
        "source_file_summary": source_file_summary,
        "unprocessed_record_count": max(0, len(records) - len(selected_records)),
        "processed_record_count": processed_records,
        "entity_count": sum(item.get("entities", 0) for item in record_results),
        "relation_count": sum(item.get("relations", 0) for item in record_results),
        "generated_triple_count": generated_triple_count,
        "inserted_triple_count": inserted_triple_count,
        "triple_count": inserted_triple_count,
        "performance": {
            "extractor_backend": selected_backend,
            "extractor_label": backend_label,
            "extraction_elapsed_seconds": round(extraction_elapsed_total, 4),
            "avg_record_latency_seconds": avg_latency,
            "throughput_records_per_second": throughput,
            "llm_degraded_records": llm_degraded_count,
        },
        "extraction_errors": extraction_errors,
        "progress_log": progress_log,
        "tool_call_trace": tool_call_trace,
        "report_markdown": (
            f"任务二知识图谱构建{status_label}：使用{backend_label}，解析 {len(records)} 条记录，"
            f"处理 {processed_records} 条"
            f"{'（跨文件均衡抽样）' if len(selected_records) < len(records) else ''}，"
            f"覆盖 {len(source_file_summary)} 个来源文件，生成 {generated_triple_count} 条三元组，"
            f"新增入库 {inserted_triple_count} 条，总耗时 {format_stage_duration(elapsed)}，"
            f"抽取吞吐 {throughput} records/s。"
        ),
        "analytics_summary": analytics_summary,
        "refresh_analytics": analytics_refresh_result,
    }

