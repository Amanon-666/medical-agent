"""任务一治理元数据登记辅助模块。

当前在线流程会在任务一报告中写入血缘、标签和质量统计。不同 DataMate
版本的治理表结构存在差异，因此本模块采用保守策略：读取清洗报告中的
可观测信息，返回结构化摘要；如果目标环境提供治理表，可在这里扩展写库。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def register_governance(report_path: Path) -> dict[str, Any]:
    """读取任务一报告并返回治理元数据摘要。

    参数:
        report_path: `mixed_cleaning_service.py` 生成的 JSON 报告路径。

    返回:
        可写入最终报告的治理摘要。函数不虚构数据库写入结果；若报告不存在
        或格式异常，会返回可观察的错误状态。
    """
    path = Path(report_path)
    if not path.exists():
        return {"status": "skipped", "reason": "report_not_found", "report_path": str(path)}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "skipped", "reason": f"invalid_report: {exc}", "report_path": str(path)}

    return {
        "status": "recorded_in_report",
        "source_dataset_id": payload.get("source_dataset", {}).get("id"),
        "final_dataset_id": payload.get("final_delivery_dataset", {}).get("id")
        or payload.get("final_dataset", {}).get("id"),
        "quality_report": payload.get("quality_report") or payload.get("reports"),
        "report_path": str(path),
    }
