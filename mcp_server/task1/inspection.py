"""
任务一数据集探查模块。
"""

from __future__ import annotations

import re
from collections import Counter

from mcp_server.task1.datasets import datamate_dataset_host_path


MULTI_RECORD_PATTERN = re.compile(r"患者[:：]|主诉[:：]|病历号|住院号|姓名[:：]|病例\s*\d|={3,}|-{3,}")


def recommend_chain(file_types: set[str], multi_record_hint: bool = False) -> tuple[str, str]:
    """返回 DataMate 清洗链推荐和用户可读提示。"""

    if file_types <= {"csv", "xlsx", "xls"}:
        recommendation = "table_chain"
    elif file_types <= {"json", "jsonl"}:
        recommendation = "json_chain"
    elif file_types & {"csv", "xlsx", "xls"}:
        recommendation = "mixed"
    else:
        recommendation = "text_chain"

    advice = {
        "table_chain": "纯表格：选择 DataMate 表格清洗链，默认保持 CSV 格式",
        "json_chain": "JSON/JSONL：选择 DataMate JSON 字段清洗链，默认保持 JSON/JSONL 格式",
        "text_chain": (
            "纯文本：选择 DataMate 文本清洗链，默认保持 TXT 格式"
            + ("；仅在明确要求切分记录或交给任务二统一入口时，才追加病历分段" if multi_record_hint else "")
        ),
        "mixed": "混合：优先选择 run_task1_mixed_cleaning，按文件类型分批清洗并保持源格式；JSONL 统一转换留到任务二入口或显式指令",
    }.get(recommendation, "")
    return recommendation, advice


def summarize_file_types(rows: list[list[str]]) -> dict[str, int]:
    return dict(Counter(row[2] for row in rows if len(row) >= 3))


def build_preview_samples(
    rows: list[list[str]],
    dataset_volume: str,
    dataset_id: str,
    read_file,
    limit: int = 3,
) -> tuple[list[dict], bool]:
    """生成文件预览并识别多记录文本标记。"""

    samples: list[dict] = []
    multi_hint = False
    for row in rows[:limit]:
        fname = row[0]
        stored_path = row[1] if len(row) >= 2 else ""
        ftype = row[2] if len(row) >= 3 else ""
        host_path = datamate_dataset_host_path(dataset_volume, dataset_id, fname, stored_path)
        raw = read_file(host_path) or ""
        n_sig = len(MULTI_RECORD_PATTERN.findall(raw))
        is_multi = n_sig >= 2
        if is_multi:
            multi_hint = True
        samples.append(
            {
                "name": fname,
                "type": ftype,
                "preview": raw[:200],
                "looks_multi_record": is_multi,
            }
        )
    return samples, multi_hint
