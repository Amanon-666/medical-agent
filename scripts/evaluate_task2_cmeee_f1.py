#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""复现任务二 CMeEE 实体识别基线指标。

支持 CBLUE CMeEE 金标文件、预测文件，以及 QASystemOnMedicalKG 词典基线。
外部数据集不随工程目录分发时，请通过 --root 或 CCF_EVAL_DATA_ROOT 指定路径。
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


DICT_TYPE_MAP = {
    "disease.txt": "dis",
    "symptom.txt": "sym",
    "drug.txt": "dru",
    "check.txt": "ite",
    "department.txt": "dep",
}


def discover_dataset_root(explicit_root: str | None = None) -> Path:
    if explicit_root:
        return Path(explicit_root).expanduser().resolve()
    env_root = os.environ.get("CCF_EVAL_DATA_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    local_root = Path(__file__).resolve().parents[1] / "data" / "external_benchmarks"
    if (local_root / "CBLUE_data").exists() and (local_root / "QASystemOnMedicalKG").exists():
        return local_root.resolve()
    raise FileNotFoundError("请通过 --root 或 CCF_EVAL_DATA_ROOT 指定包含 CBLUE_data 与 QASystemOnMedicalKG 的评测数据目录。")


def load_json(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(data, list):
        raise ValueError(f"CMeEE file must be a JSON list: {path}")
    return data


def normalize_entity(text: str, entity: dict[str, Any]) -> tuple[str, int, int, str, str] | None:
    try:
        start = int(entity["start_idx"])
        end = int(entity["end_idx"])
        entity_type = str(entity["type"])
    except (KeyError, TypeError, ValueError):
        return None
    value = str(entity.get("entity") or text[start : end + 1])
    return text, start, end, entity_type, value


def entity_set(records: list[dict[str, Any]]) -> set[tuple[str, int, int, str, str]]:
    items: set[tuple[str, int, int, str, str]] = set()
    for record in records:
        text = str(record.get("text") or "")
        for entity in record.get("entities") or []:
            normalized = normalize_entity(text, entity)
            if normalized:
                items.add(normalized)
    return items


def load_dictionary_terms(dict_dir: Path, max_terms_per_type: int) -> dict[str, list[str]]:
    terms_by_type: dict[str, list[str]] = {}
    for file_name, entity_type in DICT_TYPE_MAP.items():
        path = dict_dir / file_name
        if not path.exists():
            continue
        terms: list[str] = []
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                term = line.strip()
                if len(term) >= 2:
                    terms.append(term)
                if len(terms) >= max_terms_per_type:
                    break
        terms_by_type[entity_type] = sorted(set(terms), key=len, reverse=True)
    return terms_by_type


def dictionary_predict(
    records: list[dict[str, Any]],
    dict_dir: Path,
    max_terms_per_type: int = 5000,
) -> list[dict[str, Any]]:
    terms_by_type = load_dictionary_terms(dict_dir, max_terms_per_type)
    predictions: list[dict[str, Any]] = []
    for record in records:
        text = str(record.get("text") or "")
        entities: list[dict[str, Any]] = []
        occupied: set[tuple[int, int, str]] = set()
        for entity_type, terms in terms_by_type.items():
            for term in terms:
                start = text.find(term)
                while start != -1:
                    end = start + len(term) - 1
                    key = (start, end, entity_type)
                    if key not in occupied:
                        entities.append(
                            {
                                "start_idx": start,
                                "end_idx": end,
                                "type": entity_type,
                                "entity": term,
                            }
                        )
                        occupied.add(key)
                    start = text.find(term, start + 1)
        predictions.append({"text": text, "entities": entities})
    return predictions


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


def per_type_metrics(
    gold: set[tuple[str, int, int, str, str]],
    pred: set[tuple[str, int, int, str, str]],
) -> dict[str, dict[str, float | int]]:
    types = sorted({item[3] for item in gold | pred})
    return {
        entity_type: prf(
            {item for item in gold if item[3] == entity_type},
            {item for item in pred if item[3] == entity_type},
        )
        for entity_type in types
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None)
    parser.add_argument("--gold", default=None)
    parser.add_argument("--prediction", default=None)
    parser.add_argument("--dictionary-root", default=None)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--max-terms-per-type", type=int, default=5000)
    parser.add_argument("--out", default="data/task2_cmeee_eval_report.json")
    args = parser.parse_args()

    root = discover_dataset_root(args.root)
    gold_path = (
        Path(args.gold)
        if args.gold
        else root / "CBLUE_data" / "CMeEE-V2" / "CMeEE-V2_dev.json"
    )
    gold_records = load_json(gold_path)
    if args.limit:
        gold_records = gold_records[: args.limit]

    if args.prediction:
        pred_records = load_json(Path(args.prediction))
        if args.limit:
            pred_records = pred_records[: args.limit]
        mode = "prediction_file"
    else:
        dict_dir = (
            Path(args.dictionary_root)
            if args.dictionary_root
            else root / "QASystemOnMedicalKG" / "dict"
        )
        pred_records = dictionary_predict(
            gold_records,
            dict_dir,
            max_terms_per_type=args.max_terms_per_type,
        )
        mode = "dictionary_baseline"

    gold_items = entity_set(gold_records)
    pred_items = entity_set(pred_records)
    report = {
        "task": "CMeEE",
        "mode": mode,
        "gold_path": str(gold_path),
        "prediction_path": args.prediction,
        "sample_count": len(gold_records),
        "metrics": prf(gold_items, pred_items),
        "per_type": per_type_metrics(gold_items, pred_items),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
