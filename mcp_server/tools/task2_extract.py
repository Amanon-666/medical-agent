"""
任务二实体、关系和三元组抽取 MCP 工具。
"""
from dataclasses import asdict, is_dataclass
from typing import Any

from mcp_server.tools import mcp
from core.llm_client import LLMClient
from core.medical_extraction_service import extract_medical_knowledge, normalize_backend
from mcp_server.config import KG_DB, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

_llm = None
def _get_llm():
    global _llm
    if _llm is None:
        _llm = LLMClient(base_url=LLM_BASE_URL, model=LLM_MODEL, api_key=LLM_API_KEY or None)
    return _llm


def _jsonable(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _llm_for_backend(backend: str) -> LLMClient | None:
    selected = normalize_backend(backend)
    return _get_llm() if selected in {"llm", "hybrid"} else None


@mcp.tool
def extract_medical_entities(text: str, backend: str = "offline") -> list:
    """抽取医学实体，支持本地规则、大模型或混合后端。"""
    result = extract_medical_knowledge(
        text,
        backend=backend,
        kg_db_path=KG_DB,
        llm=_llm_for_backend(backend),
    )
    return _jsonable(result.entities)

@mcp.tool
def extract_medical_relations(text: str, backend: str = "offline") -> list:
    """抽取医学关系，支持本地规则、大模型或混合后端。"""
    result = extract_medical_knowledge(
        text,
        backend=backend,
        kg_db_path=KG_DB,
        llm=_llm_for_backend(backend),
    )
    return _jsonable(result.relations)

@mcp.tool
def generate_medical_triples(text: str, backend: str = "offline") -> list:
    """生成医学 SPO 三元组，支持本地规则、大模型或混合后端。"""
    result = extract_medical_knowledge(
        text,
        backend=backend,
        kg_db_path=KG_DB,
        llm=_llm_for_backend(backend),
    )
    return _jsonable(result.triples)
