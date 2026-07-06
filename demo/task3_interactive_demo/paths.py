# -*- coding: utf-8 -*-
"""
可视化平台运行路径模块。

该模块定义项目根目录、数据目录、知识图谱库和分析库路径。
"""

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = Path(__file__).resolve().parent / "static"

ANALYTICS_DB = ROOT / "data" / "task3_analytics.db"
KG_DB = ROOT / "data" / "task2_medical_kg.db"

TASK2_CMEEE_EVAL_REPORT = ROOT / "data" / "task2_cmeee_eval_report_v2.json"
TASK2_CMEIE_SELFCHECK_REPORT = ROOT / "data" / "task2_cmeie_selfcheck_report_v2.json"
TASK3_NL2SQL_EVAL_REPORT = ROOT / "data" / "task3_nl2sql_eval_report.json"

DEFAULT_TASK3_AGENT_ID = int(os.environ.get("CCF_TASK3_AGENT_ID", "5"))
