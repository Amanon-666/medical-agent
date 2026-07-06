#!/usr/bin/env bash
set -euo pipefail

ROOT="${CCF_PROJECT_ROOT:-$HOME/ccf-medical-ai}"
cd "$ROOT"

if [[ ! -f .env.runtime ]]; then
  echo "缺少 $ROOT/.env.runtime，请按 .env.example 配置运行环境。" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env.runtime
set +a

exec .venv/bin/python mcp_server/server.py
