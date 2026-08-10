#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_ROOT="$PROJECT_ROOT/backups/task2_llm_guardrails_$(date +%Y%m%d_%H%M%S)"

mkdir -p "$BACKUP_ROOT"
cp -p \
  "$PROJECT_ROOT/core/medical_extraction_service.py" \
  "$PROJECT_ROOT/core/medical_extraction_validation.py" \
  "$PROJECT_ROOT/mcp_server/kg/persistence.py" \
  "$BACKUP_ROOT/"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if [ -x "$PROJECT_ROOT/.venv/bin/python" ]; then
  PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
fi

"$PYTHON_BIN" "$PROJECT_ROOT/deploy/runtime_patches/apply_task2_llm_guardrails.py" "$PROJECT_ROOT"
"$PYTHON_BIN" -m py_compile \
  "$PROJECT_ROOT/core/medical_extraction_service.py" \
  "$PROJECT_ROOT/core/medical_extraction_validation.py" \
  "$PROJECT_ROOT/mcp_server/kg/persistence.py"
echo "Task 2 LLM guardrails applied; backup: $BACKUP_ROOT"
