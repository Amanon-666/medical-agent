"""Reproducible execution evaluation for the Task 3 NL2SQL path."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.llm_client import LLMClient
from core.nl2sql import execute_sql, generate_sql
from task3.sql_safety import execute_readonly


def validate_database(db_path: Path) -> None:
    manifest_path = ROOT / "evaluation" / "task3" / "benchmark_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    expected = manifest["database"]
    if not db_path.exists():
        raise RuntimeError(f"评测数据库不存在：{db_path}")
    actual_size = db_path.stat().st_size
    digest = hashlib.sha256(db_path.read_bytes()).hexdigest()
    if actual_size != expected["size_bytes"] or digest != expected["sha256"]:
        raise RuntimeError(
            "评测数据库版本不匹配。"
            f"期望 SHA-256={expected['sha256']}、大小={expected['size_bytes']}；"
            f"实际 SHA-256={digest}、大小={actual_size}。"
            "请使用 benchmark_manifest.json 指定的数据库版本。"
        )

def normalize_scalar(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 8)
    return value


def normalize_rows(rows: list[list[Any]]) -> list[tuple[Any, ...]]:
    return [tuple(normalize_scalar(value) for value in row) for row in rows]


def compare(predicted: list[list[Any]], gold: list[list[Any]]) -> dict[str, bool]:
    pred = normalize_rows(predicted)
    expected = normalize_rows(gold)
    return {
        "ordered_exact": pred == expected,
        "multiset_exact": Counter(pred) == Counter(expected),
        "set_exact": set(pred) == set(expected),
    }


def make_llm() -> LLMClient | None:
    api_key = os.environ.get("CCF_LLM_API_KEY")
    key_file = os.environ.get("CCF_LLM_API_KEY_FILE")
    if not api_key and key_file and Path(key_file).exists():
        api_key = Path(key_file).read_text(encoding="utf-8").strip()
    if not api_key:
        return None
    return LLMClient(
        base_url=os.environ.get("CCF_LLM_BASE_URL", "https://api.deepseek.com/v1/chat/completions"),
        model=os.environ.get("CCF_LLM_MODEL", "deepseek-chat"),
        api_key=api_key,
        timeout=int(os.environ.get("CCF_TASK3_LLM_TIMEOUT", "90")),
    )


def evaluate_case(case: dict[str, Any], db_path: Path, engine: str, llm: LLMClient | None) -> dict[str, Any]:
    started = time.perf_counter()
    error = None
    sql = ""
    rows: list[list[Any]] = []
    try:
        if engine == "gold":
            sql = case["gold_sql"]
        elif engine == "nl2sql":
            if llm is None:
                raise RuntimeError("NL2SQL model credentials are not configured")
            sql = generate_sql(case["question"], llm)
        else:
            from task3.semantic_layer import semantic_plan

            conn = sqlite3.connect(db_path)
            try:
                plan = semantic_plan(conn, case["question"])
            finally:
                conn.close()
            if not plan.queries:
                raise RuntimeError("semantic layer did not produce a query")
            sql = plan.queries[0].sql
        if engine == "semantic":
            result = execute_readonly(db_path, sql, max_rows=10_000)
            rows = result["rows"]
            error = result.get("error")
        else:
            result = execute_sql(sql, str(db_path))
            rows = result["rows"]
            error = result.get("error")
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    metrics = compare(rows, case["gold_result"]["rows"])
    return {
        "id": case["id"],
        "question": case["question"],
        "query_type": case["query_type"],
        "difficulty": case["difficulty"],
        "predicted_sql": sql,
        "gold_sql": case["gold_sql"],
        "predicted_row_count": len(rows),
        "gold_row_count": len(case["gold_result"]["rows"]),
        **metrics,
        "error": error,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--engine", choices=("nl2sql", "semantic", "gold"), default="nl2sql")
    parser.add_argument("--database", type=Path, default=Path("data/task3_analytics.db"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    benchmark = ROOT / "evaluation" / "task3" / f"nl2sql_{args.split}.jsonl"
    cases = [json.loads(line) for line in benchmark.read_text(encoding="utf-8").splitlines() if line]
    llm = make_llm() if args.engine == "nl2sql" else None
    db_path = args.database if args.database.is_absolute() else ROOT / args.database
    validate_database(db_path)
    results = [evaluate_case(case, db_path, args.engine, llm) for case in cases]

    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in results:
        by_type[item["query_type"]].append(item)
    summary = {
        "split": args.split,
        "engine": args.engine,
        "total": len(results),
        "ordered_exact": sum(item["ordered_exact"] for item in results),
        "multiset_exact": sum(item["multiset_exact"] for item in results),
        "set_exact": sum(item["set_exact"] for item in results),
        "errors": sum(bool(item["error"]) for item in results),
        "accuracy": round(sum(item["multiset_exact"] for item in results) / len(results), 4),
        "by_type": {
            key: {
                "total": len(items),
                "multiset_exact": sum(item["multiset_exact"] for item in items),
            }
            for key, items in sorted(by_type.items())
        },
    }
    output = args.output or ROOT / "evaluation" / "task3" / f"results_{args.engine}_{args.split}.json"
    output.write_text(json.dumps({"summary": summary, "cases": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({**summary, "output": str(output)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
