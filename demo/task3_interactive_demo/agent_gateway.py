# -*- coding: utf-8 -*-
"""
可视化平台智能体网关模块。

该模块负责连接 Nexent 运行时，并在服务不可用时返回明确的降级原因。
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from agent_answer import choose_agent_display_answer
from db_utils import connect, has_table, query_dicts
from paths import DEFAULT_TASK3_AGENT_ID, KG_DB, ROOT
from query_service import detect_stats_query, make_table_result, query_medical


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
    "来源",
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
        {"name": "识别任务类型", "status": "done", "detail": "数据来源/入库编排问题，不执行疾病实体检索"},
        {"name": "读取来源清单", "status": "done", "detail": f"当前 KG 登记 {len(rows)} 个来源"},
    ]
    result = make_table_result(question, "kg_sources_projection", "SELECT ... FROM kg_sources", rows, steps)
    result["answer"] = f"当前知识图谱已登记 {len(rows)} 个数据来源。数据源新增由 Nexent 智能体工具链执行，刷新按钮只重新读取已入库状态。"
    return result


def is_deterministic_visualization_question(question: str) -> bool:
    return is_source_orchestration_question(question) or detect_stats_query(question) is not None


def local_agent_projection(question: str, visual: dict[str, Any], reason: str) -> dict[str, Any]:
    steps = [
        {
            "name": "识别展示型问题",
            "status": "done",
            "detail": reason,
        },
        {
            "name": "执行本地只读查询",
            "status": "done",
            "detail": f"返回 {visual.get('row_count', 0)} 行证据/图表",
        },
    ]
    return {
        "mode": "nexent_agent",
        "question": question,
        "answer": str(visual.get("answer") or "查询完成。"),
        "steps": steps,
        "events_summary": {
            "event_count": 0,
            "event_types": [],
            "tool_names": [],
            "tool_records": [],
            "bypass_reason": reason,
        },
        "visualization": visual,
        "rows": visual.get("rows", []),
        "columns": visual.get("columns", []),
        "row_count": visual.get("row_count", 0),
        "chart": visual.get("chart"),
        "disease": visual.get("disease"),
        "template": f"local_readonly+{visual.get('template', '-')}",
    }


def summarize_nexent_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    final_answer = ""
    event_types: list[str] = []
    tool_names: list[str] = []
    tool_records: list[dict[str, str]] = []
    for event in events:
        event_type = str(event.get("type") or event.get("event") or "")
        if event_type:
            event_types.append(event_type)
        content = event.get("content") or event.get("answer") or event.get("data") or ""
        if event_type == "final_answer" and isinstance(content, str):
            final_answer = content
        text = json.dumps(event, ensure_ascii=False)
        for tool_name in NEXENT_TOOL_NAMES:
            if tool_name in text:
                if tool_name not in tool_names:
                    tool_names.append(tool_name)
                if len(tool_records) < 12:
                    detail = str(content)[:180] if content else text[:180]
                    tool_records.append({"tool": tool_name, "detail": detail})
    if not final_answer:
        for event in reversed(events):
            content = event.get("content") or event.get("answer") or event.get("data")
            if isinstance(content, str) and content.strip():
                final_answer = content
                break
    return {
        "event_count": len(events),
        "event_types": sorted(set(event_types)),
        "tool_names": tool_names,
        "tool_records": tool_records,
        "final_answer": final_answer,
    }


def query_nexent_agent(question: str) -> dict[str, Any]:
    """转发问题到 Nexent 任务三智能体，并补充本地可视化数据。"""
    started_visual = source_projection_result(question) if is_source_orchestration_question(question) else query_medical(question)
    if is_deterministic_visualization_question(question):
        return local_agent_projection(question, started_visual, "统计/来源类问题使用本地分析库只读查询，避免智能体生成工具草稿")
    try:
        if str(os.environ.get("CCF_DEMO_DISABLE_NEXENT", "")).lower() in {"1", "true", "yes"}:
            raise RuntimeError("Nexent agent mode disabled by CCF_DEMO_DISABLE_NEXENT")
        sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None
        from clients.nexent_client import NexentClient  # noqa: WPS433

        client = NexentClient(
            os.environ.get("CCF_NEXENT_CONFIG_BASE", "http://127.0.0.1:5010"),
            os.environ.get("CCF_NEXENT_RUNTIME_BASE", "http://127.0.0.1:5014"),
            os.environ.get("CCF_NEXENT_EMAIL", "suadmin@nexent.com"),
            os.environ.get("CCF_NEXENT_PASSWORD", ""),
        )
        client.login()
        events = list(client.run_agent_stream(DEFAULT_TASK3_AGENT_ID, question))
        summary = summarize_nexent_events(events)
        answer, answer_degraded = choose_agent_display_answer(
            summary["final_answer"] or "Nexent 智能体已返回事件流，但没有 final_answer。",
            started_visual,
        )
        steps = [
            {"name": "转发到 Nexent Agent", "status": "done", "detail": f"agent_id={DEFAULT_TASK3_AGENT_ID}"},
            {
                "name": "智能体工具编排",
                "status": "done" if summary["tool_names"] else "warn",
                "detail": "、".join(summary["tool_names"]) or "未在事件流中识别到工具名",
            },
            {
                "name": "回答展示净化",
                "status": "warn" if answer_degraded else "done",
                "detail": "Nexent 返回包含工具执行文本，已改用本地只读查询回答" if answer_degraded else "未发现工具调用草稿泄露",
            },
            {
                "name": "前端可视化投影",
                "status": "done",
                "detail": f"本地任务三 API 同步生成 {started_visual.get('row_count', 0)} 行证据/图表用于验收展示",
            },
        ]
        return {
            "mode": "nexent_agent",
            "question": question,
            "answer": answer,
            "steps": steps,
            "events_summary": {
                key: value
                for key, value in summary.items()
                if key != "final_answer"
            },
            "visualization": started_visual,
            "rows": started_visual.get("rows", []),
            "columns": started_visual.get("columns", []),
            "row_count": started_visual.get("row_count", 0),
            "chart": started_visual.get("chart"),
            "disease": started_visual.get("disease"),
            "template": f"nexent_agent+{started_visual.get('template', '-')}",
        }
    except Exception as exc:
        return {
            "mode": "nexent_agent",
            "question": question,
            "answer": f"Nexent 智能体调用失败，已保留本地任务三 API 结果作为降级展示。失败原因：{exc}",
            "steps": [
                {"name": "转发到 Nexent Agent", "status": "error", "detail": str(exc)[:240]},
                {
                    "name": "本地任务三 API 降级",
                    "status": "done",
                    "detail": f"返回 {started_visual.get('row_count', 0)} 行证据/图表",
                },
            ],
            "events_summary": {"event_count": 0, "event_types": [], "tool_names": [], "tool_records": []},
            "visualization": started_visual,
            "rows": started_visual.get("rows", []),
            "columns": started_visual.get("columns", []),
            "row_count": started_visual.get("row_count", 0),
            "chart": started_visual.get("chart"),
            "disease": started_visual.get("disease"),
            "template": f"agent_error+{started_visual.get('template', '-')}",
            "error": str(exc),
        }
