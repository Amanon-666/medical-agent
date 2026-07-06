#!/usr/bin/env bash
# Verify the CCF medical AI deployment.
set -euo pipefail

ROOT="${CCF_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
QUICK=0

usage() {
  cat <<'USAGE'
Usage: bash deploy/08_verify.sh [--quick]

Checks core services, database artifacts, and published Nexent agents.
The report is written to deploy/verification_report.txt.
USAGE
}

for arg in "$@"; do
  case "$arg" in
    --quick) QUICK=1 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $arg"; usage; exit 2 ;;
  esac
done

cd "$ROOT"
[ -f .env.runtime ] && { set -a; source .env.runtime; set +a; }

PY="${CCF_PYTHON:-$ROOT/.venv/bin/python}"
REPORT="$ROOT/deploy/verification_report.txt"

echo "=== CCF Medical AI Deployment Verification ===" | tee "$REPORT"

pass=0
fail=0

check() {
  local label="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "  [PASS] $label" | tee -a "$REPORT"
    pass=$((pass + 1))
  else
    echo "  [FAIL] $label" | tee -a "$REPORT"
    fail=$((fail + 1))
  fi
}

echo "--- Services ---" | tee -a "$REPORT"
check "DataMate API" curl -s -o /dev/null --connect-timeout 3 "${CCF_DATAMATE_BASE:-http://127.0.0.1:18000}"
check "Nexent API" curl -s -o /dev/null --connect-timeout 3 "${CCF_NEXENT_CONFIG_BASE:-http://127.0.0.1:5010}/health"
check "MCP server" curl -s -o /dev/null --connect-timeout 3 "http://127.0.0.1:8900/mcp"
check "Visualization platform" curl -s -o /dev/null --connect-timeout 3 "http://127.0.0.1:8765/"

if [ "${CCF_VERIFY_PUBLIC_URLS:-0}" = "1" ]; then
  check "Public visualization URL" curl -s -o /dev/null --connect-timeout 8 "${CCF_TASK3_DEMO_URL:-https://demo.${CCF_PUBLIC_DOMAIN:-mashiro.xin}/}"
fi

echo "--- Data Artifacts ---" | tee -a "$REPORT"
KG_DB="${CCF_TASK2_KG_DB:-$ROOT/data/task2_medical_kg.db}"
ANALYTICS_DB="${CCF_TASK3_ANALYTICS_DB:-$ROOT/data/task3_analytics.db}"
check "Task 2 knowledge graph database" test -f "$KG_DB"
check "Task 3 analytics database" test -f "$ANALYTICS_DB"

if [ "$QUICK" = "0" ] && [ -x "$PY" ]; then
  echo "--- Database Rows ---" | tee -a "$REPORT"
  "$PY" - <<'PY' "$KG_DB" "$ANALYTICS_DB" | tee -a "$REPORT"
import sqlite3
import sys
from pathlib import Path

kg, analytics = map(Path, sys.argv[1:3])
checks = [
    (kg, "data_sources"),
    (kg, "medical_triples"),
    (analytics, "diseases"),
]
for db, table in checks:
    try:
        with sqlite3.connect(db) as conn:
            count = conn.execute(f"select count(*) from {table}").fetchone()[0]
        print(f"  {db.name}:{table} rows={count}")
    except Exception as exc:
        print(f"  {db.name}:{table} unavailable: {exc}")
PY
fi

if [ "$QUICK" = "0" ] && [ -n "${CCF_NEXENT_EMAIL:-}" ] && [ -n "${CCF_NEXENT_PASSWORD:-}" ] && [ -x "$PY" ]; then
  echo "--- Nexent Agents ---" | tee -a "$REPORT"
  TOKEN=$(curl -s -X POST "${CCF_NEXENT_CONFIG_BASE:-http://127.0.0.1:5010}/user/signin" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"${CCF_NEXENT_EMAIL}\",\"password\":\"${CCF_NEXENT_PASSWORD}\"}" |
    "$PY" -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('session',{}).get('access_token',''))" 2>/dev/null || echo "")
  if [ -n "$TOKEN" ]; then
    AGENTS=$(curl -s "${CCF_NEXENT_CONFIG_BASE:-http://127.0.0.1:5010}/agent/list" -H "Authorization: Bearer $TOKEN")
    PUB_COUNT=$(echo "$AGENTS" | "$PY" -c "import sys,json; print(sum(1 for a in json.load(sys.stdin) if a.get('is_published')))" 2>/dev/null || echo "0")
    [ "$PUB_COUNT" -ge 3 ] && check "At least three published agents" true || check "At least three published agents (current: $PUB_COUNT)" false
  else
    echo "  Nexent login skipped or failed" | tee -a "$REPORT"
  fi
fi

echo "" | tee -a "$REPORT"
echo "=== Result: $pass passed, $fail failed ===" | tee -a "$REPORT"
echo "Report: $REPORT"
exit "$fail"
