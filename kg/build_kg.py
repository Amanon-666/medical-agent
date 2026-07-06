# -*- coding: utf-8 -*-
"""
知识图谱构建：三元组列表 → SQLite 数据库。
表结构见 config/schema.json 的 task3_db_schema。
这是任务二（图谱落地）和任务三（NL2SQL 查询）的衔接点。
"""
import sqlite3
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict

DDL = """
CREATE TABLE IF NOT EXISTS table_triples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT, subject_type TEXT,
    predicate TEXT,
    object TEXT, object_type TEXT,
    confidence REAL,
    source_file TEXT
);
CREATE TABLE IF NOT EXISTS table_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity TEXT, entity_type TEXT,
    freq INTEGER, source_files TEXT
);
CREATE INDEX IF NOT EXISTS idx_subject ON table_triples(subject);
CREATE INDEX IF NOT EXISTS idx_object ON table_triples(object);
CREATE INDEX IF NOT EXISTS idx_predicate ON table_triples(predicate);
"""


def build_kg(records: List[Dict[str, Any]], db_path: str) -> Dict[str, int]:
    """
    records: 每篇文档的任务二输出，格式见 schema.json task2_output：
             [{"source_file": str, "entities": [...], "triples": [...]}, ...]
    返回统计 {triples, entities}
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(DDL)

    n_triples = 0
    ent_freq = defaultdict(int)
    ent_type = {}
    ent_files = defaultdict(set)

    for rec in records:
        src = rec.get("source_file", "")
        for t in rec.get("triples", []):
            conn.execute(
                "INSERT INTO table_triples (subject, subject_type, predicate, object, object_type, confidence, source_file) "
                "VALUES (?,?,?,?,?,?,?)",
                (t.get("subject", ""), t.get("subject_type", ""), t.get("predicate", ""),
                 t.get("object", ""), t.get("object_type", ""), t.get("confidence", 1.0), src),
            )
            n_triples += 1
        for e in rec.get("entities", []):
            key = e.get("text", "")
            if not key:
                continue
            ent_freq[key] += 1
            ent_type[key] = e.get("type", "")
            ent_files[key].add(src)

    for ent, freq in ent_freq.items():
        conn.execute(
            "INSERT INTO table_entities (entity, entity_type, freq, source_files) VALUES (?,?,?,?)",
            (ent, ent_type.get(ent, ""), freq, ",".join(sorted(ent_files[ent]))),
        )

    conn.commit()
    conn.close()
    return {"triples": n_triples, "entities": len(ent_freq)}


if __name__ == "__main__":
    # 简单自测
    demo = [{
        "source_file": "demo.txt",
        "entities": [{"text": "2型糖尿病", "type": "dis"}, {"text": "二甲双胍", "type": "dru"}],
        "triples": [{"subject": "2型糖尿病", "predicate": "治疗", "object": "二甲双胍", "confidence": 0.95}],
    }]
    print(build_kg(demo, "kg/medical_kg.db"))
