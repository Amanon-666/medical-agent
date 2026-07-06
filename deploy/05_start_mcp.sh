#!/usr/bin/env bash
# CCF 部署脚本 05：启动 MCP Server
set -euo pipefail

ROOT="${CCF_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
MCP_PORT="${CCF_MCP_PORT:-8900}"
MCP_HOST="${CCF_MCP_HOST:-0.0.0.0}"

usage() {
  cat <<'USAGE'
Usage: bash deploy/05_start_mcp.sh [--stop|--status]

  启动 FastMCP Server（后台 screen 会话 "mcpserver"，端口 8900）。
  必须已配置 .env.runtime（含 CCF_LLM_API_KEY 等）。
USAGE
}

ACTION="start"
for a in "$@"; do case "$a" in --stop) ACTION="stop" ;; --status) ACTION="status" ;; --help|-h) usage; exit 0 ;; esac; done

echo "=== [05/08] MCP Server ==="

[ -f "$ROOT/.env.runtime" ] || { echo "错误: 需要 .env.runtime"; exit 1; }

if [ "$ACTION" = "stop" ]; then
  echo "停止 MCP Server..."
  pkill -f "mcp_server/server.py" 2>/dev/null && echo "已停止" || echo "未在运行"
  screen -S mcpserver -X quit 2>/dev/null || true
  exit 0
fi

if [ "$ACTION" = "status" ]; then
  if pgrep -f "mcp_server/server.py" >/dev/null 2>&1; then
    echo "MCP Server 运行中 (PID: $(pgrep -f 'mcp_server/server.py'))"
    curl -s -o /dev/null -w "HTTP %{http_code}" "http://127.0.0.1:$MCP_PORT/mcp" 2>/dev/null && echo " (MCP OK)" || echo " (端口无响应)"
  else
    echo "MCP Server 未运行"
  fi
  exit 0
fi

# 启动
if pgrep -f "mcp_server/server.py" >/dev/null 2>&1; then
  echo "MCP Server 已在运行，先停止旧进程..."
  pkill -f "mcp_server/server.py" 2>/dev/null || true
  screen -S mcpserver -X quit 2>/dev/null || true
  sleep 1
fi

echo "启动 MCP Server (端口 $MCP_PORT)..."
screen -dmS mcpserver bash -c \
  "set -a && source '$ROOT/.env.runtime' && set +a && cd '$ROOT' && .venv/bin/python mcp_server/server.py >> mcp_server.log 2>&1"
sleep 3

# 验证
CODE=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 3 "http://127.0.0.1:$MCP_PORT/mcp" 2>/dev/null || echo "000")
[ "$CODE" = "406" ] && echo "  MCP Server 就绪 (HTTP 406 = MCP OK)" || echo "  MCP Server 响应: HTTP $CODE (预期 406)"
