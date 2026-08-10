import sqlite3
from inspect import signature

from core.medical_extraction_service import extract_medical_knowledge
from core.medical_extraction_validation import (
    relation_evidence_supports_pair,
    validate_entities,
    validate_relations,
)
from core.schemas import Triple
from mcp_server.kg.persistence import persist_triples
from mcp_server.kg.schema import _task2_ensure_kg_schema
from mcp_server.shared.parsing import parse_csv, parse_jsonl
from mcp_server.task2.text_extraction_service import (
    extract_text_knowledge,
    validate_text_backend,
)
from mcp_server.task2.pipeline_service import (
    _cascade_max_gap_segments_total,
    _cascade_max_review_candidates,
    _round_robin_gap_segments,
    run_kg_pipeline_service,
)


def test_llm_validation_assigns_review_reliability() -> None:
    text = "pneumonia fever"
    entities = validate_entities(
        text,
        [
            {"text": "pneumonia", "type": "dis", "start_idx": 0, "end_idx": 8},
            {"text": "fever", "type": "sym", "start_idx": 10, "end_idx": 14},
        ],
    )
    relations = validate_relations(
        text,
        [{"subject": "pneumonia", "predicate": "临床表现", "object": "fever"}],
        entities=entities,
    )

    assert [item.reliability_level for item in entities] == ["medium", "medium"]
    assert [item.reliability_level for item in relations] == ["medium"]


def test_entity_validation_retains_cmeee_nested_symptom_mentions() -> None:
    entities = validate_entities(
        "血压升高",
        [
            {"text": "血压升高", "type": "sym", "start_idx": 0, "end_idx": 3},
            {"text": "血压", "type": "ite", "start_idx": 0, "end_idx": 1},
        ],
    )

    assert [(item.text, item.type) for item in entities] == [
        ("血压升高", "sym"),
        ("血压", "ite"),
    ]


def test_relation_validation_requires_predicate_evidence() -> None:
    text = "肺炎出现发热"
    entities = validate_entities(
        text,
        [
            {"text": "肺炎", "type": "dis"},
            {"text": "发热", "type": "sym"},
        ],
    )
    relations = validate_relations(
        text,
        [
            {"subject": "肺炎", "predicate": "相关（导致）", "object": "发热"},
            {"subject": "肺炎", "predicate": "临床表现", "object": "发热"},
        ],
        entities=entities,
    )

    assert [(item.predicate, item.object) for item in relations] == [
        ("临床表现", "发热")
    ]


def test_strict_pair_evidence_does_not_borrow_a_cue_from_another_fact() -> None:
    text = "肺炎有发热。另见阿莫西林。"

    assert not relation_evidence_supports_pair(
        text,
        "药物治疗",
        "肺炎",
        "阿莫西林",
        subject_type="dis",
        object_type="dru",
        require_disease_subject=True,
    )


def test_strict_pair_evidence_keeps_cmeie_body_site_relation() -> None:
    text = "骨性关节炎在其他关节（如踝关节和腕关节）较少见。"

    assert relation_evidence_supports_pair(
        text,
        "发病部位",
        "骨性关节炎",
        "踝关节",
        subject_type="dis",
        object_type="bod",
        require_disease_subject=True,
    )


def test_blank_llm_reliability_is_fail_closed() -> None:
    conn = sqlite3.connect(":memory:")
    _task2_ensure_kg_schema(conn)
    result = persist_triples(
        conn,
        [
            Triple(
                subject="pneumonia",
                predicate="临床表现",
                object="fever",
                subject_type="dis",
                object_type="sym",
                extraction_method="llm",
                reliability_level="",
            )
        ],
        source_file="guardrail-test",
        source_id=1,
        return_details=True,
    )

    assert result == {"inserted": 0, "candidate": 1, "rejected": 0}
    assert conn.execute("SELECT COUNT(*) FROM kg_triples").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM kg_quality_issues").fetchone()[0] == 1


def test_unknown_reliability_is_fail_closed() -> None:
    conn = sqlite3.connect(":memory:")
    _task2_ensure_kg_schema(conn)
    result = persist_triples(
        conn,
        [
            Triple(
                subject="pneumonia",
                predicate="临床表现",
                object="fever",
                subject_type="dis",
                object_type="sym",
                extraction_method="offline",
                reliability_level="untrusted",
            )
        ],
        source_file="guardrail-test",
        source_id=1,
        return_details=True,
    )

    assert result == {"inserted": 0, "candidate": 0, "rejected": 1}
    assert conn.execute("SELECT COUNT(*) FROM kg_triples").fetchone()[0] == 0


def test_hybrid_without_client_reports_degraded_fallback() -> None:
    result = extract_medical_knowledge("plain text", backend="hybrid", llm=None)

    assert result.backend == "hybrid"
    assert "LLM client is not configured" in result.llm_error


def test_task2_interactive_defaults_avoid_external_model_and_full_analytics_rebuild() -> None:
    parameters = signature(run_kg_pipeline_service).parameters

    assert parameters["backend"].default == "offline"
    assert parameters["refresh_analytics"].default is False
    assert validate_text_backend(None) == "offline"


def test_hybrid_dataset_budget_is_bounded_and_keeps_later_records(monkeypatch) -> None:
    monkeypatch.setenv("CCF_TASK2_CASCADE_MAX_GAP_SEGMENTS_TOTAL", "3")
    monkeypatch.setenv("CCF_TASK2_CASCADE_MAX_REVIEW_CANDIDATES", "7")
    per_record = [
        {"index": 0, "gap_segments": ["r0-s0", "r0-s1"]},
        {"index": 1, "gap_segments": ["r1-s0", "r1-s1"]},
        {"index": 2, "gap_segments": ["r2-s0"]},
    ]

    selected = _round_robin_gap_segments(
        per_record,
        _cascade_max_gap_segments_total(),
    )

    assert _cascade_max_gap_segments_total() == 3
    assert _cascade_max_review_candidates() == 7
    assert sum(len(items) for items in selected.values()) == 3
    assert all(selected[index] for index in (0, 1, 2))


def test_inline_text_service_returns_a_success_object_for_empty_fact_lists() -> None:
    result = extract_text_knowledge(
        "plain text without medical facts",
        backend="offline",
        kg_db_path="",
    )

    assert result["status"] == "success"
    assert result["entities"] == []
    assert result["relations"] == []
    assert result["triples"] == []
    assert result["counts"] == {
        "entity_count": 0,
        "relation_count": 0,
        "triple_count": 0,
    }


def test_inline_text_service_rejects_unknown_backend() -> None:
    try:
        validate_text_backend("local")
    except ValueError as exc:
        assert "offline" in str(exc) and "hybrid" in str(exc)
    else:
        raise AssertionError("unknown backend must not silently fall back")


def test_structured_parsers_preserve_source_record_identity() -> None:
    csv_records = parse_csv("record_id,text\ncase-7,胸痛", "cases.csv")
    jsonl_records = parse_jsonl(
        '{"record_id":"case-8","text":"呼吸困难"}\n',
        "cases.jsonl",
    )

    assert csv_records[0]["record_id"] == "cases.csv:case-7"
    assert csv_records[0]["source_record_id"] == "case-7"
    assert jsonl_records[0]["record_id"] == "cases.jsonl:case-8"
    assert jsonl_records[0]["source_record_id"] == "case-8"


def test_persisted_triple_keeps_file_and_record_lineage() -> None:
    conn = sqlite3.connect(":memory:")
    _task2_ensure_kg_schema(conn)
    result = persist_triples(
        conn,
        [
            Triple(
                subject="急性心肌梗死",
                predicate="临床表现",
                object="胸痛",
                subject_type="dis",
                object_type="sym",
                extraction_method="known_pair",
                reliability_level="high",
                evidence="急性心肌梗死表现为胸痛",
            )
        ],
        source_file="cases.jsonl",
        source_record_id="cases.jsonl:case-8",
        source_id=1,
        return_details=True,
    )

    assert result == {"inserted": 1, "candidate": 0, "rejected": 0}
    row = conn.execute(
        "SELECT source_file, source_record_id FROM kg_triples"
    ).fetchone()
    assert row == ("cases.jsonl", "cases.jsonl:case-8")
