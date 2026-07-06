#!/usr/bin/env bash
# CCF 部署脚本 03：注册算子到 DataMate 数据库
set -euo pipefail

ROOT="${CCF_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
DB_CONTAINER="${CCF_DATAMATE_DB_CONTAINER:-datamate-database}"
SQL_DIR="$ROOT/release_assets/datamate_state"

usage() {
  cat <<'USAGE'
Usage: bash deploy/03_register_operators.sh [--check-only]

  将 CCF 自定义算子注册到 DataMate PostgreSQL（t_operator + category 关系）。
  先尝试 release_assets/ 中预导出的 SQL；若无，则从 DataMate API 的算子列表推断。

  --check-only  仅检查算子是否已注册，不执行 SQL
USAGE
}
CHECK_ONLY=0
for a in "$@"; do case "$a" in --check-only) CHECK_ONLY=1 ;; --help|-h) usage; exit 0 ;; esac; done

echo "=== [03/08] 注册算子到 DataMate DB ==="

# 找到最新导出目录
LATEST_SQL=$(find "$SQL_DIR" -name "datamate_operator_registration.sql" -type f 2>/dev/null | sort -r | head -1)

if [ -n "$LATEST_SQL" ]; then
  echo "使用预导出 SQL: $LATEST_SQL"
  if [ "$CHECK_ONLY" = "1" ]; then
    echo "[CHECK-ONLY] 跳过执行。文件位置: $LATEST_SQL"
    exit 0
  fi
  docker exec -i "$DB_CONTAINER" psql -U postgres -d datamate < "$LATEST_SQL" 2>&1 | tail -5
else
  echo "未找到预导出 SQL，使用 generate_datamate_registration_sql.py 生成..."
  [ "$CHECK_ONLY" = "1" ] && { echo "无预导出 SQL，无法检查"; exit 1; }
  "$ROOT/.venv/bin/python" "$ROOT/scripts/generate_datamate_registration_sql.py" --dry-run=false 2>&1
fi

# 验证
echo "验证算子注册..."
docker exec "$DB_CONTAINER" psql -U postgres -d datamate -c "SELECT id, name FROM t_operator WHERE id IN ('EmojiCleaner','UrlRemover','LLMNoiseFilter','MedicalTermNormalizer','MedicalEntityExtractor','MedicalRelationExtractor','MedicalTripleGenerator','TableColumnCleaner','JsonFieldCleaner','WhitespaceNormalizer');" 2>&1

echo "算子注册完成。"
