"""
任务三 NL2SQL MCP 工具。
"""
from mcp_server.tools import mcp
from core.llm_client import LLMClient
from core.nl2sql import nl2sql as _nl2sql_func
from mcp_server.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, SQL_DB

_llm = None
def _get_llm():
    global _llm
    if _llm is None:
        _llm = LLMClient(base_url=LLM_BASE_URL, model=LLM_MODEL, api_key=LLM_API_KEY or None)
    return _llm

@mcp.tool
def execute_nl2sql(question: str) -> dict:
    """将中文医学统计问题转换为只读 SQL，并在分析库中执行返回结果。"""
    return _nl2sql_func(question, _get_llm(), db_path=SQL_DB)
