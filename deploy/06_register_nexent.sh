#!/usr/bin/env bash
# CCF 部署脚本 06：注册 MCP + 创建/更新 Nexent Agent
set -euo pipefail

ROOT="${CCF_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SKIP_AGENTS=0; DRY_RUN=0

usage() {
  cat <<'USAGE'
Usage: bash deploy/06_register_nexent.sh [--skip-agents] [--dry-run]

  1) 注册 MCP Server 到 Nexent (scripts/register_mcp.py)
  2) 扫描 MCP 工具 + 更新/发布任务一/二/三 Agent (scripts/update_nexent_agents.py)

  --skip-agents  只注册 MCP，不更新 Agent
USAGE
}
for a in "$@"; do case "$a" in --skip-agents) SKIP_AGENTS=1 ;; --dry-run) DRY_RUN=1 ;; --help|-h) usage; exit 0 ;; esac; done

echo "=== [06/08] 注册 Nexent MCP + Agent ==="
[ -f "$ROOT/.env.runtime" ] || { echo "错误: 需要 .env.runtime"; exit 1; }

cd "$ROOT"
set -a; source .env.runtime; set +a
PY="$ROOT/.venv/bin/python"

if [ "$SKIP_AGENTS" != "1" ] && [ -z "${CCF_NEXENT_PASSWORD:-}" ]; then
  cat >&2 <<'MSG'
错误: 缺少 CCF_NEXENT_PASSWORD，无法更新/发布 Nexent Agent。

处理方式:
  1. 在 .env.runtime 中填写 CCF_NEXENT_EMAIL 和 CCF_NEXENT_PASSWORD；
  2. 或只注册 MCP 时执行: bash deploy/06_register_nexent.sh --skip-agents。

脚本不会使用空密码继续发布，以免把部署失败误判为 Agent 已更新。
MSG
  exit 1
fi

# Step 1: 注册 MCP
echo "[1/2] 注册 MCP Server..."
if [ "$DRY_RUN" = "1" ]; then
  echo "  [DRY-RUN] $PY scripts/register_mcp.py"
else
  "$PY" scripts/register_mcp.py 2>&1
  echo "  MCP 注册完成"
fi

# Step 2: 更新 Agent
if [ "$SKIP_AGENTS" = "1" ]; then
  echo "[2/2] 跳过 Agent 更新 (--skip-agents)"
else
  echo "[2/2] 扫描工具 + 更新 Agent prompt..."
  if [ "$DRY_RUN" = "1" ]; then
    echo "  [DRY-RUN] $PY scripts/update_nexent_agents.py"
  else
    "$PY" scripts/update_nexent_agents.py 2>&1 | tail -10
    echo "  Agent 更新完成"
  fi

  # 验证
  echo "验证 Agent 状态..."
  TOKEN=$(curl -s -X POST "${CCF_NEXENT_CONFIG_BASE:-http://127.0.0.1:5010}/user/signin" -H 'Content-Type: application/json' -d "{\"email\":\"${CCF_NEXENT_EMAIL:-suadmin@nexent.com}\",\"password\":\"${CCF_NEXENT_PASSWORD:-}\"}" | "$PY" -c "import sys,json; print(json.load(sys.stdin)['data']['session']['access_token'])" 2>/dev/null || echo "")
  if [ -n "$TOKEN" ]; then
    curl -s "${CCF_NEXENT_CONFIG_BASE:-http://127.0.0.1:5010}/agent/list" -H "Authorization: Bearer $TOKEN" | "$PY" -c "import sys,json; [print(f'  Agent {a[\"agent_id\"]}: {a[\"display_name\"]} published={a[\"is_published\"]}') for a in json.load(sys.stdin)]" 2>/dev/null
  fi
fi

echo "Nexent 注册完成。"
