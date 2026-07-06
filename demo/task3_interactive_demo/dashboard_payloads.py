# -*- coding: utf-8 -*-
"""
可视化平台数据面板构造模块。

该模块从知识图谱库和分析库读取数据，生成前端所需的数据来源、指标、图表和证据载荷。
"""

from __future__ import annotations

from typing import Any

from db_utils import connect, count_rows, has_table, query_dicts, read_json_file, scalar
from paths import (
    ANALYTICS_DB,
    KG_DB,
)
from quality import (
    filter_quality_display_rows,
    filter_suspicious_rows,
    is_suspicious_fact_value,
    load_quality_values,
    mask_quality_rows,
    summarize_hidden_quality_rows,
)
from query_service import find_disease


RELATION_LABELS = {
    "has_symptom": "症状",
    "uses_drug": "用药",
    "has_department": "就诊科室",
    "needs_test": "检查",
    "has_procedure": "治疗方式",
    "has_cause": "病因",
    "has_prevention": "预防",
    "has_population": "易感人群",
    "has_complication": "并发症",
    "belongs_to_category": "所属类别",
    "belongs_to_department": "所属科室",
    "requires_test": "检查",
    "treated_by_drug": "药物治疗",
    "treated_by_procedure": "治疗方式",
    "visit_department": "就诊科室",
    "susceptible_population": "易感人群",
    "affects_body_part": "发病部位",
    "transmission_way": "传播途径",
    "differential_diagnosis": "鉴别诊断",
    "alias_of": "别名",
}


SAMPLE_QUESTIONS = [
    "肺泡蛋白质沉积症有哪些症状？",
    "肺泡蛋白质沉积症需要做哪些检查？",
    "肺泡蛋白质沉积症怎么治疗？",
    "百日咳应该挂什么科？",
    "糖尿病可以用哪些药物？",
    "统计每个科室关联的疾病数量",
    "统计实体类型分布",
    "统计关系类型分布",
]


def overview_payload() -> dict[str, Any]:
    analytics_counts: dict[str, int] = {}
    kg_counts: dict[str, int] = {}
    top_departments: list[dict[str, Any]] = []
    top_drugs: list[dict[str, Any]] = []
    top_symptoms: list[dict[str, Any]] = []
    entity_stats: list[dict[str, Any]] = []
    relation_stats: list[dict[str, Any]] = []
    examples: list[dict[str, Any]] = []
    quality_summary: list[dict[str, Any]] = []
    source_summary: list[dict[str, Any]] = []
    total_source_count = 0

    if ANALYTICS_DB.exists():
        with connect(ANALYTICS_DB) as conn:
            for table in (
                "diseases",
                "disease_facts",
                "disease_symptoms",
                "disease_drugs",
                "disease_departments",
                "disease_tests",
                "disease_procedures",
                "disease_causes",
                "disease_preventions",
                "disease_populations",
                "disease_complications",
                "qa_examples",
            ):
                if has_table(conn, table):
                    analytics_counts[table] = count_rows(conn, table)
            top_departments = query_dicts(
                conn,
                "SELECT department, disease_count FROM v_department_disease_counts ORDER BY disease_count DESC LIMIT 10",
            )
            top_drugs = query_dicts(
                conn,
                "SELECT drug, disease_count FROM v_drug_disease_counts ORDER BY disease_count DESC LIMIT 10",
            )
            top_symptoms = query_dicts(
                conn,
                "SELECT symptom, disease_count FROM v_top_symptoms ORDER BY disease_count DESC LIMIT 10",
            )
            top_symptoms, _ = filter_suspicious_rows(top_symptoms, "symptom")
            entity_stats = query_dicts(
                conn,
                "SELECT entity_type, entity_count FROM entity_stats ORDER BY entity_count DESC LIMIT 10",
            )
            relation_stats = query_dicts(
                conn,
                """
                SELECT relation_code, display_name, triple_count
                FROM relation_stats
                WHERE relation_code NOT LIKE 'cmeie_%'
                ORDER BY triple_count DESC LIMIT 12
                """,
            )
            examples = query_dicts(
                conn,
                "SELECT name, description FROM diseases WHERE description <> '' ORDER BY source_count DESC, disease_id LIMIT 8",
            )

    if KG_DB.exists():
        with connect(KG_DB) as conn:
            for table in ("kg_entities", "kg_triples", "kg_quality_issues", "kg_sources"):
                if has_table(conn, table):
                    kg_counts[table] = count_rows(conn, table)
            quality_summary = query_dicts(
                conn,
                """
                SELECT issue_type, field_name, COUNT(*) AS issue_count
                FROM kg_quality_issues
                GROUP BY issue_type, field_name
                ORDER BY issue_count DESC
                LIMIT 10
                """,
            )
            if has_table(conn, "kg_sources"):
                total_source_count = count_rows(conn, "kg_sources")
                source_summary = query_dicts(
                    conn,
                    """
                    SELECT source_id, source_name, source_type, source_path, source_url, record_count, created_at
                    FROM kg_sources
                    ORDER BY datetime(created_at) DESC, source_id DESC
                    LIMIT 12
                    """,
                )

    return {
        "analytics_db": str(ANALYTICS_DB),
        "kg_db": str(KG_DB),
        "analytics_counts": analytics_counts,
        "kg_counts": kg_counts,
        "top_departments": top_departments,
        "top_drugs": top_drugs,
        "top_symptoms": top_symptoms,
        "entity_stats": entity_stats,
        "relation_stats": relation_stats,
        "quality_summary": quality_summary,
        "source_summary": source_summary,
        "source_total_count": total_source_count,
        "source_returned_count": len(source_summary),
        "example_diseases": examples,
        "sample_questions": SAMPLE_QUESTIONS,
    }


def evaluation_payload() -> dict[str, Any]:
    return {
        "task2": {
            "extractor_label": "本地知识抽取链",
            "runtime_metrics_source": "run_task2_kg_pipeline response",
            "runtime_metric_label": "任务执行时返回吞吐量、平均耗时和入库数量",
        },
        "npu": {
            "status": "未启用",
            "claim": "未申报加速",
            "note": "当前环境展示 CPU 基线；如接入真实 NPU，可替换为实测报告。",
        },
    }


def lineage_payload() -> dict[str, Any]:
    overview = overview_payload()
    sources = overview.get("source_summary", [])
    total_source_count = int(overview.get("source_total_count") or len(sources))
    source_names = "、".join(source["source_name"] for source in sources[:3]) if sources else "暂无来源登记"
    source_records = sum(int(source.get("record_count") or 0) for source in sources)
    nodes = [
        {
            "id": "raw",
            "label": "原始混合数据集",
            "type": "source",
            "detail": f"任务一可接入 txt / csv / json / jsonl 等混合文件；当前图谱已登记 {total_source_count} 个真实来源，近源：{source_names}。",
        },
        {
            "id": "task1",
            "label": "任务一清洗链",
            "type": "pipeline",
            "detail": "按文件类型保留源格式输出，前置噪声清洗链统一处理内容质量。",
        },
        {
            "id": "clean",
            "label": "任务一最终数据集",
            "type": "dataset",
            "detail": "清洗后的 txt/csv/json/jsonl 仍放在一个最终数据集中，必要时再为任务二导出统一 JSONL。",
        },
        {
            "id": "task2",
            "label": "任务二知识抽取",
            "type": "pipeline",
            "detail": f"抽取疾病、症状、药物、检查、科室、治疗、病因等实体和关系；已纳入来源记录约 {source_records:,} 条。",
        },
        {
            "id": "kg",
            "label": "医学知识图谱",
            "type": "database",
            "detail": f"实体 {overview['kg_counts'].get('kg_entities', 0):,}，关系 {overview['kg_counts'].get('kg_triples', 0):,}。",
        },
        {
            "id": "task3",
            "label": "任务三问答与洞察",
            "type": "app",
            "detail": "把图谱转成分析库、自然语言查询、关系子图和质量审计视图。",
        },
    ]
    edges = [
        {"source": "raw", "target": "task1", "label": "接入与清洗"},
        {"source": "task1", "target": "clean", "label": "保留源格式交付"},
        {"source": "clean", "target": "task2", "label": "按任务二入口解析"},
        {"source": "task2", "target": "kg", "label": "实体关系入库"},
        {"source": "kg", "target": "task3", "label": "查询/推理/可视化"},
    ]
    return {
        "nodes": nodes,
        "edges": edges,
        "sources": sources,
        "source_total_count": total_source_count,
        "source_returned_count": len(sources),
    }


def disease_graph_payload(disease: str, limit: int = 80) -> dict[str, Any]:
    if not ANALYTICS_DB.exists():
        return {"disease": disease, "nodes": [], "edges": [], "facts": [], "description": ""}
    with connect(ANALYTICS_DB) as conn:
        matched = find_disease(conn, disease) or disease.strip()
        description = scalar(conn, "SELECT description FROM diseases WHERE name = ?", (matched,)) or ""
        facts = query_dicts(
            conn,
            """
            SELECT fact_type, fact_name, evidence, source_name, confidence
            FROM disease_facts
            WHERE disease = ?
              AND fact_type NOT LIKE 'cmeie_%'
            ORDER BY confidence DESC, fact_type, fact_name
            LIMIT ?
            """,
            (matched, limit),
        )
        known = load_quality_values()
        facts = [
            fact for fact in facts
            if not str(fact.get("fact_type", "")).startswith("cmeie_")
            and not (str(fact.get("fact_type")) == "has_symptom" and is_suspicious_fact_value(fact.get("fact_name"), known))
        ]

    nodes: list[dict[str, Any]] = [
        {"id": "disease", "label": matched, "type": "disease", "size": 28, "description": description}
    ]
    edges: list[dict[str, Any]] = []
    seen = {"disease"}
    relation_counts: dict[str, int] = {}
    for idx, fact in enumerate(facts):
        rel = str(fact["fact_type"])
        node_id = f"{rel}_{idx}"
        label = str(fact["fact_name"])
        if label in seen:
            continue
        seen.add(label)
        relation_counts[rel] = relation_counts.get(rel, 0) + 1
        nodes.append(
            {
                "id": node_id,
                "label": label,
                "type": rel,
                "size": 16,
                "confidence": fact.get("confidence"),
                "source": fact.get("source_name"),
            }
        )
        edges.append(
            {
                "source": "disease",
                "target": node_id,
                "label": RELATION_LABELS.get(rel, rel),
                "confidence": fact.get("confidence"),
            }
        )
    return {
        "disease": matched,
        "description": description,
        "nodes": nodes,
        "edges": edges,
        "facts": facts,
        "relation_counts": relation_counts,
    }


def quality_payload(q: str = "") -> dict[str, Any]:
    if not KG_DB.exists():
        return {"summary": [], "top_values": [], "issues": [], "total_issues": 0}
    keyword = q.strip()
    filter_clause = ""
    params: tuple[Any, ...] = ()
    if keyword:
        like = f"%{keyword}%"
        filter_clause = "WHERE value LIKE ? OR evidence LIKE ? OR field_name LIKE ?"
        params = (like, like, like)
    with connect(KG_DB) as conn:
        total_issues = int(conn.execute("SELECT COUNT(*) FROM kg_quality_issues").fetchone()[0])
        summary = query_dicts(
            conn,
            f"""
            SELECT
                issue_type AS 噪声类型,
                field_name AS 来源字段,
                COUNT(*) AS 拦截数量,
                '已拦截，未进入主知识图谱' AS 处理状态
            FROM kg_quality_issues
            {filter_clause}
            GROUP BY issue_type, field_name
            ORDER BY 拦截数量 DESC
            LIMIT 20
            """,
            params,
        )
        top_values = query_dicts(
            conn,
            f"""
            SELECT
                value AS 可疑值,
                COUNT(*) AS 出现次数,
                MIN(field_name) AS 来源字段,
                MIN(evidence) AS 示例证据,
                '原始数据字段污染，已隔离' AS 说明
            FROM kg_quality_issues
            {filter_clause}
            GROUP BY value
            ORDER BY 出现次数 DESC, 可疑值
            LIMIT 80
            """,
            params,
        )
        issues = query_dicts(
            conn,
            f"""
            SELECT
                issue_type AS 类型,
                field_name AS 字段,
                value AS 可疑值,
                evidence AS 原始证据,
                '已拦截，未进入主图谱/问答库' AS 处理状态
            FROM kg_quality_issues
            {filter_clause}
            ORDER BY issue_id DESC
            LIMIT 240
            """,
            params,
        )
    display_issues = sum(int(row.get("拦截数量") or 0) for row in summary) if keyword else total_issues
    visible_top_values = filter_quality_display_rows(top_values, 16)
    grouped_hidden_values = summarize_hidden_quality_rows(top_values)
    visible_issues = filter_quality_display_rows(issues, 80)
    return {
        "summary": summary,
        "top_values": mask_quality_rows(visible_top_values or grouped_hidden_values),
        "issues": mask_quality_rows(visible_issues),
        "total_issues": total_issues,
        "display_issues": display_issues,
        "query": keyword,
        "filtered": bool(keyword),
        "explanation": (
            ("当前仅展示与查询词相关的拦截记录；" if keyword else "")
            + "这些记录是构建知识图谱时识别出的可疑噪声，用于证明质量过滤生效；"
            "它们不会进入主知识图谱、疾病问答或关系子图。"
        ),
    }


def search_diseases_payload(q: str) -> dict[str, Any]:
    if not ANALYTICS_DB.exists():
        return {"items": []}
    like = f"%{q.strip()}%"
    with connect(ANALYTICS_DB) as conn:
        rows = query_dicts(
            conn,
            """
            SELECT name, description, source_count
            FROM diseases
            WHERE name LIKE ? OR description LIKE ?
            ORDER BY source_count DESC, LENGTH(name)
            LIMIT 20
            """,
            (like, like),
        )
    return {"items": rows}
