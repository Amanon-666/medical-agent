#!/usr/bin/env bash
# Start the official task-three medical visualization platform.
set -euo pipefail

ROOT="${CCF_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ACTION="start"

usage() {
  cat <<'USAGE'
Usage: bash deploy/07_start_demo.sh [--stop|--status|--restart]

Starts the official visualization platform:
  demo/task3_interactive_demo/server.py on port 8765
USAGE
}

for arg in "$@"; do
  case "$arg" in
    --stop) ACTION="stop" ;;
    --status) ACTION="status" ;;
    --restart) ACTION="restart" ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $arg"; usage; exit 2 ;;
  esac
done

echo "=== [07/08] Medical data visualization platform ==="

[ -f "$ROOT/.env.runtime" ] || { echo "ERROR: .env.runtime is required"; exit 1; }
set -a
source "$ROOT/.env.runtime"
set +a

PUBLIC_DEMO_URL="${CCF_TASK3_DEMO_URL:-https://demo.${CCF_PUBLIC_DOMAIN:-mashiro.xin}/}"

stop_svc() {
  local name="$1" pattern="$2"
  local pids
  pids="$(pgrep -f "$pattern" 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    for pid in $pids; do
      [ "$pid" = "$$" ] && continue
      [ "$pid" = "${PPID:-}" ] && continue
      kill "$pid" >/dev/null 2>&1 || true
    done
    echo "Stopped $name"
  else
    echo "$name is not running"
  fi
  screen -S "$name" -X quit >/dev/null 2>&1 || true
}

status_svc() {
  local name="$1" pattern="$2" port="$3"
  if pgrep -f "$pattern" >/dev/null 2>&1; then
    printf '  %s: running (port %s) ' "$name" "$port"
    curl -s -o /dev/null -w "HTTP %{http_code}" "http://127.0.0.1:$port" 2>/dev/null && echo "" || echo "(no HTTP response)"
  else
    echo "  $name: stopped"
  fi
}

if [ "$ACTION" = "stop" ]; then
  stop_svc "task3demo" "task3_interactive_demo/server.py"
  exit 0
fi

if [ "$ACTION" = "restart" ]; then
  stop_svc "task3demo" "task3_interactive_demo/server.py"
fi

if [ "$ACTION" = "status" ]; then
  status_svc "visualization platform" "task3_interactive_demo/server.py" "8765"
  echo "  public URL: $PUBLIC_DEMO_URL"
  exit 0
fi

cd "$ROOT"

if pgrep -f "task3_interactive_demo/server.py" >/dev/null 2>&1; then
  echo "Visualization platform is already running"
else
  echo "Starting visualization platform on port 8765..."
  screen -dmS task3demo bash -c \
    "set -a && source '$ROOT/.env.runtime' && set +a && cd '$ROOT' && .venv/bin/python demo/task3_interactive_demo/server.py --host 0.0.0.0 --port 8765 > task3_demo.log 2>&1"
  sleep 2
  curl -s -o /dev/null -w "  HTTP %{http_code}" http://127.0.0.1:8765 2>/dev/null && echo " OK" || echo " startup check failed"
fi

echo "Official demo URL: $PUBLIC_DEMO_URL"
echo "Local health check: http://127.0.0.1:8765"
