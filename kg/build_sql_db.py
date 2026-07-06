# -*- coding: utf-8 -*-
"""
从 medical.json 构建 SQLite 结构化分析数据库，供 NL2SQL 查询。

表结构：
  diseases    — 疾病基本信息（名称、分类、描述、治愈率、易感人群）
  symptoms    — 疾病症状（多对多，拍平）
  drugs       — 推荐/常用药物
  departments — 就诊科室
  complications — 并发症

用法：
    python kg/build_sql_db.py
    python kg/build_sql_db.py --src D:/ccf数据集/QASystemOnMedicalKG/data/medical.json --db data/medical_analytics.db
"""
import json
import sqlite3
import argparse
from pathlib import Path

DEFAULT_SRC = r"D:\ccf数据集\QASystemOnMedicalKG\data\medical.json"
DEFAULT_DB  = str(Path(__file__).resolve().parent.parent / "data" / "medical_analytics.db")

DDL = """
CREATE TABLE IF NOT EXISTS diseases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT,
    description TEXT,
    cure_probability TEXT,
    susceptible_population TEXT,
    infection_way TEXT,
    prevention TEXT
);
CREATE TABLE IF NOT EXISTS symptoms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    disease_id INTEGER NOT NULL,
    symptom TEXT NOT NULL,
    FOREIGN KEY (disease_id) REFERENCES diseases(id)
);
CREATE TABLE IF NOT EXISTS drugs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    disease_id INTEGER NOT NULL,
    drug_name TEXT NOT NULL,
    drug_type TEXT NOT NULL,
    FOREIGN KEY (disease_id) REFERENCES diseases(id)
);
CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    disease_id INTEGER NOT NULL,
    department TEXT NOT NULL,
    FOREIGN KEY (disease_id) REFERENCES diseases(id)
);
CREATE TABLE IF NOT EXISTS complications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    disease_id INTEGER NOT NULL,
    complication TEXT NOT NULL,
    FOREIGN KEY (disease_id) REFERENCES diseases(id)
);
CREATE INDEX IF NOT EXISTS idx_symptoms_disease ON symptoms(disease_id);
CREATE INDEX IF NOT EXISTS idx_drugs_disease ON drugs(disease_id);
CREATE INDEX IF NOT EXISTS idx_symptoms_text ON symptoms(symptom);
CREATE INDEX IF NOT EXISTS idx_drugs_name ON drugs(drug_name);
CREATE INDEX IF NOT EXISTS idx_diseases_name ON diseases(name);
"""


def _join(lst, sep="、"):
    if not lst:
        return None
    if isinstance(lst, list):
        return sep.join(str(x) for x in lst)
    return str(lst)


def build(src: str, db_path: str):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(DDL)

    total = 0
    with open(src, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue

            name = d.get("name", "").strip()
            if not name:
                continue

            cats = d.get("category", [])
            cat_str = _join(cats if isinstance(cats, list) else [cats])

            cur = conn.execute(
                """INSERT OR IGNORE INTO diseases
                   (name, category, description, cure_probability,
                    susceptible_population, infection_way, prevention)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    name,
                    cat_str,
                    (d.get("desc") or "")[:500],
                    d.get("cured_prob") or d.get("cure_prob") or "",
                    _join(d.get("easy_get")) or "",
                    _join(d.get("get_way")) or "",
                    _join(d.get("prevent")) or "",
                ),
            )
            disease_id = cur.lastrowid
            if disease_id == 0:
                row = conn.execute("SELECT id FROM diseases WHERE name=?", (name,)).fetchone()
                if row:
                    disease_id = row[0]
                else:
                    continue

            for sym in (d.get("symptom") or []):
                sym = str(sym).strip()
                if sym:
                    conn.execute("INSERT INTO symptoms (disease_id, symptom) VALUES (?,?)",
                                 (disease_id, sym))

            for drug in (d.get("recommand_drug") or []):
                drug = str(drug).strip()
                if drug:
                    conn.execute("INSERT INTO drugs (disease_id, drug_name, drug_type) VALUES (?,?,?)",
                                 (disease_id, drug, "recommended"))
            for drug in (d.get("common_drug") or []):
                drug = str(drug).strip()
                if drug:
                    conn.execute("INSERT INTO drugs (disease_id, drug_name, drug_type) VALUES (?,?,?)",
                                 (disease_id, drug, "common"))

            for dept in (d.get("cure_department") or []):
                dept = str(dept).strip()
                if dept:
                    conn.execute("INSERT INTO departments (disease_id, department) VALUES (?,?)",
                                 (disease_id, dept))

            for comp in (d.get("acompany") or []):
                comp = str(comp).strip()
                if comp:
                    conn.execute("INSERT INTO complications (disease_id, complication) VALUES (?,?)",
                                 (disease_id, comp))
            total += 1

    conn.commit()
    conn.close()

    # 汇总统计
    conn2 = sqlite3.connect(db_path)
    stats = {t: conn2.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
             for t in ("diseases", "symptoms", "drugs", "departments", "complications")}
    conn2.close()
    print(f"构建完成：{db_path}")
    for k, v in stats.items():
        print(f"  {k}: {v} 条")
    print(f"  共处理 {total} 种疾病")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--db",  default=DEFAULT_DB)
    args = ap.parse_args()
    build(args.src, args.db)
