# -*- coding: utf-8 -*-
"""Runtime paths for the medical data visualization platform."""

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = Path(__file__).resolve().parent / "static"

ANALYTICS_DB = Path(
    os.environ.get("CCF_TASK3_ANALYTICS_DB", ROOT / "data" / "task3_analytics.db")
).expanduser()
KG_DB = Path(
    os.environ.get("CCF_TASK2_KG_DB", ROOT / "data" / "task2_medical_kg.db")
).expanduser()
ANALYSIS_RESULT_DIR = Path(
    os.environ.get(
        "CCF_TASK3_RESULT_DIR",
        ROOT / "data" / "task3_analysis_results",
    )
).expanduser()

TASK2_CMEEE_EVAL_REPORT = ROOT / "data" / "task2_cmeee_eval_report_v2.json"
TASK2_CMEIE_SELFCHECK_REPORT = ROOT / "data" / "task2_cmeie_selfcheck_report_v2.json"
TASK3_NL2SQL_EVAL_REPORT = ROOT / "data" / "task3_nl2sql_eval_report.json"
TASK3_NL2SQL_BENCHMARK = ROOT / "evaluation" / "task3" / "results" / "benchmark_metrics.json"

DEFAULT_TASK3_AGENT_ID = int(os.environ.get("CCF_TASK3_AGENT_ID", "5"))
