#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""构建任务二离线词典、分组可靠性配置并生成验证报告。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


CMEIE_TYPE_MAP = {
    "疾病": "dis",
    "症状": "sym",
    "药物": "dru",
    "检查": "ite",
    "手术治疗": "pro",
    "其他治疗": "pro",
    "部位": "bod",
}


_HTML_MARKUP_RE = re.compile(r"</?[A-Za-z][^>]*>", re.IGNORECASE)


def is_clean_term(term: str) -> bool:
    """过滤训练数据中残留的 HTML 标签词条。"""
    return bool(term) and not _HTML_MARKUP_RE.search(term)


def load_json(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"文件必须是 JSON 数组: {path}")
    return data


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def nested_value(value: Any) -> str:
    if isinstance(value, dict):
        if "@value" in value:
            return str(value.get("@value") or "").strip()
        for item in value.values():
            text = nested_value(item)
            if text:
                return text
        return ""
    return str(value or "").strip()


def build_assets(
    cmeee_train: list[dict[str, Any]],
    cmeie_train: list[dict[str, Any]],
    asset_dir: Path,
) -> None:
    terms: dict[str, Counter[str]] = defaultdict(Counter)
    cmeee_term_frequency: Counter[str] = Counter()
    cmeie_term_frequency: Counter[str] = Counter()
    pairs: dict[str, Counter[str]] = defaultdict(Counter)

    for record in cmeee_train:
        for entity in record.get("entities") or []:
            term = str(entity.get("entity") or "").strip()
            entity_type = str(entity.get("type") or "").strip()
            if 2 <= len(term) <= 32 and entity_type:
                terms[term][entity_type] += 1
                cmeee_term_frequency[term] += 1

    for record in cmeie_train:
        for spo in record.get("spo_list") or []:
            subject = str(spo.get("subject") or "").strip()
            obj = nested_value(spo.get("object"))
            predicate = str(spo.get("predicate") or "").strip()
            subject_type = CMEIE_TYPE_MAP.get(str(spo.get("subject_type") or ""))
            raw_object_type = spo.get("object_type")
            if isinstance(raw_object_type, dict):
                raw_object_type = raw_object_type.get("@value")
            object_type = CMEIE_TYPE_MAP.get(str(raw_object_type or ""))
            if subject and subject_type and 2 <= len(subject) <= 32:
                terms[subject][subject_type] += 1
                cmeie_term_frequency[subject] += 1
            if obj and object_type and 2 <= len(obj) <= 32:
                terms[obj][object_type] += 1
                cmeie_term_frequency[obj] += 1
            if subject and obj and predicate:
                pairs[f"{subject}\u0001{obj}"][predicate] += 1

    asset_dir.mkdir(parents=True, exist_ok=True)
    term_occurrences: Counter[str] = Counter()
    term_index: dict[str, list[str]] = defaultdict(list)
    for term in cmeee_term_frequency:
        term_index[term[0]].append(term)
    for record in cmeee_train:
        text = str(record.get("text") or "")
        for first_char in set(text):
            for term in term_index.get(first_char, []):
                term_occurrences[term] += text.count(term)
    selected_terms = {
        key: value
        for key, value in terms.items()
        if is_clean_term(key)
        if cmeee_term_frequency[key] >= 1
        and cmeee_term_frequency[key] / max(1, term_occurrences[key]) >= 0.5
    }
    relation_terms = {
        key: value
        for key, value in terms.items()
        if is_clean_term(key)
        if cmeie_term_frequency[key] >= 2
    }
    lexicon_payload = {
        "schema_version": 1,
        "source": ["CBLUE CMeEE-V2 train", "CBLUE CMeIE train"],
        "term_count": len(selected_terms),
        "terms": {key: dict(value) for key, value in sorted(selected_terms.items())},
    }
    pair_payload = {
        "schema_version": 1,
        "source": ["CBLUE CMeIE train"],
        "pair_count": sum(1 for value in pairs.values() if sum(value.values()) >= 2),
        "pairs": {
            key: dict(value)
            for key, value in sorted(pairs.items())
            if sum(value.values()) >= 2
        },
        "term_count": len(relation_terms),
        "terms": {key: dict(value) for key, value in sorted(relation_terms.items())},
    }
    (asset_dir / "entity_lexicon.json").write_text(
        json.dumps(lexicon_payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    (asset_dir / "relation_pairs.json").write_text(
        json.dumps(pair_payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def prf(gold: set[Any], predicted: set[Any]) -> dict[str, float | int]:
    true_positive = len(gold & predicted)
    precision = true_positive / len(predicted) if predicted else 0.0
    recall = true_positive / len(gold) if gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "gold": len(gold),
        "predicted": len(predicted),
        "true_positive": true_positive,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
    }


def entity_gold(record: dict[str, Any]) -> set[tuple[int, int, str, str]]:
    # CMeEE 的 end_idx 是开区间；项目内部 Entity 使用闭区间。
    return {
        (
            int(item["start_idx"]),
            int(item["end_idx"]),
            str(item["type"]),
            str(item.get("entity") or ""),
        )
        for item in record.get("entities") or []
    }


def relation_gold(record: dict[str, Any]) -> set[tuple[str, str, str]]:
    return {
        (
            str(item.get("subject") or "").strip(),
            str(item.get("predicate") or "").strip(),
            nested_value(item.get("object")),
        )
        for item in record.get("spo_list") or []
        if item.get("subject") and item.get("predicate") and nested_value(item.get("object"))
    }


def collect_group_metrics(
    records: Iterable[dict[str, Any]],
    stage: str,
) -> tuple[dict[str, dict[str, int]], set[Any], set[Any]]:
    from core.medical_offline_extraction import extract_entities_offline, extract_relations_offline

    groups: dict[str, dict[str, int]] = defaultdict(lambda: {"predicted": 0, "true_positive": 0})
    all_gold: set[Any] = set()
    all_predicted: set[Any] = set()
    for index, record in enumerate(records):
        text = str(record.get("text") or "")
        entities = extract_entities_offline(text)
        if stage == "entity":
            gold = entity_gold(record)
            predicted_items = [
                (
                    int(item.start_idx or 0),
                    int(item.end_idx or 0),
                    item.type,
                    item.text,
                    item.extraction_method or "dictionary_exact",
                )
                for item in entities
            ]
            all_gold.update((index, *item) for item in gold)
            all_predicted.update((index, *item[:4]) for item in predicted_items)
            for item in predicted_items:
                key = f"entity|{item[4]}|{item[2]}"
                groups[key]["predicted"] += 1
                if item[:4] in gold:
                    groups[key]["true_positive"] += 1
        else:
            gold = relation_gold(record)
            relations = extract_relations_offline(text, entities=entities)
            predicted_items = [
                (
                    item.subject,
                    item.predicate,
                    item.object,
                    item.extraction_method or "sentence_rule",
                )
                for item in relations
            ]
            all_gold.update((index, *item) for item in gold)
            all_predicted.update((index, *item[:3]) for item in predicted_items)
            for item in predicted_items:
                key = f"relation|{item[3]}|{item[1]}"
                groups[key]["predicted"] += 1
                if item[:3] in gold:
                    groups[key]["true_positive"] += 1
    return groups, all_gold, all_predicted


def reliability_level(precision: float, predicted: int) -> str:
    if predicted >= 8 and precision >= 0.80:
        return "high"
    if predicted >= 8 and precision >= 0.50:
        return "medium"
    return "low"


def build_profile(
    cmeee_calibration: list[dict[str, Any]],
    cmeie_calibration: list[dict[str, Any]],
    asset_dir: Path,
) -> dict[str, dict[str, float | int | str]]:
    combined: dict[str, dict[str, int]] = {}
    for stage, records in (("entity", cmeee_calibration), ("relation", cmeie_calibration)):
        groups, _, _ = collect_group_metrics(records, stage)
        combined.update(groups)
    profile: dict[str, dict[str, float | int | str]] = {}
    for key, counts in combined.items():
        predicted = counts["predicted"]
        precision = counts["true_positive"] / predicted if predicted else 0.0
        profile[key] = {
            **counts,
            "precision": round(precision, 6),
            "level": reliability_level(precision, predicted),
        }
    payload = {
        "schema_version": 1,
        "meaning": "grouped validation precision; not per-item probability",
        "groups": profile,
    }
    (asset_dir / "reliability_profile.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return profile


def evaluate(
    cmeee_records: list[dict[str, Any]],
    cmeie_records: list[dict[str, Any]],
    profile: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    from core.medical_lexicon import clear_lexicon_caches
    from core.medical_offline_extraction import _dictionary_index, load_entity_dictionary
    from core.medical_reliability import clear_reliability_cache

    clear_lexicon_caches()
    clear_reliability_cache()
    load_entity_dictionary.cache_clear()
    _dictionary_index.cache_clear()
    _, entity_gold_items, entity_predicted = collect_group_metrics(cmeee_records, "entity")
    relation_groups, relation_gold_items, relation_predicted = collect_group_metrics(cmeie_records, "relation")

    level_counts = Counter()
    level_true_positives = Counter()
    for key, counts in relation_groups.items():
        level = str(profile.get(key, {}).get("level") or "low")
        level_counts[level] += counts["predicted"]
        level_true_positives[level] += counts["true_positive"]
    decision_quality = {}
    for level in ("high", "medium", "low"):
        predicted = level_counts[level]
        true_positive = level_true_positives[level]
        decision_quality[level] = {
            "predicted": predicted,
            "true_positive": true_positive,
            "precision": round(true_positive / predicted, 6) if predicted else 0.0,
        }
    return {
        "entity": prf(entity_gold_items, entity_predicted),
        "relation": prf(relation_gold_items, relation_predicted),
        "relation_decisions": {
            "accepted_high": level_counts["high"],
            "candidate_medium": level_counts["medium"],
            "rejected_low": level_counts["low"],
        },
        "relation_decision_quality": decision_quality,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cmeee-train", type=Path, required=True)
    parser.add_argument("--cmeee-dev", type=Path, required=True)
    parser.add_argument("--cmeie-train", type=Path, required=True)
    parser.add_argument("--cmeie-dev", type=Path, required=True)
    parser.add_argument("--asset-dir", type=Path, default=Path("data/task2"))
    parser.add_argument("--report", type=Path, default=Path("data/task2/offline_eval_report.json"))
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    cmeee_train = load_json(args.cmeee_train)
    cmeee_dev = load_json(args.cmeee_dev)
    cmeie_train = load_jsonl(args.cmeie_train)
    cmeie_dev = load_jsonl(args.cmeie_dev)
    if args.limit:
        cmeee_dev = cmeee_dev[: args.limit]
        cmeie_dev = cmeie_dev[: args.limit]

    build_assets(cmeee_train, cmeie_train, args.asset_dir)
    cmeee_mid = len(cmeee_dev) // 2
    cmeie_mid = len(cmeie_dev) // 2
    profile = build_profile(cmeee_dev[:cmeee_mid], cmeie_dev[:cmeie_mid], args.asset_dir)
    report = {
        "split": {
            "cmeee_calibration": cmeee_mid,
            "cmeee_evaluation": len(cmeee_dev) - cmeee_mid,
            "cmeie_calibration": cmeie_mid,
            "cmeie_evaluation": len(cmeie_dev) - cmeie_mid,
        },
        "metrics": evaluate(cmeee_dev[cmeee_mid:], cmeie_dev[cmeie_mid:], profile),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
