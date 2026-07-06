# -*- coding: utf-8 -*-
"""
数据结构定义 —— 对应 config/schema.json 的数据契约。
所有核心函数的输入输出都用这些结构，保证三任务接口一致。
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional


@dataclass
class Entity:
    """医疗实体"""
    text: str
    type: str                      # 见 schema.json entity_types
    start_idx: Optional[int] = None
    end_idx: Optional[int] = None
    confidence: float = 1.0
    evidence: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = {"text": self.text, "type": self.type}
        if self.start_idx is not None:
            d["start_idx"] = self.start_idx
            d["end_idx"] = self.end_idx
        d["confidence"] = round(float(self.confidence), 4)
        if self.evidence:
            d["evidence"] = self.evidence
        return d


@dataclass
class Relation:
    """医疗关系（SPO 三元组，无置信度）"""
    subject: str
    predicate: str                 # 见 schema.json relation_types
    object: str
    subject_type: str = ""
    object_type: str = ""
    confidence: float = 1.0
    evidence: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "confidence": round(float(self.confidence), 4),
        }
        if self.subject_type:
            data["subject_type"] = self.subject_type
        if self.object_type:
            data["object_type"] = self.object_type
        if self.evidence:
            data["evidence"] = self.evidence
        return data


@dataclass
class Triple:
    """知识三元组（带置信度，用于入图谱）"""
    subject: str
    predicate: str
    object: str
    confidence: float = 1.0
    subject_type: str = ""
    object_type: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class QualityResult:
    """文本质量评分结果"""
    score: float
    detail: Dict[str, float] = field(default_factory=dict)
    passed: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {"quality_score": round(self.score, 4),
                "quality_detail": self.detail,
                "passed": self.passed}
