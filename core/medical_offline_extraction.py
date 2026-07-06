# -*- coding: utf-8 -*-
"""
本地医学实体和关系抽取模块。

该模块基于词典、规则和文本模式完成基础抽取，降低任务二对外部模型接口的依赖。
"""

from __future__ import annotations

import re
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from .schemas import Entity, Relation, Triple
from .medical_extraction_validation import relations_to_triples


KG_TO_ENTITY_TYPE = {
    "disease": "dis",
    "symptom": "sym",
    "drug": "dru",
    "test": "ite",
    "procedure": "pro",
    "department": "dep",
    "body_part": "bod",
    "microorganism": "mic",
}

KG_TO_RELATION_TYPE = {
    "has_symptom": "临床表现",
    "treated_by_drug": "药物治疗",
    "treated_by_procedure": "辅助治疗",
    "requires_test": "辅助检查",
    "visit_department": "就诊科室",
    "has_complication": "并发症",
    "has_cause": "病因",
    "has_prevention": "预防",
    "affects_body_part": "发病部位",
    "alias_of": "同义词",
    "related_to": "相关（导致）",
}

TYPE_TO_DEFAULT_RELATION = {
    "sym": "临床表现",
    "dru": "药物治疗",
    "ite": "辅助检查",
    "pro": "辅助治疗",
    "dep": "就诊科室",
    "bod": "发病部位",
    "mic": "病因",
}

SEED_TERMS = {
    "dis": ["糖尿病", "2型糖尿病", "高血压", "胃溃疡", "心力衰竭", "幽门螺杆菌感染"],
    "sym": ["多饮", "多尿", "口干", "胸闷", "气促", "水肿", "上腹部疼痛", "反酸", "嗳气"],
    "dru": ["二甲双胍", "胰岛素", "硝苯地平", "奥美拉唑", "阿莫西林", "克拉霉素"],
    "ite": ["血糖", "空腹血糖", "糖化血红蛋白", "HbA1c", "血压", "胃镜", "尿糖"],
    "pro": ["饮食控制", "血糖监测", "利尿", "降压"],
    "dep": ["内分泌科", "心内科", "消化内科"],
    "mic": ["幽门螺杆菌", "Hp"],
}

STOP_TERMS = {
    "患者", "医生", "治疗", "检查", "诊断", "病史", "阳性", "阴性",
    "糖尿", "内科", "外科", "儿童", "老人", "男性", "女性",
}
TYPE_PRIORITY = {
    "dis": 0,
    "dru": 1,
    "sym": 2,
    "ite": 3,
    "pro": 4,
    "dep": 5,
    "mic": 6,
    "bod": 7,
}
SENTENCE_RE = re.compile(r"[^。！？!?；;\n]+")


def _valid_term(term: str) -> bool:
    term = (term or "").strip()
    if not term or term in STOP_TERMS:
        return False
    if len(term) < 2:
        return False
    if len(term) > 32:
        return False
    if re.fullmatch(r"[\d.]+", term):
        return False
    return True


@lru_cache(maxsize=8)
def load_entity_dictionary(db_path: str = "") -> tuple[tuple[str, str], ...]:
    """加载实体词典，返回术语和 CMeEE 类型。"""
    term_types: dict[str, set[str]] = {}
    path = Path(db_path) if db_path else None
    if path and path.exists():
        conn = sqlite3.connect(str(path))
        try:
            rows = conn.execute(
                """
                SELECT canonical_name, entity_type
                FROM kg_entities
                WHERE canonical_name IS NOT NULL AND canonical_name != ''
                """
            )
            for name, kg_type in rows:
                entity_type = KG_TO_ENTITY_TYPE.get(str(kg_type or "").strip())
                value = str(name or "").strip()
                if entity_type and _valid_term(value):
                    term_types.setdefault(value, set()).add(entity_type)
        finally:
            conn.close()

    for entity_type, values in SEED_TERMS.items():
        for value in values:
            if _valid_term(value):
                term_types.setdefault(value, set()).add(entity_type)

    terms = [
        (value, sorted(types, key=lambda item: TYPE_PRIORITY.get(item, 99))[0])
        for value, types in term_types.items()
    ]
    return tuple(sorted(terms, key=lambda item: (-len(item[0]), item[0], item[1])))


def _find_occurrences(text: str, term: str) -> Iterable[tuple[int, int]]:
    start = text.find(term)
    while start >= 0:
        yield start, start + len(term) - 1
        start = text.find(term, start + 1)


def extract_entities_offline(text: str, db_path: str = "") -> list[Entity]:
    """使用本地知识图谱词典匹配抽取实体。"""
    if not text or not text.strip():
        return []

    entities: list[Entity] = []
    seen: set[tuple[int, int, str]] = set()
    occupied_spans: list[tuple[int, int]] = []
    for term, entity_type in load_entity_dictionary(db_path):
        if term not in text:
            continue
        for start, end in _find_occurrences(text, term):
            if any(old_start <= start and end <= old_end for old_start, old_end in occupied_spans):
                continue
            key = (start, end, entity_type)
            if key in seen:
                continue
            seen.add(key)
            occupied_spans.append((start, end))
            left = max(0, start - 20)
            right = min(len(text), end + 21)
            entities.append(
                Entity(
                    text=term,
                    type=entity_type,
                    start_idx=start,
                    end_idx=end,
                    confidence=0.82,
                    evidence=text[left:right],
                )
            )

    return sorted(entities, key=lambda item: (item.start_idx or 0, -len(item.text)))


def _sentence_spans(text: str) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), m.group(0)) for m in SENTENCE_RE.finditer(text or "")]


def _primary_diseases(text: str, entities: list[Entity]) -> list[Entity]:
    diseases = [entity for entity in entities if entity.type == "dis"]
    if not diseases:
        return []
    diagnosis_pos = text.find("诊断")
    if diagnosis_pos >= 0:
        near = [entity for entity in diseases if (entity.start_idx or 0) >= diagnosis_pos]
        if near:
            return near[:3]
    return diseases[:3]


def _known_relation(db_path: str, subject: str, obj: str) -> str:
    path = Path(db_path) if db_path else None
    if not path or not path.exists():
        return ""
    conn = sqlite3.connect(str(path))
    try:
        row = conn.execute(
            """
            SELECT t.relation_code
            FROM kg_triples t
            JOIN kg_entities s ON s.entity_id = t.subject_id
            JOIN kg_entities o ON o.entity_id = t.object_id
            WHERE s.canonical_name = ? AND o.canonical_name = ?
            GROUP BY t.relation_code
            ORDER BY COUNT(*) DESC
            LIMIT 1
            """,
            (subject, obj),
        ).fetchone()
    finally:
        conn.close()
    return KG_TO_RELATION_TYPE.get(row[0], "") if row else ""


def _relation_for(disease: Entity, obj: Entity, db_path: str = "") -> str:
    known = _known_relation(db_path, disease.text, obj.text)
    if known:
        return known
    return TYPE_TO_DEFAULT_RELATION.get(obj.type, "")


def extract_relations_offline(
    text: str,
    entities: list[Entity] | None = None,
    db_path: str = "",
) -> list[Relation]:
    """基于本地规则和知识图谱实体对抽取疾病中心关系。"""
    if not text or not text.strip():
        return []
    entities = entities if entities is not None else extract_entities_offline(text, db_path)
    diseases = [entity for entity in entities if entity.type == "dis"]
    if not diseases:
        return []

    relations: list[Relation] = []
    seen: set[tuple[str, str, str]] = set()

    sentence_spans = _sentence_spans(text)
    for sent_start, sent_end, sentence in sentence_spans:
        sent_diseases = [
            entity
            for entity in diseases
            if entity.start_idx is not None and sent_start <= entity.start_idx < sent_end
        ]
        if not sent_diseases:
            continue
        sent_entities = [
            entity
            for entity in entities
            if entity.start_idx is not None and sent_start <= entity.start_idx < sent_end
        ]
        for disease in sent_diseases[:2]:
            for obj in sent_entities:
                if obj.text == disease.text or obj.type == "dis":
                    continue
                predicate = _relation_for(disease, obj, db_path)
                if not predicate:
                    continue
                key = (disease.text, predicate, obj.text)
                if key in seen:
                    continue
                seen.add(key)
                relations.append(
                    Relation(
                        subject=disease.text,
                        subject_type=disease.type,
                        predicate=predicate,
                        object=obj.text,
                        object_type=obj.type,
                        confidence=0.78,
                        evidence=sentence.strip()[:500],
                    )
                )

    primary = _primary_diseases(text, entities)
    treatment_keywords = ("治疗", "处理", "用药", "给予", "予", "加用", "口服", "服用")
    check_keywords = ("检查", "监测", "复查", "提示", "示")
    for _, _, sentence in sentence_spans:
        has_context = any(keyword in sentence for keyword in treatment_keywords + check_keywords)
        if not has_context:
            continue
        sent_entities = [entity for entity in entities if entity.text in sentence]
        for disease in primary[:2]:
            for obj in sent_entities:
                if obj.text == disease.text or obj.type == "dis":
                    continue
                if obj.type == "dru" and not any(k in sentence for k in treatment_keywords):
                    continue
                if obj.type in {"ite", "pro"} and not any(k in sentence for k in check_keywords + treatment_keywords):
                    continue
                predicate = _relation_for(disease, obj, db_path)
                if not predicate:
                    continue
                key = (disease.text, predicate, obj.text)
                if key in seen:
                    continue
                seen.add(key)
                relations.append(
                    Relation(
                        subject=disease.text,
                        subject_type=disease.type,
                        predicate=predicate,
                        object=obj.text,
                        object_type=obj.type,
                        confidence=0.72,
                        evidence=sentence.strip()[:500],
                    )
                )

    return relations


def generate_triples_offline(
    text: str,
    entities: list[Entity] | None = None,
    relations: list[Relation] | None = None,
    db_path: str = "",
) -> list[Triple]:
    """根据本地关系抽取结果生成三元组。"""
    entities = entities if entities is not None else extract_entities_offline(text, db_path)
    relations = relations if relations is not None else extract_relations_offline(text, entities, db_path)
    return relations_to_triples(relations, min_confidence=0.7)
