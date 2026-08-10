from __future__ import annotations

import sqlite3

from core.medical_offline_extraction import (
    extract_entities_offline,
    extract_relations_offline,
)
from core.schemas import Entity, Relation
from core.task2_cascade import (
    _find_gap_segments,
    apply_cascade_merge,
)
from core.task2_cascade_schemas import CascadeSegment, ReviewCandidate, ReviewDecision
from core.task2_verifier import (
    _gap_entity_context_is_supported,
    _gap_relation_context_is_supported,
    _gap_section_subject_is_supported,
    normalize_verified_entity,
)


def _sample_text() -> str:
    return (
        "\u9aa8\u6027\u5173\u8282\u708e"
        " \u5728\u5176\u4ed6\u5173\u8282\uff08\u5982\u8e1d\u5173\u8282\u548c\u8155\u5173\u8282\uff09\uff0c"
        "\u9aa8\u6027\u5173\u8282\u708e\u6bd4\u8f83\u5c11\u89c1\uff0c"
        "\u5e76\u4e14\u4e00\u822c\u6709\u6f5c\u5728\u7684\u75c5\u56e0"
        "\uff08\u5982\u7ed3\u6676\u6027\u5173\u8282\u75c5\u3001\u521b\u4f24\uff09\u3002"
    ).replace(" ", "")


def _create_kg_fixture(path) -> None:
    def u(value: str) -> str:
        return "".join(chr(int(item, 16)) for item in value.split())

    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE kg_entities ("
        "entity_id INTEGER PRIMARY KEY, canonical_name TEXT, entity_type TEXT)"
    )
    conn.execute(
        "CREATE TABLE kg_triples (subject_id INTEGER, object_id INTEGER, relation_code TEXT)"
    )
    conn.executemany(
        "INSERT INTO kg_entities(canonical_name, entity_type) VALUES (?, ?)",
        [
            (u("9aa8 6027 5173 8282 708e"), "disease"),
            (u("5173 8282"), "body_part"),
            (u("5173 8282"), "symptom"),
            (u("8e1d 5173 8282"), "body_part"),
            (u("8155 5173 8282"), "body_part"),
            (u("521b 4f24"), "symptom"),
        ],
    )
    conn.commit()
    conn.close()


def test_explicit_structured_lists_become_medium_offline_relations() -> None:
    text = _sample_text().replace("骨性关节炎", "骨性关节炎@", 1)
    specs = [
        ("骨性关节炎", "dis"),
        ("关节", "bod"),
        ("踝关节", "bod"),
        ("腕关节", "bod"),
        ("创伤", "sym"),
    ]
    entities = []
    for value, entity_type in specs:
        start = text.find(value, text.find("@") + 1) if value == "关节" else text.find(value)
        entities.append(
            Entity(
                text=value,
                type=entity_type,
                start_idx=start,
                end_idx=start + len(value) - 1,
                reliability_level="medium",
            )
        )

    relations = extract_relations_offline(text, entities=entities)
    explicit = {
        (item.subject, item.predicate, item.object)
        for item in relations
        if item.extraction_method == "explicit_section_frame"
    }

    assert explicit == {
        ("骨性关节炎", "发病部位", "关节"),
        ("骨性关节炎", "发病部位", "踝关节"),
        ("骨性关节炎", "发病部位", "腕关节"),
        ("骨性关节炎", "病因", "创伤"),
    }
    assert all(item.reliability_level == "medium" for item in relations if item.extraction_method == "explicit_section_frame")


def test_cmeie_sentence_uses_longest_mentions_and_context_relations(tmp_path) -> None:
    db_path = tmp_path / "kg.db"
    _create_kg_fixture(db_path)

    entities = extract_entities_offline(_sample_text(), str(db_path))
    relations = extract_relations_offline(
        _sample_text(), entities=entities, db_path=str(db_path)
    )

    assert [(item.text, item.type) for item in entities] == [
        ("\u9aa8\u6027\u5173\u8282\u708e", "dis"),
        ("\u5173\u8282", "bod"),
        ("\u8e1d\u5173\u8282", "bod"),
        ("\u8155\u5173\u8282", "bod"),
        ("\u9aa8\u6027\u5173\u8282\u708e", "dis"),
        ("\u521b\u4f24", "sym"),
    ]
    assert [(item.predicate, item.object) for item in relations] == [
        ("\u53d1\u75c5\u90e8\u4f4d", "\u5173\u8282"),
        ("\u53d1\u75c5\u90e8\u4f4d", "\u8e1d\u5173\u8282"),
        ("\u53d1\u75c5\u90e8\u4f4d", "\u8155\u5173\u8282"),
        ("\u75c5\u56e0", "\u521b\u4f24"),
    ]


def test_partial_relation_coverage_still_enters_gap_queue(tmp_path) -> None:
    db_path = tmp_path / "kg.db"
    _create_kg_fixture(db_path)
    text = _sample_text()
    entities = extract_entities_offline(text, str(db_path))
    relations = extract_relations_offline(text, entities=entities, db_path=str(db_path))

    gaps = _find_gap_segments(text, entities, relations)

    assert len(gaps) == 1
    assert "partial_relation_coverage" in gaps[0].reasons


def test_section_marker_keeps_disease_context_for_gap_review() -> None:
    entity = Entity(
        text="肺炎",
        type="dis",
        start_idx=0,
        end_idx=1,
        reliability_level="medium",
    )

    gaps = _find_gap_segments(
        "肺炎@出现发热。",
        [entity],
        [],
    )

    assert len(gaps) == 1
    assert gaps[0].start_idx == 0
    assert gaps[0].text == "肺炎@出现发热。"
    assert "section_context_gap" in gaps[0].reasons


def test_later_sentence_in_at_section_keeps_disease_subject() -> None:
    text = "肺炎@首句介绍背景。患者随后出现胸痛。"
    disease = Entity(
        text="肺炎",
        type="dis",
        start_idx=0,
        end_idx=1,
        reliability_level="high",
    )

    gaps = _find_gap_segments(text, [disease], [])

    later = next(item for item in gaps if "胸痛" in item.text)
    assert later.start_idx == 0
    assert later.text.startswith("肺炎@")
    assert "section_context_gap" in later.reasons


def test_section_marker_prevents_cross_section_relation_attribution() -> None:
    text = (
        "\u598a\u5a20\u80c6\u6c41\u6dc4\u79ef@"
        "[HELLP \u7efc\u5408\u5f81] ### \u6025\u6027\u598a\u5a20\u671f\u8102\u80aa\u809d "
        "\u4f53\u5f81/\u75c7\u72b6 \u68c0\u67e5 \u4f53\u5f81/\u75c7\u72b6 \u60a3\u8005\u611f\u89c9\u4e0d\u9002，"
        "\u5e38\u89c1\u8868\u73b0\u4e3a\u5168\u8eab\u4e4f\u529b、\u6076\u5fc3。"
    )
    diseases = [
        "HELLP \u7efc\u5408\u5f81",
        "\u6025\u6027\u598a\u5a20\u671f\u8102\u80aa\u809d",
    ]
    symptoms = ["\u5168\u8eab\u4e4f\u529b", "\u6076\u5fc3"]
    entities = [
        Entity(
            text=value,
            type="dis" if value in diseases else "sym",
            start_idx=text.find(value),
            end_idx=text.find(value) + len(value) - 1,
        )
        for value in diseases + symptoms
    ]

    relations = extract_relations_offline(text, entities=entities, db_path="")
    relation_keys = {
        (item.subject, item.predicate, item.object) for item in relations
    }

    assert ("HELLP \u7efc\u5408\u5f81", "\u4e34\u5e8a\u8868\u73b0", "\u6076\u5fc3") not in relation_keys


def test_gap_relation_uses_the_latest_section_disease_heading() -> None:
    text = (
        "\u666e\u901a\u611f\u5192@### \u54ee\u5598\u6025\u6027\u53d1\u4f5c "
        "\u666e\u901a\u611f\u5192@\u7ed9\u4e88\u652f\u6c14\u7ba1\u6269\u5f20\u5242"
    )
    relation = Relation(
        subject="\u666e\u901a\u611f\u5192",
        subject_type="dis",
        predicate="\u836f\u7269\u6cbb\u7597",
        object="\u652f\u6c14\u7ba1\u6269\u5f20\u5242",
        object_type="dru",
    )

    assert not _gap_section_subject_is_supported(
        text,
        relation,
        {"\u666e\u901a\u611f\u5192", "\u54ee\u5598\u6025\u6027\u53d1\u4f5c"},
    )


def test_gap_cause_relation_rejects_effect_direction() -> None:
    relation = Relation(
        subject="感染性疾病",
        subject_type="dis",
        predicate="病因",
        object="早产",
        object_type="dis",
    )

    assert not _gap_relation_context_is_supported(
        "感染性疾病可能导致早产。",
        relation,
        [],
    )


def test_gap_relation_rejects_generic_outcomes_and_inline_drug_headings() -> None:
    symptom_relation = Relation(
        subject="脑疝",
        subject_type="dis",
        predicate="临床表现",
        object="颅内压增高症状",
        object_type="sym",
    )
    drug_relation = Relation(
        subject="早产",
        subject_type="dis",
        predicate="药物治疗",
        object="保胎药",
        object_type="dru",
    )

    assert not _gap_relation_context_is_supported(
        "脑疝主要表现包括颅内压增高症状。",
        symptom_relation,
        [],
    )
    assert not _gap_relation_context_is_supported(
        "前置胎盘@病情稳定：早产联合保胎药。",
        drug_relation,
        [],
    )


def test_gap_cause_relation_requires_a_causal_frame() -> None:
    relation = Relation(
        subject="脑炎",
        subject_type="dis",
        predicate="病因",
        object="肠道病毒感染",
        object_type="dis",
    )

    assert not _gap_relation_context_is_supported(
        "脑炎@便培养（如果怀疑肠道病毒感染，次数应更频繁）。",
        relation,
        [],
    )


def test_entity_rejection_does_not_remove_relation_anchor() -> None:
    candidate = ReviewCandidate(
        candidate_id="r0:offline_entity:0",
        kind="entity",
        source="offline",
        entity_text="\u5173\u8282",
        entity_type="bod",
        reliability_level="medium",
    )
    relation = Relation(
        subject="\u9aa8\u6027\u5173\u8282\u708e",
        subject_type="dis",
        predicate="\u53d1\u75c5\u90e8\u4f4d",
        object="\u5173\u8282",
        object_type="bod",
        extraction_method="known_pair",
        reliability_level="medium",
    )
    result = apply_cascade_merge(
        text="\u9aa8\u6027\u5173\u8282\u708e\u5728\u5173\u8282",
        entities=[
            Entity(
                text="\u5173\u8282",
                type="bod",
                start_idx=7,
                end_idx=8,
                reliability_level="medium",
            )
        ],
        relations=[relation],
        gap_segments=[],
        review_candidates=[candidate],
        decisions={
            candidate.candidate_id: ReviewDecision(
                candidate_id=candidate.candidate_id,
                decision="reject",
            )
        },
        gap_entities=[],
        gap_relations=[],
        candidate_scope="r0",
        reviewed_candidate_ids={candidate.candidate_id},
    )

    assert [(item.subject, item.predicate, item.object) for item in result.relations] == [
        ("\u9aa8\u6027\u5173\u8282\u708e", "\u53d1\u75c5\u90e8\u4f4d", "\u5173\u8282")
    ]
    assert {item.text for item in result.entities} == {
        "\u9aa8\u6027\u5173\u8282\u708e",
        "\u5173\u8282",
    }


def test_low_reliability_relation_is_filtered_from_final_result() -> None:
    relation = Relation(
        subject="\u9aa8\u6027\u5173\u8282\u708e",
        subject_type="dis",
        predicate="\u53d1\u75c5\u90e8\u4f4d",
        object="\u5173\u8282",
        object_type="bod",
        extraction_method="context_rule",
        reliability_level="low",
    )
    result = apply_cascade_merge(
        text="\u9aa8\u6027\u5173\u8282\u708e\u5728\u5173\u8282",
        entities=[
            Entity(
                text="\u9aa8\u6027\u5173\u8282\u708e",
                type="dis",
                start_idx=0,
                end_idx=4,
                reliability_level="medium",
            ),
            Entity(
                text="\u5173\u8282",
                type="bod",
                start_idx=7,
                end_idx=8,
                reliability_level="low",
            ),
        ],
        relations=[relation],
        gap_segments=[],
        review_candidates=[],
        decisions={},
        gap_entities=[],
        gap_relations=[],
        candidate_scope="r0",
        reviewed_candidate_ids=set(),
    )

    assert result.relations == []
    assert result.offline_filtered_candidate_count == 2


def test_targeted_low_relation_is_promoted_only_after_llm_acceptance() -> None:
    relation = Relation(
        subject="肺炎",
        subject_type="dis",
        predicate="药物治疗",
        object="阿莫西林",
        object_type="dru",
        evidence="肺炎使用阿莫西林治疗",
        extraction_method="sentence_rule",
        reliability_level="low",
    )
    candidate = ReviewCandidate(
        candidate_id="r0:offline_relation:0",
        kind="relation",
        source="offline",
        evidence=relation.evidence,
        reliability_level="low",
        subject=relation.subject,
        subject_type=relation.subject_type,
        predicate=relation.predicate,
        object=relation.object,
        object_type=relation.object_type,
    )
    result = apply_cascade_merge(
        text=relation.evidence,
        entities=[
            Entity(text="肺炎", type="dis", reliability_level="high"),
            Entity(text="阿莫西林", type="dru", reliability_level="high"),
        ],
        relations=[relation],
        gap_segments=[],
        review_candidates=[candidate],
        decisions={
            candidate.candidate_id: ReviewDecision(
                candidate_id=candidate.candidate_id,
                decision="accept",
            )
        },
        gap_entities=[],
        gap_relations=[],
        candidate_scope="r0",
        reviewed_candidate_ids={candidate.candidate_id},
    )

    assert len(result.relations) == 1
    assert result.relations[0].extraction_method == "llm_review_verified"
    assert result.relations[0].reliability_level == "high"
    assert result.offline_filtered_candidate_count == 0


def test_gap_entity_gate_rejects_measurement_and_bare_equipment_noise() -> None:
    segment = CascadeSegment(
        segment_id="gap-0",
        start_idx=0,
        end_idx=13,
        text="\u68c0\u67e5\u663e\u793a\u4f53\u5faa\u73af\u963b\u529b\u589e\u52a0",
        reasons=(),
    )

    assert not _gap_entity_context_is_supported(
        Entity(text="\u4f53\u5faa\u73af\u963b\u529b", type="ite", start_idx=4, end_idx=9),
        segment,
        [],
    )
    assert not _gap_entity_context_is_supported(
        Entity(text="V3R", type="equ", start_idx=0, end_idx=2),
        CascadeSegment(
            segment_id="gap-1",
            start_idx=0,
            end_idx=5,
            text="V3R\u5bfc\u8054",
            reasons=(),
        ),
        [],
    )
    assert _gap_entity_context_is_supported(
        Entity(text="HFO\u8bbe\u5907", type="equ", start_idx=0, end_idx=5),
        CascadeSegment(
            segment_id="gap-2",
            start_idx=0,
            end_idx=11,
            text="\u91c7\u7528HFO\u8bbe\u5907\u8fdb\u884c\u901a\u6c14",
            reasons=(),
        ),
        [],
    )


def test_gap_entity_gate_keeps_specific_procedure_and_microbe() -> None:
    assert _gap_entity_context_is_supported(
        Entity(text="\u80ba\u704c\u6d17", type="pro", start_idx=0, end_idx=2),
        CascadeSegment(
            segment_id="gap-3",
            start_idx=0,
            end_idx=10,
            text="\u91c7\u7528\u80ba\u704c\u6d17\u8fdb\u884c\u68c0\u67e5",
            reasons=(),
        ),
        [],
    )
    assert not _gap_entity_context_is_supported(
        Entity(text="\u591a\u6838\u5de8\u7ec6\u80de", type="mic", start_idx=0, end_idx=5),
        CascadeSegment(
            segment_id="gap-4",
            start_idx=0,
            end_idx=8,
            text="\u591a\u6838\u5de8\u7ec6\u80de\u68c0\u67e5",
            reasons=(),
        ),
        [],
    )


def test_verified_entity_gate_is_shared_by_reviewed_and_gap_routes() -> None:
    text = "实验室检查淋巴细胞计数减少，胸部X线片提示异常，有休克表现。"

    indicator_start = text.index("淋巴细胞")
    procedure_start = text.index("胸部X线片")
    disease_start = text.index("休克")
    indicator = normalize_verified_entity(
        text,
        Entity(
            text="淋巴细胞",
            type="bod",
            start_idx=indicator_start,
            end_idx=indicator_start + len("淋巴细胞") - 1,
        ),
    )
    procedure = normalize_verified_entity(
        text,
        Entity(
            text="胸部X线片",
            type="ite",
            start_idx=procedure_start,
            end_idx=procedure_start + len("胸部X线片") - 1,
        ),
    )
    disease = normalize_verified_entity(
        text,
        Entity(
            text="休克",
            type="sym",
            start_idx=disease_start,
            end_idx=disease_start + len("休克") - 1,
        ),
    )

    assert indicator is not None
    assert (indicator.text, indicator.type) == ("淋巴细胞计数", "ite")
    assert procedure is not None and procedure.type == "pro"
    assert disease is not None and disease.type == "dis"


def test_verified_entity_gate_rejects_direction_fragment() -> None:
    text = "影像显示病灶位于单侧。"
    start = text.index("单侧")
    assert normalize_verified_entity(
        text,
        Entity(text="单侧", type="bod", start_idx=start, end_idx=start + 1),
    ) is None


def test_bedside_span_extension_does_not_extend_end_offset() -> None:
    text = "应进行床边动态心电监护。"
    start = text.index("动态心电监护")
    entity = normalize_verified_entity(
        text,
        Entity(
            text="动态心电监护",
            type="pro",
            start_idx=start,
            end_idx=start + len("动态心电监护") - 1,
        ),
    )
    assert entity is not None
    assert entity.text == "床边动态心电监护"
    assert text[entity.start_idx : entity.end_idx + 1] == entity.text
