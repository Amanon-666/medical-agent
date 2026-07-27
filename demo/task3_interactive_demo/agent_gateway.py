# -*- coding: utf-8 -*-
"""Nexent 任务三智能体网关。

智能体负责理解与编排，医学事实、证据表和图表只采用结构化分析工具
的实际返回值，避免把模型补写内容当作数据库结论。
"""

from __future__ import annotations

import ast
import json
import os
import sys
from json import JSONDecoder
from typing import Any, Iterator

from analysis_runtime import remember_analysis
from db_utils import connect, has_table, query_dicts
from paths import DEFAULT_TASK3_AGENT_ID, KG_DB, ROOT
from query_service import make_table_result, query_medical


NEXENT_TOOL_NAMES = (
    "run_task2_kg_pipeline",
    "inspect_dataset",
    "get_medical_data_sources",
    "query_disease_analytics",
    "ask_medical_analytics",
    "query_knowledge_graph",
    "execute_nl2sql",
)

SOURCE_ORCHESTRATION_KEYWORDS = (
    "数据来源",
    "已接入来源",
    "新增数据源",
    "新增数据来源",
    "接入",
    "DataMate",
    "dataset",
    "数据集",
    "dry_run",
    "入库",
    "任务一",
    "任务二",
)


def is_source_orchestration_question(question: str) -> bool:
    text = str(question or "")
    return any(keyword in text for keyword in SOURCE_ORCHESTRATION_KEYWORDS)


def source_projection_result(question: str) -> dict[str, Any]:
    """读取已入库来源，来源管理不进入医学 NL2SQL 分析链。"""

    rows: list[dict[str, Any]] = []
    if KG_DB.exists():
        with connect(KG_DB) as conn:
            if has_table(conn, "kg_sources"):
                rows = query_dicts(
                    conn,
                    """
                    SELECT source_name AS 来源名称,
                           source_type AS 来源类型,
                           record_count AS 记录数,
                           created_at AS 接入时间
                    FROM kg_sources
                    ORDER BY datetime(created_at) DESC, source_id DESC
                    LIMIT 20
                    """,
                )
    steps = [
        {"name": "识别任务类型", "status": "done", "detail": "数据来源管理"},
        {"name": "读取来源清单", "status": "done", "detail": f"当前登记 {len(rows)} 个来源"},
    ]
    result = make_table_result(
        question,
        "kg_sources_projection",
        "SELECT ... FROM kg_sources",
        rows,
        steps,
    )
    result["answer"] = (
        f"当前知识图谱已登记 {len(rows)} 个数据来源。"
        "刷新操作仅重新读取已入库状态，不会重复接入数据。"
    )
    return result


def _decoded_objects(text: str) -> Iterator[Any]:
    """从事件文本中提取 JSON 或 Python 字面量对象。"""

    raw = str(text or "").strip()
    if not raw:
        return
    decoder = JSONDecoder()
    for index, char in enumerate(raw):
        if char not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(raw[index:])
        except (TypeError, ValueError):
            continue
        yield value
    if raw[:1] in "[{" and raw[-1:] in "]}":
        try:
            yield ast.literal_eval(raw)
        except (SyntaxError, ValueError):
            return


def _walk_payload(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _walk_payload(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_payload(nested)
    elif isinstance(value, str):
        for decoded in _decoded_objects(value):
            yield from _walk_payload(decoded)


def _is_analysis_result(payload: dict[str, Any]) -> bool:
    return bool(payload.get("analysis_id")) and isinstance(payload.get("analyses"), list)


def summarize_nexent_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """汇总事件，并提取分析工具返回的结构化事实。"""

    final_answer = ""
    structured_result: dict[str, Any] | None = None
    event_types: list[str] = []
    tool_names: list[str] = []
    for event in events:
        event_type = str(event.get("type") or event.get("event") or "")
        if event_type:
            event_types.append(event_type)
        content = event.get("content") or event.get("answer") or event.get("data") or ""
        if event_type == "final_answer" and isinstance(content, str):
            final_answer = content
        text = json.dumps(event, ensure_ascii=False)
        for tool_name in NEXENT_TOOL_NAMES:
            if tool_name in text and tool_name not in tool_names:
                tool_names.append(tool_name)
        for payload in _walk_payload(event):
            if _is_analysis_result(payload):
                structured_result = payload

    return {
        "event_count": len(events),
        "event_types": sorted(set(event_types)),
        "tool_names": tool_names,
        "tool_records": [{"tool": name, "detail": "已调用"} for name in tool_names],
        "final_answer": final_answer,
        "structured_result": structured_result,
    }


def _with_agent_context(
    result: dict[str, Any],
    summary: dict[str, Any],
    *,
    degraded_reason: str | None = None,
) -> dict[str, Any]:
    payload = dict(result)
    tool_names = summary.get("tool_names") or []
    agent_step = {
        "name": "Nexent 智能体编排",
        "status": "done" if not degraded_reason else "warn",
        "detail": (
            "、".join(tool_names)
            if tool_names and not degraded_reason
            else degraded_reason or "已调用结构化分析工具"
        ),
    }
    payload["steps"] = [agent_step, *(payload.get("steps") or [])]
    payload["mode"] = "nexent_agent"
    payload["events_summary"] = {
        key: value
        for key, value in summary.items()
        if key not in {"final_answer", "structured_result"}
    }
    payload["degraded"] = bool(degraded_reason)
    if degraded_reason:
        payload["degraded_reason"] = degraded_reason
    return payload


def query_nexent_agent(question: str) -> dict[str, Any]:
    """让 Nexent 编排任务三工具，并以工具结构化结果驱动页面。"""

    if is_source_orchestration_question(question):
        result = source_projection_result(question)
        result["mode"] = "source_management"
        return result

    empty_summary = {
        "event_count": 0,
        "event_types": [],
        "tool_names": [],
        "tool_records": [],
    }
    try:
        if str(os.environ.get("CCF_DEMO_DISABLE_NEXENT", "")).lower() in {"1", "true", "yes"}:
            raise RuntimeError("Nexent 智能体模式未启用")
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from clients.nexent_client import NexentClient  # noqa: WPS433

        client = NexentClient(
            os.environ.get("CCF_NEXENT_CONFIG_BASE", "http://127.0.0.1:5010"),
            os.environ.get("CCF_NEXENT_RUNTIME_BASE", "http://127.0.0.1:5014"),
            os.environ.get("CCF_NEXENT_EMAIL", "suadmin@nexent.com"),
            os.environ.get("CCF_NEXENT_PASSWORD", ""),
        )
        client.login()
        summary = summarize_nexent_events(
            list(client.run_agent_stream(DEFAULT_TASK3_AGENT_ID, question))
        )
        structured = summary.get("structured_result")
        if structured:
            remember_analysis(structured)
            return _with_agent_context(structured, summary)

        fallback = query_medical(question)
        reason = "智能体事件流未返回可验证的结构化分析结果，已执行同源只读分析"
        return _with_agent_context(fallback, summary, degraded_reason=reason)
    except Exception as exc:
        fallback = query_medical(question)
        fallback["agent_error"] = str(exc)
        return _with_agent_context(
            fallback,
            empty_summary,
            degraded_reason="Nexent 智能体暂不可用，已执行同源只读分析",
        )
