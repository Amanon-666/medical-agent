#!/usr/bin/env bash
# CCF 部署脚本 00：环境检查
# 检查 DataMate/Nexent 可达性、Python 版本、.env.runtime 是否存在
set -euo pipefail

ROOT="${CCF_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
DATAMATE="${CCF_DATAMATE_BASE:-http://127.0.0.1:18000}"
NEXENT="${CCF_NEXENT_CONFIG_BASE:-http://127.0.0.1:5010}"
PYTHON="${CCF_PYTHON:-python3}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
pass=0; fail=0

check() { local label="$1"; shift; if "$@" >/dev/null 2>&1; then echo -e "  ${GREEN}[PASS]${NC} $label"; pass=$((pass+1)); else echo -e "  ${RED}[FAIL]${NC} $label"; fail=$((fail+1)); fi; }
warn() { echo -e "  ${YELLOW}[WARN]${NC} $1"; }

usage() {
  cat <<'USAGE'
Usage: bash deploy/00_check_prereqs.sh

  检查项目运行所需的前置条件：
  - .env.runtime 配置文件存在
  - Python >= 3.10
  - screen、docker 系统命令可用
  - DataMate (18000) 和 Nexent (5010) API 可达

  环境变量覆盖:
    CCF_DATAMATE_BASE     DataMate API 地址（默认 http://127.0.0.1:18000）
    CCF_NEXENT_CONFIG_BASE Nexent Config API 地址（默认 http://127.0.0.1:5010）
USAGE
}
[[ "${1:-}" == "--help" || "${1:-}" == "-h" ]] && { usage; exit 0; }

echo "=== CCF 环境检查 ==="
echo ""

# 1. .env.runtime
echo "[1/5] 配置文件..."
if [ -f "$ROOT/.env.runtime" ]; then
  check ".env.runtime 存在" true
  set -a; source "$ROOT/.env.runtime"; set +a
else
  warn ".env.runtime 不存在，请从 .env.example 复制并填写"
  echo "  cp .env.example .env.runtime"
  fail=$((fail+1))
fi

# 2. Python
echo "[2/5] Python 环境..."
PY_VER=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0")
PY_MAJOR="${PY_VER%%.*}"; PY_MINOR="${PY_VER#*.}"
if [ "$PY_MAJOR" -gt 3 ] 2>/dev/null || { [ "$PY_MAJOR" -eq 3 ] 2>/dev/null && [ "$PY_MINOR" -ge 10 ] 2>/dev/null; }; then
  check "Python $PY_VER >= 3.10" true
else
  warn "Python 版本: $PY_VER (需要 >= 3.10)"
  fail=$((fail+1))
fi
[ -d "$ROOT/.venv" ] && check ".venv/ 已存在" true || warn ".venv/ 不存在，运行 deploy/01_setup_python.sh"

# 3. 系统命令
echo "[3/5] 系统命令..."
command -v screen >/dev/null 2>&1 && check "screen 已安装" true || { warn "screen 未安装（MCP 和 Demo 需要后台运行）"; fail=$((fail+1)); }
command -v docker >/dev/null 2>&1 && check "docker 已安装" true || { warn "docker 未安装"; fail=$((fail+1)); }

# 4. DataMate
echo "[4/5] DataMate 连接..."
DM_URL="${CCF_DATAMATE_BASE:-$DATAMATE}"
DM_CODE=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 5 "$DM_URL" 2>/dev/null || echo "000")
if [ "$DM_CODE" != "000" ]; then check "DataMate $DM_URL (HTTP $DM_CODE)" true
else warn "DataMate $DM_URL 不可达，请确认服务已启动"; fail=$((fail+1)); fi

# 5. Nexent
echo "[5/5] Nexent 连接..."
NX_URL="${CCF_NEXENT_CONFIG_BASE:-$NEXENT}"
NX_CODE=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 5 "$NX_URL/user/signin" -X POST -H 'Content-Type: application/json' -d '{"email":"test","password":"test"}' 2>/dev/null || echo "000")
if [ "$NX_CODE" != "000" ]; then check "Nexent $NX_URL (HTTP $NX_CODE)" true
else warn "Nexent $NX_URL 不可达，请确认服务已启动"; fail=$((fail+1)); fi

echo ""
echo "=== 结果: $pass 通过, $fail 失败 ==="
[ "$fail" -eq 0 ] && echo "环境就绪，可以继续部署。" || echo "请先修复上述问题。"
exit $fail
