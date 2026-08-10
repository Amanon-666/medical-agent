# -*- coding: utf-8 -*-
"""运行任务一算子级压力评测并生成图表。"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
from pathlib import Path
from typing import Any

from .datamate_emulator import OperatorRuntime
from .fixtures import CorpusCase, build_corpus
from .knowledge_base import build_evaluation_kb
from .metrics import build_markdown_report, evaluate_case, summarize_case_metrics, write_metrics_csv
from .plotting import render_plots
from .stress_fixtures import LEARNED_NOISE


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN_DIR = PROJECT_ROOT / "evaluation" / "task1" / "runs" / "operator_v2_latest"


def _distill_repeated_segments(*args, **kwargs):
    path = PROJECT_ROOT / "operators" / "llm_noise_filter" / "noise_distiller.py"
    spec = importlib.util.spec_from_file_location("task1_noise_distiller", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load noise distiller: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.distill_repeated_segments(*args, **kwargs)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _teacher_clean(text: str) -> str:
    lines = []
    for line in str(text).splitlines():
        cleaned = line
        for phrase in LEARNED_NOISE:
            cleaned = cleaned.replace(phrase, "")
        if cleaned.strip():
            lines.append(cleaned.strip())
    return "\n".join(lines)


def _train_noise_rules(kb_dir: Path, work_dir: Path) -> dict[str, Any]:
    input_dir = work_dir / "input"
    output_dir = work_dir / "output"
    runtime_dir = work_dir / "runtime"
    input_dir.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        (runtime_dir / f"noise_log.db{suffix}").unlink(missing_ok=True)
    runtime = OperatorRuntime(
        PROJECT_ROOT,
        kb_dir,
        runtime_dir,
        noise_teacher=_teacher_clean,
    )
    observations = []
    for phrase_index, phrase in enumerate(LEARNED_NOISE):
        for repeat in range(4):
            case_id = f"learn-{phrase_index + 1}-{repeat + 1}"
            file_name = f"{case_id}.txt"
            input_path = input_dir / file_name
            input_path.write_text(
                f"患者胸闷，血压 132/84 mmHg，否认发热。\n{phrase}",
                encoding="utf-8",
            )
            execution = runtime.process(
                case_id=case_id,
                file_name=file_name,
                file_path=input_path,
                file_format="txt",
                output_path=output_dir / file_name,
            )
            observations.append(execution)
    distilled = _distill_repeated_segments(
        runtime_dir / "noise_log.db",
        kb_dir / "noise_kb.db",
        min_occurrences=3,
    )
    distilled["training_files"] = len(observations)
    distilled["network_calls"] = 0
    return distilled


def _run_cases(
    cases: list[CorpusCase],
    input_dir: Path,
    output_dir: Path,
    kb_dir: Path,
    runtime_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    runtime = OperatorRuntime(PROJECT_ROOT, kb_dir, runtime_dir)
    executions = []
    metrics = []
    for case in cases:
        output_path = output_dir / case.file_name
        try:
            execution = runtime.process(
                case_id=case.case_id,
                file_name=case.file_name,
                file_path=input_dir / case.file_name,
                file_format=case.file_format,
                output_path=output_path,
            )
        except Exception as exc:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("", encoding="utf-8")
            execution = {
                "case_id": case.case_id,
                "file_name": case.file_name,
                "file_format": case.file_format,
                "output_path": str(output_path),
                "status": "FAILED",
                "elapsed_ms": None,
                "error": f"{type(exc).__name__}: {exc}",
            }
        executions.append(execution)
        metrics.append(evaluate_case(case, output_path, execution))
    return executions, metrics


def _quality_gate(summary: dict[str, Any]) -> bool:
    overall = summary["overall"]
    thresholds = summary["thresholds"]
    return (
        overall["files_failed"] == 0
        and overall["noise_recall"] >= thresholds["noise_recall"]
        and overall["term_accuracy"] >= thresholds["term_accuracy"]
        and overall["semantic_preservation"] >= thresholds["semantic_preservation"]
        and overall["field_accuracy"] >= thresholds["field_accuracy"]
        and overall["structure_pass_rate"] >= thresholds["structure_pass_rate"]
    )


def run(run_dir: Path, strict: bool = False) -> tuple[int, dict[str, Any]]:
    input_dir = run_dir / "input"
    kb_root = run_dir / "knowledge_base"
    base_kb = kb_root / "base"
    learned_kb = kb_root / "learned"
    results_dir = run_dir / "results"
    figures_dir = run_dir / "figures"
    run_dir.mkdir(parents=True, exist_ok=True)

    cases, corpus_manifest = build_corpus(input_dir)
    kb_metadata = build_evaluation_kb(base_kb)
    learned_kb.mkdir(parents=True, exist_ok=True)
    shutil.copy2(base_kb / "term_kb.db", learned_kb / "term_kb.db")
    shutil.copy2(base_kb / "noise_kb.db", learned_kb / "noise_kb.db")
    learning = _train_noise_rules(learned_kb, run_dir / "learning")

    base_executions, base_metrics = _run_cases(
        cases,
        input_dir,
        run_dir / "outputs" / "base",
        base_kb,
        run_dir / "runtime" / "base",
    )
    learned_executions, learned_metrics = _run_cases(
        cases,
        input_dir,
        run_dir / "outputs" / "learned",
        learned_kb,
        run_dir / "runtime" / "learned",
    )
    baseline_summary = summarize_case_metrics(base_metrics)
    summary = summarize_case_metrics(learned_metrics)
    quality_gate_pass = _quality_gate(summary)
    figures = render_plots(summary, baseline_summary, figures_dir)

    artifacts = {
        "input_dir": str(input_dir),
        "gold_manifest": str(input_dir / "gold_manifest.json"),
        "base_outputs": str(run_dir / "outputs" / "base"),
        "learned_outputs": str(run_dir / "outputs" / "learned"),
        "metrics_json": str(results_dir / "benchmark_metrics.json"),
        "metrics_csv": str(results_dir / "benchmark_metrics.csv"),
        "markdown_report": str(results_dir / "benchmark_results_zh.md"),
        "figures": figures,
    }
    report = {
        "benchmark": "task1_local_operator_stress_v3",
        "schema_version": "task1-operator-benchmark-v3",
        "scope": {
            "operator_execution": "项目实际自定义算子源码，本地直接执行",
            "datamate_or_nexent": False,
            "llm_network_calls": 0,
            "covered_formats": ["txt", "csv", "json", "jsonl"],
            "result_role": "固定生成压力语料上的工程回归，不是官方盲测成绩",
        },
        "corpus": corpus_manifest,
        "knowledge_base": {
            **kb_metadata,
            "learning": learning,
        },
        "baseline": {
            "executions": base_executions,
            "case_metrics": base_metrics,
            "summary": baseline_summary,
        },
        "learned": {
            "executions": learned_executions,
            "case_metrics": learned_metrics,
            "summary": summary,
        },
        "quality_gate_pass": quality_gate_pass,
        "artifacts": artifacts,
    }
    _write_json(results_dir / "benchmark_metrics.json", report)
    write_metrics_csv(summary, results_dir / "benchmark_metrics.csv")
    (results_dir / "benchmark_results_zh.md").write_text(
        build_markdown_report(summary, baseline_summary, learning),
        encoding="utf-8",
    )

    compact = {
        "quality_gate_pass": quality_gate_pass,
        "files": summary["overall"]["files_total"],
        "records": summary["overall"]["records_expected"],
        "cleaning_f1": summary["overall"]["cleaning_f1"],
        "term_accuracy": summary["overall"]["term_accuracy"],
        "field_accuracy": summary["overall"]["field_accuracy"],
        "semantic_preservation": summary["overall"]["semantic_preservation"],
        "semantic_noise_recall_before": baseline_summary["overall"]["semantic_noise_recall"],
        "semantic_noise_recall_after": summary["overall"]["semantic_noise_recall"],
        "learned_noise_recall_after": summary["overall"]["learned_noise_recall"],
        "unseen_noise_recall_after": summary["overall"]["unseen_noise_recall"],
        "learned_rules": learning["promoted_count"],
        "report": str(results_dir / "benchmark_results_zh.md"),
    }
    print("TASK1_OPERATOR_BENCHMARK_V2")
    print(json.dumps(compact, ensure_ascii=False, indent=2))
    return (0 if quality_gate_pass or not strict else 2), report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    code, _ = run(args.run_dir.resolve(), strict=args.strict)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
