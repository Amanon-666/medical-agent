#!/usr/bin/env bash
set -euo pipefail

# 将任务二级联抽取以同一组文件部署到运行态。主机和路径均可通过环境变量覆盖，
# 不把当前服务器地址写死到业务代码中。
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE_HOST="${CCF_REMOTE_HOST:-ccf-server}"
REMOTE_ROOT="${CCF_REMOTE_ROOT:-/home/panyushuo/ccf-medical-ai}"
STAMP="$(date +%Y%m%d_%H%M%S)"
REMOTE_BACKUP="${REMOTE_ROOT}/backups/task2_cascade_${STAMP}"

FILES=(
  core/task2_cascade.py
  core/task2_cascade_schemas.py
  core/task2_verifier.py
  core/medical_extraction_service.py
  mcp_server/task2/pipeline_service.py
  mcp_server/tools/task2_pipeline.py
  mcp_server/tools/task2_extract.py
  operators/medical_entity_extractor/process.py
  operators/medical_relation_extractor/process.py
  operators/medical_triple_generator/process.py
)

ssh "$REMOTE_HOST" "set -eu
cd '$REMOTE_ROOT'
mkdir -p '$REMOTE_BACKUP/core' '$REMOTE_BACKUP/mcp_server/task2' '$REMOTE_BACKUP/mcp_server/tools' \
  '$REMOTE_BACKUP/operators/medical_entity_extractor' '$REMOTE_BACKUP/operators/medical_relation_extractor' \
  '$REMOTE_BACKUP/operators/medical_triple_generator'
cp -p core/medical_extraction_service.py '$REMOTE_BACKUP/core/'
cp -p mcp_server/task2/pipeline_service.py '$REMOTE_BACKUP/mcp_server/task2/'
cp -p mcp_server/tools/task2_pipeline.py mcp_server/tools/task2_extract.py '$REMOTE_BACKUP/mcp_server/tools/'
cp -p operators/medical_entity_extractor/process.py '$REMOTE_BACKUP/operators/medical_entity_extractor/'
cp -p operators/medical_relation_extractor/process.py '$REMOTE_BACKUP/operators/medical_relation_extractor/'
cp -p operators/medical_triple_generator/process.py '$REMOTE_BACKUP/operators/medical_triple_generator/'
"

for relative_path in "${FILES[@]}"; do
  scp "$PROJECT_ROOT/$relative_path" "$REMOTE_HOST:$REMOTE_ROOT/$relative_path"
done

ssh "$REMOTE_HOST" "set -eu
cd '$REMOTE_ROOT'
.venv/bin/python -m py_compile ${FILES[*]}
screen -S mcpserver -X quit || true
sleep 1
screen -dmS mcpserver bash -c \"set -a && source '$REMOTE_ROOT/.env.runtime' && set +a && cd '$REMOTE_ROOT' && .venv/bin/python mcp_server/server.py >> mcp_server.log 2>&1\"
sleep 2
grep -q 'Uvicorn running on http://0.0.0.0:8900' mcp_server.log
"

echo "Task 2 cascade deployed to $REMOTE_HOST:$REMOTE_ROOT; backup: $REMOTE_BACKUP"
