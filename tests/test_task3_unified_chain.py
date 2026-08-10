from __future__ import annotations

import importlib
import sys
from pathlib import Path

from mcp_server.config import ANALYTICS_DB, SQL_DB
from task3.runtime import build_analysis_service


def test_legacy_sql_database_alias_points_to_canonical_analytics_db() -> None:
    assert Path(SQL_DB) == Path(ANALYTICS_DB)


def test_shared_service_returns_traceable_analysis_result() -> None:
    service = build_analysis_service(ANALYTICS_DB)
    result = service.analyze("肺不张有哪些常见症状？")

    assert result["status"] == "success"
    assert result["planner"] == "deterministic_nl2sql"
    assert result["row_count"] == 20
    assert result["analyses"]
    assert result["analyses"][0]["status"] == "ok"
    assert result["provenance"]["database"] == "task3_analytics.db"


def test_mcp_natural_language_entries_delegate_to_same_service(monkeypatch) -> None:
    """在没有安装 FastMCP 的开发环境中验证两个入口的委托契约。"""

    import mcp_server.tools as tool_package

    class FakeMcp:
        def tool(self, function=None):
            if function is None:
                return lambda wrapped: wrapped
            return function

    monkeypatch.setattr(tool_package, "mcp", FakeMcp())
    for module_name in (
        "mcp_server.tools.task3_query",
        "mcp_server.tools.task3_nl2sql",
    ):
        sys.modules.pop(module_name, None)

    query_module = importlib.import_module("mcp_server.tools.task3_query")
    nl2sql_module = importlib.import_module("mcp_server.tools.task3_nl2sql")

    class FakeService:
        def __init__(self):
            self.questions = []

        def analyze(self, question):
            self.questions.append(question)
            return {"status": "success", "question": question, "chain": "task3"}

    service = FakeService()
    query_module.get_task3_analysis_service = lambda: service
    nl2sql_module.get_task3_analysis_service = lambda: service

    first = query_module.ask_medical_analytics("按科室统计关联疾病条目")
    second = nl2sql_module.execute_nl2sql("按科室统计关联疾病条目")

    assert first == second
    assert service.questions == ["按科室统计关联疾病条目"] * 2
