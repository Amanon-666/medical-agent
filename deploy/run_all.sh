#!/usr/bin/env bash
# CCF 一键部署：按顺序执行 00-08
# 用法: bash deploy/run_all.sh [--from N] [--to N] [--dry-run]
set -euo pipefail

ROOT="${CCF_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
START=0; END=8; DRY=""

usage() {
  cat <<'USAGE'
Usage: bash deploy/run_all.sh [--from N] [--to N] [--dry-run]

  按顺序执行 deploy/00_check_prereqs.sh 到 deploy/08_verify.sh
  --from N  从第 N 步开始（默认 0）
  --to N    到第 N 步停止（默认 8）
  --dry-run 仅打印每步命令，不执行
USAGE
}
while [ "$#" -gt 0 ]; do
  case "$1" in
    --from)
      START="${2:?--from requires a step number}"
      shift 2
      ;;
    --to)
      END="${2:?--to requires a step number}"
      shift 2
      ;;
    --dry-run)
      DRY="1"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

echo "============================================"
echo "  CCF 医疗AI 项目一键部署"
echo "  步骤 $START -> $END"
echo "============================================"

SCRIPTS=(
  "00_check_prereqs.sh"
  "01_setup_python.sh"
  "02_deploy_operators.sh"
  "03_register_operators.sh"
  "04_build_databases.sh"
  "05_start_mcp.sh"
  "06_register_nexent.sh"
  "07_start_demo.sh"
  "08_verify.sh"
)

for i in $(seq $START $END); do
  s="${SCRIPTS[$i]}"
  echo ""
  echo ">>> 步骤 $i: bash deploy/$s"
  if [ -n "$DRY" ]; then
    echo "    [DRY-RUN 跳过]"
  else
    bash "$ROOT/deploy/$s" || { echo "步骤 $i 失败，部署中断。"; exit 1; }
  fi
done

echo ""
echo "============================================"
echo "  部署完成！"
echo ""
echo "  验收入口:"
if [ -f "$ROOT/.env.runtime" ]; then
  set -a
  source "$ROOT/.env.runtime"
  set +a
fi
echo "    Nexent 对话:  ${CCF_NEXENT_FRONTEND_URL:-https://nexent.${CCF_PUBLIC_DOMAIN:-mashiro.xin}/}"
echo "    DataMate UI:  ${CCF_DATAMATE_FRONTEND_URL:-https://datamate.${CCF_PUBLIC_DOMAIN:-mashiro.xin}/}"
echo "    可视化平台:    ${CCF_TASK3_DEMO_URL:-https://demo.${CCF_PUBLIC_DOMAIN:-mashiro.xin}/}"
echo "    本机可视化健康检查: http://127.0.0.1:8765"
echo "============================================"
