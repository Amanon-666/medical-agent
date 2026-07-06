#!/usr/bin/env bash
# CCF 部署脚本 02：部署算子到 DataMate Runtime
set -euo pipefail

ROOT="${CCF_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
RUNTIME_CONTAINER="${CCF_DATAMATE_RUNTIME_CONTAINER:-datamate-runtime}"
DRY_RUN=0

usage() {
  cat <<'USAGE'
Usage: bash deploy/02_deploy_operators.sh [--dry-run]

  把 task1(14个) + task2(4个) 算子代码和 SQLite KB 部署到
  DataMate runtime 容器，最后重启容器使新代码生效。

  环境变量:
    CCF_DATAMATE_RUNTIME_CONTAINER  容器名（默认 datamate-runtime）
USAGE
}

for a in "$@"; do case "$a" in --dry-run) DRY_RUN=1 ;; --help|-h) usage; exit 0 ;; esac; done

echo "=== [02/08] 部署算子到 DataMate Runtime ==="

# task1: 文本清洗 + 结构化清洗
TASK1_OPS=(emoji_cleaner url_remover grable_characters_cleaner invisible_characters_cleaner fullwidth_character_cleaner traditional_chinese_cleaner html_tag_cleaner whitespace_normalizer medical_term_normalizer llm_noise_filter table_column_cleaner json_field_cleaner medical_record_splitter unified_jsonl_exporter)
# task2: 知识抽取
TASK2_OPS=(medical_entity_extractor medical_relation_extractor medical_triple_generator medical_text_quality_filter)

CONTAINER_DIR="/opt/runtime/datamate/ops/user"

deploy_op() {
  local op="$1" src="$ROOT/operators/$op"
  [ -d "$src" ] || { echo "  SKIP: $op（内置算子，无需文件部署）"; return; }
  [ "$DRY_RUN" = "1" ] || docker exec "$RUNTIME_CONTAINER" mkdir -p "$CONTAINER_DIR/$op" 2>/dev/null
  for f in process.py metadata.yml __init__.py; do
    [ -f "$src/$f" ] || continue
    [ "$DRY_RUN" = "1" ] && { echo "  [DRY-RUN] docker cp $src/$f $RUNTIME_CONTAINER:$CONTAINER_DIR/$op/$f"; continue; }
    docker cp "$src/$f" "$RUNTIME_CONTAINER:$CONTAINER_DIR/$op/$f" && echo "  OK: $op/$f"
  done
  for py in "$src"/*.py; do
    [ -f "$py" ] || continue
    local f="$(basename "$py")"
    case "$f" in process.py|__init__.py) continue ;; esac
    [ "$DRY_RUN" = "1" ] && { echo "  [DRY-RUN] docker cp $py $RUNTIME_CONTAINER:$CONTAINER_DIR/$op/$f"; continue; }
    docker cp "$py" "$RUNTIME_CONTAINER:$CONTAINER_DIR/$op/$f" && echo "  OK: $op/$f"
  done
  # 算子内的 SQLite KB
  for db in "$src"/*.db; do
    [ -f "$db" ] || continue
    [ "$DRY_RUN" = "1" ] && { echo "  [DRY-RUN] docker cp $db $RUNTIME_CONTAINER:$CONTAINER_DIR/$op/$(basename "$db")"; continue; }
    docker cp "$db" "$RUNTIME_CONTAINER:$CONTAINER_DIR/$op/$(basename "$db")" && echo "  OK: $op/$(basename "$db")"
  done
}

echo "部署 task1 算子 (${#TASK1_OPS[@]}个)..."
for op in "${TASK1_OPS[@]}"; do deploy_op "$op"; done

echo "部署 task2 算子 (${#TASK2_OPS[@]}个)..."
for op in "${TASK2_OPS[@]}"; do deploy_op "$op"; done

# core/ 目录
if [ -d "$ROOT/core" ]; then
  echo "部署 core/ 到 runtime 容器..."
  [ "$DRY_RUN" = "1" ] && { echo "  [DRY-RUN] docker cp core/ $RUNTIME_CONTAINER:/opt/runtime/ccf_medical_ai/core/"; }
  [ "$DRY_RUN" = "0" ] && { docker exec "$RUNTIME_CONTAINER" rm -rf /opt/runtime/ccf_medical_ai/core 2>/dev/null || true; docker cp "$ROOT/core" "$RUNTIME_CONTAINER:/opt/runtime/ccf_medical_ai/core/" && echo "  OK: core/"; }
fi

if [ -f "$ROOT/data/task2_medical_kg.db" ]; then
  echo "部署 task2 KG 词典库到 runtime 容器..."
  if [ "$DRY_RUN" = "1" ]; then
    echo "  [DRY-RUN] docker cp data/task2_medical_kg.db $RUNTIME_CONTAINER:/opt/runtime/ccf_medical_ai/data/task2_medical_kg.db"
  else
    docker exec "$RUNTIME_CONTAINER" mkdir -p /opt/runtime/ccf_medical_ai/data
    docker cp "$ROOT/data/task2_medical_kg.db" "$RUNTIME_CONTAINER:/opt/runtime/ccf_medical_ai/data/task2_medical_kg.db"
    echo "  OK: task2_medical_kg.db"
  fi
fi

# 重启
echo "重启 $RUNTIME_CONTAINER..."
[ "$DRY_RUN" = "1" ] && { echo "  [DRY-RUN] docker restart $RUNTIME_CONTAINER"; exit 0; }
docker restart "$RUNTIME_CONTAINER"
sleep 3
echo "算子部署完成。等待 runtime 就绪后继续 03_register_operators.sh"
