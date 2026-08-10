#!/usr/bin/env bash
set -euo pipefail

# 将任务一同步等待、格式分组并发与可选后台模式作为一个可回滚单元部署。
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
: "${CCF_REMOTE_HOST:?Set CCF_REMOTE_HOST to the deployment host}"
: "${CCF_REMOTE_ROOT:?Set CCF_REMOTE_ROOT to the project root on the deployment host}"
REMOTE_HOST="$CCF_REMOTE_HOST"
REMOTE_ROOT="$CCF_REMOTE_ROOT"
STAMP="$(date +%Y%m%d_%H%M%S)"
REMOTE_BACKUP="$REMOTE_ROOT/backups/task1_async_parallel_$STAMP"

FILES=(
  mcp_server/task1/execution.py
  mcp_server/task1/status.py
  mcp_server/task1/async_worker.py
  mcp_server/task1/mixed_cleaning_service.py
  mcp_server/task1/mineru_client.py
  mcp_server/task1/runtime_helpers/preserved_pipeline.py
  mcp_server/tools/task1_data.py
  deploy/runtime_patches/apply_nexent_task1_deterministic_route.py
  deploy/runtime_patches/README.md
  deploy/verify_task1_async_parallel.py
  deploy/verify_nexent_task1_status.py
  deploy/verify_nexent_task1_submit.py
  deploy/verify_nexent_task1_sync.py
  scripts/update_nexent_agents.py
  scripts/update_nexent_task1_agent.py
  clients/nexent_client.py
)
PY_FILES=(
  mcp_server/task1/execution.py
  mcp_server/task1/status.py
  mcp_server/task1/async_worker.py
  mcp_server/task1/mixed_cleaning_service.py
  mcp_server/task1/mineru_client.py
  mcp_server/task1/runtime_helpers/preserved_pipeline.py
  mcp_server/tools/task1_data.py
  deploy/runtime_patches/apply_nexent_task1_deterministic_route.py
  deploy/verify_task1_async_parallel.py
  deploy/verify_nexent_task1_status.py
  deploy/verify_nexent_task1_submit.py
  deploy/verify_nexent_task1_sync.py
  scripts/update_nexent_agents.py
  scripts/update_nexent_task1_agent.py
  clients/nexent_client.py
)

ssh "$REMOTE_HOST" "set -eu
cd '$REMOTE_ROOT'
mkdir -p '$REMOTE_BACKUP/mcp_server/task1/runtime_helpers' '$REMOTE_BACKUP/mcp_server/tools' '$REMOTE_BACKUP/deploy/runtime_patches' '$REMOTE_BACKUP/scripts' '$REMOTE_BACKUP/clients'
if [ -f .env.runtime ]; then
  cp -p .env.runtime '$REMOTE_BACKUP/.env.runtime'
  sed -i 's/^CCF_MINERU_TIMEOUT_SECONDS=.*/CCF_MINERU_TIMEOUT_SECONDS=/' .env.runtime
fi
for path in mcp_server/task1/status.py mcp_server/task1/async_worker.py mcp_server/task1/mixed_cleaning_service.py \
  mcp_server/task1/mineru_client.py \
  mcp_server/task1/runtime_helpers/preserved_pipeline.py \
  mcp_server/tools/task1_data.py deploy/runtime_patches/apply_nexent_task1_deterministic_route.py \
  deploy/runtime_patches/README.md scripts/update_nexent_agents.py \
  scripts/update_nexent_task1_agent.py clients/nexent_client.py; do
  if [ -f \"\$path\" ]; then
    cp -p \"\$path\" '$REMOTE_BACKUP/'\"\$path\"
  fi
done
if [ -f mcp_server/task1/execution.py ]; then
  cp -p mcp_server/task1/execution.py '$REMOTE_BACKUP/mcp_server/task1/execution.py'
fi
"

for relative_path in "${FILES[@]}"; do
  scp "$PROJECT_ROOT/$relative_path" "$REMOTE_HOST:$REMOTE_ROOT/$relative_path"
done

ssh "$REMOTE_HOST" "set -eu
cd '$REMOTE_ROOT'
.venv/bin/python -m py_compile ${PY_FILES[*]}
bash deploy/runtime_patches/apply_all.sh
screen -S mcpserver -X quit || true
sleep 1
screen -dmS mcpserver bash -c \"set -a && source '$REMOTE_ROOT/.env.runtime' && set +a && cd '$REMOTE_ROOT' && .venv/bin/python mcp_server/server.py >> mcp_server.log 2>&1\"
sleep 3
grep -q 'Uvicorn running on http://0.0.0.0:8900' mcp_server.log
set -a
source '$REMOTE_ROOT/.env.runtime'
set +a
.venv/bin/python scripts/update_nexent_task1_agent.py
"

echo "Task 1 sync-wait/parallel runtime deployed; backup: $REMOTE_BACKUP"
