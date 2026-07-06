"""复现任务三 NL2SQL/模板查询准确率。

该脚本评估任务三使用的规则优先查询层，不依赖模型随机输出。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.medical_query_engine import ask_medical_db  # noqa: E402


DEFAULT_EVAL_SET = ROOT / "tests" / "task3_nl2sql_eval_set.json"
DEFAULT_DB = ROOT / "data" / "task3_analytics.db"
DEFAULT_JSON_OUT = ROOT / "data" / "task3_nl2sql_eval_report.json"
DEFAULT_MD_OUT = ROOT / "docs" / "TASK3_NL2SQL_EVAL_REPORT.md"


def load_cases(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_case(case: dict[str, Any], db_path: Path) -> dict[str, Any]:
    result = ask_medical_db(case["question"], str(db_path))
    expected_template = case.get("expected_template")
    required_columns = list(case.get("required_columns") or [])
    min_rows = int(case.get("min_rows", 0))
    columns = list(result.get("columns") or [])
    row_count = int(result.get("row_count") or 0)
    error = result.get("error")
    matched_template = result.get("matched_template")
    template_ok = matched_template == expected_template
    execution_ok = not error and bool(result.get("sql"))
    columns_ok = all(column in columns for column in required_columns)
    rows_ok = row_count >= min_rows
    passed = bool(template_ok and execution_ok and columns_ok and rows_ok)
    return {
        "id": case["id"],
        "question": case["question"],
        "expected_template": expected_template,
        "matched_template": matched_template,
        "required_columns": required_columns,
        "columns": columns,
        "min_rows": min_rows,
        "row_count": row_count,
        "template_ok": template_ok,
        "execution_ok": execution_ok,
        "columns_ok": columns_ok,
        "rows_ok": rows_ok,
        "passed": passed,
        "error": error,
        "sql": result.get("sql", ""),
        "sample_rows": (result.get("rows") or [])[:3],
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for item in results if item["passed"])
    template_ok = sum(1 for item in results if item["template_ok"])
    execution_ok = sum(1 for item in results if item["execution_ok"])
    columns_ok = sum(1 for item in results if item["columns_ok"])
    rows_ok = sum(1 for item in results if item["rows_ok"])
    non_empty = sum(1 for item in results if item["row_count"] > 0)
    failures = [item for item in results if not item["passed"]]
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "accuracy": round(passed / total, 4) if total else 0,
        "template_match_rate": round(template_ok / total, 4) if total else 0,
        "execution_success_rate": round(execution_ok / total, 4) if total else 0,
        "column_match_rate": round(columns_ok / total, 4) if total else 0,
        "row_requirement_rate": round(rows_ok / total, 4) if total else 0,
        "non_empty_rate": round(non_empty / total, 4) if total else 0,
        "meets_85_percent": (passed / total) >= 0.85 if total else False,
        "failures": [
            {
                "id": item["id"],
                "question": item["question"],
                "expected_template": item["expected_template"],
                "matched_template": item["matched_template"],
                "row_count": item["row_count"],
                "error": item["error"],
            }
            for item in failures
        ],
    }


def write_markdown(path: Path, db_path: Path, eval_set: Path, summary: dict[str, Any], results: list[dict[str, Any]]) -> None:
    lines = [
        "# 任务三 NL2SQL 指标说明",
        "",
        "## 评估口径",
        "",
        "- 评估对象：任务三自然语言统计查询引擎。",
        "- 评估原因：该路径无模型随机性，可在相同数据库上稳定复现。",
        "- 判定标准：模板命中正确、SQL 只读执行成功、必需列存在、返回行数满足样例要求。",
        "- 说明：指标用于展示当前分析库上的只读统计查询能力。",
        "",
        "## 输入",
        "",
        f"- 数据库：`{db_path}`",
        f"- 评测集：`{eval_set}`",
        f"- 样例数：{summary['total']}",
        "",
        "## 汇总指标",
        "",
        "| 指标 | 数值 |",
        "|---|---:|",
        f"| 综合准确率 | {summary['accuracy'] * 100:.2f}% |",
        f"| 模板命中率 | {summary['template_match_rate'] * 100:.2f}% |",
        f"| SQL 执行成功率 | {summary['execution_success_rate'] * 100:.2f}% |",
        f"| 列匹配率 | {summary['column_match_rate'] * 100:.2f}% |",
        f"| 行数要求满足率 | {summary['row_requirement_rate'] * 100:.2f}% |",
        f"| 非空结果率 | {summary['non_empty_rate'] * 100:.2f}% |",
        f"| 是否达到 85% | {'是' if summary['meets_85_percent'] else '否'} |",
        "",
        "## 逐项结果",
        "",
        "| ID | 问题 | 期望模板 | 命中模板 | 行数 | 结论 |",
        "|---|---|---|---|---:|---|",
    ]
    for item in results:
        status = "通过" if item["passed"] else "失败"
        lines.append(
            "| {id} | {question} | {expected} | {matched} | {rows} | {status} |".format(
                id=item["id"],
                question=str(item["question"]).replace("|", "\\|"),
                expected=item["expected_template"],
                matched=item["matched_template"] or "-",
                rows=item["row_count"],
                status=status,
            )
        )
    if summary["failures"]:
        lines.extend(["", "## 失败样例", ""])
        for failure in summary["failures"]:
            lines.append(
                f"- `{failure['id']}` {failure['question']}：期望 `{failure['expected_template']}`，"
                f"命中 `{failure['matched_template']}`，行数 {failure['row_count']}，错误：{failure['error'] or '-'}"
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--eval-set", type=Path, default=DEFAULT_EVAL_SET)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    args = parser.parse_args()

    cases = load_cases(args.eval_set)
    results = [evaluate_case(case, args.db) for case in cases]
    summary = summarize(results)
    payload = {
        "db_path": str(args.db),
        "eval_set": str(args.eval_set),
        "summary": summary,
        "results": results,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(args.md_out, args.db, args.eval_set, summary, results)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json={args.json_out}")
    print(f"md={args.md_out}")
    if not summary["meets_85_percent"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
