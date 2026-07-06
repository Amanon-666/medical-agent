# -*- coding: utf-8 -*-
"""
医学抽取结果校验模块。

该模块校验实体、关系和三元组结构，过滤缺字段、类型不合法或明显冲突的结果。
"""

from __future__ import annotations

from typing import Any, Iterable

from .schemas import Entity, Relation, Triple


ENTITY_TYPES = {
    "dis",
    "sym",
    "dru",
    "equ",
    "pro",
    "bod",
    "ite",
    "mic",
    "dep",
}

ENTITY_TYPE_ALIASES = {
    "疾病": "dis",
    "disease": "dis",
    "症状": "sym",
    "症状体征": "sym",
    "symptom": "sym",
    "药物": "dru",
    "药品": "dru",
    "drug": "dru",
    "医疗设备": "equ",
    "设备": "equ",
    "equipment": "equ",
    "医疗程序": "pro",
    "治疗": "pro",
    "治疗方法": "pro",
    "手术": "pro",
    "操作": "pro",
    "procedure": "pro",
    "身体部位": "bod",
    "部位": "bod",
    "body": "bod",
    "检验项目": "ite",
    "检查项目": "ite",
    "检查": "ite",
    "检验": "ite",
    "test": "ite",
    "微生物": "mic",
    "microorganism": "mic",
    "科室": "dep",
    "department": "dep",
}

CMEIE_RELATION_TYPES = {
    "临床表现",
    "传播途径",
    "侵及周围组织转移的症状",
    "内窥镜检查",
    "化疗",
    "发病年龄",
    "发病性别倾向",
    "发病机制",
    "发病率",
    "发病部位",
    "同义词",
    "外侵部位",
    "多发地区",
    "多发季节",
    "多发群体",
    "实验室检查",
    "就诊科室",
    "并发症",
    "影像学检查",
    "手术治疗",
    "放射治疗",
    "死亡率",
    "治疗后症状",
    "病史",
    "病因",
    "病理分型",
    "病理生理",
    "相关（导致）",
    "相关（症状）",
    "相关（转化）",
    "筛查",
    "组织学检查",
    "药物治疗",
    "转移部位",
    "辅助检查",
    "辅助治疗",
    "遗传因素",
    "鉴别诊断",
    "阶段",
    "预后状况",
    "预后生存率",
    "预防",
    "风险评估因素",
    "高危因素",
}

RELATION_ALIASES = {
    "症状": "临床表现",
    "临床症状": "临床表现",
    "治疗": "辅助治疗",
    "治疗方式": "辅助治疗",
    "检查": "辅助检查",
    "诊断": "辅助检查",
    "风险因素": "高危因素",
    "危险因素": "高危因素",
    "所属科室": "就诊科室",
    "科室": "就诊科室",
    "预后": "预后状况",
    "转移": "转移部位",
}


def normalize_entity_type(value: Any) -> str:
    raw = str(value or "").strip()
    normalized = ENTITY_TYPE_ALIASES.get(raw, raw.lower())
    return normalized if normalized in ENTITY_TYPES else ""


def normalize_relation_type(value: Any) -> str:
    raw = str(value or "").strip()
    normalized = RELATION_ALIASES.get(raw, raw)
    return normalized if normalized in CMEIE_RELATION_TYPES else ""


def _all_occurrences(text: str, value: str) -> Iterable[tuple[int, int]]:
    start = text.find(value)
    while start >= 0:
        yield start, start + len(value) - 1
        start = text.find(value, start + 1)


def validate_entities(text: str, raw_items: Any) -> list[Entity]:
    if not isinstance(raw_items, list):
        return []

    entities: list[Entity] = []
    seen: set[tuple[int, int, str]] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        value = str(item.get("text", item.get("entity", "")) or "").strip()
        entity_type = normalize_entity_type(item.get("type"))
        if not value or not entity_type or value not in text:
            continue

        positions: list[tuple[int, int]] = []
        try:
            start = int(item.get("start_idx", item.get("start")))
            end = int(item.get("end_idx", item.get("end")))
        except (TypeError, ValueError):
            start = end = -1
        if 0 <= start <= end < len(text) and text[start : end + 1] == value:
            positions.append((start, end))
        else:
            positions.extend(_all_occurrences(text, value))

        try:
            confidence = min(1.0, max(0.0, float(item.get("confidence", 0.9))))
        except (TypeError, ValueError):
            confidence = 0.9

        for start, end in positions:
            key = (start, end, entity_type)
            if key in seen:
                continue
            seen.add(key)
            left = max(0, start - 20)
            right = min(len(text), end + 21)
            entities.append(
                Entity(
                    text=value,
                    type=entity_type,
                    start_idx=start,
                    end_idx=end,
                    confidence=confidence,
                    evidence=text[left:right],
                )
            )
    return sorted(entities, key=lambda entity: (entity.start_idx or 0, -(len(entity.text))))


def validate_relations(
    text: str,
    raw_items: Any,
    entities: list[Entity] | None = None,
) -> list[Relation]:
    if not isinstance(raw_items, list):
        return []

    entity_types: dict[str, str] = {}
    for entity in entities or []:
        entity_types.setdefault(entity.text, entity.type)

    relations: list[Relation] = []
    seen: set[tuple[str, str, str]] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        subject = str(item.get("subject", "") or "").strip()
        object_value = item.get("object", "")
        if isinstance(object_value, dict):
            object_value = object_value.get("@value", object_value.get("value", ""))
        obj = str(object_value or "").strip()
        predicate = normalize_relation_type(item.get("predicate"))
        if not subject or not obj or not predicate:
            continue
        if subject not in text or obj not in text:
            continue
        if entities and (subject not in entity_types or obj not in entity_types):
            continue

        key = (subject, predicate, obj)
        if key in seen:
            continue
        seen.add(key)
        try:
            confidence = min(1.0, max(0.0, float(item.get("confidence", 0.88))))
        except (TypeError, ValueError):
            confidence = 0.88
        subject_type = entity_types.get(
            subject, normalize_entity_type(item.get("subject_type"))
        )
        object_type = entity_types.get(
            obj, normalize_entity_type(item.get("object_type"))
        )
        relations.append(
            Relation(
                subject=subject,
                predicate=predicate,
                object=obj,
                subject_type=subject_type,
                object_type=object_type,
                confidence=confidence,
                evidence=text[:500],
            )
        )
    return relations


def relations_to_triples(
    relations: Iterable[Relation],
    min_confidence: float = 0.7,
) -> list[Triple]:
    triples: list[Triple] = []
    seen: set[tuple[str, str, str]] = set()
    for relation in relations:
        key = (relation.subject, relation.predicate, relation.object)
        if relation.confidence < min_confidence or key in seen:
            continue
        seen.add(key)
        triples.append(
            Triple(
                subject=relation.subject,
                predicate=relation.predicate,
                object=relation.object,
                confidence=relation.confidence,
                subject_type=relation.subject_type,
                object_type=relation.object_type,
            )
        )
    return triples
