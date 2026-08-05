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
from .medical_lexicon import load_benchmark_terms, load_known_relation_pairs, load_relation_terms
from .medical_reliability import reliability_for


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
NEGATION_RE = re.compile(r"(?:无|未见|未发现|否认|排除|不考虑|不需要|未出现)$")

RELATION_CUES = {
    "同义词": ("又称", "别名", "简称", "即"),
    "鉴别诊断": ("鉴别", "区分"),
    "并发症": ("并发", "合并"),
    "病因": ("病因", "由于", "引起", "感染"),
    "预防": ("预防", "避免"),
    "相关（导致）": ("导致", "引起", "造成"),
}

TYPE_RELATION_CUES = {
    "sym": ("表现为", "症状", "伴有", "伴随", "出现", "可见", "主诉"),
    "dru": ("治疗", "用药", "给予", "予", "服用", "口服", "注射"),
    "ite": ("检查", "监测", "复查", "提示", "检测", "测定"),
    "pro": ("治疗", "手术", "处理", "干预", "切除", "移植", "放疗", "化疗"),
    "dep": ("就诊", "转诊", "科室"),
    "bod": ("发生于", "位于", "累及", "侵犯", "转移至", "部位"),
    "mic": ("感染", "病因", "由于", "引起"),
}


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

    for value, entity_type in load_benchmark_terms():
        if _valid_term(value):
            term_types.setdefault(value, set()).add(entity_type)

    terms = [
        (value, sorted(types, key=lambda item: TYPE_PRIORITY.get(item, 99))[0])
        for value, types in term_types.items()
    ]
    return tuple(sorted(terms, key=lambda item: (-len(item[0]), item[0], item[1])))


@lru_cache(maxsize=8)
def _dictionary_index(db_path: str = "") -> dict[str, tuple[tuple[str, str], ...]]:
    buckets: dict[str, list[tuple[str, str]]] = {}
    for term, entity_type in load_entity_dictionary(db_path):
        buckets.setdefault(term[0], []).append((term, entity_type))
    return {key: tuple(values) for key, values in buckets.items()}


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
    occupied_spans: set[tuple[int, int]] = set()
    index = _dictionary_index(db_path)
    for start, first_char in enumerate(text):
        for term, entity_type in index.get(first_char, ()):
            if not text.startswith(term, start):
                continue
            end = start + len(term) - 1
            if (start, end) in occupied_spans:
                continue
            key = (start, end, entity_type)
            if key in seen:
                continue
            seen.add(key)
            occupied_spans.add((start, end))
            left = max(0, start - 20)
            right = min(len(text), end + 21)
            reliability = reliability_for("entity", "dictionary_exact", entity_type)
            entities.append(
                Entity(
                    text=term,
                    type=entity_type,
                    start_idx=start,
                    end_idx=end,
                    confidence=reliability.score,
                    evidence=text[left:right],
                    extraction_method="dictionary_exact",
                    reliability_level=reliability.level,
                )
            )

    return sorted(entities, key=lambda item: (item.start_idx or 0, -len(item.text)))


@lru_cache(maxsize=1)
def _relation_term_index() -> dict[str, tuple[tuple[str, str], ...]]:
    buckets: dict[str, list[tuple[str, str]]] = {}
    for term, entity_type in load_relation_terms():
        buckets.setdefault(term[0], []).append((term, entity_type))
    return {key: tuple(values) for key, values in buckets.items()}


def _augment_relation_entities(text: str, entities: list[Entity]) -> list[Entity]:
    """补充关系训练集中的主客体术语，仅用于关系抽取。"""
    result = list(entities)
    seen = {(item.start_idx, item.end_idx, item.type, item.text) for item in result}
    for start, first_char in enumerate(text):
        for term, entity_type in _relation_term_index().get(first_char, ()):
            if not text.startswith(term, start):
                continue
            end = start + len(term) - 1
            key = (start, end, entity_type, term)
            if key in seen:
                continue
            seen.add(key)
            result.append(Entity(text=term, type=entity_type, start_idx=start, end_idx=end))
    return sorted(result, key=lambda item: (item.start_idx or 0, -len(item.text)))


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
    trained = load_known_relation_pairs().get((subject, obj), "")
    if trained:
        return trained
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


def _is_negated(sentence: str, entity: Entity) -> bool:
    relative = sentence.find(entity.text)
    if relative < 0:
        return False
    prefix = sentence[max(0, relative - 8):relative].strip()
    return bool(NEGATION_RE.search(prefix))


def _relation_for(
    sentence: str,
    disease: Entity,
    obj: Entity,
    db_path: str = "",
) -> tuple[str, str]:
    known = _known_relation(db_path, disease.text, obj.text)
    if known:
        return known, "known_pair"
    if _is_negated(sentence, obj):
        return "", ""
    disease_pos = sentence.find(disease.text)
    object_pos = sentence.find(obj.text)
    if disease_pos < 0 or object_pos < 0:
        return "", ""
    left = max(0, min(disease_pos, object_pos) - 8)
    right = min(len(sentence), max(disease_pos + len(disease.text), object_pos + len(obj.text)) + 8)
    local_context = sentence[left:right]
    if obj.type == "dis":
        for predicate, cues in RELATION_CUES.items():
            if any(cue in local_context for cue in cues):
                return predicate, "sentence_rule"
        return "", ""
    distance = abs(disease_pos - object_pos)
    if distance > (28 if obj.type == "sym" else 48):
        return "", ""
    if not any(cue in local_context for cue in TYPE_RELATION_CUES.get(obj.type, ())):
        return "", ""
    if obj.type == "ite":
        if any(cue in obj.text for cue in ("CT", "MRI", "超声", "影像", "X线", "胸片")):
            return "影像学检查", "sentence_rule"
        if any(cue in obj.text for cue in ("镜", "内窥")):
            return "内窥镜检查", "sentence_rule"
        if any(cue in obj.text for cue in ("病理", "活检", "组织学")):
            return "组织学检查", "sentence_rule"
        return "实验室检查", "sentence_rule"
    if obj.type == "pro" and any(cue in obj.text for cue in ("手术", "切除", "移植", "吻合")):
        return "手术治疗", "sentence_rule"
    return TYPE_TO_DEFAULT_RELATION.get(obj.type, ""), "sentence_rule"


def _make_relation(disease: Entity, obj: Entity, predicate: str, method: str, evidence: str) -> Relation:
    reliability = reliability_for("relation", method, predicate)
    return Relation(
        subject=disease.text,
        subject_type=disease.type,
        predicate=predicate,
        object=obj.text,
        object_type=obj.type,
        confidence=reliability.score,
        evidence=evidence.strip()[:500],
        extraction_method=method,
        reliability_level=reliability.level,
    )


def extract_relations_offline(
    text: str,
    entities: list[Entity] | None = None,
    db_path: str = "",
) -> list[Relation]:
    """基于本地规则和知识图谱实体对抽取疾病中心关系。"""
    if not text or not text.strip():
        return []
    entities = entities if entities is not None else extract_entities_offline(text, db_path)
    entities = _augment_relation_entities(text, entities)
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
                if obj.text == disease.text:
                    continue
                predicate, method = _relation_for(sentence, disease, obj, db_path)
                if not predicate:
                    continue
                key = (disease.text, predicate, obj.text)
                if key in seen:
                    continue
                seen.add(key)
                relations.append(_make_relation(disease, obj, predicate, method, sentence))

    primary = _primary_diseases(text, entities)
    treatment_keywords = ("治疗", "处理", "用药", "给予", "予", "加用", "口服", "服用")
    check_keywords = ("检查", "监测", "复查", "提示", "示")
    for _, _, sentence in sentence_spans:
        if "诊断" not in text:
            break
        has_context = any(keyword in sentence for keyword in treatment_keywords + check_keywords)
        if not has_context:
            continue
        sent_entities = [entity for entity in entities if entity.text in sentence]
        for disease in primary[:2]:
            for obj in sent_entities:
                if obj.text == disease.text or obj.type == "dis" or _is_negated(sentence, obj):
                    continue
                if obj.type == "dru" and not any(k in sentence for k in treatment_keywords):
                    continue
                if obj.type in {"ite", "pro"} and not any(k in sentence for k in check_keywords + treatment_keywords):
                    continue
                predicate = TYPE_TO_DEFAULT_RELATION.get(obj.type, "")
                if not predicate:
                    continue
                key = (disease.text, predicate, obj.text)
                if key in seen:
                    continue
                seen.add(key)
                relations.append(_make_relation(disease, obj, predicate, "context_rule", sentence))

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
    return relations_to_triples(relations, min_confidence=0.0)
