# -*- coding: utf-8 -*-
"""
可视化平台只读查询服务。

该模块负责疾病详情、图谱子图、统计查询和证据表读取。
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from db_utils import connect, query_dicts
from paths import ANALYTICS_DB
from quality import filter_suspicious_rows


QUERY_TEMPLATES = {
    "symptom": {
        "keywords": ("症状", "表现", "临床表现", "体征"),
        "table": "disease_symptoms",
        "value_column": "symptom",
        "label": "症状",
    },
    "drug": {
        "keywords": ("药", "药物", "用药", "吃什么", "口服"),
        "table": "disease_drugs",
        "value_column": "drug",
        "label": "药物",
    },
    "department": {
        "keywords": ("科室", "挂什么科", "挂哪科", "看哪科", "就诊"),
        "table": "disease_departments",
        "value_column": "department",
        "label": "科室",
    },
    "test": {
        "keywords": ("检查", "化验", "诊断", "检测", "检验"),
        "table": "disease_tests",
        "value_column": "test",
        "label": "检查",
    },
    "procedure": {
        "keywords": ("治疗", "怎么治", "疗法", "手术", "处理"),
        "table": "disease_procedures",
        "value_column": "procedure",
        "label": "治疗方式",
    },
    "cause": {
        "keywords": ("病因", "原因", "为什么", "导致", "引起"),
        "table": "disease_causes",
        "value_column": "cause",
        "label": "病因",
    },
    "prevention": {
        "keywords": ("预防", "避免", "怎么防", "防治"),
        "table": "disease_preventions",
        "value_column": "prevention",
        "label": "预防",
    },
    "population": {
        "keywords": ("易感", "好发", "多发人群", "哪些人", "人群"),
        "table": "disease_populations",
        "value_column": "population",
        "label": "易感人群",
    },
    "complication": {
        "keywords": ("并发", "并发症", "合并", "伴随"),
        "table": "disease_complications",
        "value_column": "complication",
        "label": "并发症",
    },
}


def clean_question(question: str) -> str:
    return re.sub(r"\s+", "", question.strip())


def find_disease(conn: sqlite3.Connection, question: str) -> str | None:
    compact = clean_question(question)
    row = conn.execute(
        """
        SELECT name
        FROM diseases
        WHERE ? LIKE '%' || name || '%'
        ORDER BY LENGTH(name) DESC
        LIMIT 1
        """,
        (compact,),
    ).fetchone()
    if row:
        return str(row["name"])

    candidate = re.split(
        r"(?:有哪些|有什么|需要|应该|可以|怎么|如何|为什么|病因|原因|检查|症状|治疗|预防|挂|属于|统计|数量)",
        compact,
        maxsplit=1,
    )[0].strip("，。？！：:、 的")
    if len(candidate) >= 2:
        row = conn.execute(
            """
            SELECT name
            FROM diseases
            WHERE name LIKE ?
            ORDER BY LENGTH(name) ASC
            LIMIT 1
            """,
            (f"%{candidate}%",),
        ).fetchone()
        if row:
            return str(row["name"])
    return None


def detect_template(question: str) -> str | None:
    compact = clean_question(question)
    for template, spec in QUERY_TEMPLATES.items():
        if any(keyword in compact for keyword in spec["keywords"]):
            return template
    return None


def detect_stats_query(question: str) -> tuple[str, str] | None:
    compact = clean_question(question)
    stat_words = ("统计", "数量", "分布", "排行", "排名", "最多", "Top", "top")
    if not any(word in compact for word in stat_words):
        return None
    if "实体" in compact:
        return (
            "entity_type_counts",
            "SELECT entity_type AS 类型, entity_count AS 数量 FROM v_entity_type_counts ORDER BY entity_count DESC LIMIT 30",
        )
    if "关系" in compact:
        return (
            "relation_counts",
            "SELECT display_name AS 关系, relation_code AS 关系编码, triple_count AS 数量 FROM v_relation_counts ORDER BY triple_count DESC LIMIT 30",
        )
    if "科室" in compact:
        return (
            "department_counts",
            "SELECT department AS 科室, disease_count AS 疾病数量 FROM v_department_disease_counts ORDER BY disease_count DESC LIMIT 30",
        )
    if "症状" in compact:
        return (
            "top_symptoms",
            "SELECT symptom AS 症状, disease_count AS 关联疾病数量 FROM v_top_symptoms ORDER BY disease_count DESC LIMIT 30",
        )
    if "药" in compact or "药物" in compact:
        return (
            "top_drugs",
            "SELECT drug AS 药物, disease_count AS 关联疾病数量 FROM v_drug_disease_counts ORDER BY disease_count DESC LIMIT 30",
        )
    return None


def make_table_result(
    question: str,
    template: str,
    sql: str,
    rows: list[dict[str, Any]],
    steps: list[dict[str, str]],
) -> dict[str, Any]:
    columns = list(rows[0].keys()) if rows else []
    answer = "查询完成，但没有命中记录。"
    if rows:
        if len(rows[0]) >= 2 and any(key in rows[0] for key in ("数量", "疾病数量", "关联疾病数量")):
            first_label = next(iter(rows[0].keys()))
            count_key = next((k for k in rows[0].keys() if "数量" in k), None)
            top_items = [f"{row[first_label]}({row[count_key]})" for row in rows[:8] if count_key]
            answer = "排行靠前的结果是：" + "、".join(top_items)
        else:
            first_key = columns[0]
            values = [str(row[first_key]) for row in rows[:12]]
            answer = "查询结果：" + "、".join(values)
    return {
        "question": question,
        "answer": answer,
        "template": template,
        "sql": sql,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "steps": steps,
        "chart": infer_chart(rows),
    }


def infer_chart(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    keys = list(rows[0].keys())
    numeric_key = None
    label_key = None
    for key in keys:
        if key in {"置信度", "confidence"}:
            continue
        if isinstance(rows[0].get(key), (int, float)):
            numeric_key = key
            break
    for key in keys:
        if key != numeric_key:
            label_key = key
            break
    if numeric_key and label_key:
        return {
            "type": "bar",
            "label_key": label_key,
            "value_key": numeric_key,
            "data": rows[:12],
        }
    return None


def query_medical(question: str) -> dict[str, Any]:
    if not ANALYTICS_DB.exists():
        return {
            "question": question,
            "answer": f"分析库不存在：{ANALYTICS_DB}",
            "template": "error",
            "sql": "",
            "columns": [],
            "rows": [],
            "row_count": 0,
            "steps": [{"name": "环境检查", "status": "error", "detail": "缺少 task3_analytics.db"}],
            "chart": None,
        }

    with connect(ANALYTICS_DB) as conn:
        steps: list[dict[str, str]] = [
            {"name": "识别问句类型", "status": "done", "detail": "先匹配统计类问题，再匹配疾病属性问题"},
        ]

        stats = detect_stats_query(question)
        if stats:
            template, sql = stats
            rows = query_dicts(conn, sql)
            filtered_count = 0
            if template == "top_symptoms":
                rows, filtered_count = filter_suspicious_rows(rows, "症状")
            steps.extend(
                [
                    {"name": "选择查询模板", "status": "done", "detail": template},
                    {
                        "name": "执行只读 SQL",
                        "status": "done",
                        "detail": f"返回 {len(rows)} 行" + (f"，过滤可疑症状 {filtered_count} 条" if filtered_count else ""),
                    },
                ]
            )
            return make_table_result(question, template, sql, rows, steps)

        disease = find_disease(conn, question)
        template = detect_template(question)
        if disease and not template:
            template = "summary"
        steps.append(
            {
                "name": "识别医学实体",
                "status": "done" if disease else "warn",
                "detail": disease or "未识别到疾病名，返回相近疾病或问答样例",
            }
        )

        if disease and template == "summary":
            sql = """
            SELECT name AS 疾病, description AS 简介, source_count AS 来源数
            FROM diseases
            WHERE name = ?
            """
            rows = query_dicts(conn, sql, (disease,))
            steps.extend(
                [
                    {"name": "选择查询模板", "status": "done", "detail": "disease_summary"},
                    {"name": "执行只读 SQL", "status": "done", "detail": f"返回 {len(rows)} 行"},
                ]
            )
            result = make_table_result(question, "disease_summary", sql, rows, steps)
            result["disease"] = disease
            if rows:
                result["answer"] = rows[0].get("简介") or f"{disease} 已在知识库中，但暂无简介字段。"
            return result

        if disease and template:
            spec = QUERY_TEMPLATES[template]
            sql = f"""
            SELECT {spec['value_column']} AS {spec['label']}, confidence AS 置信度, source_name AS 来源
            FROM {spec['table']}
            WHERE disease = ?
            GROUP BY {spec['value_column']}
            ORDER BY confidence DESC, {spec['value_column']}
            LIMIT 40
            """
            rows = query_dicts(conn, sql, (disease,))
            filtered_count = 0
            if template == "symptom":
                rows, filtered_count = filter_suspicious_rows(rows, spec["label"])
            steps.extend(
                [
                    {"name": "选择查询模板", "status": "done", "detail": f"{disease} -> {spec['label']}"},
                    {
                        "name": "执行只读 SQL",
                        "status": "done",
                        "detail": f"返回 {len(rows)} 行" + (f"，过滤可疑症状 {filtered_count} 条" if filtered_count else ""),
                    },
                ]
            )
            result = make_table_result(question, template, sql, rows, steps)
            result["disease"] = disease
            if rows:
                values = [str(row[spec["label"]]) for row in rows[:12]]
                result["answer"] = f"{disease}的{spec['label']}包括：" + "、".join(values)
            return result

        compact = clean_question(question)
        like = f"%{compact[:12]}%"
        rows = query_dicts(
            conn,
            """
            SELECT name AS 疾病, description AS 简介
            FROM diseases
            WHERE name LIKE ? OR description LIKE ?
            ORDER BY source_count DESC, LENGTH(name)
            LIMIT 20
            """,
            (like, like),
        )
        if not rows:
            rows = query_dicts(
                conn,
                """
                SELECT question AS 相似问题, answer AS 参考回答, source_name AS 来源
                FROM qa_examples
                WHERE question LIKE ? OR answer LIKE ?
                LIMIT 10
                """,
                (like, like),
            )
        sql = "fallback disease/qa search"
        steps.extend(
            [
                {"name": "选择查询模板", "status": "warn", "detail": "未命中固定模板，执行相近检索"},
                {"name": "执行只读查询", "status": "done", "detail": f"返回 {len(rows)} 行"},
            ]
        )
        return make_table_result(question, "fallback_search", sql, rows, steps)
