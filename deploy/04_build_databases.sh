#!/usr/bin/env bash
# CCF 部署脚本 04：构建/恢复知识图谱与分析数据库
set -euo pipefail

ROOT="${CCF_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
KG_DB="${CCF_TASK2_KG_DB:-$ROOT/data/task2_medical_kg.db}"
ANALYTICS_DB="${CCF_TASK3_ANALYTICS_DB:-$ROOT/data/task3_analytics.db}"
FORCE=0

usage() {
  cat <<'USAGE'
Usage: bash deploy/04_build_databases.sh [--force]

  构建/恢复任务二知识图谱(task2_medical_kg.db)和任务三分析库(task3_analytics.db)。
  已有则跳过；--force 强制重建。

  环境变量:
    CCF_MEDICAL_KG_DATA   medical.json 路径（KG 数据源）
    CCF_TASK2_KG_DB       KG DB 路径
    CCF_TASK3_ANALYTICS_DB 分析库路径
USAGE
}
for a in "$@"; do case "$a" in --force) FORCE=1 ;; --help|-h) usage; exit 0 ;; esac; done

echo "=== [04/08] 构建数据库 ==="

[ -f "$ROOT/.env.runtime" ] && { set -a; source "$ROOT/.env.runtime"; set +a; }

# task2 KG
if [ "$FORCE" = "1" ] || [ ! -f "$KG_DB" ]; then
  echo "构建 task2 KG: $KG_DB"
  MEDICAL_JSON="${CCF_MEDICAL_KG_DATA:-}"
  [ -z "$MEDICAL_JSON" ] && { echo "错误: 设置 CCF_MEDICAL_KG_DATA=medical.json 路径"; exit 1; }
  [ ! -f "$MEDICAL_JSON" ] && { echo "错误: medical.json 不存在: $MEDICAL_JSON"; exit 1; }
  "$ROOT/.venv/bin/python" "$ROOT/kg/build_kg_v2.py" --db "$KG_DB" --medical-json "$MEDICAL_JSON" 2>&1 | tail -10
  echo "  KG 构建完成: $(du -h "$KG_DB" | cut -f1)"
else
  echo "task2 KG 已存在 ($(du -h "$KG_DB" | cut -f1))，跳过构建"
fi

# task3 analytics
if [ "$FORCE" = "1" ] || [ ! -f "$ANALYTICS_DB" ]; then
  echo "构建 task3 analytics: $ANALYTICS_DB"
  "$ROOT/.venv/bin/python" "$ROOT/kg/build_analytics_v2.py" --kg-db "$KG_DB" --analytics-db "$ANALYTICS_DB" 2>&1 | tail -5
  echo "  Analytics 构建完成: $(du -h "$ANALYTICS_DB" | cut -f1)"
else
  echo "task3 analytics 已存在 ($(du -h "$ANALYTICS_DB" | cut -f1))，跳过构建"
fi

# 验证
echo "验证数据库..."
"$ROOT/.venv/bin/python" -c "
import sqlite3
for db, label in [('$KG_DB','KG'),('$ANALYTICS_DB','Analytics')]:
  c=sqlite3.connect(db)
  tables=c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()
  print(f'  {label}: {len(tables)} tables')
  c.close()
"
echo "数据库就绪。"
