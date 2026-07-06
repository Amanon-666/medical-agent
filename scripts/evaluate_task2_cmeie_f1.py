#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""复现任务二 CMeIE 关系抽取指标。"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


def discover_dataset_root(explicit_root: str | None = None) -> Path:
    if explicit_root:
        return Path(explicit_root).expanduser().resolve()
    env_root = os.environ.get("CCF_EVAL_DATA_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    local_root = Path(__file__).resolve().parents[1] / "data" / "external_benchmarks"
    if (local_root / "CBLUE_data").exists():
        return local_root.resolve()
    raise FileNotFoundError("请通过 --root 或 CCF_EVAL_DATA_ROOT 指定包含 CBLUE_data 的评测数据目录。")


def load_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if limit is not None and len(records) >= limit:
                break
            if not line.strip():
                continue
            records.append(json.loads(line))
    return records


def object_value(value: Any) -> str:
    if isinstance(value, dict):
        if "@value" in value:
            return str(value.get("@value") or "").strip()
        for item in value.values():
            text = object_value(item)
            if text:
                return text
        return ""
    return str(value or "").strip()


def spo_set(records: list[dict[str, Any]]) -> set[tuple[str, str, str, str]]:
    items: set[tuple[str, str, str, str]] = set()
    for record in records:
        text = str(record.get("text") or "")
        for spo in record.get("spo_list") or []:
            subject = str(spo.get("subject") or "").strip()
            predicate = str(spo.get("predicate") or "").strip()
            obj = object_value(spo.get("object"))
            if subject and predicate and obj:
                items.add((text, subject, predicate, obj))
    return items


def prf(gold: set[Any], pred: set[Any]) -> dict[str, float | int]:
    true_positive = len(gold & pred)
    predicted = len(pred)
    total = len(gold)
    precision = true_positive / predicted if predicted else 0.0
    recall = true_positive / total if total else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "gold": total,
        "predicted": predicted,
        "true_positive": true_positive,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
    }


def per_predicate_metrics(
    gold: set[tuple[str, str, str, str]],
    pred: set[tuple[str, str, str, str]],
) -> dict[str, dict[str, float | int]]:
    predicates = sorted({item[2] for item in gold | pred})
    return {
        predicate: prf(
            {item for item in gold if item[2] == predicate},
            {item for item in pred if item[2] == predicate},
        )
        for predicate in predicates
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None)
    parser.add_argument("--gold", default=None)
    parser.add_argument("--prediction", default=None)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--out", default="data/task2_cmeie_eval_report.json")
    args = parser.parse_args()

    root = discover_dataset_root(args.root)
    gold_path = (
        Path(args.gold)
        if args.gold
        else root / "CBLUE_data" / "CMeIE" / "CMeIE_dev.jsonl"
    )
    gold_records = load_jsonl(gold_path, args.limit)

    if args.prediction:
        pred_records = load_jsonl(Path(args.prediction), args.limit)
        mode = "prediction_file"
    elif args.self_check:
        pred_records = gold_records
        mode = "gold_self_check"
    else:
        raise SystemExit("请提供 --prediction，或使用 --self-check 执行金标自检。")

    gold_items = spo_set(gold_records)
    pred_items = spo_set(pred_records)
    report = {
        "task": "CMeIE",
        "mode": mode,
        "gold_path": str(gold_path),
        "prediction_path": args.prediction,
        "sample_count": len(gold_records),
        "diagnostic_only": mode == "gold_self_check",
        "metrics": prf(gold_items, pred_items),
        "per_predicate": per_predicate_metrics(gold_items, pred_items),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
