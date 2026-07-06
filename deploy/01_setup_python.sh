#!/usr/bin/env bash
# CCF 部署脚本 01：Python 环境安装
set -euo pipefail

ROOT="${CCF_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PYTHON="${CCF_PYTHON:-python3}"

usage() {
  cat <<'USAGE'
Usage: bash deploy/01_setup_python.sh

  创建 Python venv 并安装依赖。幂等：已安装的包跳过。
USAGE
}
[[ "${1:-}" == "--help" || "${1:-}" == "-h" ]] && { usage; exit 0; }

echo "=== [01/08] Python 环境安装 ==="

# venv
if [ ! -d "$ROOT/.venv" ]; then
  echo "创建虚拟环境..."
  $PYTHON -m venv "$ROOT/.venv"
else
  echo ".venv/ 已存在，跳过创建"
fi

# pip install (幂等)
echo "安装/更新依赖..."
"$ROOT/.venv/bin/pip" install -r "$ROOT/requirements.txt" -q 2>&1 | tail -3

# 编译检查
echo "编译检查核心模块..."
for f in mcp_server/server.py core/medical_query_engine.py kg/build_kg_v2.py kg/build_analytics_v2.py demo/task3_interactive_demo/server.py; do
  [ -f "$ROOT/$f" ] && "$ROOT/.venv/bin/python" -m py_compile "$ROOT/$f" && echo "  OK: $f" || echo "  SKIP: $f"
done

echo "Python 环境就绪。"
