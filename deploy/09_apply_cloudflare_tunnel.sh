#!/usr/bin/env bash
# CCF 部署脚本 09：应用 Cloudflare Tunnel 固定域名配置
#
# 默认只预览，不修改运行态。由于 live cloudflared 配置通常位于
# /home/panyushuo/.cloudflared/config.yml，运行 --apply 前需要确认该动作
# 符合当前服务器操作边界。
set -euo pipefail

ROOT="${CCF_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SOURCE="${CCF_CLOUDFLARED_PROJECT_CONFIG:-$ROOT/cloudflared/ccf-main-config.yml}"
TARGET="${CCF_CLOUDFLARED_CONFIG:-$HOME/.cloudflared/config.yml}"
CONTAINER="${CCF_CLOUDFLARED_CONTAINER:-cf-ccf-main}"
APPLY=0
RESTART=0

usage() {
  cat <<'USAGE'
Usage: bash deploy/09_apply_cloudflare_tunnel.sh [--apply] [--restart]

  作用:
    将仓库中的 cloudflared/ccf-main-config.yml 应用到运行态 Tunnel 配置，
    让 nexent/datamate/demo/mcp 等固定域名指向对应本机端口。

  默认:
    只显示源文件、目标文件和 diff，不写入、不重启。

  选项:
    --apply    备份目标配置后写入新配置
    --restart  写入后重启 cloudflared 容器，默认容器名 cf-ccf-main
USAGE
}

for a in "$@"; do
  case "$a" in
    --apply) APPLY=1 ;;
    --restart) RESTART=1 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $a"; usage; exit 1 ;;
  esac
done

[ -f "$SOURCE" ] || { echo "错误: 源配置不存在: $SOURCE"; exit 1; }

echo "=== [09] Cloudflare Tunnel 固定域名配置 ==="
echo "源配置: $SOURCE"
echo "目标配置: $TARGET"
echo "容器名: $CONTAINER"
echo ""

if [ -f "$TARGET" ]; then
  echo "--- 当前差异 ---"
  diff -u "$TARGET" "$SOURCE" || true
else
  echo "目标配置不存在，将创建: $TARGET"
fi

if [ "$APPLY" = "0" ]; then
  echo ""
  echo "预览完成，未修改运行态。确认后执行:"
  echo "  bash deploy/09_apply_cloudflare_tunnel.sh --apply --restart"
  exit 0
fi

mkdir -p "$(dirname "$TARGET")"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
if [ -f "$TARGET" ]; then
  BACKUP="$TARGET.bak.$STAMP"
  cp "$TARGET" "$BACKUP"
  echo "已备份: $BACKUP"
fi

cp "$SOURCE" "$TARGET"
echo "已写入: $TARGET"

if [ "$RESTART" = "1" ]; then
  if docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
    docker restart "$CONTAINER"
    echo "已重启容器: $CONTAINER"
  else
    echo "未找到运行中的容器: $CONTAINER"
  fi
else
  echo "未重启容器。需要生效时执行:"
  echo "  docker restart $CONTAINER"
fi
