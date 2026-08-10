"""可视化平台共享的任务三分析服务与短期结果缓存。"""

from __future__ import annotations

import os
import sys
from collections import OrderedDict
from functools import lru_cache
from threading import Lock
from typing import Any

from paths import ANALYSIS_RESULT_DIR, ANALYTICS_DB, KG_DB, ROOT


if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.llm_client import LLMClient  # noqa: E402
from task3.result_repository import AnalysisResultRepository  # noqa: E402
from task3.runtime import build_analysis_service  # noqa: E402
from task3.service import MedicalAnalysisService  # noqa: E402


_CACHE_LIMIT = 32
_CACHE_LOCK = Lock()
_ANALYSIS_CACHE: OrderedDict[str, dict[str, Any]] = OrderedDict()


def _load_api_key() -> str | None:
    api_key = os.environ.get("CCF_LLM_API_KEY")
    key_file = os.environ.get("CCF_LLM_API_KEY_FILE")
    if api_key:
        return api_key.strip()
    if key_file:
        try:
            return open(key_file, encoding="utf-8").read().strip() or None
        except OSError:
            return None
    return None


@lru_cache(maxsize=1)
def get_analysis_repository() -> AnalysisResultRepository:
    return AnalysisResultRepository(
        ANALYSIS_RESULT_DIR,
        max_records=int(os.environ.get("CCF_TASK3_RESULT_LIMIT", "128")),
    )


@lru_cache(maxsize=1)
def get_analysis_service() -> MedicalAnalysisService:
    """按运行环境装配分析服务，避免在请求间重复创建客户端。"""

    api_key = _load_api_key()
    llm = None
    if api_key:
        llm = LLMClient(
            base_url=os.environ.get(
                "CCF_LLM_BASE_URL",
                "https://api.deepseek.com/v1/chat/completions",
            ),
            model=os.environ.get("CCF_LLM_MODEL", "deepseek-chat"),
            api_key=api_key,
            timeout=int(os.environ.get("CCF_TASK3_LLM_TIMEOUT", "90")),
        )
    return build_analysis_service(
        ANALYTICS_DB,
        kg_db_path=KG_DB,
        llm=llm,
    )


def remember_analysis(result: dict[str, Any]) -> dict[str, Any]:
    """保留最近的分析记录，供同一页面导出，不形成无界内存增长。"""

    analysis_id = str(result.get("analysis_id") or "")
    if not analysis_id:
        return result
    with _CACHE_LOCK:
        _ANALYSIS_CACHE[analysis_id] = result
        _ANALYSIS_CACHE.move_to_end(analysis_id)
        while len(_ANALYSIS_CACHE) > _CACHE_LIMIT:
            _ANALYSIS_CACHE.popitem(last=False)
    get_analysis_repository().save(result)
    return result


def analyze_question(question: str) -> dict[str, Any]:
    return remember_analysis(get_analysis_service().analyze(question))


def get_cached_analysis(analysis_id: str) -> dict[str, Any] | None:
    key = str(analysis_id or "")
    with _CACHE_LOCK:
        result = _ANALYSIS_CACHE.get(key)
        if result is not None:
            _ANALYSIS_CACHE.move_to_end(key)
            return result
    result = get_analysis_repository().load(key)
    if result is None:
        return None
    with _CACHE_LOCK:
        _ANALYSIS_CACHE[key] = result
        _ANALYSIS_CACHE.move_to_end(key)
        while len(_ANALYSIS_CACHE) > _CACHE_LIMIT:
            _ANALYSIS_CACHE.popitem(last=False)
    return result
