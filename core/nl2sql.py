# -*- coding: utf-8 -*-
"""
任务三只读 NL2SQL 模块。

该模块把受支持的自然语言统计问题转换为只读 SQL，并阻断写入、删除和结构变更语句。
"""

import re
import sqlite3
from typing import Any, Dict

from .llm_client import LLMClient


SCHEMA_DESC = """
SQLite database schema:

diseases(disease_id, name, description, source_count)
  - name: disease name, unique in practice
  - description: disease summary

disease_symptoms(id, disease, symptom, confidence, source_name)
disease_drugs(id, disease, drug, confidence, source_name)
disease_complications(id, disease, complication, confidence, source_name)
disease_departments(id, disease, department, confidence, source_name)
disease_tests(id, disease, test, confidence, source_name)
disease_procedures(id, disease, procedure, confidence, source_name)
disease_populations(id, disease, population, confidence, source_name)
disease_causes(id, disease, cause, evidence, confidence, source_name)
disease_preventions(id, disease, prevention, evidence, confidence, source_name)
disease_facts(id, disease, fact_type, fact_name, evidence, source_name, confidence)

entity_stats(entity_type, entity_count)
relation_stats(relation_code, display_name, triple_count)
"""

FEW_SHOTS = [
    {
        "question": "糖尿病有哪些症状？",
        "sql": "SELECT DISTINCT symptom FROM disease_symptoms WHERE disease LIKE '%糖尿病%' LIMIT 20",
    },
    {
        "question": "2型糖尿病有哪些药物？",
        "sql": "SELECT DISTINCT drug FROM disease_drugs WHERE disease LIKE '%2型糖尿病%' LIMIT 20",
    },
    {
        "question": "糖尿病常见并发症有哪些？",
        "sql": "SELECT DISTINCT complication FROM disease_complications WHERE disease LIKE '%糖尿病%' LIMIT 20",
    },
    {
        "question": "内科有哪些疾病？",
        "sql": "SELECT DISTINCT disease FROM disease_departments WHERE department LIKE '%内科%' LIMIT 20",
    },
    {
        "question": "哪些疾病有发热症状？",
        "sql": "SELECT DISTINCT disease FROM disease_symptoms WHERE symptom LIKE '%发热%' LIMIT 20",
    },
    {
        "question": "一共有多少种疾病？",
        "sql": "SELECT COUNT(*) AS total_diseases FROM diseases",
    },
    {
        "question": "各类实体数量是多少？",
        "sql": "SELECT entity_type, entity_count FROM entity_stats ORDER BY entity_count DESC LIMIT 20",
    },
    {
        "question": "关系类型按数量排序",
        "sql": "SELECT display_name, triple_count FROM relation_stats ORDER BY triple_count DESC LIMIT 20",
    },
]

SYSTEM_PROMPT = f"""You are a medical analytics NL2SQL assistant.
Generate exactly one SQLite read-only query for the user's Chinese question.

{SCHEMA_DESC}

Rules:
1. Output SQL only. Do not output Markdown or explanation.
2. Only SELECT or WITH queries are allowed.
3. Never generate INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, REPLACE, TRUNCATE, PRAGMA, ATTACH, DETACH, or VACUUM.
4. Use LIKE '%keyword%' for fuzzy Chinese matching.
5. Use LIMIT 20 unless the user explicitly asks for a different limit or a count query.
6. Use the exact table and column names from the schema above.
"""

_UNSAFE_SQL_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|attach|detach|pragma|vacuum)\b",
    re.IGNORECASE,
)
_WRITE_INTENT_RE = re.compile(
    r"(插入|写入|新增|添加|更新|删除|清空|建表|建库|修改|提交|入库|导入|导出|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE)",
    re.IGNORECASE,
)


def _make_prompt(question: str) -> str:
    examples = "\n\n".join(
        f"Question: {example['question']}\nSQL: {example['sql']}" for example in FEW_SHOTS
    )
    return f"{examples}\n\nQuestion: {question}\nSQL:"


def _extract_sql(text: str) -> str:
    text = re.sub(r"```(?:sql)?\s*", "", text or "", flags=re.IGNORECASE)
    text = text.replace("```", "").strip()
    for keyword in ("SELECT", "WITH", "select", "with"):
        idx = text.find(keyword)
        if idx != -1:
            stmt = text[idx:]
            end = stmt.find(";")
            if end != -1:
                stmt = stmt[:end]
            return stmt.strip()
    return text.strip()


def generate_sql(question: str, llm: LLMClient) -> str:
    raw = llm.chat(_make_prompt(question), system=SYSTEM_PROMPT)
    return _extract_sql(raw)


def execute_sql(sql: str, db_path: str) -> Dict[str, Any]:
    stripped = (sql or "").strip()
    if not stripped:
        return {"columns": [], "rows": [], "row_count": 0, "error": "empty SQL"}
    if _UNSAFE_SQL_RE.search(stripped):
        return {
            "columns": [],
            "rows": [],
            "row_count": 0,
            "error": "execute_nl2sql is read-only; write or schema-changing SQL is not allowed",
        }
    if not re.match(r"^(select|with)\b", stripped, flags=re.IGNORECASE):
        return {
            "columns": [],
            "rows": [],
            "row_count": 0,
            "error": "execute_nl2sql only executes SELECT/WITH queries",
        }
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.execute(stripped)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        data = [list(row) for row in rows]
        conn.close()
        return {"columns": cols, "rows": data, "row_count": len(data), "error": None}
    except Exception as exc:
        return {"columns": [], "rows": [], "row_count": 0, "error": str(exc)}


def nl2sql(question: str, llm: LLMClient, db_path: str) -> Dict[str, Any]:
    if _WRITE_INTENT_RE.search(question or ""):
        return {
            "columns": [],
            "rows": [],
            "row_count": 0,
            "error": "execute_nl2sql is read-only; use the Task 2 ingestion pipeline to add KG/analytics data",
            "sql": "",
            "question": question,
        }
    sql = generate_sql(question, llm)
    result = execute_sql(sql, db_path)
    result["sql"] = sql
    result["question"] = question
    return result
