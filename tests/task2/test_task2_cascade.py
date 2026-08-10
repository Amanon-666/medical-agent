from __future__ import annotations

from core.schemas import Entity, Relation
from core.task2_cascade import (
    apply_cascade_merge,
    build_gap_review_candidates,
    extract_medical_knowledge_cascade,
    prepare_cascade_targets,
    select_auto_accepted_gap_candidate_ids,
)
from core.task2_cascade_schemas import CascadeSegment, ReviewCandidate, ReviewDecision


class FakeCascadeLLM:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def chat_json(self, prompt: str):
        self.prompts.append(prompt)
        if "Segments:" in prompt:
            return {
                "segments": [
                    {
                        "segment_id": "s1",
                        "entities": [
                            {"text": "阿莫西林", "type": "dru", "start_idx": 0, "end_idx": 3},
                            {"text": "肺炎", "type": "dis", "start_idx": 6, "end_idx": 7},
                        ],
                        "relations": [
                            {
                                "subject": "肺炎",
                                "subject_type": "dis",
                                "predicate": "药物治疗",
                                "object": "阿莫西林",
                                "object_type": "dru",
                                "confidence": 0.95,
                            }
                        ],
                    }
                ]
            }
        return {
            "decisions": [
                {"candidate_id": "offline_entity:0", "decision": "reject", "confidence": 0.95},
                {"candidate_id": "offline_relation:0", "decision": "reject", "confidence": 0.95},
                {"candidate_id": "gap_entity:s1:0", "decision": "accept", "confidence": 0.95},
                {"candidate_id": "gap_entity:s1:1", "decision": "accept", "confidence": 0.95},
                {"candidate_id": "gap_relation:s1:0", "decision": "accept", "confidence": 0.95},
            ]
        }


def test_cascade_keeps_offline_first_and_filters_then_promotes_gap_facts(monkeypatch) -> None:
    import core.task2_cascade as cascade

    text = "肺炎有发热。阿莫西林治疗肺炎。"
    offline_entity = Entity(
        text="肺炎",
        type="dis",
        start_idx=0,
        end_idx=1,
        confidence=0.7,
        extraction_method="dictionary_exact",
        reliability_level="medium",
    )
    offline_relation = Relation(
        subject="肺炎",
        subject_type="dis",
        predicate="临床表现",
        object="发热",
        object_type="sym",
        confidence=0.65,
        extraction_method="sentence_rule",
        reliability_level="medium",
    )
    monkeypatch.setattr(cascade, "extract_entities_offline", lambda *_args: [offline_entity])
    monkeypatch.setattr(cascade, "extract_relations_offline", lambda *_args, **_kwargs: [offline_relation])

    result = extract_medical_knowledge_cascade(text, llm=FakeCascadeLLM())

    assert result.gap_segment_count == 1
    assert result.reviewed_candidate_count == 3
    assert result.rejected_candidate_count == 0
    assert result.llm_added_count == 1
    assert [(item.subject, item.predicate, item.object) for item in result.relations] == [
        ("肺炎", "临床表现", "发热"),
        ("肺炎", "药物治疗", "阿莫西林")
    ]
    added_entity = next(item for item in result.entities if item.text == "阿莫西林")
    assert added_entity.start_idx == 6
    assert added_entity.end_idx == 9
    added_relation = next(item for item in result.relations if item.object == "阿莫西林")
    assert added_relation.extraction_method == "llm_gap_verified"
    assert added_relation.reliability_level == "high"


def test_missing_review_decision_does_not_add_gap_fact(monkeypatch) -> None:
    import core.task2_cascade as cascade

    text = "治疗需要阿莫西林。"
    monkeypatch.setattr(cascade, "extract_entities_offline", lambda *_args: [])
    monkeypatch.setattr(cascade, "extract_relations_offline", lambda *_args, **_kwargs: [])

    class NoDecisionLLM(FakeCascadeLLM):
        def chat_json(self, prompt: str):
            self.prompts.append(prompt)
            if "Segments:" in prompt:
                return {
                    "segments": [
                        {
                            "segment_id": "s0",
                            "entities": [{"text": "阿莫西林", "type": "dru"}],
                            "relations": [],
                        }
                    ]
                }
            return {"decisions": []}

    result = extract_medical_knowledge_cascade(text, llm=NoDecisionLLM())

    assert result.entities == []
    assert result.relations == []
    assert result.llm_added_count == 0


def test_batch_merge_reviews_gap_facts_and_scopes_decisions() -> None:
    offline_entity = Entity(
        text="肺炎",
        type="dis",
        start_idx=0,
        end_idx=1,
        confidence=0.7,
        extraction_method="dictionary_exact",
        reliability_level="medium",
    )
    gap_entity = Entity(
        text="阿莫西林",
        type="dru",
        start_idx=4,
        end_idx=7,
        confidence=0.9,
        extraction_method="llm_gap",
        reliability_level="medium",
    )
    segment = CascadeSegment(
        segment_id="s0",
        start_idx=0,
        end_idx=10,
        text="肺炎使用阿莫西林",
        reasons=("entity_without_relation",),
    )
    offline_candidate = ReviewCandidate(
        candidate_id="r0:offline_entity:0",
        kind="entity",
        source="offline",
        entity_text="肺炎",
        entity_type="dis",
        reliability_level="medium",
    )
    decisions = {
        "r0:offline_entity:0": ReviewDecision(
            candidate_id="r0:offline_entity:0", decision="reject"
        ),
        "r0:gap_entity:s0:0": ReviewDecision(
            candidate_id="r0:gap_entity:s0:0", decision="accept", confidence=0.95
        ),
        # A same-number candidate from another record must not affect r0.
        "r1:offline_entity:0": ReviewDecision(
            candidate_id="r1:offline_entity:0", decision="reject"
        ),
    }

    result = apply_cascade_merge(
        text=segment.text,
        entities=[offline_entity],
        relations=[],
        gap_segments=[segment],
        review_candidates=[offline_candidate],
        decisions=decisions,
        gap_entities=[gap_entity],
        gap_relations=[],
        candidate_scope="r0",
        reviewed_candidate_ids={
            "r0:offline_entity:0",
            "r0:gap_entity:s0:0",
        },
    )

    assert result.reviewed_candidate_count == 2
    assert result.review_skipped_candidate_count == 0
    assert result.rejected_candidate_count == 1
    assert result.llm_added_count == 0
    assert [entity.text for entity in result.entities] == ["肺炎", "阿莫西林"]


def test_batch_merge_reports_unreviewed_candidates_without_rejecting_them() -> None:
    entity = Entity(
        text="肺炎",
        type="dis",
        start_idx=0,
        end_idx=1,
        confidence=0.7,
        extraction_method="dictionary_exact",
        reliability_level="medium",
    )
    candidate = ReviewCandidate(
        candidate_id="r2:offline_entity:0",
        kind="entity",
        source="offline",
        entity_text="肺炎",
        entity_type="dis",
        reliability_level="medium",
    )

    result = apply_cascade_merge(
        text="肺炎",
        entities=[entity],
        relations=[],
        gap_segments=[],
        review_candidates=[candidate],
        decisions={},
        gap_entities=[],
        gap_relations=[],
        candidate_scope="r2",
        reviewed_candidate_ids=set(),
    )

    assert result.reviewed_candidate_count == 0
    assert result.review_skipped_candidate_count == 1
    assert result.rejected_candidate_count == 0
    assert [item.text for item in result.entities] == ["肺炎"]


def test_reliability_router_reviews_low_facts_not_preserved_medium_facts() -> None:
    entities = [
        Entity(text="肺炎", type="dis", start_idx=0, end_idx=1, reliability_level="medium"),
        Entity(text="肺部", type="bod", start_idx=4, end_idx=5, reliability_level="low"),
    ]

    relations = [
        Relation(
            subject="肺炎",
            subject_type="dis",
            predicate="发病部位",
            object="肺部",
            object_type="bod",
            evidence="肺炎发生于肺部。",
            confidence=0.05,
            reliability_level="low",
        ),
        Relation(
            subject="肺炎",
            subject_type="dis",
            predicate="发病部位",
            object="肺部",
            object_type="bod",
            evidence="肺炎发生于肺部。",
            confidence=0.75,
            reliability_level="low",
        ),
    ]

    _, candidates = prepare_cascade_targets("肺炎发生于肺部。", entities, relations)

    assert [(item.kind, item.confidence) for item in candidates] == [
        ("entity", 1.0),
        ("relation", 0.75),
    ]


def test_high_confidence_supported_gap_relation_uses_fast_path() -> None:
    text = "骨性关节炎的发病部位包括踝关节。"
    segment = CascadeSegment(
        segment_id="s0",
        start_idx=0,
        end_idx=len(text),
        text=text,
        reasons=("entity_without_relation",),
    )
    gap_entities = [
        Entity(text="骨性关节炎", type="dis", start_idx=0, end_idx=4, confidence=0.95),
        Entity(text="踝关节", type="bod", start_idx=12, end_idx=14, confidence=0.95),
    ]
    gap_relations = [
        Relation(
            subject="骨性关节炎",
            subject_type="dis",
            predicate="发病部位",
            object="踝关节",
            object_type="bod",
            confidence=0.95,
            evidence=text,
        )
    ]
    candidates = build_gap_review_candidates(gap_entities, gap_relations, [segment])
    auto_ids = select_auto_accepted_gap_candidate_ids(candidates)

    result = apply_cascade_merge(
        text=text,
        entities=[],
        relations=[],
        gap_segments=[segment],
        review_candidates=[],
        decisions={},
        gap_entities=gap_entities,
        gap_relations=gap_relations,
        reviewed_candidate_ids=set(),
        auto_accepted_candidate_ids=auto_ids,
    )

    assert len(auto_ids) == 3
    assert result.reviewed_candidate_count == 0
    assert result.auto_accepted_candidate_count == 3
    assert result.llm_added_entity_count == 2
    assert result.llm_added_relation_count == 1
    assert [(item.subject, item.predicate, item.object) for item in result.relations] == [
        ("骨性关节炎", "发病部位", "踝关节")
    ]


def test_reviewed_low_relation_uses_review_confidence() -> None:
    text = "初步诊断：心肌梗死。给予阿司匹林治疗。"
    disease = Entity(
        text="心肌梗死",
        type="dis",
        start_idx=text.index("心肌梗死"),
        end_idx=text.index("心肌梗死") + len("心肌梗死") - 1,
        reliability_level="medium",
    )
    drug = Entity(
        text="阿司匹林",
        type="dru",
        start_idx=text.index("阿司匹林"),
        end_idx=text.index("阿司匹林") + len("阿司匹林") - 1,
        reliability_level="medium",
    )
    relation = Relation(
        subject="心肌梗死",
        subject_type="dis",
        predicate="药物治疗",
        object="阿司匹林",
        object_type="dru",
        confidence=0.4,
        evidence=text,
        extraction_method="explicit_medication_frame",
        reliability_level="low",
    )
    candidate = ReviewCandidate(
        candidate_id="offline_relation:0",
        kind="relation",
        source="offline",
        subject=relation.subject,
        subject_type=relation.subject_type,
        predicate=relation.predicate,
        object=relation.object,
        object_type=relation.object_type,
        confidence=relation.confidence,
        reliability_level="low",
        extraction_method=relation.extraction_method,
        evidence=text,
    )
    result = apply_cascade_merge(
        text=text,
        entities=[disease, drug],
        relations=[relation],
        gap_segments=[],
        review_candidates=[candidate],
        decisions={
            "offline_relation:0": ReviewDecision(
                candidate_id="offline_relation:0",
                decision="accept",
                confidence=0.93,
            )
        },
        gap_entities=[],
        gap_relations=[],
        reviewed_candidate_ids={"offline_relation:0"},
    )

    assert result.relations[0].confidence == 0.93
    assert result.relations[0].reliability_level == "high"
    assert result.relations[0].extraction_method == "llm_review_verified"
