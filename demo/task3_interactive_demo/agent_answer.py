"""
可视化平台回答安全处理模块。

该模块清理智能体返回文本中的非用户可见技术标记、危险 SQL 和不适合直接展示的内容。
"""

from __future__ import annotations

import re
from typing import Any


AGENT_TRACE_MARKERS = (
    "Calling tools:",
    "python_interpreter",
    "execute_nl2sql(",
    "inspect_dataset(",
    "run_task",
    "tool_calls",
    "arguments",
    "[{'id': 'call_",
    '"type": "function"',
    "<code>",
    "</code>",
    "```python",
    "SQL 被错误映射",
)


def is_agent_trace_leak(answer: str) -> bool:
    """判断智能体回答中是否混入工具调用草稿或过程痕迹。"""
    text = str(answer or "")
    if not text.strip():
        return True
    return any(marker in text for marker in AGENT_TRACE_MARKERS)


def clean_agent_answer(answer: str) -> str:
    """移除常见代码块和工具调用包装，保留正常回答正文。"""
    text = str(answer or "").strip()
    text = re.sub(r"<code>(.*?)</code>", r"\1", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"```(?:python|sql)?\s*.*?```", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.split(r"Calling tools:", text, maxsplit=1)[0].strip()
    return text


def choose_agent_display_answer(agent_answer: str, local_visual: dict[str, Any]) -> tuple[str, bool]:
    """选择面向用户的回答；若检测到过程痕迹则回退到本地证据回答。"""
    cleaned = clean_agent_answer(agent_answer)
    if is_agent_trace_leak(agent_answer) or len(cleaned) < 8:
        local_answer = str(local_visual.get("answer") or "查询完成。")
        row_count = int(local_visual.get("row_count") or 0)
        if row_count:
            return f"{local_answer}\n\n已同步生成证据表和统计图表。", True
        return local_answer, True
    return cleaned, False
