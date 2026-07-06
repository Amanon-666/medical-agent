#!/usr/bin/env bash
# CCF 部署脚本 10：为 Cloudflare Tunnel 注册 public hostname DNS 路由
#
# 默认只预览命令；--apply 后执行 cloudflared tunnel route dns。
set -euo pipefail

TUNNEL="${CCF_CLOUDFLARED_TUNNEL:-ccf-main}"
CONTAINER="${CCF_CLOUDFLARED_CONTAINER:-cf-ccf-main}"
APPLY=0
OVERWRITE=0

HOSTNAMES=(
  "demo.mashiro.xin"
  "datamate-api.mashiro.xin"
  "nexent-api.mashiro.xin"
  "nexent-runtime.mashiro.xin"
)

usage() {
  cat <<'USAGE'
Usage: bash deploy/10_route_cloudflare_dns.sh [--apply] [--overwrite-dns]

  作用:
    为命名 Tunnel 注册 public hostname DNS 路由，让 Cloudflare 能把
    demo/datamate-api/nexent-api/nexent-runtime 子域名送入同一个 tunnel。

  默认:
    只打印将执行的 cloudflared 命令。

  选项:
    --apply          实际执行 DNS 路由注册
    --overwrite-dns  覆盖同名旧 DNS 记录
USAGE
}

for a in "$@"; do
  case "$a" in
    --apply) APPLY=1 ;;
    --overwrite-dns) OVERWRITE=1 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $a"; usage; exit 1 ;;
  esac
done

echo "=== [10] Cloudflare Tunnel DNS 路由 ==="
echo "Tunnel: $TUNNEL"
echo "Container: $CONTAINER"

for hostname in "${HOSTNAMES[@]}"; do
  cmd=(docker exec "$CONTAINER" cloudflared tunnel route dns)
  if [ "$OVERWRITE" = "1" ]; then
    cmd+=(--overwrite-dns)
  fi
  cmd+=("$TUNNEL" "$hostname")
  echo "+ ${cmd[*]}"
  if [ "$APPLY" = "1" ]; then
    "${cmd[@]}"
  fi
done

if [ "$APPLY" = "0" ]; then
  echo ""
  echo "预览完成，未修改 Cloudflare DNS。确认后执行:"
  echo "  bash deploy/10_route_cloudflare_dns.sh --apply --overwrite-dns"
fi
