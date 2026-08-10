# -*- coding: utf-8 -*-
"""生成任务一评测专用的最小 SQLite 知识库。

项目运行态的 term_kb.db/noise_kb.db 由平台维护，不能为了本地评测去改动。
因此本模块在本次运行目录下生成一个只覆盖自建语料的可审计知识库，并在报告
中明确标注来源。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


TERM_MAPPINGS = (
    ("T2DM", "2型糖尿病"),
    ("HbA1c", "糖化血红蛋白"),
    ("BP", "血压"),
    ("bid", "每日两次"),
    ("HTN", "高血压"),
    ("FPG", "空腹血糖"),
    ("mmol/L", "毫摩尔/升"),
    ("CHD", "冠心病"),
    ("mmHg", "毫米汞柱"),
    ("CKD", "慢性肾脏病"),
    ("Cr", "肌酐"),
    ("umol/L", "微摩尔/升"),
    ("qd", "每日一次"),
    ("COPD", "慢性阻塞性肺疾病"),
    ("SpO2", "血氧饱和度"),
    ("HR", "心率"),
    ("bpm", "次/分"),
    ("HLP", "高脂血症"),
    ("LDL-C", "低密度脂蛋白胆固醇"),
    ("po", "口服"),
    ("tid", "每日三次"),
)


NOISE_RULES = (
    ("eval_mention", "mention", r"@[A-Za-z0-9_\-\u4e00-\u9fff]{1,30}", "regex", "match", 1),
    ("eval_controlled", "fixture_noise", r"controlled_noise_\d{8}", "regex", "match", 1),
    ("hint_chat", "chitchat", "跟隔壁老王聊天，顺便聊了球赛", "semantic_hint", "match", 0),
    ("hint_colloquial", "colloquial", "哎呀妈呀，今天路上堵车太久了", "semantic_hint", "match", 0),
    ("hint_work", "work_instruction", "记得把这个录入，交接班群里再说", "semantic_hint", "match", 0),
)


def build_evaluation_kb(output_dir: Path) -> dict[str, Any]:
    """生成本地评测知识库并返回可写入报告的元数据。"""

    output_dir.mkdir(parents=True, exist_ok=True)
    term_path = output_dir / "term_kb.db"
    noise_path = output_dir / "noise_kb.db"

    with sqlite3.connect(term_path) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS term_mappings;
            CREATE TABLE term_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                abbr TEXT NOT NULL,
                full TEXT NOT NULL,
                negative_patterns TEXT DEFAULT '',
                status TEXT DEFAULT 'active'
            );
            """
        )
        conn.executemany(
            "INSERT INTO term_mappings (abbr, full, negative_patterns, status) "
            "VALUES (?, ?, '', 'active')",
            TERM_MAPPINGS,
        )

    with sqlite3.connect(noise_path) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS noise_rules;
            CREATE TABLE noise_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id TEXT NOT NULL,
                category TEXT NOT NULL,
                pattern TEXT NOT NULL,
                match_type TEXT DEFAULT 'exact',
                scope TEXT DEFAULT 'match',
                confidence REAL DEFAULT 1.0,
                medical_safe INTEGER DEFAULT 1,
                status TEXT DEFAULT 'active',
                negative_patterns TEXT DEFAULT ''
                ,source_type TEXT DEFAULT 'evaluation_controlled'
                ,source_ref TEXT DEFAULT ''
                ,evidence TEXT DEFAULT ''
            );
            """
        )
        conn.executemany(
            "INSERT INTO noise_rules "
            "(rule_id, category, pattern, match_type, scope, confidence, medical_safe, status) "
            "VALUES (?, ?, ?, ?, ?, 1.0, ?, 'active')",
            NOISE_RULES,
        )

    return {
        "source": "generated_evaluation_kb",
        "purpose": "覆盖压力语料的术语、基础规则和仅用于触发教师判断的语义提示",
        "term_kb_path": str(term_path),
        "noise_kb_path": str(noise_path),
        "term_rule_count": len(TERM_MAPPINGS),
        "noise_rule_count": len(NOISE_RULES),
        "semantic_hint_count": sum(1 for item in NOISE_RULES if item[3] == "semantic_hint"),
        "production_kb_modified": False,
    }
