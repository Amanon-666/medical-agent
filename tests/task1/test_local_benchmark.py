# -*- coding: utf-8 -*-
"""任务一算子级压力评测契约。"""

from evaluation.task1.fixtures import build_corpus
from evaluation.task1.run_benchmark import run


def test_stress_corpus_has_enough_files_and_records(tmp_path):
    cases, manifest = build_corpus(tmp_path / "input")

    assert len(cases) == 80
    assert sum(case.expected_records for case in cases) == 260
    assert {case.file_format for case in cases} == {"txt", "csv", "json", "jsonl"}
    assert all(sum(case.file_format == fmt for case in cases) == 20 for fmt in ("txt", "csv", "json", "jsonl"))
    assert sum(len(case.semantic_noise_labels) for case in cases) > 0
    assert sum(len(case.learned_noise_labels) for case in cases) > 0
    assert len({item for case in cases for item in case.unseen_noise_labels}) >= 5
    assert manifest["schema_version"] == "task1-local-gold-v3"


def test_full_operator_benchmark_and_noise_learning_ablation(tmp_path):
    code, report = run(tmp_path / "run", strict=True)
    learned = report["learned"]["summary"]["overall"]
    baseline = report["baseline"]["summary"]["overall"]
    learning = report["knowledge_base"]["learning"]

    assert code == 0
    assert learning["promoted_count"] == 3
    assert learning["network_calls"] == 0
    assert learned["semantic_noise_recall"] > baseline["semantic_noise_recall"]
    assert learned["learned_noise_recall"] == 1.0
    assert learned["unseen_noise_recall"] <= 0.10
    assert learned["noise_recall"] >= 0.93
    assert learned["term_accuracy"] >= 0.95
    assert learned["semantic_preservation"] >= 0.99
    assert learned["field_accuracy"] >= 0.93
    assert learned["structure_pass_rate"] == 1.0
    assert report["scope"]["datamate_or_nexent"] is False
    assert report["artifacts"]["figures"]["operator_quality"]["png"].endswith(".png")
