from __future__ import annotations

import sqlite3

from core.nl2sql import deterministic_sql
from task3.planner import build_plan


def test_common_symptom_question_uses_stable_columns_and_order() -> None:
    sql = deterministic_sql("肺不张有哪些常见症状？")
    assert sql == (
        "SELECT symptom, confidence FROM disease_symptoms "
        "WHERE disease LIKE '%肺不张%' ORDER BY confidence DESC LIMIT 20"
    )


def test_source_confidence_question_uses_fuzzy_source_match() -> None:
    sql = deterministic_sql(
        "在来源'QASystemOnMedicalKG'中，置信度大于0.8的症状记录有多少条？"
    )
    assert sql is not None
    assert "disease_symptoms" in sql
    assert "source_name LIKE '%QASystemOnMedicalKG%'" in sql
    assert "confidence > 0.8" in sql


def test_open_question_remains_on_model_fallback() -> None:
    assert deterministic_sql("请自由分析当前数据中值得关注的异常") is None


def test_planner_adopts_deterministic_query() -> None:
    plan = build_plan(sqlite3.connect(":memory:"), "肺不张有哪些常见症状？", None)
    assert plan.planner == "deterministic_nl2sql"
    assert len(plan.queries) == 1
    assert plan.queries[0].source == "deterministic_nl2sql"
