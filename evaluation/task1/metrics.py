# -*- coding: utf-8 -*-
"""任务一算子级评测指标。"""

from __future__ import annotations

import csv
import io
import json
import math
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

from .fixtures import CorpusCase, serialize_payload


EVAL_ONLY_KEYS = {
    "clean_reference",
    "noise_labels",
    "noise",
    "noise_injected",
    "output_format_hint",
}


def _strip_eval_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_eval_fields(item)
            for key, item in value.items()
            if str(key).strip() not in EVAL_ONLY_KEYS
        }
    if isinstance(value, list):
        return [_strip_eval_fields(item) for item in value]
    return value


def _read_output(case: CorpusCase, output_path: Path) -> tuple[Any, str | None]:
    raw = output_path.read_text(encoding="utf-8", errors="replace")
    try:
        if case.file_format == "txt":
            return raw, None
        if case.file_format == "csv":
            return list(csv.DictReader(io.StringIO(raw))), None
        if case.file_format == "json":
            return json.loads(raw), None
        if case.file_format == "jsonl":
            return [json.loads(line) for line in raw.splitlines() if line.strip()], None
    except Exception as exc:
        return raw, f"{type(exc).__name__}: {exc}"
    return raw, f"unsupported format: {case.file_format}"


def _search_text(file_format: str, value: Any) -> str:
    if file_format == "txt":
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _normalize_scalar(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value))
    text = text.translate(str.maketrans({"，": ",", "。": ".", "；": ";", "：": ":", "！": "!", "？": "?"}))
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s*([,;:!?])\s*", r"\1", text)
    text = re.sub(r"[\s,;:!?。.]+$", "", text)
    return text


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonical(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    if isinstance(value, str):
        return _normalize_scalar(value)
    return value


def _leaf_map(value: Any, prefix: str = "$") -> dict[str, Any]:
    if isinstance(value, dict):
        leaves = {}
        for key, item in value.items():
            leaves.update(_leaf_map(item, f"{prefix}.{key}"))
        return leaves
    if isinstance(value, list):
        leaves = {}
        for index, item in enumerate(value):
            leaves.update(_leaf_map(item, f"{prefix}[{index}]"))
        return leaves
    return {prefix: _canonical(value)}


def _token_count(text: str, token: str) -> int:
    return len(re.findall(re.escape(token), text)) if token else 0


def _term_token_count(text: str, token: str) -> int:
    if not token:
        return 0
    pattern = r"(?<![A-Za-z0-9])" + re.escape(token) + r"(?![A-Za-z0-9])"
    return len(re.findall(pattern, text))


def _marker_counts(markers: tuple[str, ...], raw_text: str, output_text: str) -> dict[str, Any]:
    details = []
    expected = removed = remaining = 0
    for marker in sorted(set(markers)):
        raw_count = _token_count(raw_text, marker)
        output_count = _token_count(output_text, marker)
        removed_count = max(0, raw_count - output_count)
        expected += raw_count
        removed += min(raw_count, removed_count)
        remaining += min(raw_count, output_count)
        details.append(
            {
                "marker": marker,
                "expected": raw_count,
                "removed": min(raw_count, removed_count),
                "remaining": min(raw_count, output_count),
            }
        )
    return {"expected": expected, "removed": removed, "remaining": remaining, "details": details}


def _structure(case: CorpusCase, observed: Any, parse_error: str | None) -> dict[str, Any]:
    expected = case.expected
    if parse_error:
        return {"ok": False, "parse_error": parse_error, "expected_records": case.expected_records, "output_records": 0}
    if case.file_format == "txt":
        output_records = 1 if str(observed).strip() else 0
        return {"ok": output_records == 1, "parse_error": None, "expected_records": 1, "output_records": output_records}
    if not isinstance(observed, list) or not isinstance(expected, list):
        return {"ok": False, "parse_error": "top-level type mismatch", "expected_records": len(expected), "output_records": 0}
    expected_keys = [set(item.keys()) for item in expected if isinstance(item, dict)]
    observed_keys = [set(item.keys()) for item in observed if isinstance(item, dict)]
    ok = len(observed) == len(expected) and observed_keys == expected_keys
    return {"ok": ok, "parse_error": None, "expected_records": len(expected), "output_records": len(observed)}


def _records(value: Any) -> list[Any]:
    return value if isinstance(value, list) else [value]


def evaluate_case(case: CorpusCase, output_path: Path, execution: dict[str, Any]) -> dict[str, Any]:
    observed, parse_error = _read_output(case, output_path)
    raw_content = _strip_eval_fields(case.payload)
    raw_text = serialize_payload(case.file_format, raw_content)
    output_text = _search_text(case.file_format, observed)
    expected_text = _search_text(case.file_format, case.expected)

    noise = _marker_counts(case.noise_labels, raw_text, output_text)
    semantic_noise = _marker_counts(case.semantic_noise_labels, raw_text, output_text)
    learned_noise = _marker_counts(case.learned_noise_labels, raw_text, output_text)
    unseen_noise = _marker_counts(case.unseen_noise_labels, raw_text, output_text)
    fixed_noise = {
        "expected": noise["expected"] - semantic_noise["expected"],
        "removed": noise["removed"] - semantic_noise["removed"],
        "remaining": noise["remaining"] - semantic_noise["remaining"],
    }

    protected_details = []
    protected_expected = protected_preserved = 0
    for fragment in sorted(set(case.protected)):
        expected_count = _token_count(expected_text, fragment)
        output_count = _token_count(output_text, fragment)
        protected_expected += expected_count
        protected_preserved += min(expected_count, output_count)
        protected_details.append(
            {"fragment": fragment, "expected": expected_count, "preserved": min(expected_count, output_count)}
        )

    term_details = []
    for expectation in sorted(set(case.terms), key=lambda item: (item.raw, item.normalized)):
        raw_count = _term_token_count(raw_text, expectation.raw)
        output_raw_count = _term_token_count(output_text, expectation.raw)
        expected_full_count = _token_count(expected_text, expectation.normalized)
        output_full_count = _token_count(output_text, expectation.normalized)
        correct = raw_count > 0 and output_raw_count == 0 and output_full_count == expected_full_count
        term_details.append(
            {
                "raw": expectation.raw,
                "normalized": expectation.normalized,
                "raw_count": raw_count,
                "output_raw_count": output_raw_count,
                "expected_normalized_count": expected_full_count,
                "output_normalized_count": output_full_count,
                "correct": correct,
            }
        )

    expected_leaves = _leaf_map(case.expected)
    observed_leaves = _leaf_map(observed) if parse_error is None else {}
    leaf_paths = set(expected_leaves) | set(observed_leaves)
    exact_fields = sum(expected_leaves.get(path) == observed_leaves.get(path) for path in leaf_paths)

    expected_records = _records(case.expected)
    observed_records = _records(observed) if parse_error is None else []
    exact_records = sum(
        _canonical(expected_records[index]) == _canonical(observed_records[index])
        for index in range(min(len(expected_records), len(observed_records)))
    )
    structure = _structure(case, observed, parse_error)
    return {
        "case_id": case.case_id,
        "file_name": case.file_name,
        "file_format": case.file_format,
        "status": execution.get("status", "UNKNOWN"),
        "output_path": str(output_path),
        "elapsed_ms": execution.get("elapsed_ms"),
        "exact_match": parse_error is None and _canonical(observed) == _canonical(case.expected),
        "structure": structure,
        "noise": noise,
        "semantic_noise": semantic_noise,
        "fixed_noise": fixed_noise,
        "learned_noise": learned_noise,
        "unseen_noise": unseen_noise,
        "terms": {"expected": len(term_details), "correct": sum(item["correct"] for item in term_details), "details": term_details},
        "protected": {"expected": protected_expected, "preserved": protected_preserved, "details": protected_details},
        "fields": {"expected": len(leaf_paths), "exact": exact_fields},
        "records": {"expected": len(expected_records), "exact": exact_records},
    }


def _rate(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) / denominator, 4) if denominator else 1.0


def _f1(left: float, right: float) -> float:
    return round(2 * left * right / (left + right), 4) if left + right else 0.0


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)], 3)


def summarize_case_metrics(case_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in case_metrics:
        groups[item["file_format"]].append(item)

    def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
        files_total = len(items)
        noise_expected = sum(item["noise"]["expected"] for item in items)
        noise_removed = sum(item["noise"]["removed"] for item in items)
        semantic_expected = sum(item["semantic_noise"]["expected"] for item in items)
        semantic_removed = sum(item["semantic_noise"]["removed"] for item in items)
        fixed_expected = sum(item["fixed_noise"]["expected"] for item in items)
        fixed_removed = sum(item["fixed_noise"]["removed"] for item in items)
        learned_expected = sum(item["learned_noise"]["expected"] for item in items)
        learned_removed = sum(item["learned_noise"]["removed"] for item in items)
        unseen_expected = sum(item["unseen_noise"]["expected"] for item in items)
        unseen_removed = sum(item["unseen_noise"]["removed"] for item in items)
        protected_expected = sum(item["protected"]["expected"] for item in items)
        protected_preserved = sum(item["protected"]["preserved"] for item in items)
        term_expected = sum(item["terms"]["expected"] for item in items)
        term_correct = sum(item["terms"]["correct"] for item in items)
        fields_expected = sum(item["fields"]["expected"] for item in items)
        fields_exact = sum(item["fields"]["exact"] for item in items)
        records_expected = sum(item["records"]["expected"] for item in items)
        records_exact = sum(item["records"]["exact"] for item in items)
        noise_recall = _rate(noise_removed, noise_expected)
        content_preservation = _rate(protected_preserved, protected_expected)
        term_accuracy = _rate(term_correct, term_expected)
        field_accuracy = _rate(fields_exact, fields_expected)
        record_accuracy = _rate(records_exact, records_expected)
        structure_pass = sum(bool(item["structure"]["ok"]) for item in items)
        structure_rate = _rate(structure_pass, files_total)
        latencies = [float(item["elapsed_ms"]) for item in items if item.get("elapsed_ms") is not None]
        cleaning_f1 = _f1(noise_recall, content_preservation)
        score = round(
            0.30 * cleaning_f1
            + 0.20 * term_accuracy
            + 0.20 * content_preservation
            + 0.20 * field_accuracy
            + 0.10 * record_accuracy,
            4,
        )
        return {
            "files_total": files_total,
            "files_completed": sum(item["status"] == "COMPLETED" for item in items),
            "files_failed": sum(item["status"] != "COMPLETED" for item in items),
            "exact_files": sum(bool(item["exact_match"]) for item in items),
            "exact_file_rate": _rate(sum(bool(item["exact_match"]) for item in items), files_total),
            "records_expected": records_expected,
            "records_exact": records_exact,
            "record_accuracy": record_accuracy,
            "parse_errors": sum(bool(item["structure"].get("parse_error")) for item in items),
            "noise_expected": noise_expected,
            "noise_removed": noise_removed,
            "noise_recall": noise_recall,
            "semantic_noise_expected": semantic_expected,
            "semantic_noise_removed": semantic_removed,
            "semantic_noise_recall": _rate(semantic_removed, semantic_expected),
            "fixed_noise_expected": fixed_expected,
            "fixed_noise_removed": fixed_removed,
            "fixed_noise_recall": _rate(fixed_removed, fixed_expected),
            "learned_noise_expected": learned_expected,
            "learned_noise_removed": learned_removed,
            "learned_noise_recall": _rate(learned_removed, learned_expected),
            "unseen_noise_expected": unseen_expected,
            "unseen_noise_removed": unseen_removed,
            "unseen_noise_recall": _rate(unseen_removed, unseen_expected),
            "protected_expected": protected_expected,
            "protected_preserved": protected_preserved,
            "semantic_preservation": content_preservation,
            "cleaning_f1": cleaning_f1,
            "term_expected": term_expected,
            "term_correct": term_correct,
            "term_accuracy": term_accuracy,
            "fields_expected": fields_expected,
            "fields_exact": fields_exact,
            "field_accuracy": field_accuracy,
            "structure_pass": structure_pass,
            "structure_pass_rate": structure_rate,
            "mean_latency_ms": round(sum(latencies) / len(latencies), 3) if latencies else 0.0,
            "p95_latency_ms": _p95(latencies),
            "local_quality_score": score,
        }

    by_format = {file_format: summarize(items) for file_format, items in sorted(groups.items())}
    overall = summarize(case_metrics)
    return {
        "by_format": by_format,
        "overall": overall,
        "thresholds": {
            "noise_recall": 0.93,
            "term_accuracy": 0.95,
            "semantic_preservation": 0.99,
            "field_accuracy": 0.93,
            "structure_pass_rate": 1.0,
        },
    }


def write_metrics_csv(summary: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"format": key, **value} for key, value in summary["by_format"].items()]
    rows.append({"format": "overall", **summary["overall"]})
    fieldnames = ["format", *[key for key in rows[0] if key != "format"]]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
