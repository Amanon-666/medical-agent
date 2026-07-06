# -*- coding: utf-8 -*-
"""
任务二医学抽取服务。

该模块统一调度实体识别、关系抽取和三元组生成能力，并支持本地规则链与模型增强链按配置切换。
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Iterable

from .llm_client import LLMClient
from .medical_ner import extract_entities as extract_entities_llm
from .medical_re import extract_relations as extract_relations_llm
from .medical_extraction_validation import relations_to_triples
from .medical_offline_extraction import (
    extract_entities_offline,
    extract_relations_offline,
    generate_triples_offline,
)
from .schemas import Entity, Relation, Triple


VALID_BACKENDS = {"offline", "llm", "hybrid"}


@dataclass
class ExtractionBundle:
    entities: list[Entity]
    relations: list[Relation]
    triples: list[Triple]
    backend: str
    elapsed_seconds: float
    llm_error: str = ""


def normalize_backend(value: str | None) -> str:
    backend = (value or "offline").strip().lower()
    return backend if backend in VALID_BACKENDS else "offline"


def _merge_entities(primary: Iterable[Entity], secondary: Iterable[Entity]) -> list[Entity]:
    merged: list[Entity] = []
    seen: set[tuple[str, str, int | None, int | None]] = set()
    for entity in list(primary) + list(secondary):
        key = (entity.text, entity.type, entity.start_idx, entity.end_idx)
        if key in seen:
            continue
        seen.add(key)
        merged.append(entity)
    return sorted(merged, key=lambda item: (item.start_idx or 0, -len(item.text)))


def _merge_relations(primary: Iterable[Relation], secondary: Iterable[Relation]) -> list[Relation]:
    merged: list[Relation] = []
    seen: set[tuple[str, str, str]] = set()
    for relation in list(primary) + list(secondary):
        key = (relation.subject, relation.predicate, relation.object)
        if key in seen:
            continue
        seen.add(key)
        merged.append(relation)
    return merged


def extract_medical_knowledge(
    text: str,
    *,
    backend: str = "offline",
    kg_db_path: str = "",
    llm: LLMClient | None = None,
) -> ExtractionBundle:
    """从医学文本中抽取实体、关系和三元组。

    ``offline`` never calls an LLM. ``llm`` uses the existing LLM-driven
    extractors. ``hybrid`` runs offline first and uses LLM as an enhancer when
    a client is provided; LLM failures are reported without discarding offline
    results.
    """
    selected = normalize_backend(backend)
    started = perf_counter()

    if selected == "llm":
        if llm is None:
            raise ValueError("llm backend requires an LLMClient")
        entities = extract_entities_llm(text, llm)
        relations = extract_relations_llm(text, llm, entities=entities)
        triples = relations_to_triples(relations, min_confidence=0.7)
        return ExtractionBundle(
            entities=entities,
            relations=relations,
            triples=triples,
            backend="llm",
            elapsed_seconds=round(perf_counter() - started, 4),
        )

    entities = extract_entities_offline(text, kg_db_path)
    relations = extract_relations_offline(text, entities=entities, db_path=kg_db_path)
    triples = generate_triples_offline(text, entities=entities, relations=relations, db_path=kg_db_path)
    llm_error = ""

    if selected == "hybrid" and llm is not None:
        try:
            llm_entities = extract_entities_llm(text, llm)
            merged_entities = _merge_entities(entities, llm_entities)
            llm_relations = extract_relations_llm(text, llm, entities=merged_entities)
            merged_relations = _merge_relations(relations, llm_relations)
            entities = merged_entities
            relations = merged_relations
            triples = relations_to_triples(relations, min_confidence=0.7)
        except Exception as exc:
            llm_error = f"{type(exc).__name__}: {str(exc)[:240]}"

    return ExtractionBundle(
        entities=entities,
        relations=relations,
        triples=triples,
        backend=selected,
        elapsed_seconds=round(perf_counter() - started, 4),
        llm_error=llm_error,
    )
