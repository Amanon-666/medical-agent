#!/usr/bin/env python3
"""任务二正式评测器。

评测分成三个明确范围：

* ``holdout``：固定留出集，作为正式报告口径；
* ``full_dev``：完整开发集描述性统计；
* ``smoke``：快速检查或 PPT 挑战样本，不得当作正式指标。

实体采用 CMeEE 的 ``记录号 + 起止位置 + 类型 + 文本`` 精确匹配，
关系采用 CMeIE 的 ``记录号 + 主语 + 关系 + 宾语`` 精确匹配。
评测结果、终端输出、图表和 PPT 表格均由同一份结构化报告生成。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

_proj_root = Path(__file__).resolve().parents[1]
if str(_proj_root) not in sys.path:
    sys.path.insert(0, str(_proj_root))

from core.medical_extraction_service import extract_medical_knowledge
from core.medical_offline_extraction import (
    extract_entities_offline,
    extract_relations_offline,
)
from core.medical_extraction_validation import ENTITY_TYPE_ALIASES
from core.llm_client import LLMClient
from mcp_server.config import KG_DB, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


ENTITY_CN = {
    "dis": "疾病",
    "sym": "症状体征",
    "dru": "药物",
    "equ": "医疗设备",
    "pro": "医疗操作",
    "bod": "身体部位",
    "ite": "检验检查",
    "mic": "微生物",
    "dep": "科室",
}

RELATION_CN = {
    "临床表现": "临床表现",
    "药物治疗": "药物治疗",
    "辅助治疗": "治疗方式",
    "辅助检查": "检查",
    "实验室检查": "实验室检查",
    "影像学检查": "影像学检查",
    "内窥镜检查": "内窥镜检查",
    "组织学检查": "组织学检查",
    "筛查": "筛查",
    "手术治疗": "手术治疗",
    "放射治疗": "放射治疗",
    "化疗": "化疗",
    "就诊科室": "就诊科室",
    "并发症": "并发症",
    "病因": "病因",
    "发病部位": "发病部位",
    "转移部位": "转移部位",
    "外侵部位": "外侵部位",
    "鉴别诊断": "鉴别诊断",
    "同义词": "同义词",
    "相关（症状）": "相关症状",
    "相关（导致）": "相关导致",
    "相关（转化）": "相关转化",
    "预防": "预防",
    "高危因素": "高危因素",
    "风险评估因素": "风险因素",
    "发病年龄": "发病年龄",
    "发病性别倾向": "发病性别倾向",
    "发病机制": "发病机制",
    "发病率": "发病率",
    "病理分型": "病理分型",
    "病理生理": "病理生理",
    "遗传因素": "遗传因素",
    "多发群体": "易感人群",
    "多发地区": "多发地区",
    "多发季节": "多发季节",
    "传播途径": "传播途径",
    "治疗后症状": "治疗后症状",
    "死亡率": "死亡率",
    "预后状况": "预后状况",
    "预后生存率": "预后生存率",
    "阶段": "阶段",
    "病史": "病史",
}


def _cn_type(code: str) -> str:
    return ENTITY_CN.get(code, code)


def _cn_rel(code: str) -> str:
    return RELATION_CN.get(code, code)


def ts() -> str:
    return time.strftime("%H:%M:%S")


def _load_cmeee(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("CMeEE 文件必须是 JSON 数组")
    return data


def _load_cmeie(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"CMeIE 第 {line_no} 行不是合法 JSON: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"CMeIE 第 {line_no} 行不是 JSON 对象")
            records.append(value)
    return records


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _nested_value(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("@value", value.get("value", "")) or "").strip()
    return str(value or "").strip()


def _map_entity_type(value: Any) -> str:
    raw = str(value or "").strip()
    return ENTITY_TYPE_ALIASES.get(raw, raw)


def _prf(gold: set[Any], predicted: set[Any]) -> dict[str, float | int]:
    true_positive = len(gold & predicted)
    predicted_count = len(predicted)
    gold_count = len(gold)
    precision = true_positive / predicted_count if predicted_count else 0.0
    recall = true_positive / gold_count if gold_count else 0.0
    f1 = 2 * true_positive / (gold_count + predicted_count) if gold_count + predicted_count else 0.0
    return {
        "gold": gold_count,
        "predicted": predicted_count,
        "true_positive": true_positive,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
    }


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _performance(latencies_ms: list[float], total_seconds: float) -> dict[str, float | int]:
    count = len(latencies_ms)
    return {
        "evaluated_count": count,
        "extraction_elapsed_seconds": round(total_seconds, 4),
        "avg_latency_ms": round(sum(latencies_ms) / count, 3) if count else 0.0,
        "p50_latency_ms": round(_percentile(latencies_ms, 50), 3),
        "p95_latency_ms": round(_percentile(latencies_ms, 95), 3),
        "p99_latency_ms": round(_percentile(latencies_ms, 99), 3),
        "throughput_records_per_second": round(count / total_seconds, 3) if total_seconds else 0.0,
    }


def _new_cascade_stats() -> dict[str, Any]:
    return {
        "records_with_llm_error": 0,
        "gap_segment_count": 0,
        "gap_candidate_count": 0,
        "reviewed_candidate_count": 0,
        "auto_accepted_candidate_count": 0,
        "review_skipped_candidate_count": 0,
        "offline_filtered_candidate_count": 0,
        "rejected_candidate_count": 0,
        "llm_added_count": 0,
        "llm_added_entity_count": 0,
        "llm_added_relation_count": 0,
        "backend_counts": Counter(),
        "errors": [],
    }


def _add_bundle_stats(stats: dict[str, Any], bundle: Any, index: int) -> None:
    llm_error = str(getattr(bundle, "llm_error", "") or "")
    if llm_error:
        stats["records_with_llm_error"] += 1
        if len(stats["errors"]) < 20:
            stats["errors"].append({"index": index, "error": llm_error})
    requested = str(getattr(bundle, "backend", "") or "")
    effective = "offline_fallback" if requested == "hybrid" and llm_error else requested
    stats["backend_counts"][effective] += 1
    for field_name in (
        "gap_segment_count",
        "gap_candidate_count",
        "reviewed_candidate_count",
        "auto_accepted_candidate_count",
        "review_skipped_candidate_count",
        "offline_filtered_candidate_count",
        "rejected_candidate_count",
        "llm_added_count",
        "llm_added_entity_count",
        "llm_added_relation_count",
    ):
        stats[field_name] += int(getattr(bundle, field_name, 0) or 0)


def _finalize_cascade_stats(stats: dict[str, Any]) -> dict[str, Any]:
    result = dict(stats)
    result["backend_counts"] = dict(stats["backend_counts"])
    return result


def _select_records(
    records: list[dict[str, Any]],
    split: str,
    calibration_size: int,
    limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if split == "holdout":
        selected = records[calibration_size:]
        selection = {
            "name": "fixed_holdout",
            "calibration_size": calibration_size,
            "evaluation_start": calibration_size,
            "evaluation_count": len(selected),
        }
    elif split == "calibration":
        selected = records[:calibration_size]
        selection = {
            "name": "calibration_only",
            "calibration_size": calibration_size,
            "evaluation_start": 0,
            "evaluation_count": len(selected),
        }
    elif split == "full_dev":
        selected = records
        selection = {
            "name": "full_development_set",
            "calibration_size": calibration_size,
            "evaluation_start": 0,
            "evaluation_count": len(selected),
            "warning": "描述性统计；包含校准区间，不作为独立留出集分数",
        }
    elif split == "smoke":
        if limit <= 0:
            raise ValueError("split=smoke 必须指定 --limit")
        selected = records[:limit]
        selection = {
            "name": "prefix_smoke_sample",
            "calibration_size": calibration_size,
            "evaluation_start": 0,
            "evaluation_count": len(selected),
            "warning": "快速检查；不是正式评测",
        }
    else:
        raise ValueError(f"不支持的评测划分: {split}")
    return selected, selection


def _valid_gold_entity(record_index: int, text: str, item: dict[str, Any]) -> tuple[Any, ...] | None:
    value = str(item.get("entity", item.get("text", "")) or "").strip()
    entity_type = _map_entity_type(item.get("type"))
    try:
        start = int(item["start_idx"])
        end = int(item["end_idx"])
    except (KeyError, TypeError, ValueError):
        return None
    if not value or not entity_type or start < 0 or end < start or text[start : end + 1] != value:
        return None
    return record_index, start, end, entity_type, value


def _valid_pred_entity(record_index: int, text: str, entity: Any) -> tuple[Any, ...] | None:
    value = str(getattr(entity, "text", "") or "").strip()
    entity_type = _map_entity_type(getattr(entity, "type", ""))
    start = getattr(entity, "start_idx", None)
    end = getattr(entity, "end_idx", None)
    if start is None or end is None:
        return None
    try:
        start = int(start)
        end = int(end)
    except (TypeError, ValueError):
        return None
    if not value or not entity_type or start < 0 or end < start or text[start : end + 1] != value:
        return None
    return record_index, start, end, entity_type, value


def _type_counts(
    gold: set[tuple[Any, ...]],
    predicted: set[tuple[Any, ...]],
    hits: set[tuple[Any, ...]],
    label_index: int,
    cn_mapper,
) -> dict[str, dict[str, Any]]:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"gold": 0, "predicted": 0, "true_positive": 0})
    for item in gold:
        counts[str(item[label_index])]["gold"] += 1
    for item in predicted:
        counts[str(item[label_index])]["predicted"] += 1
    for item in hits:
        counts[str(item[label_index])]["true_positive"] += 1
    result: dict[str, dict[str, Any]] = {}
    for key, value in sorted(counts.items()):
        metrics = _prf(
            {item for item in gold if item[label_index] == key},
            {item for item in predicted if item[label_index] == key},
        )
        result[key] = {"cn": cn_mapper(key), **metrics}
    return result


@dataclass
class EvalConfig:
    backend: str
    kg_db_path: str
    llm: LLMClient | None
    requested_backend: str
    offline_view: str = "gated"


def eval_entities(
    samples: list[dict[str, Any]],
    config: EvalConfig,
    verbose: bool = False,
    verbose_limit: int = 12,
) -> dict[str, Any]:
    gold_all: set[tuple[Any, ...]] = set()
    predicted_all: set[tuple[Any, ...]] = set()
    latencies: list[float] = []
    sample_rows: list[dict[str, Any]] = []
    invalid_gold = 0
    invalid_predictions = 0
    raw_prediction_count = 0
    duplicate_prediction_count = 0
    skipped = 0
    cascade = _new_cascade_stats()
    started = time.perf_counter()

    for index, sample in enumerate(samples):
        text = str(sample.get("text", "") or "")
        if not text.strip():
            skipped += 1
            continue
        gold = set()
        for item in sample.get("entities") or []:
            key = _valid_gold_entity(index, text, item)
            if key is None:
                invalid_gold += 1
            else:
                gold.add(key)

        tick = time.perf_counter()
        bundle = None
        if config.backend == "offline" and config.offline_view == "raw":
            predicted_items = extract_entities_offline(text, config.kg_db_path)
        else:
            bundle = extract_medical_knowledge(
                text,
                backend=config.backend,
                kg_db_path=config.kg_db_path,
                llm=config.llm,
            )
            predicted_items = bundle.entities
            _add_bundle_stats(cascade, bundle, index)
        latency_ms = (time.perf_counter() - tick) * 1000
        latencies.append(latency_ms)

        raw_items = list(predicted_items or [])
        raw_prediction_count += len(raw_items)
        valid_predictions = []
        for item in raw_items:
            key = _valid_pred_entity(index, text, item)
            if key is None:
                invalid_predictions += 1
            else:
                valid_predictions.append(key)
        duplicate_prediction_count += len(valid_predictions) - len(set(valid_predictions))
        predicted = set(valid_predictions)
        gold_all.update(gold)
        predicted_all.update(predicted)
        hits = gold & predicted

        if verbose and len(sample_rows) < verbose_limit:
            sample_rows.append(
                {
                    "index": index,
                    "text": text[:180],
                    "gold_count": len(gold),
                    "predicted_count": len(predicted),
                    "true_positive": len(hits),
                    "gold": [
                        {"entity": item[4], "type": _cn_type(item[3]), "start_idx": item[1], "end_idx": item[2]}
                        for item in sorted(gold, key=lambda value: (value[1], value[2]))
                    ],
                    "predicted": [
                        {"entity": item[4], "type": _cn_type(item[3]), "start_idx": item[1], "end_idx": item[2]}
                        for item in sorted(predicted, key=lambda value: (value[1], value[2]))
                    ],
                }
            )

    total_seconds = time.perf_counter() - started
    hits_all = gold_all & predicted_all
    report = {
        "task": "CMeEE",
        "requested_backend": config.requested_backend,
        "backend": config.backend,
        "offline_view": config.offline_view if config.backend == "offline" else "",
        "evaluated_count": len(latencies),
        "skipped_count": skipped,
        "invalid_gold_count": invalid_gold,
        "invalid_prediction_count": invalid_predictions,
        "quality": {
            "raw_prediction_count": raw_prediction_count,
            "unique_prediction_count": len(predicted_all),
            "duplicate_prediction_count": duplicate_prediction_count,
        },
        "total": _prf(gold_all, predicted_all),
        "per_type": _type_counts(gold_all, predicted_all, hits_all, 3, _cn_type),
        "performance": _performance(latencies, total_seconds),
        "cascade": _finalize_cascade_stats(cascade),
        "samples": sample_rows,
    }
    return report


def eval_relations(
    samples: list[dict[str, Any]],
    config: EvalConfig,
    verbose: bool = False,
    verbose_limit: int = 12,
) -> dict[str, Any]:
    gold_all: set[tuple[Any, ...]] = set()
    predicted_all: set[tuple[Any, ...]] = set()
    latencies: list[float] = []
    sample_rows: list[dict[str, Any]] = []
    invalid_gold = 0
    invalid_predictions = 0
    raw_prediction_count = 0
    duplicate_prediction_count = 0
    relation_endpoint_checks = 0
    relation_endpoint_valid = 0
    skipped = 0
    cascade = _new_cascade_stats()
    started = time.perf_counter()

    for index, sample in enumerate(samples):
        text = str(sample.get("text", "") or "")
        if not text.strip():
            skipped += 1
            continue
        gold = set()
        for item in sample.get("spo_list") or []:
            subject = str(item.get("subject", "") or "").strip()
            predicate = str(item.get("predicate", "") or "").strip()
            object_value = _nested_value(item.get("object", item.get("object@value", "")))
            if subject and predicate and object_value:
                gold.add((index, subject, predicate, object_value))
            else:
                invalid_gold += 1

        tick = time.perf_counter()
        bundle = None
        if config.backend == "offline" and config.offline_view == "raw":
            entities = extract_entities_offline(text, config.kg_db_path)
            entity_texts = {str(getattr(item, "text", "") or "").strip() for item in entities}
            predicted_items = extract_relations_offline(
                text,
                entities=entities,
                db_path=config.kg_db_path,
            )
        else:
            bundle = extract_medical_knowledge(
                text,
                backend=config.backend,
                kg_db_path=config.kg_db_path,
                llm=config.llm,
            )
            predicted_items = bundle.relations
            entity_texts = {
                str(getattr(item, "text", "") or "").strip()
                for item in (getattr(bundle, "entities", None) or [])
            }
            _add_bundle_stats(cascade, bundle, index)
        latency_ms = (time.perf_counter() - tick) * 1000
        latencies.append(latency_ms)

        raw_items = list(predicted_items or [])
        raw_prediction_count += len(raw_items)
        valid_predictions = []
        for item in raw_items:
            subject = str(getattr(item, "subject", "") or "").strip()
            predicate = str(getattr(item, "predicate", "") or "").strip()
            object_value = str(getattr(item, "object", "") or "").strip()
            if subject and predicate and object_value:
                key = (index, subject, predicate, object_value)
                valid_predictions.append(key)
                relation_endpoint_checks += 1
                if subject in entity_texts and object_value in entity_texts:
                    relation_endpoint_valid += 1
            else:
                invalid_predictions += 1
        duplicate_prediction_count += len(valid_predictions) - len(set(valid_predictions))
        predicted = set(valid_predictions)
        gold_all.update(gold)
        predicted_all.update(predicted)
        hits = gold & predicted

        if verbose and len(sample_rows) < verbose_limit:
            sample_rows.append(
                {
                    "index": index,
                    "text": text[:180],
                    "gold_count": len(gold),
                    "predicted_count": len(predicted),
                    "true_positive": len(hits),
                    "gold": [
                        {"subject": item[1], "predicate": _cn_rel(item[2]), "object": item[3]}
                        for item in sorted(gold)
                    ],
                    "predicted": [
                        {"subject": item[1], "predicate": _cn_rel(item[2]), "object": item[3]}
                        for item in sorted(predicted)
                    ],
                }
            )

    total_seconds = time.perf_counter() - started
    hits_all = gold_all & predicted_all
    return {
        "task": "CMeIE",
        "requested_backend": config.requested_backend,
        "backend": config.backend,
        "offline_view": config.offline_view if config.backend == "offline" else "",
        "evaluated_count": len(latencies),
        "skipped_count": skipped,
        "invalid_gold_count": invalid_gold,
        "invalid_prediction_count": invalid_predictions,
        "quality": {
            "raw_prediction_count": raw_prediction_count,
            "unique_prediction_count": len(predicted_all),
            "duplicate_prediction_count": duplicate_prediction_count,
            "relation_endpoint_checks": relation_endpoint_checks,
            "relation_endpoint_valid_count": relation_endpoint_valid,
            "relation_endpoint_valid_rate": (
                relation_endpoint_valid / relation_endpoint_checks if relation_endpoint_checks else 0.0
            ),
        },
        "total": _prf(gold_all, predicted_all),
        "per_type": _type_counts(gold_all, predicted_all, hits_all, 2, _cn_rel),
        "performance": _performance(latencies, total_seconds),
        "cascade": _finalize_cascade_stats(cascade),
        "samples": sample_rows,
    }


def _fmt_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def _fmt_float(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "-"


def _write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_ppt_tables(report: dict[str, Any], out_dir: Path) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    files: list[str] = []
    summary_rows = []
    for key in ("entity", "relation"):
        item = report.get(key)
        if not item:
            continue
        total = item["total"]
        performance = item["performance"]
        summary_rows.append(
            {
                "任务": "实体识别" if key == "entity" else "关系抽取",
                "数据集": item["task"],
                "后端": item["backend"],
                "评测样本": item["evaluated_count"],
                "Gold": total["gold"],
                "预测": total["predicted"],
                "命中": total["true_positive"],
                "Precision": _fmt_percent(total["precision"]),
                "Recall": _fmt_percent(total["recall"]),
                "F1": _fmt_percent(total["f1"]),
                "P50(ms)": _fmt_float(performance["p50_latency_ms"]),
                "P95(ms)": _fmt_float(performance["p95_latency_ms"]),
                "吞吐(records/s)": _fmt_float(performance["throughput_records_per_second"]),
            }
        )
    path = out_dir / "task2_ppt_summary.csv"
    _write_csv(path, summary_rows, list(summary_rows[0].keys()) if summary_rows else ["任务"])
    files.append(str(path))

    for key, filename in (("entity", "task2_entity_by_type.csv"), ("relation", "task2_relation_by_type.csv")):
        item = report.get(key)
        if not item:
            continue
        rows = []
        for code, metrics in item["per_type"].items():
            rows.append(
                {
                    "类型": metrics["cn"],
                    "标注": metrics["gold"],
                    "预测": metrics["predicted"],
                    "命中": metrics["true_positive"],
                    "Precision": _fmt_percent(metrics["precision"]),
                    "Recall": _fmt_percent(metrics["recall"]),
                    "F1": _fmt_percent(metrics["f1"]),
                    "代码": code,
                }
            )
        path = out_dir / filename
        _write_csv(path, rows, ["类型", "标注", "预测", "命中", "Precision", "Recall", "F1", "代码"])
        files.append(str(path))

    relation = report.get("relation")
    if relation:
        cascade = relation.get("cascade") or {}
        route_rows = []
        for level, label in (("high", "高可靠"), ("medium", "中可靠"), ("low", "低可靠")):
            quality = (report.get("offline_profile") or {}).get(level, {})
            route_rows.append(
                {
                    "级别": label,
                    "预测候选": quality.get("predicted", ""),
                    "校准命中": quality.get("true_positive", ""),
                    "校准精确率": _fmt_percent(quality.get("precision", 0.0)),
                    "运行期拒绝数": cascade.get("rejected_candidate_count", 0) if level == "low" else "",
                    "离线低可靠过滤数": cascade.get("offline_filtered_candidate_count", 0) if level == "low" else "",
                }
            )
        path = out_dir / "task2_cascade_summary.csv"
        _write_csv(path, route_rows, ["级别", "预测候选", "校准命中", "校准精确率", "运行期拒绝数", "离线低可靠过滤数"])
        files.append(str(path))

    markdown = out_dir / "task2_ppt_tables.md"
    selection = report.get("selection", {})
    cmeee_selection = (selection.get("cmeee") or {}).get("name", "-")
    cmeie_selection = (selection.get("cmeie") or {}).get("name", "-")
    lines = [
        "# 任务二正式评测 PPT 表格",
        "",
        f"- 评测划分：{selection.get('split', '-')}（CMeEE：{cmeee_selection}；CMeIE：{cmeie_selection}）",
        f"- CMeEE 样本：{report.get('dataset', {}).get('cmeee_selected_count', '-')}",
        f"- CMeIE 样本：{report.get('dataset', {}).get('cmeie_selected_count', '-')}",
        "- 指标口径：实体按记录内起止位置、类型和文本严格匹配；关系按记录内主语、关系和宾语严格匹配。",
        "",
        "## 总体指标",
        "",
        "| 任务 | 后端 | 样本 | Gold | 预测 | 命中 | Precision | Recall | F1 | P50(ms) | P95(ms) | 吞吐(records/s) |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            "| {任务} | {后端} | {评测样本} | {Gold} | {预测} | {命中} | {Precision} | {Recall} | {F1} | {P50(ms)} | {P95(ms)} | {吞吐(records/s)} |".format(**row)
        )
    markdown.write_text("\n".join(lines) + "\n", encoding="utf-8")
    files.append(str(markdown))
    return files


def generate_charts(report: dict[str, Any], out_dir: Path, show: bool) -> list[str]:
    try:
        import matplotlib
        if not show:
            matplotlib.use("Agg")
        import matplotlib.font_manager as fm
        import matplotlib.pyplot as plt
    except ImportError:
        print("[charts] matplotlib 未安装，跳过图表生成")
        return []

    font_path = None
    for name in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "WenQuanYi Micro Hei"):
        try:
            candidate = fm.findfont(name, fallback_to_default=False)
            if candidate:
                font_path = candidate
                break
        except Exception:
            continue
    if font_path:
        plt.rcParams["font.sans-serif"] = [fm.FontProperties(fname=font_path).get_name()]
    plt.rcParams["axes.unicode_minus"] = False

    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    open_figures: list[Any] = []

    overall = []
    labels = []
    for key, label in (("entity", "实体识别"), ("relation", "关系抽取")):
        item = report.get(key)
        if not item:
            continue
        labels.append(label)
        overall.append(
            [
                item["total"]["precision"] * 100,
                item["total"]["recall"] * 100,
                item["total"]["f1"] * 100,
            ]
        )
    if overall:
        fig, ax = plt.subplots(figsize=(9.5, 5.4), dpi=180)
        x = list(range(len(labels)))
        width = 0.24
        for offset, metric, color in ((-width, "Precision", "#2563EB"), (0, "Recall", "#059669"), (width, "F1", "#7C3AED")):
            values = [row[{"Precision": 0, "Recall": 1, "F1": 2}[metric]] for row in overall]
            bars = ax.bar([value + offset for value in x], values, width, label=metric, color=color)
            ax.bar_label(bars, fmt="%.1f", fontsize=9, padding=2)
        ax.set_xticks(x, labels)
        ax.set_ylim(0, 100)
        ax.set_ylabel("百分比（%）")
        ax.set_title("任务二实体与关系抽取总体指标")
        ax.grid(axis="y", alpha=0.25)
        ax.legend(frameon=False, ncol=3, loc="upper right")
        fig.tight_layout()
        path = out_dir / "task2_overall_prf.png"
        fig.savefig(path, bbox_inches="tight", facecolor="white")
        saved.append(str(path))
        if show:
            open_figures.append(fig)
        else:
            plt.close(fig)

    performance_labels = []
    p50_values = []
    p95_values = []
    for key, label in (("entity", "实体识别"), ("relation", "关系抽取")):
        item = report.get(key)
        if not item:
            continue
        performance_labels.append(label)
        p50_values.append(float(item["performance"].get("p50_latency_ms", 0.0)))
        p95_values.append(float(item["performance"].get("p95_latency_ms", 0.0)))
    if performance_labels:
        fig, ax = plt.subplots(figsize=(9.5, 5.0), dpi=180)
        x = list(range(len(performance_labels)))
        width = 0.32
        p50_bars = ax.bar([value - width / 2 for value in x], p50_values, width, label="P50", color="#0EA5E9")
        p95_bars = ax.bar([value + width / 2 for value in x], p95_values, width, label="P95", color="#F97316")
        ax.bar_label(p50_bars, fmt="%.2f", fontsize=9, padding=2)
        ax.bar_label(p95_bars, fmt="%.2f", fontsize=9, padding=2)
        ax.set_xticks(x, performance_labels)
        ax.set_ylabel("毫秒")
        ax.set_title("任务二抽取延迟（按记录）")
        ax.grid(axis="y", alpha=0.25)
        ax.legend(frameon=False, ncol=2, loc="upper left")
        fig.tight_layout()
        path = out_dir / "task2_performance_latency.png"
        fig.savefig(path, bbox_inches="tight", facecolor="white")
        saved.append(str(path))
        if show:
            open_figures.append(fig)
        else:
            plt.close(fig)

    entity = report.get("entity")
    if entity and entity.get("per_type"):
        rows = sorted(entity["per_type"].items(), key=lambda pair: list(ENTITY_CN).index(pair[0]) if pair[0] in ENTITY_CN else 99)
        labels = [metrics["cn"] for _, metrics in rows]
        values = [metrics["f1"] * 100 for _, metrics in rows]
        fig, ax = plt.subplots(figsize=(10.5, 5.2), dpi=180)
        bars = ax.bar(labels, values, color="#2563EB")
        ax.bar_label(bars, fmt="%.1f", fontsize=8, padding=2)
        ax.set_ylim(0, 100)
        ax.set_ylabel("F1（%）")
        ax.set_title("CMeEE 各实体类型 F1")
        ax.tick_params(axis="x", rotation=35)
        ax.grid(axis="y", alpha=0.25)
        fig.tight_layout()
        path = out_dir / "task2_entity_type_f1.png"
        fig.savefig(path, bbox_inches="tight", facecolor="white")
        saved.append(str(path))
        if show:
            open_figures.append(fig)
        else:
            plt.close(fig)

    relation = report.get("relation")
    if relation and relation.get("per_type"):
        rows = sorted(relation["per_type"].items(), key=lambda pair: pair[1]["gold"], reverse=True)[:15]
        labels = [metrics["cn"] for _, metrics in rows]
        values = [metrics["f1"] * 100 for _, metrics in rows]
        fig, ax = plt.subplots(figsize=(12, 5.8), dpi=180)
        bars = ax.bar(labels, values, color="#7C3AED")
        ax.bar_label(bars, fmt="%.1f", fontsize=8, padding=2)
        ax.set_ylim(0, max(100, max(values, default=0) * 1.25))
        ax.set_ylabel("F1（%）")
        ax.set_title("CMeIE 高频关系类型 F1（按标注数量前 15）")
        ax.tick_params(axis="x", rotation=40)
        ax.grid(axis="y", alpha=0.25)
        fig.tight_layout()
        path = out_dir / "task2_relation_type_f1_top15.png"
        fig.savefig(path, bbox_inches="tight", facecolor="white")
        saved.append(str(path))
        if show:
            open_figures.append(fig)
        else:
            plt.close(fig)

        cascade = relation.get("cascade") or {}
        if cascade.get("rejected_candidate_count", 0) or cascade.get("llm_added_relation_count", 0):
            labels = ["缺口段落", "送入复核", "证据直通", "跳过复核", "拒绝候选", "新增关系"]
            values = [
                cascade.get("gap_segment_count", 0),
                cascade.get("reviewed_candidate_count", 0),
                cascade.get("auto_accepted_candidate_count", 0),
                cascade.get("review_skipped_candidate_count", 0),
                cascade.get("rejected_candidate_count", 0),
                cascade.get("llm_added_relation_count", 0),
            ]
            fig, ax = plt.subplots(figsize=(10, 5.2), dpi=180)
            bars = ax.bar(labels, values, color=["#0EA5E9", "#2563EB", "#7C3AED", "#94A3B8", "#DC2626", "#059669"])
            ax.bar_label(bars, fmt="%d", fontsize=9, padding=2)
            ax.set_title("任务二级联路由统计")
            ax.grid(axis="y", alpha=0.25)
            fig.tight_layout()
            path = out_dir / "task2_cascade_counts.png"
            fig.savefig(path, bbox_inches="tight", facecolor="white")
            saved.append(str(path))
            if show:
                open_figures.append(fig)
            else:
                plt.close(fig)

    if show and open_figures:
        plt.show()
        for fig in open_figures:
            plt.close(fig)
    return saved


def print_report(report: dict[str, Any], label: str) -> None:
    total = report["total"]
    perf = report["performance"]
    print()
    print("=" * 96)
    print(f"  {label} | {report['task']} | backend={report['backend']} | samples={report['evaluated_count']}")
    print("-" * 96)
    print(f"  Gold={total['gold']}  Predicted={total['predicted']}  TP={total['true_positive']}  "
          f"P={_fmt_percent(total['precision'])}  R={_fmt_percent(total['recall'])}  F1={_fmt_percent(total['f1'])}")
    print(f"  latency avg={perf['avg_latency_ms']:.2f}ms  p50={perf['p50_latency_ms']:.2f}ms  "
          f"p95={perf['p95_latency_ms']:.2f}ms  p99={perf['p99_latency_ms']:.2f}ms  "
          f"throughput={perf['throughput_records_per_second']:.2f} records/s")
    print(f"  skipped={report['skipped_count']}  invalid_gold={report.get('invalid_gold_count', 0)}  "
          f"invalid_prediction={report.get('invalid_prediction_count', 0)}")
    quality = report.get("quality") or {}
    print(f"  raw_predictions={quality.get('raw_prediction_count', 0)}  "
          f"unique_predictions={quality.get('unique_prediction_count', 0)}  "
          f"duplicate_predictions={quality.get('duplicate_prediction_count', 0)}")
    if "relation_endpoint_checks" in quality:
        print(f"  relation_endpoint_validity={quality.get('relation_endpoint_valid_rate', 0.0) * 100:.2f}%  "
              f"({quality.get('relation_endpoint_valid_count', 0)}/{quality.get('relation_endpoint_checks', 0)})")
    if report.get("per_type"):
        print("-" * 96)
        print(f"  {'类型/关系':<20} {'Gold':>8} {'Pred':>8} {'TP':>8} {'P':>9} {'R':>9} {'F1':>9}")
        for _, value in report["per_type"].items():
            print(f"  {value['cn']:<20} {value['gold']:>8} {value['predicted']:>8} {value['true_positive']:>8} "
                  f"{_fmt_percent(value['precision']):>9} {_fmt_percent(value['recall']):>9} {_fmt_percent(value['f1']):>9}")
    cascade = report.get("cascade") or {}
    if any(cascade.get(key, 0) for key in ("gap_segment_count", "reviewed_candidate_count", "offline_filtered_candidate_count", "rejected_candidate_count", "llm_added_count")):
        print("-" * 96)
        print("  cascade: "
              f"gap_segments={cascade.get('gap_segment_count', 0)}  "
              f"gap_candidates={cascade.get('gap_candidate_count', 0)}  "
              f"reviewed={cascade.get('reviewed_candidate_count', 0)}  "
              f"skipped={cascade.get('review_skipped_candidate_count', 0)}  "
              f"offline_filtered={cascade.get('offline_filtered_candidate_count', 0)}  "
              f"rejected={cascade.get('rejected_candidate_count', 0)}  "
              f"llm_added={cascade.get('llm_added_count', 0)}")
    print("=" * 96)


def print_samples(report: dict[str, Any]) -> None:
    samples = report.get("samples") or []
    if not samples:
        return
    print(f"\n{'─' * 96}")
    print(f"  代表性样本（{len(samples)} 条）")
    print(f"{'─' * 96}")
    for sample in samples:
        print(f"\n  [{sample['index']}] {sample['text']}")
        print(f"    gold={sample['gold_count']} predicted={sample['predicted_count']} tp={sample['true_positive']}")


def _load_offline_profile(asset_dir: Path) -> dict[str, Any]:
    path = asset_dir / "reliability_profile.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    levels: dict[str, dict[str, Any]] = {}
    for value in (payload.get("groups") or {}).values():
        level = str(value.get("level") or "")
        if level:
            levels.setdefault(level, {"predicted": 0, "true_positive": 0})
            levels[level]["predicted"] += int(value.get("predicted", 0) or 0)
            levels[level]["true_positive"] += int(value.get("true_positive", 0) or 0)
    for value in levels.values():
        value["precision"] = value["true_positive"] / value["predicted"] if value["predicted"] else 0.0
    return levels


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass
    parser = argparse.ArgumentParser(description="MediFlow 任务二正式实体/关系评测")
    parser.add_argument("--cmeee", required=True, help="CMeEE JSON 开发集")
    parser.add_argument("--cmeie", required=True, help="CMeIE JSONL 开发集")
    parser.add_argument("--backend", default="offline", choices=["offline", "hybrid", "llm"], help="默认 offline；hybrid 需明确指定")
    parser.add_argument(
        "--offline-view",
        default="gated",
        choices=["gated", "raw"],
        help="offline 评测口径：gated=生产门禁后的结果，raw=原始候选；默认 gated",
    )
    parser.add_argument("--split", default="holdout", choices=["holdout", "calibration", "full_dev", "smoke"], help="默认固定留出集")
    parser.add_argument("--cmeee-calibration-size", type=int, default=2500)
    parser.add_argument("--cmeie-calibration-size", type=int, default=1792)
    parser.add_argument("--limit", type=int, default=0, help="仅 split=smoke 时使用")
    parser.add_argument("--kg-db", default=str(KG_DB), help="知识图谱词典数据库")
    parser.add_argument("--asset-dir", default=str(_proj_root / "data" / "task2"), help="离线资产目录")
    parser.add_argument("--output", "-o", default=str(_proj_root / "tmp" / "task2_formal_eval" / "report.json"))
    parser.add_argument("--charts", "-c", default=str(_proj_root / "tmp" / "task2_formal_eval" / "charts"), help="PNG/CSV/Markdown 输出目录")
    parser.add_argument("--no-display", action="store_true", help="不弹出图表窗口，仅保存图表")
    parser.add_argument("--verbose", "-v", action="store_true", help="打印代表性样本")
    parser.add_argument("--verbose-limit", type=int, default=12)
    parser.add_argument("--llm-key", help="hybrid/llm API key")
    parser.add_argument("--llm-base-url", default=LLM_BASE_URL)
    parser.add_argument("--llm-model", default=LLM_MODEL)
    args = parser.parse_args()

    cmeee_path = Path(args.cmeee).resolve()
    cmeie_path = Path(args.cmeie).resolve()
    kg_db_path = Path(args.kg_db).resolve() if args.kg_db else None
    if not cmeee_path.exists() or not cmeie_path.exists():
        parser.error("CMeEE/CMeIE 文件不存在")
    if args.split != "smoke" and args.limit:
        parser.error("正式划分不接受 --limit；需要快速检查时使用 --split smoke")

    cmeee_records = _load_cmeee(cmeee_path)
    cmeie_records = _load_cmeie(cmeie_path)
    cmeee_selected, cmeee_selection = _select_records(
        cmeee_records, args.split, args.cmeee_calibration_size, args.limit
    )
    cmeie_selected, cmeie_selection = _select_records(
        cmeie_records, args.split, args.cmeie_calibration_size, args.limit
    )

    requested_backend = args.backend
    llm = None
    effective_backend = args.backend
    degraded_reason = ""
    if args.backend in ("hybrid", "llm"):
        api_key = args.llm_key or LLM_API_KEY or ""
        if not api_key:
            effective_backend = "offline_fallback"
            degraded_reason = "LLM API key 未配置"
            print(f"[{ts()}] requested_backend={requested_backend} effective_backend=offline_fallback")
            print(f"[{ts()}] degraded_reason={degraded_reason}")
        else:
            llm = LLMClient(base_url=args.llm_base_url, model=args.llm_model, api_key=api_key)
            print(f"[{ts()}] requested_backend={requested_backend} effective_backend={requested_backend}")
            print(f"[{ts()}] llm_model={args.llm_model}")
    else:
        print(f"[{ts()}] requested_backend=offline effective_backend=offline view={args.offline_view}")

    config = EvalConfig(
        backend=args.backend if llm is not None else "offline",
        kg_db_path=args.kg_db,
        llm=llm,
        requested_backend=requested_backend,
        offline_view=args.offline_view,
    )

    print(f"[{ts()}] split={args.split}")
    print(f"[{ts()}] CMeEE source={cmeee_path} total={len(cmeee_records)} selected={len(cmeee_selected)} sha256={_sha256(cmeee_path)[:16]}...")
    print(f"[{ts()}] CMeIE source={cmeie_path} total={len(cmeie_records)} selected={len(cmeie_selected)} sha256={_sha256(cmeie_path)[:16]}...")
    print(f"[{ts()}] kg_db={kg_db_path or '-'} exists={bool(kg_db_path and kg_db_path.exists())}")
    if kg_db_path and not kg_db_path.exists():
        print(f"[{ts()}] warning=知识图谱数据库不存在，将只使用 data/task2 中的离线资产")
    print(f"[{ts()}] calibration_sizes cmeee={args.cmeee_calibration_size} cmeie={args.cmeie_calibration_size}")
    for dataset_name, selection in (("CMeEE", cmeee_selection), ("CMeIE", cmeie_selection)):
        if selection.get("warning"):
            print(f"[{ts()}] warning={dataset_name}: {selection['warning']}")

    results: dict[str, Any] = {
        "schema_version": 2,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "dataset": {
            "cmeee_path": str(cmeee_path),
            "cmeie_path": str(cmeie_path),
            "cmeee_sha256": _sha256(cmeee_path),
            "cmeie_sha256": _sha256(cmeie_path),
            "cmeee_total_count": len(cmeee_records),
            "cmeie_total_count": len(cmeie_records),
            "cmeee_selected_count": len(cmeee_selected),
            "cmeie_selected_count": len(cmeie_selected),
        },
        "selection": {
            "split": args.split,
            "name": cmeee_selection.get("name") if cmeee_selection.get("name") == cmeie_selection.get("name") else "mixed",
            "cmeee": cmeee_selection,
            "cmeie": cmeie_selection,
        },
        "backend": {
            "requested": requested_backend,
            "effective": effective_backend,
            "offline_view": args.offline_view,
            "degraded": bool(degraded_reason),
            "degraded_reason": degraded_reason,
            "model": args.llm_model if llm is not None else "offline",
        },
        "assets": {
            "kg_db_path": str(kg_db_path) if kg_db_path else "",
            "kg_db_exists": bool(kg_db_path and kg_db_path.exists()),
            "task2_asset_dir": str(Path(args.asset_dir).resolve()),
        },
        "entity": None,
        "relation": None,
        "offline_profile": _load_offline_profile(Path(args.asset_dir)),
    }

    if args.cmeee:
        print(f"[{ts()}] evaluating CMeEE ...")
        results["entity"] = eval_entities(
            cmeee_selected,
            config,
            verbose=args.verbose,
            verbose_limit=args.verbose_limit,
        )
        print_report(results["entity"], "CMeEE 实体识别")
        if args.verbose:
            print_samples(results["entity"])

    if args.cmeie:
        print(f"[{ts()}] evaluating CMeIE ...")
        results["relation"] = eval_relations(
            cmeie_selected,
            config,
            verbose=args.verbose,
            verbose_limit=args.verbose_limit,
        )
        print_report(results["relation"], "CMeIE 关系抽取")
        if args.verbose:
            print_samples(results["relation"])

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{ts()}] report={output_path}")

    chart_dir = Path(args.charts)
    chart_paths = generate_charts(results, chart_dir, show=not args.no_display)
    table_paths = write_ppt_tables(results, chart_dir)
    print(f"[{ts()}] charts={len(chart_paths)} tables={len(table_paths)} output_dir={chart_dir}")
    for path in chart_paths + table_paths:
        print(f"  artifact={path}")


if __name__ == "__main__":
    main()
