# -*- coding: utf-8 -*-
"""任务二的离线优先级联抽取。

流程固定为：

1. 离线词典和规则扫描全文；
2. 只把低可靠离线关系和离线未覆盖的医学句子交给 LLM；
3. LLM 复核通过的新增事实才进入最终结果，复核失败或不确定不新增；
4. LLM 调用失败时完整保留离线结果，并由上层返回显式错误。

这使 hybrid 成为一个安全的级联入口，而不是两个抽取器的无条件并集。
"""

from __future__ import annotations

import os
import re
from dataclasses import replace
from typing import Any

from .llm_client import LLMClient
from .medical_extraction_validation import relations_to_triples
from .medical_offline_extraction import (
    extract_entities_offline,
    extract_relations_offline,
)
from .schemas import Entity, Relation, Triple
from .task2_cascade_schemas import CascadeOutput, CascadeSegment, ReviewCandidate
from .task2_verifier import extract_gap_facts, review_candidates


_SENTENCE_RE = re.compile(r"[^。！？!?；;\n]+(?:[。！？!?；;\n]|$)")
_GAP_CUES = (
    "诊断",
    "症状",
    "表现",
    "病因",
    "并发",
    "治疗",
    "用药",
    "服用",
    "检查",
    "监测",
    "感染",
    "预防",
    "导致",
    "包括",
    "患者",
    "疾病",
    "药物",
    "手术",
    "检验",
)


def _sentence_spans(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    for match in _SENTENCE_RE.finditer(text or ""):
        raw = match.group(0)
        leading = len(raw) - len(raw.lstrip())
        trailing = len(raw.rstrip())
        start = match.start() + leading
        end = match.start() + trailing
        if start < end:
            spans.append((start, end, text[start:end]))
    return spans


def _entity_in_segment(entity: Entity, start: int, end: int) -> bool:
    if entity.start_idx is None:
        return False
    entity_end = (entity.end_idx if entity.end_idx is not None else entity.start_idx) + 1
    return entity.start_idx < end and entity_end > start


def _segment_relations(segment_text: str, relations: list[Relation]) -> list[Relation]:
    return [
        relation
        for relation in relations
        if relation.subject in segment_text and relation.object in segment_text
    ]


_CASCADE_CAUSAL_CUES = (
    "\u6f5c\u5728\u7684\u75c5\u56e0",
    "\u75c5\u56e0",
    "\u539f\u56e0",
    "\u7531\u4e8e",
    "\u5f15\u8d77",
    "\u5bfc\u81f4",
    "\u8bf1\u53d1",
)
_CASCADE_BODY_SITE_CUES = (
    "\u53d1\u75c5\u90e8\u4f4d",
    "\u597d\u53d1\u4e8e",
    "\u53d1\u751f\u4e8e",
    "\u4f4d\u4e8e",
    "\u7d2f\u53ca",
    "\u4fb5\u72af",
    "\u8f6c\u79fb\u81f3",
)
_CASCADE_LIST_CUES = ("\u5982", "\u5305\u62ec", "\u4f8b\u5982")
_CASCADE_CAUSAL_RELATIONS = {"\u75c5\u56e0", "\u76f8\u5173\uff08\u5bfc\u81f4\uff09"}
_CASCADE_BODY_SITE_RELATIONS = {"\u53d1\u75c5\u90e8\u4f4d", "\u5916\u4fb5\u90e8\u4f4d", "\u8f6c\u79fb\u90e8\u4f4d"}


def _segment_requires_gap_review(
    sentence: str,
    sentence_entities: list[Entity],
    sentence_relations: list[Relation],
) -> bool:
    """Detect partial coverage, rather than treating one relation as complete."""

    has_causal_cue = any(cue in sentence for cue in _CASCADE_CAUSAL_CUES)
    has_body_site_cue = any(cue in sentence for cue in _CASCADE_BODY_SITE_CUES)
    has_location_list = (
        "\u5728" in sentence
        and any(entity.type == "bod" for entity in sentence_entities)
        and any(cue in sentence for cue in _CASCADE_LIST_CUES)
    )
    has_gap_cue = (
        any(cue in sentence for cue in _GAP_CUES)
        or has_causal_cue
        or has_body_site_cue
        or has_location_list
    )
    if not has_gap_cue:
        return False
    if not sentence_entities or not sentence_relations:
        return True
    if any(cue in sentence for cue in _CASCADE_LIST_CUES) and (
        has_causal_cue or has_body_site_cue or has_location_list
    ):
        return True

    relation_endpoints = {
        endpoint
        for relation in sentence_relations
        for endpoint in (relation.subject, relation.object)
    }
    if any(
        entity.type != "dis" and entity.text not in relation_endpoints
        for entity in sentence_entities
    ):
        return True
    if has_causal_cue and not any(
        relation.predicate in _CASCADE_CAUSAL_RELATIONS
        for relation in sentence_relations
    ):
        return True
    if (has_body_site_cue or has_location_list) and not any(
        relation.predicate in _CASCADE_BODY_SITE_RELATIONS
        for relation in sentence_relations
    ):
        return True
    return False


def _max_gap_segments() -> int:
    raw = os.getenv("CCF_TASK2_CASCADE_MAX_GAP_SEGMENTS", "12")
    try:
        return max(1, min(32, int(raw)))
    except ValueError:
        return 12


def _find_gap_segments(
    text: str,
    entities: list[Entity],
    relations: list[Relation],
) -> list[CascadeSegment]:
    gaps: list[CascadeSegment] = []
    for index, (start, end, sentence) in enumerate(_sentence_spans(text)):
        sentence_entities = [
            entity for entity in entities if _entity_in_segment(entity, start, end)
        ]
        sentence_relations = _segment_relations(sentence, relations)
        reasons: list[str] = []
        if _segment_requires_gap_review(sentence, sentence_entities, sentence_relations):
            reasons.append(
                "partial_relation_coverage" if sentence_relations else "entity_without_relation"
            )
        if reasons:
            gaps.append(
                CascadeSegment(
                    segment_id=f"s{index}",
                    start_idx=start,
                    end_idx=end,
                    text=sentence,
                    reasons=tuple(reasons),
                )
            )
    return gaps[: _max_gap_segments()]


def _scoped_candidate_id(candidate_scope: str, candidate_id: str) -> str:
    return f"{candidate_scope}:{candidate_id}" if candidate_scope else candidate_id


def _offline_relation_candidates(
    relations: list[Relation], *, candidate_scope: str = ""
) -> list[ReviewCandidate]:
    candidates: list[ReviewCandidate] = []
    for index, relation in enumerate(relations):
        if relation.reliability_level == "high":
            continue
        candidates.append(
            ReviewCandidate(
                candidate_id=_scoped_candidate_id(candidate_scope, f"offline_relation:{index}"),
                kind="relation",
                source="offline",
                evidence=relation.evidence,
                reliability_level=relation.reliability_level,
                subject=relation.subject,
                subject_type=relation.subject_type,
                predicate=relation.predicate,
                object=relation.object,
                object_type=relation.object_type,
            )
        )
    return candidates


def _offline_entity_candidates(
    entities: list[Entity], *, candidate_scope: str = ""
) -> list[ReviewCandidate]:
    candidates: list[ReviewCandidate] = []
    for index, entity in enumerate(entities):
        if entity.reliability_level == "high":
            continue
        candidates.append(
            ReviewCandidate(
                candidate_id=_scoped_candidate_id(candidate_scope, f"offline_entity:{index}"),
                kind="entity",
                source="offline",
                evidence=entity.evidence,
                reliability_level=entity.reliability_level,
                entity_text=entity.text,
                entity_type=entity.type,
            )
        )
    return candidates


def _gap_candidates(
    entities: list[Entity],
    relations: list[Relation],
    segments: list[CascadeSegment],
    *,
    candidate_scope: str = "",
) -> list[ReviewCandidate]:
    candidates: list[ReviewCandidate] = []
    for index, entity in enumerate(entities):
        segment_id = ""
        for segment in segments:
            if _entity_in_segment(entity, segment.start_idx, segment.end_idx):
                segment_id = segment.segment_id
                break
        candidates.append(
            ReviewCandidate(
                candidate_id=_scoped_candidate_id(
                    candidate_scope, f"gap_entity:{segment_id}:{index}"
                ),
                kind="entity",
                source="llm_gap",
                evidence=entity.evidence,
                reliability_level=entity.reliability_level,
                entity_text=entity.text,
                entity_type=entity.type,
                segment_id=segment_id,
            )
        )
    for index, relation in enumerate(relations):
        segment_id = ""
        for segment in segments:
            if relation.subject in segment.text and relation.object in segment.text:
                segment_id = segment.segment_id
                break
        candidates.append(
            ReviewCandidate(
                candidate_id=_scoped_candidate_id(
                    candidate_scope, f"gap_relation:{segment_id}:{index}"
                ),
                kind="relation",
                source="llm_gap",
                evidence=relation.evidence,
                reliability_level=relation.reliability_level,
                subject=relation.subject,
                subject_type=relation.subject_type,
                predicate=relation.predicate,
                object=relation.object,
                object_type=relation.object_type,
                segment_id=segment_id,
            )
        )
    return candidates


def _candidate_semantic_key(candidate: ReviewCandidate) -> tuple:
    if candidate.kind == "entity":
        return (
            "entity",
            candidate.entity_text,
            candidate.entity_type,
        )
    return (
        "relation",
        candidate.subject,
        candidate.predicate,
        candidate.object,
    )


def dedupe_review_candidates(
    candidates: list[ReviewCandidate],
) -> list[ReviewCandidate]:
    """Deduplicate semantic duplicates before spending an LLM review call."""

    result: list[ReviewCandidate] = []
    seen: set[tuple] = set()
    for candidate in candidates:
        key = _candidate_semantic_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        result.append(candidate)
    return result

def prepare_cascade_targets(
    text: str,
    entities: list[Entity],
    relations: list[Relation],
    *,
    candidate_scope: str = "",
) -> tuple[list[CascadeSegment], list[ReviewCandidate]]:
    """Prepare the offline review queue and uncovered segments for batch mode.

    Low-reliability offline candidates remain controlled by the offline quality
    gate. They are not sent to the LLM review queue, which keeps the cascade's
    role as precision enhancement instead of turning it into a full LLM pass.
    """

    gap_segments = _find_gap_segments(text, entities, relations)
    entity_candidates = [
        candidate
        for candidate in _offline_entity_candidates(
            entities, candidate_scope=candidate_scope
        )
        if candidate.reliability_level == "medium"
    ][:32]
    relation_candidates = [
        candidate
        for candidate in _offline_relation_candidates(
            relations, candidate_scope=candidate_scope
        )
        if candidate.reliability_level == "medium"
    ][:32]
    return gap_segments, dedupe_review_candidates(
        entity_candidates + relation_candidates
    )


def count_skipped_offline_candidates(
    entities: list[Entity],
    relations: list[Relation],
    review_candidates: list[ReviewCandidate],
) -> int:
    """Count offline candidates intentionally kept out of LLM review."""

    all_candidates = (
        _offline_entity_candidates(entities)
        + _offline_relation_candidates(relations)
    )
    reviewed_ids = {candidate.candidate_id for candidate in review_candidates}
    return sum(
        1
        for candidate in all_candidates
        if candidate.candidate_id not in reviewed_ids
    )


def build_gap_review_candidates(
    entities: list[Entity],
    relations: list[Relation],
    segments: list[CascadeSegment],
    *,
    candidate_scope: str = "",
) -> list[ReviewCandidate]:
    """Build review candidates for facts extracted from uncovered segments."""

    return _gap_candidates(
        entities,
        relations,
        segments,
        candidate_scope=candidate_scope,
    )


def _merge_entities(primary: list[Entity], secondary: list[Entity]) -> list[Entity]:
    merged: list[Entity] = []
    seen: set[tuple[str, int | None, int | None]] = set()
    for entity in primary + secondary:
        key = (entity.text, entity.start_idx, entity.end_idx)
        if key in seen:
            continue
        seen.add(key)
        merged.append(entity)
    return sorted(merged, key=lambda item: (item.start_idx or 0, -len(item.text)))


def _dedupe_relations(relations: list[Relation]) -> list[Relation]:
    result: list[Relation] = []
    seen: set[tuple[str, str, str]] = set()
    for relation in relations:
        key = (relation.subject, relation.predicate, relation.object)
        if key in seen:
            continue
        seen.add(key)
        result.append(relation)
    return result


def _rebind_relation_to_entities(
    relation: Relation,
    entities: list[Entity],
) -> Relation | None:
    """Bind relation endpoint types to the surviving entity set by text."""

    type_by_text: dict[str, str] = {}
    for entity in entities:
        type_by_text.setdefault(entity.text, entity.type)
    subject_type = type_by_text.get(relation.subject)
    object_type = type_by_text.get(relation.object)
    if not subject_type or not object_type:
        return None
    return replace(
        relation,
        subject_type=subject_type,
        object_type=object_type,
    )


def _ensure_relation_anchors(
    entities: list[Entity],
    relations: list[Relation],
    source_entities: list[Entity],
) -> list[Entity]:
    """Keep endpoint entities when entity review rejected only their mention."""

    result = list(entities)
    for relation in relations:
        for endpoint_text, endpoint_type in (
            (relation.subject, relation.subject_type),
            (relation.object, relation.object_type),
        ):
            if not endpoint_text or any(item.text == endpoint_text for item in result):
                continue
            template = next(
                (item for item in source_entities if item.text == endpoint_text),
                None,
            )
            if template is not None:
                result.append(
                    replace(
                        template,
                        type=endpoint_type or template.type,
                        extraction_method="relation_anchor",
                        reliability_level=template.reliability_level
                        or relation.reliability_level,
                    )
                )
            elif endpoint_type:
                result.append(
                    Entity(
                        text=endpoint_text,
                        type=endpoint_type,
                        confidence=relation.confidence,
                        evidence=relation.evidence,
                        extraction_method="relation_anchor",
                        reliability_level=relation.reliability_level,
                    )
                )
    return _merge_entities(result, [])


def extract_medical_knowledge_cascade(
    text: str,
    *,
    kg_db_path: str = "",
    llm: LLMClient,
) -> CascadeOutput:
    """执行离线优先、LLM 查缺补漏和候选复核。"""

    offline_entities = extract_entities_offline(text, kg_db_path)
    offline_relations = extract_relations_offline(
        text,
        entities=offline_entities,
        db_path=kg_db_path,
    )
    gap_segments, offline_review_candidates = prepare_cascade_targets(
        text,
        offline_entities,
        offline_relations,
    )
    all_offline_candidates = (
        _offline_entity_candidates(offline_entities)
        + _offline_relation_candidates(offline_relations)
    )
    offline_review_skipped = len(all_offline_candidates) - len(
        offline_review_candidates
    )
    offline_entity_candidates = [
        candidate
        for candidate in offline_review_candidates
        if candidate.kind == "entity"
    ]
    offline_relation_candidates = [
        candidate
        for candidate in offline_review_candidates
        if candidate.kind == "relation"
    ]
    gap_entities, gap_relations = extract_gap_facts(text, gap_segments, llm)
    gap_candidates = _gap_candidates(gap_entities, gap_relations, gap_segments)
    all_candidates = dedupe_review_candidates(
        gap_candidates + offline_review_candidates
    )
    decisions = review_candidates(llm, all_candidates)

    rejected_offline_entity_ids = {
        candidate.candidate_id
        for candidate in offline_entity_candidates
        if decisions.get(candidate.candidate_id)
        and decisions[candidate.candidate_id].decision == "reject"
    }
    rejected_offline_relation_ids = {
        candidate.candidate_id
        for candidate in offline_relation_candidates
        if decisions.get(candidate.candidate_id)
        and decisions[candidate.candidate_id].decision == "reject"
    }
    retained_offline_entities = [
        entity
        for index, entity in enumerate(offline_entities)
        if f"offline_entity:{index}" not in rejected_offline_entity_ids
    ]
    retained_offline_relations = [
        relation
        for index, relation in enumerate(offline_relations)
        if f"offline_relation:{index}" not in rejected_offline_relation_ids
    ]

    accepted_gap_entity_ids = {
        candidate.candidate_id
        for candidate in gap_candidates
        if candidate.kind == "entity"
        and decisions.get(candidate.candidate_id)
        and decisions[candidate.candidate_id].decision == "accept"
    }
    accepted_gap_entities: list[Entity] = []
    for index, entity in enumerate(gap_entities):
        candidate_id = next(
            (
                candidate.candidate_id
                for candidate in gap_candidates
                if candidate.kind == "entity"
                and candidate.entity_text == entity.text
                and candidate.entity_type == entity.type
                and candidate.candidate_id.endswith(f":{index}")
            ),
            "",
        )
        if candidate_id not in accepted_gap_entity_ids:
            continue
        accepted_gap_entities.append(
            replace(
                entity,
                extraction_method="llm_gap_verified",
                reliability_level="high",
            )
        )

    accepted_gap_relations: list[Relation] = []
    for index, relation in enumerate(gap_relations):
        candidate_id = next(
            (
                candidate.candidate_id
                for candidate in gap_candidates
                if candidate.kind == "relation"
                and candidate.subject == relation.subject
                and candidate.predicate == relation.predicate
                and candidate.object == relation.object
                and candidate.candidate_id.endswith(f":{index}")
            ),
            "",
        )
        decision = decisions.get(candidate_id)
        if not decision or decision.decision != "accept":
            continue
        bound_relation = _rebind_relation_to_entities(
            relation,
            retained_offline_entities + accepted_gap_entities,
        )
        if bound_relation is None:
            continue
        accepted_gap_relations.append(
            replace(
                bound_relation,
                extraction_method="llm_gap_verified",
                reliability_level="high",
            )
        )

    entities = _merge_entities(retained_offline_entities, accepted_gap_entities)
    relations = _dedupe_relations(retained_offline_relations + accepted_gap_relations)
    entities = _ensure_relation_anchors(entities, relations, offline_entities + gap_entities)
    relations = [
        bound_relation
        for relation in relations
        if (bound_relation := _rebind_relation_to_entities(relation, entities)) is not None
    ]
    offline_relation_keys = {
        (relation.subject, relation.predicate, relation.object)
        for relation in retained_offline_relations
    }
    llm_added_relations = [
        relation
        for relation in accepted_gap_relations
        if (relation.subject, relation.predicate, relation.object) not in offline_relation_keys
    ]
    triples: list[Triple] = relations_to_triples(relations, min_confidence=0.0)

    rejected_count = sum(
        1 for decision in decisions.values() if decision.decision == "reject"
    )
    return CascadeOutput(
        entities=entities,
        relations=relations,
        triples=triples,
        gap_segment_count=len(gap_segments),
        gap_candidate_count=len(gap_candidates),
        reviewed_candidate_count=len(all_candidates),
        review_skipped_candidate_count=offline_review_skipped,
        rejected_candidate_count=rejected_count,
        llm_added_count=len(llm_added_relations),
    )


def apply_cascade_merge(
    text: str,
    entities: list[Entity],
    relations: list[Relation],
    *,
    gap_segments: list[CascadeSegment],
    review_candidates: list[ReviewCandidate],
    decisions: dict[str, Any],
    gap_entities: list[Entity],
    gap_relations: list[Relation],
    candidate_scope: str = "",
    reviewed_candidate_ids: set[str] | None = None,
    offline_review_skipped_count: int = 0,
) -> CascadeOutput:
    """Apply a batch review result to one record without cross-record leakage.

    ``reviewed_candidate_ids`` is the authoritative queue sent to the LLM. It
    keeps reported review counts honest when a batch-level safety cap is used.
    A missing decision never rejects an offline fact and never accepts a gap
    fact; the offline result is therefore the safe fallback.
    """

    offline_entity_candidates = [
        candidate
        for candidate in review_candidates
        if candidate.kind == "entity" and candidate.source == "offline"
    ]
    offline_relation_candidates = [
        candidate
        for candidate in review_candidates
        if candidate.kind == "relation" and candidate.source == "offline"
    ]
    gap_candidates = _gap_candidates(
        gap_entities,
        gap_relations,
        gap_segments,
        candidate_scope=candidate_scope,
    )
    all_candidates = dedupe_review_candidates(
        gap_candidates + review_candidates
    )
    all_candidate_ids = {candidate.candidate_id for candidate in all_candidates}
    if reviewed_candidate_ids is None:
        reviewed_ids = set(all_candidate_ids)
    else:
        reviewed_ids = set(reviewed_candidate_ids) & all_candidate_ids

    def is_rejected(candidate_id: str) -> bool:
        decision = decisions.get(candidate_id)
        return (
            candidate_id in reviewed_ids
            and decision is not None
            and getattr(decision, "decision", "") == "reject"
        )

    rejected_offline_entity_ids = {
        candidate.candidate_id
        for candidate in offline_entity_candidates
        if is_rejected(candidate.candidate_id)
    }
    rejected_offline_relation_ids = {
        candidate.candidate_id
        for candidate in offline_relation_candidates
        if is_rejected(candidate.candidate_id)
    }
    retained_offline_entities = [
        entity
        for index, entity in enumerate(entities)
        if _scoped_candidate_id(candidate_scope, f"offline_entity:{index}")
        not in rejected_offline_entity_ids
    ]
    retained_offline_relations = [
        relation
        for index, relation in enumerate(relations)
        if _scoped_candidate_id(candidate_scope, f"offline_relation:{index}")
        not in rejected_offline_relation_ids
    ]

    accepted_gap_entity_ids = {
        candidate.candidate_id
        for candidate in gap_candidates
        if candidate.kind == "entity"
        and candidate.candidate_id in reviewed_ids
        and getattr(decisions.get(candidate.candidate_id), "decision", "") == "accept"
    }
    accepted_gap_entities: list[Entity] = []
    for index, entity in enumerate(gap_entities):
        candidate_id = next(
            (
                candidate.candidate_id
                for candidate in gap_candidates
                if candidate.kind == "entity"
                and candidate.entity_text == entity.text
                and candidate.entity_type == entity.type
                and candidate.candidate_id.endswith(f":{index}")
            ),
            "",
        )
        if candidate_id not in accepted_gap_entity_ids:
            continue
        accepted_gap_entities.append(
            replace(
                entity,
                extraction_method="llm_gap_verified",
                reliability_level="high",
            )
        )

    accepted_gap_relations: list[Relation] = []
    for index, relation in enumerate(gap_relations):
        candidate_id = next(
            (
                candidate.candidate_id
                for candidate in gap_candidates
                if candidate.kind == "relation"
                and candidate.subject == relation.subject
                and candidate.predicate == relation.predicate
                and candidate.object == relation.object
                and candidate.candidate_id.endswith(f":{index}")
            ),
            "",
        )
        if not candidate_id or candidate_id not in reviewed_ids:
            continue
        if getattr(decisions.get(candidate_id), "decision", "") != "accept":
            continue
        bound_relation = _rebind_relation_to_entities(
            relation,
            retained_offline_entities + accepted_gap_entities,
        )
        if bound_relation is None:
            continue
        accepted_gap_relations.append(
            replace(
                bound_relation,
                extraction_method="llm_gap_verified",
                reliability_level="high",
            )
        )

    merged_entities = _merge_entities(retained_offline_entities, accepted_gap_entities)
    merged_relations = _dedupe_relations(
        retained_offline_relations + accepted_gap_relations
    )
    merged_entities = _ensure_relation_anchors(
        merged_entities,
        merged_relations,
        entities + gap_entities,
    )
    merged_relations = [
        bound_relation
        for relation in merged_relations
        if (bound_relation := _rebind_relation_to_entities(relation, merged_entities))
        is not None
    ]
    offline_relation_keys = {
        (relation.subject, relation.predicate, relation.object)
        for relation in retained_offline_relations
    }
    llm_added_relations = [
        relation
        for relation in accepted_gap_relations
        if (relation.subject, relation.predicate, relation.object) not in offline_relation_keys
    ]
    triples: list[Triple] = relations_to_triples(merged_relations, min_confidence=0.0)
    rejected_count = sum(
        1
        for candidate in all_candidates
        if candidate.candidate_id in reviewed_ids
        and getattr(decisions.get(candidate.candidate_id), "decision", "") == "reject"
    )
    return CascadeOutput(
        entities=merged_entities,
        relations=merged_relations,
        triples=triples,
        gap_segment_count=len(gap_segments),
        gap_candidate_count=len(gap_candidates),
        reviewed_candidate_count=len(reviewed_ids),
        review_skipped_candidate_count=(
            offline_review_skipped_count
            + len(all_candidate_ids - reviewed_ids)
        ),
        rejected_candidate_count=rejected_count,
        llm_added_count=len(llm_added_relations),
    )
