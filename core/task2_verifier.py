# -*- coding: utf-8 -*-
"""任务二级联抽取的 LLM 适配层。

本模块只做两件事：批量复核已经存在的低可靠候选，以及从被离线链路漏掉
的句子中提出候选。最终是否进入结果由 ``task2_cascade`` 的严格门控决定。
LLM 不会在这里直接写数据库。
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any, Iterable

from .llm_client import LLMClient
from .medical_extraction_validation import (
    normalize_entity_type,
    normalize_relation_type,
    validate_entities,
    validate_relations,
)
from .medical_ner import ENTITY_TYPES
from .medical_re import RELATION_TYPES
from .schemas import Entity, Relation
from .task2_cascade_schemas import CascadeSegment, ReviewCandidate, ReviewDecision


_DECISION_ALIASES = {
    "accept": "accept",
    "accepted": "accept",
    "yes": "accept",
    "支持": "accept",
    "保留": "accept",
    "reject": "reject",
    "rejected": "reject",
    "no": "reject",
    "不支持": "reject",
    "删除": "reject",
    "uncertain": "uncertain",
    "unknown": "uncertain",
    "不确定": "uncertain",
    "无法判断": "uncertain",
}


def _as_list(payload: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _normalize_decision(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return _DECISION_ALIASES.get(raw, "uncertain")


def _normalize_confidence(value: Any) -> float:
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _review_prompt(candidates: Iterable[ReviewCandidate]) -> str:
    candidate_payload = [candidate.to_prompt_dict() for candidate in candidates]
    return (
        "You are a conservative medical fact verifier. Review only the supplied candidates; "
        "do not create new facts and do not rewrite any text.\n"
        "Review each offline mention independently. An offline candidate is the baseline: "
        "reject it only when the evidence explicitly contradicts, negates, or clearly "
        "invalidates the candidate. Do not reject a candidate merely because the term is "
        "generic, appears inside a longer mention, or has an ambiguous type; use uncertain "
        "and keep the offline baseline in those cases. A relation decision is independent "
        "from the review decision for either endpoint entity.\n"
        "For a gap candidate, accept means every endpoint and the relation are directly "
        "supported by its evidence; reject or uncertain means do not add it. Be conservative.\n"
        "Return JSON only in this form: "
        '{"decisions":[{"candidate_id":"...","decision":"accept|reject|uncertain",'
        '"reason":"short reason","confidence":0.0}]}\n'
        "Use each candidate_id at most once.\n"
        "Candidates:\n"
        + json.dumps(candidate_payload, ensure_ascii=False)
    )


def review_candidates(
    llm: LLMClient,
    candidates: list[ReviewCandidate],
    *,
    batch_size: int = 32,
) -> dict[str, ReviewDecision]:
    """批量复核候选；缺失或无法解析的结果一律视为 uncertain。"""

    decisions: dict[str, ReviewDecision] = {}
    size = max(1, int(batch_size))
    for offset in range(0, len(candidates), size):
        batch = candidates[offset : offset + size]
        payload = llm.chat_json(_review_prompt(batch))
        for item in _as_list(payload, "decisions", "results"):
            candidate_id = str(item.get("candidate_id", "")).strip()
            if not candidate_id or candidate_id not in {c.candidate_id for c in batch}:
                continue
            decisions[candidate_id] = ReviewDecision(
                candidate_id=candidate_id,
                decision=_normalize_decision(item.get("decision")),
                reason=str(item.get("reason", "") or "").strip()[:240],
                confidence=_normalize_confidence(item.get("confidence")),
            )
    return decisions


def _gap_prompt(segments: list[CascadeSegment]) -> str:
    segment_payload = [
        {"segment_id": segment.segment_id, "text": segment.text[:600], "reasons": segment.reasons}
        for segment in segments
    ]
    entity_types = ", ".join(f"{key}={value}" for key, value in ENTITY_TYPES.items())
    relation_types = ", ".join(RELATION_TYPES)
    return (
        "You extract only directly stated medical facts from the supplied Chinese text segments. "
        "Do not use outside medical knowledge. Preserve exact source strings.\n"
        f"Entity types: {entity_types}\n"
        f"Relation types: {relation_types}\n"
        "Important extraction rules: enumerate every item introduced by Chinese list cues "
        "such as \u5982, \u5305\u62ec, \u4f8b\u5982, or joined by \u548c/\u3001. Propagate the "
        "nearest explicit relation frame across that list even when the verb is not repeated. "
        "For example, \u5728\u5173\u8282(\u5982 A \u548c B) yields a separate \u53d1\u75c5\u90e8\u4f4d "
        "relation to \u5173\u8282, A, and B; \u6f5c\u5728\u7684\u75c5\u56e0(\u5982 C\u3001D) yields a "
        "separate \u75c5\u56e0 relation to C and D. Do not invent a cause entity type; use "
        "one of the listed CMeIE entity types, and keep the relation predicate as \u75c5\u56e0.\n"
        "For every relation, include both endpoints in that segment's entities. "
        "Use an empty list when no fact is directly stated.\n"
        "Return JSON only in this form: "
        '{"segments":[{"segment_id":"s0","entities":[{"text":"...","type":"dis",'
        '"start_idx":0,"end_idx":1,"confidence":0.9}],"relations":[{"subject":"...",'
        '"subject_type":"dis","predicate":"...","object":"...",'
        '"object_type":"sym","confidence":0.9}]}]}\n'
        "Segments:\n"
        + json.dumps(segment_payload, ensure_ascii=False)
    )


def _add_missing_relation_endpoints(raw_entities: Any, raw_relations: Any) -> list[dict[str, Any]]:
    """Make relation endpoints visible to validation when the model omitted them."""

    entities = [item for item in raw_entities if isinstance(item, dict)] if isinstance(raw_entities, list) else []
    relations = raw_relations if isinstance(raw_relations, list) else []
    known_texts = {
        str(item.get("text", item.get("entity", "")) or "").strip()
        for item in entities
    }
    for item in relations:
        if not isinstance(item, dict):
            continue
        predicate = normalize_relation_type(item.get("predicate"))
        object_value = item.get("object", "")
        if isinstance(object_value, dict):
            object_value = object_value.get("@value", object_value.get("value", ""))
        endpoint_specs = (
            ("subject", "subject_type", "dis"),
            ("object", "object_type", "sym"),
        )
        for value_key, type_key, fallback_type in endpoint_specs:
            raw_value = object_value if value_key == "object" else item.get(value_key, "")
            value = str(raw_value or "").strip()
            if not value or value in known_texts:
                continue
            entity_type = normalize_entity_type(item.get(type_key))
            if not entity_type and predicate == "\u53d1\u75c5\u90e8\u4f4d" and value_key == "object":
                entity_type = "bod"
            elif not entity_type and predicate == "\u75c5\u56e0" and value_key == "object":
                entity_type = "sym"
            elif not entity_type:
                entity_type = fallback_type
            if entity_type:
                entities.append({"text": value, "type": entity_type})
                known_texts.add(value)
    return entities


def extract_gap_facts(
    text: str,
    segments: list[CascadeSegment],
    llm: LLMClient,
) -> tuple[list[Entity], list[Relation]]:
    """用一次受限批量请求处理缺口句子，并把局部位置还原到原文。"""

    if not segments:
        return [], []
    payload = llm.chat_json(_gap_prompt(segments))
    segment_by_id = {segment.segment_id: segment for segment in segments}
    entities: list[Entity] = []
    relations: list[Relation] = []

    for segment_item in _as_list(payload, "segments", "results"):
        segment_id = str(segment_item.get("segment_id", "")).strip()
        segment = segment_by_id.get(segment_id)
        if segment is None:
            continue
        raw_entities = _add_missing_relation_endpoints(
            segment_item.get("entities", []),
            segment_item.get("relations", []),
        )
        local_entities = validate_entities(segment.text, raw_entities)
        local_relations = validate_relations(
            segment.text,
            segment_item.get("relations", []),
            entities=local_entities,
        )
        for entity in local_entities:
            local_start = entity.start_idx or 0
            local_end = entity.end_idx if entity.end_idx is not None else local_start + len(entity.text) - 1
            left = max(0, segment.start_idx + local_start - 20)
            right = min(len(text), segment.start_idx + local_end + 21)
            entities.append(
                replace(
                    entity,
                    start_idx=segment.start_idx + local_start,
                    end_idx=segment.start_idx + local_end,
                    evidence=text[left:right],
                    extraction_method="llm_gap_candidate",
                    reliability_level="medium",
                )
            )
        for relation in local_relations:
            relations.append(
                replace(
                    relation,
                    evidence=segment.text[:500],
                    extraction_method="llm_gap_candidate",
                    reliability_level="medium",
                )
            )
    return entities, relations
