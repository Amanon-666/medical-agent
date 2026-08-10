#!/usr/bin/env python3
"""任务二多医学场景与多后端评测。

该脚本复用 ``tests/eval_offline.py`` 的严格指标实现，不接触 Nexent、知识图谱
持久化或分析库。公开 CMeEE/CMeIE 开发集按医学主题划分为多个互斥场景，另对
本地四格式糖尿病示例做无金标准的真实输入性能统计。
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_EVALUATOR_PATH = PROJECT_ROOT / "tests" / "eval_offline.py"
DEFAULT_DEMO_DIR = PROJECT_ROOT / "data" / "standard_diabetes_demo" / "datamate_upload"

# 允许从项目根目录直接执行 `python tests\\eval_task2_scenarios.py`，不要求
# 用户先手工设置 PYTHONPATH；评测仍只加载本地项目代码。
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp_server.shared.parsing import parse_files


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    label: str
    terms: tuple[str, ...]


SCENARIOS = (
    Scenario("respiratory", "呼吸系统", ("肺炎", "流感", "支气管", "哮喘", "肺癌", "咳嗽", "呼吸")),
    Scenario("cardiovascular", "心血管", ("高血压", "冠心病", "心肌梗死", "心脏", "心律", "动脉", "心绞痛")),
    Scenario("digestive", "消化系统", ("胃炎", "胃癌", "肝炎", "肝硬化", "结肠", "胃溃疡", "消化")),
    Scenario("metabolic", "代谢内分泌", ("糖尿病", "甲状腺", "肥胖", "血糖", "胰岛素", "痛风")),
    Scenario("oncology", "肿瘤", ("癌", "肿瘤", "白血病", "淋巴瘤", "转移")),
    Scenario("infection", "感染传染", ("感染", "病毒", "细菌", "结核", "流行性", "传染")),
    Scenario("neurology", "神经系统", ("脑卒中", "癫痫", "帕金森", "头痛", "神经", "痴呆")),
    Scenario("other", "其他医学文本", ()),
)
SCENARIO_BY_ID = {item.scenario_id: item for item in SCENARIOS}


def _load_base_module() -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("task2_base_eval", BASE_EVALUATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载基础评测器: {BASE_EVALUATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return vars(module)


def _load_cmeee(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("CMeEE 文件必须是 JSON 数组")
    return payload


def _load_cmeie(path: Path) -> list[dict[str, Any]]:
    records = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError(f"CMeIE 第 {line_no} 行不是 JSON 对象")
        records.append(payload)
    return records


def _partition(records: list[dict[str, Any]], max_per_scenario: int = 0) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
    buckets = {item.scenario_id: [] for item in SCENARIOS}
    for record in records:
        text = str(record.get("text", "") or "")
        selected = "other"
        for scenario in SCENARIOS[:-1]:
            if any(term in text for term in scenario.terms):
                selected = scenario.scenario_id
                break
        buckets[selected].append(record)

    source_counts = {key: len(value) for key, value in buckets.items()}
    if max_per_scenario > 0:
        buckets = {key: value[:max_per_scenario] for key, value in buckets.items()}
    return buckets, source_counts


def _select_for_split(base: dict[str, Any], records: list[dict[str, Any]], split: str, calibration_size: int) -> list[dict[str, Any]]:
    selected, _ = base["_select_records"](records, split, calibration_size, 0)
    return selected


def _client_for_backend(base: dict[str, Any], backend: str, explicit_key: str = "") -> Any:
    if backend == "offline":
        return None
    api_key = explicit_key or os.environ.get("CCF_LLM_API_KEY", "") or base["LLM_API_KEY"]
    if not api_key:
        raise RuntimeError(f"backend={backend} 缺少 CCF_LLM_API_KEY；不会静默回退到 offline")
    return base["LLMClient"](
        base_url=os.environ.get("CCF_LLM_BASE_URL", "") or base["LLM_BASE_URL"],
        model=os.environ.get("CCF_LLM_MODEL", "") or base["LLM_MODEL"],
        api_key=api_key,
    )


def _summary_row(base: dict[str, Any], backend: str, scenario: Scenario, task: str, report: dict[str, Any]) -> dict[str, Any]:
    total = report["total"]
    performance = report["performance"]
    quality = report.get("quality") or {}
    cascade = report.get("cascade") or {}
    return {
        "场景代码": scenario.scenario_id,
        "场景": scenario.label,
        "后端": backend,
        "任务": task,
        "样本": report["evaluated_count"],
        "Gold": total["gold"],
        "预测": total["predicted"],
        "命中": total["true_positive"],
        "Precision": base["_fmt_percent"](total["precision"]),
        "Recall": base["_fmt_percent"](total["recall"]),
        "F1": base["_fmt_percent"](total["f1"]),
        "平均延迟(ms)": performance["avg_latency_ms"],
        "P50(ms)": performance["p50_latency_ms"],
        "P95(ms)": performance["p95_latency_ms"],
        "吞吐(records/s)": performance["throughput_records_per_second"],
        "重复预测": quality.get("duplicate_prediction_count", 0),
        "关系端点有效率": base["_fmt_percent"](quality.get("relation_endpoint_valid_rate", 0.0)) if task == "关系抽取" else "",
        "缺口段落": cascade.get("gap_segment_count", 0),
        "复核候选": cascade.get("reviewed_candidate_count", 0),
        "证据直通": cascade.get("auto_accepted_candidate_count", 0),
        "跳过候选": cascade.get("review_skipped_candidate_count", 0),
        "离线低可靠过滤": cascade.get("offline_filtered_candidate_count", 0),
        "拒绝候选": cascade.get("rejected_candidate_count", 0),
        "LLM新增": cascade.get("llm_added_count", 0),
        "LLM新增实体": cascade.get("llm_added_entity_count", 0),
        "LLM新增关系": cascade.get("llm_added_relation_count", 0),
        "LLM错误记录": cascade.get("records_with_llm_error", 0),
    }


def _aggregate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["后端"], row["任务"])].append(row)
    result = []
    for (backend, task), values in sorted(grouped.items()):
        gold = sum(int(item["Gold"]) for item in values)
        predicted = sum(int(item["预测"]) for item in values)
        true_positive = sum(int(item["命中"]) for item in values)
        seconds = sum(float(item["样本"]) / float(item["吞吐(records/s)"]) for item in values if float(item["吞吐(records/s)"]) > 0)
        count = sum(int(item["样本"]) for item in values)
        precision = true_positive / predicted if predicted else 0.0
        recall = true_positive / gold if gold else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        result.append({
            "后端": backend,
            "任务": task,
            "样本": count,
            "Gold": gold,
            "预测": predicted,
            "命中": true_positive,
            "Precision": f"{precision * 100:.2f}%",
            "Recall": f"{recall * 100:.2f}%",
            "F1": f"{f1 * 100:.2f}%",
            "总耗时(s)": round(seconds, 3),
            "吞吐(records/s)": round(count / seconds, 3) if seconds else 0.0,
        })
    return result


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else ["结果"]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _parse_demo_records(base: dict[str, Any], demo_dir: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    files = []
    for path in sorted(demo_dir.iterdir()):
        if not path.is_file():
            continue
        files.append({
            "file_name": path.name,
            "file_type": path.suffix.lstrip("."),
            "content": path.read_text(encoding="utf-8"),
        })
    records, stats = parse_files(files)
    return records, stats


def _eval_demo(base: dict[str, Any], records: list[dict[str, Any]], formats: dict[str, int], backend: str, kg_db: str, llm: Any) -> dict[str, Any]:
    started = time.perf_counter()
    entity_count = relation_count = triple_count = 0
    errors = []
    cascade = Counter()
    latencies = []
    for index, record in enumerate(records):
        text = str(record.get("text", "") or "")
        tick = time.perf_counter()
        try:
            bundle = base["extract_medical_knowledge"](text, backend=backend, kg_db_path=kg_db, llm=llm)
            entity_count += len(bundle.entities or [])
            relation_count += len(bundle.relations or [])
            triple_count += len(bundle.triples or [])
            for key in ("gap_segment_count", "gap_candidate_count", "reviewed_candidate_count", "auto_accepted_candidate_count", "review_skipped_candidate_count", "offline_filtered_candidate_count", "rejected_candidate_count", "llm_added_count", "llm_added_entity_count", "llm_added_relation_count"):
                cascade[key] += int(getattr(bundle, key, 0) or 0)
            if getattr(bundle, "llm_error", "") and len(errors) < 20:
                errors.append({"index": index, "error": str(bundle.llm_error)})
        except Exception as exc:
            errors.append({"index": index, "error": f"{type(exc).__name__}: {str(exc)[:240]}"})
        latencies.append((time.perf_counter() - tick) * 1000)
    elapsed = time.perf_counter() - started
    return {
        "backend": backend,
        "record_count": len(records),
        "source_formats": formats,
        "entity_count": entity_count,
        "relation_count": relation_count,
        "triple_count": triple_count,
        "elapsed_seconds": round(elapsed, 4),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 3) if latencies else 0.0,
        "p50_latency_ms": round(base["_percentile"](latencies, 50), 3),
        "p95_latency_ms": round(base["_percentile"](latencies, 95), 3),
        "throughput_records_per_second": round(len(records) / elapsed, 3) if elapsed else 0.0,
        "errors": errors,
        "error_count": len(errors),
        "cascade": dict(cascade),
    }


def _generate_charts(report: dict[str, Any], out_dir: Path, show: bool) -> list[str]:
    import matplotlib
    if not show:
        matplotlib.use("Agg")
    import matplotlib.font_manager as fm
    import matplotlib.pyplot as plt

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
    saved = []
    open_figures = []
    rows = report["scenario_rows"]
    backends = list(report["backends"])
    scenario_ids = [item.scenario_id for item in SCENARIOS if any(row["场景代码"] == item.scenario_id for row in rows)]
    scenario_labels = [SCENARIO_BY_ID[item].label for item in scenario_ids]

    fig, axes = plt.subplots(1, 2, figsize=(16, 6), dpi=180)
    for axis, task, title in zip(axes, ("实体识别", "关系抽取"), ("各场景实体 F1", "各场景关系 F1")):
        x = list(range(len(scenario_ids)))
        width = 0.78 / max(1, len(backends))
        for index, backend in enumerate(backends):
            values = []
            for scenario_id in scenario_ids:
                candidates = [row for row in rows if row["场景代码"] == scenario_id and row["后端"] == backend and row["任务"] == task]
                values.append(float(candidates[0]["F1"].rstrip("%")) if candidates else 0.0)
            bars = axis.bar([value - 0.39 + width * (index + 0.5) for value in x], values, width, label=backend)
            axis.bar_label(bars, fmt="%.1f", fontsize=7, padding=2)
        axis.set_xticks(x, scenario_labels, rotation=35, ha="right")
        axis.set_ylim(0, 100)
        axis.set_ylabel("F1（%）")
        axis.set_title(title)
        axis.grid(axis="y", alpha=0.25)
    axes[0].legend(frameon=False, ncol=max(1, len(backends)), loc="upper right")
    fig.tight_layout()
    path = out_dir / "task2_scenario_f1.png"
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    saved.append(str(path))
    if show:
        open_figures.append(fig)
    else:
        plt.close(fig)

    overall = report["backend_rows"]
    backend_cn = {"offline": "离线", "hybrid": "混合", "llm": "纯模型"}
    metric_cn = {"Precision": "精确率", "Recall": "召回率", "F1": "F1综合分"}
    backend_colors = {"offline": "#4F81BD", "hybrid": "#F28E2B", "llm": "#59A14F"}
    fig, axes = plt.subplots(1, 2, figsize=(14.5, 5.8), dpi=180, constrained_layout=True)
    for axis, task, title in zip(axes, ("实体识别", "关系抽取"), ("CMeEE 实体识别", "CMeIE 关系抽取")):
        x = list(range(3))
        available = [backend for backend in backends if any(row["后端"] == backend and row["任务"] == task for row in overall)]
        width = 0.72 / max(1, len(available))
        for index, backend in enumerate(available):
            item = next(row for row in overall if row["后端"] == backend and row["任务"] == task)
            values = [float(item[metric].rstrip("%")) for metric in ("Precision", "Recall", "F1")]
            positions = [value - 0.36 + width * (index + 0.5) for value in x]
            bars = axis.bar(positions, values, width, label=backend_cn.get(backend, backend), color=backend_colors.get(backend, "#9CA3AF"))
            axis.bar_label(bars, fmt="%.1f", fontsize=8, padding=2)
        axis.set_xticks(x, [metric_cn[item] for item in ("Precision", "Recall", "F1")])
        axis.set_ylim(0, 100)
        axis.set_ylabel("指标值（%）")
        axis.set_title(title, fontweight="bold")
        axis.grid(axis="y", alpha=0.22)
        axis.spines[["top", "right"]].set_visible(False)
    axes[0].legend(frameon=False, ncol=max(1, len(backends)), loc="upper right")
    path = out_dir / "task2_backend_prf.png"
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    saved.append(str(path))
    if show:
        open_figures.append(fig)
    else:
        plt.close(fig)

    comparison_available = all(backend in backends for backend in ("offline", "hybrid"))
    comparison_rows: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    if comparison_available:
        for task in ("实体识别", "关系抽取"):
            offline_row = next((row for row in overall if row["后端"] == "offline" and row["任务"] == task), None)
            hybrid_row = next((row for row in overall if row["后端"] == "hybrid" and row["任务"] == task), None)
            if offline_row and hybrid_row:
                comparison_rows[task] = (offline_row, hybrid_row)

    if comparison_rows:
        fig, axes = plt.subplots(1, len(comparison_rows), figsize=(14.5, 6.2), dpi=180, constrained_layout=True)
        if len(comparison_rows) == 1:
            axes = [axes]
        for axis, (task, (offline_row, hybrid_row)) in zip(axes, comparison_rows.items()):
            net_predictions = int(hybrid_row["预测"]) - int(offline_row["预测"])
            strict_hits = int(hybrid_row["命中"]) - int(offline_row["命中"])
            unmatched = max(0, net_predictions - strict_hits)
            bars = axis.bar(
                ["净新增严格命中", "净新增未命中标注"],
                [strict_hits, unmatched],
                color=["#59A14F", "#E15759"],
                width=0.58,
            )
            axis.bar_label(bars, fmt="%d", fontsize=11, fontweight="bold", padding=4)
            precision = strict_hits / net_predictions * 100 if net_predictions > 0 else 0.0
            recall_delta = float(hybrid_row["Recall"].rstrip("%")) - float(offline_row["Recall"].rstrip("%"))
            f1_delta = float(hybrid_row["F1"].rstrip("%")) - float(offline_row["F1"].rstrip("%"))
            axis.set_title("CMeEE 实体识别" if task == "实体识别" else "CMeIE 关系抽取", fontweight="bold")
            axis.set_ylabel("净新增结果数")
            axis.grid(axis="y", alpha=0.22)
            axis.spines[["top", "right"]].set_visible(False)
            axis.text(
                0.5,
                -0.18,
                f"净新增精确率 {precision:.1f}%   |   召回率 {recall_delta:+.2f}个百分点   |   F1 {f1_delta:+.2f}个百分点",
                transform=axis.transAxes,
                ha="center",
                va="top",
                fontsize=9,
            )
        path = out_dir / "task2_hybrid_increment_quality.png"
        fig.savefig(path, bbox_inches="tight", facecolor="white")
        saved.append(str(path))
        if show:
            open_figures.append(fig)
        else:
            plt.close(fig)

        fig, axes = plt.subplots(1, len(comparison_rows), figsize=(14.5, 5.2), dpi=180, constrained_layout=True)
        if len(comparison_rows) == 1:
            axes = [axes]
        for axis, (task, (offline_row, hybrid_row)) in zip(axes, comparison_rows.items()):
            metrics = ("Precision", "Recall", "F1")
            relative_changes = []
            for metric in metrics:
                before = float(offline_row[metric].rstrip("%"))
                after = float(hybrid_row[metric].rstrip("%"))
                relative_changes.append((after - before) / before * 100 if before else 0.0)
            colors = ["#59A14F" if value >= 0 else "#E15759" for value in relative_changes]
            bars = axis.bar([metric_cn[item] for item in metrics], relative_changes, color=colors, width=0.58)
            axis.bar_label(bars, labels=[f"{value:+.1f}%" for value in relative_changes], fontsize=10, padding=4)
            axis.axhline(0, color="#6B7280", linewidth=0.8)
            axis.set_title("CMeEE 实体识别" if task == "实体识别" else "CMeIE 关系抽取", fontweight="bold")
            axis.set_ylabel("混合相对离线的变化（%）")
            axis.grid(axis="y", alpha=0.22)
            axis.spines[["top", "right"]].set_visible(False)
        path = out_dir / "task2_hybrid_relative_gain.png"
        fig.savefig(path, bbox_inches="tight", facecolor="white")
        saved.append(str(path))
        if show:
            open_figures.append(fig)
        else:
            plt.close(fig)

    hybrid_rows = [row for row in report["cascade_rows"] if row["后端"] == "hybrid"]
    if hybrid_rows:
        labels = [row["场景"] for row in hybrid_rows]
        metrics = (
            ("复核候选", "reviewed_candidate_count", "#2563EB"),
            ("证据直通", "auto_accepted_candidate_count", "#7C3AED"),
            ("低可靠过滤", "offline_filtered_candidate_count", "#F59E0B"),
            ("拒绝候选", "rejected_candidate_count", "#DC2626"),
            ("新增关系", "llm_added_relation_count", "#059669"),
        )
        fig, axis = plt.subplots(figsize=(12, 5.5), dpi=180)
        x = list(range(len(labels)))
        width = 0.78 / len(metrics)
        for index, (label, key, color) in enumerate(metrics):
            offset = (index - (len(metrics) - 1) / 2) * width
            bars = axis.bar([value + offset for value in x], [row[key] for row in hybrid_rows], width, label=label, color=color)
            axis.bar_label(bars, fmt="%d", fontsize=8, padding=2)
        axis.set_xticks(x, labels, rotation=35, ha="right")
        axis.set_title("hybrid 级联候选路由")
        axis.grid(axis="y", alpha=0.25)
        axis.legend(frameon=False, ncol=3, loc="upper right")
        fig.tight_layout()
        path = out_dir / "task2_hybrid_cascade.png"
        fig.savefig(path, bbox_inches="tight", facecolor="white")
        saved.append(str(path))
        if show:
            open_figures.append(fig)
        else:
            plt.close(fig)

    demo = report.get("demo_operational") or []
    if demo:
        fig, axis = plt.subplots(figsize=(11, 5.5), dpi=180)
        labels = [row["backend"] for row in demo]
        x = list(range(len(labels)))
        width = 0.25
        for index, (key, label, color) in enumerate((("entity_count", "实体数", "#2563EB"), ("relation_count", "关系数", "#7C3AED"), ("triple_count", "三元组数", "#059669"))):
            bars = axis.bar([value + (index - 1) * width for value in x], [row[key] for row in demo], width, label=label, color=color)
            axis.bar_label(bars, fmt="%d", fontsize=8, padding=2)
        axis.set_xticks(x, labels)
        axis.set_title("真实四格式输入的抽取产物数量")
        axis.grid(axis="y", alpha=0.25)
        axis.legend(frameon=False, ncol=3, loc="upper right")
        fig.tight_layout()
        path = out_dir / "task2_demo_outputs.png"
        fig.savefig(path, bbox_inches="tight", facecolor="white")
        saved.append(str(path))
        if show:
            open_figures.append(fig)
        else:
            plt.close(fig)

    if show and open_figures:
        plt.show()
        for figure in open_figures:
            plt.close(figure)
    return saved


def _write_ppt_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# 任务二多场景评测 PPT 表格",
        "",
        f"- 评测划分：{report['split']}",
        f"- offline 评测口径：{report.get('offline_view', 'gated')}",
        f"- 结果性质：{report['scope_note']}",
        f"- 场景覆盖：{', '.join(item.label for item in SCENARIOS)}",
        "- CMeEE/CMeIE：严格实体位置和严格关系三元组匹配。",
        "- 糖尿病四格式：无人工金标准，仅用于真实输入吞吐、延迟和抽取产物统计。",
        "",
        "## 后端总体结果",
        "",
        "| 后端 | 任务 | 样本 | Gold | 预测 | 命中 | Precision | Recall | F1 | 吞吐(records/s) |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["backend_rows"]:
        lines.append("| {后端} | {任务} | {样本} | {Gold} | {预测} | {命中} | {Precision} | {Recall} | {F1} | {吞吐(records/s)} |".format(**row))
    lines.extend(["", "## 场景结果", "", "| 场景 | 后端 | 任务 | 样本 | Precision | Recall | F1 | P50(ms) | P95(ms) |", "|---|---|---|---:|---:|---:|---:|---:|---:|"])
    for row in report["scenario_rows"]:
        lines.append("| {场景} | {后端} | {任务} | {样本} | {Precision} | {Recall} | {F1} | {P50(ms)} | {P95(ms)} |".format(**row))
    lines.extend(["", "## 真实四格式输入", "", "| 后端 | 记录数 | 实体数 | 关系数 | 三元组数 | P50(ms) | P95(ms) | 吞吐(records/s) |", "|---|---:|---:|---:|---:|---:|---:|---:|"])
    for row in report.get("demo_operational") or []:
        lines.append("| {backend} | {record_count} | {entity_count} | {relation_count} | {triple_count} | {p50_latency_ms} | {p95_latency_ms} | {throughput_records_per_second} |".format(**row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass

    parser = argparse.ArgumentParser(description="任务二多医学场景与多后端评测")
    parser.add_argument("--cmeee", required=True, help="CMeEE JSON 开发集")
    parser.add_argument("--cmeie", required=True, help="CMeIE JSONL 开发集")
    parser.add_argument("--kg-db", required=True, help="当前离线抽取使用的知识图谱数据库")
    parser.add_argument("--demo-dir", default=str(DEFAULT_DEMO_DIR), help="本地四格式真实示例目录")
    parser.add_argument("--split", default="full_dev", choices=("holdout", "full_dev"))
    parser.add_argument("--cmeee-calibration-size", type=int, default=2500)
    parser.add_argument("--cmeie-calibration-size", type=int, default=1792)
    parser.add_argument("--max-per-scenario", type=int, default=0, help="每个场景最多评测多少条；0=全量")
    parser.add_argument("--backends", default="offline,hybrid,llm", help="逗号分隔：offline,hybrid,llm")
    parser.add_argument(
        "--offline-view",
        default="gated",
        choices=["gated", "raw"],
        help="offline 评测口径：gated=生产门禁后的结果，raw=原始候选；默认 gated",
    )
    parser.add_argument("--llm-key", default="", help="只在当前进程使用，不写入报告")
    parser.add_argument("--output", default=str(PROJECT_ROOT / "tmp" / "task2_scenarios" / "report.json"))
    parser.add_argument("--charts", default=str(PROJECT_ROOT / "tmp" / "task2_scenarios" / "assets"))
    parser.add_argument("--no-display", action="store_true", help="只保存图表，不弹出窗口")
    args = parser.parse_args()

    base = _load_base_module()
    cmeee_path = Path(args.cmeee).resolve()
    cmeie_path = Path(args.cmeie).resolve()
    kg_db_path = Path(args.kg_db).resolve()
    demo_dir = Path(args.demo_dir).resolve()
    if not cmeee_path.exists() or not cmeie_path.exists() or not kg_db_path.exists():
        parser.error("CMeEE、CMeIE 或知识图谱数据库不存在")
    if not demo_dir.exists():
        parser.error(f"真实示例目录不存在: {demo_dir}")

    backends = [item.strip() for item in args.backends.split(",") if item.strip()]
    invalid_backends = set(backends) - {"offline", "hybrid", "llm"}
    if invalid_backends:
        parser.error(f"不支持的后端: {sorted(invalid_backends)}")
    clients = {backend: _client_for_backend(base, backend, args.llm_key) for backend in backends}

    cmeee_records = _select_for_split(base, _load_cmeee(cmeee_path), args.split, args.cmeee_calibration_size)
    cmeie_records = _select_for_split(base, _load_cmeie(cmeie_path), args.split, args.cmeie_calibration_size)
    cmeee_buckets, cmeee_source_counts = _partition(cmeee_records, args.max_per_scenario)
    cmeie_buckets, cmeie_source_counts = _partition(cmeie_records, args.max_per_scenario)
    print(f"split={args.split} backends={','.join(backends)} max_per_scenario={args.max_per_scenario or 'all'}")
    scope_note = (
        f"每个场景最多 {args.max_per_scenario} 条，适合多后端接口、级联和录制演示，不作为独立泛化 F1"
        if args.max_per_scenario > 0
        else "每个场景全量，适合完整场景统计；hybrid/llm 会产生较多外部模型调用"
    )
    print(f"scope_note={scope_note}")
    print(f"CMeEE selected={len(cmeee_records)} scenarios={cmeee_source_counts}")
    print(f"CMeIE selected={len(cmeie_records)} scenarios={cmeie_source_counts}")

    scenario_rows = []
    cascade_rows = []
    for backend in backends:
        print(f"\n{'=' * 100}\nBACKEND {backend}\n{'=' * 100}")
        for scenario in SCENARIOS:
            print(f"\n[{scenario.label}] CMeEE={len(cmeee_buckets[scenario.scenario_id])} CMeIE={len(cmeie_buckets[scenario.scenario_id])}")
            entity_report = base["eval_entities"](
                cmeee_buckets[scenario.scenario_id],
                base["EvalConfig"](backend=backend, kg_db_path=str(kg_db_path), llm=clients[backend], requested_backend=backend, offline_view=args.offline_view),
            )
            relation_report = base["eval_relations"](
                cmeie_buckets[scenario.scenario_id],
                base["EvalConfig"](backend=backend, kg_db_path=str(kg_db_path), llm=clients[backend], requested_backend=backend, offline_view=args.offline_view),
            )
            entity_row = _summary_row(base, backend, scenario, "实体识别", entity_report)
            relation_row = _summary_row(base, backend, scenario, "关系抽取", relation_report)
            scenario_rows.extend((entity_row, relation_row))
            relation_cascade = relation_report.get("cascade") or {}
            cascade_rows.append({"场景代码": scenario.scenario_id, "场景": scenario.label, "后端": backend, **{key: relation_cascade.get(key, 0) for key in ("gap_segment_count", "reviewed_candidate_count", "auto_accepted_candidate_count", "offline_filtered_candidate_count", "rejected_candidate_count", "llm_added_entity_count", "llm_added_relation_count")}})
            print(f"  实体 F1={entity_row['F1']} P95={entity_row['P95(ms)']}ms | 关系 F1={relation_row['F1']} P95={relation_row['P95(ms)']}ms | LLM新增={relation_row['LLM新增']}")

    backend_rows = _aggregate_rows(scenario_rows)
    demo_records, demo_formats = _parse_demo_records(base, demo_dir)
    demo_rows = []
    print(f"\n{'=' * 100}\nREAL FOUR-FORMAT INPUT | records={len(demo_records)} formats={demo_formats}\n{'=' * 100}")
    for backend in backends:
        result = _eval_demo(base, demo_records, demo_formats, backend, str(kg_db_path), clients[backend])
        demo_rows.append(result)
        print(f"{backend}: entities={result['entity_count']} relations={result['relation_count']} triples={result['triple_count']} P95={result['p95_latency_ms']}ms throughput={result['throughput_records_per_second']} records/s errors={result['error_count']}")

    report = {
        "schema_version": 1,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "split": args.split,
        "backends": backends,
        "offline_view": args.offline_view,
        "max_per_scenario": args.max_per_scenario,
        "scope_note": scope_note,
        "source_counts": {"cmeee": cmeee_source_counts, "cmeie": cmeie_source_counts},
        "evaluated_counts": {"cmeee": {key: len(value) for key, value in cmeee_buckets.items()}, "cmeie": {key: len(value) for key, value in cmeie_buckets.items()}},
        "scenario_rows": scenario_rows,
        "backend_rows": backend_rows,
        "cascade_rows": cascade_rows,
        "demo_operational": demo_rows,
        "dataset": {"cmeee": str(cmeee_path), "cmeie": str(cmeie_path), "kg_db": str(kg_db_path), "demo_dir": str(demo_dir)},
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    chart_paths = _generate_charts(report, Path(args.charts), show=not args.no_display)
    out_dir = Path(args.charts)
    _write_csv(out_dir / "task2_scenario_summary.csv", scenario_rows)
    _write_csv(out_dir / "task2_backend_summary.csv", backend_rows)
    _write_csv(out_dir / "task2_hybrid_cascade.csv", cascade_rows)
    _write_csv(out_dir / "task2_real_demo_operations.csv", demo_rows)
    markdown_path = out_dir / "task2_scenario_tables.md"
    _write_ppt_markdown(report, markdown_path)
    print(f"\nreport={output_path}")
    print(f"charts={len(chart_paths)} tables=5 output_dir={out_dir}")
    for path in chart_paths:
        print(f"  artifact={path}")
    for path in (out_dir / "task2_scenario_summary.csv", out_dir / "task2_backend_summary.csv", out_dir / "task2_hybrid_cascade.csv", out_dir / "task2_real_demo_operations.csv", markdown_path):
        print(f"  artifact={path}")


if __name__ == "__main__":
    main()
