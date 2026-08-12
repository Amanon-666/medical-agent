# -*- coding: utf-8 -*-
"""任务一算子评测图表。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.font_manager import FontProperties


COLORS = ("#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00")


def _font() -> FontProperties:
    for family in (
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "WenQuanYi Zen Hei",
    ):
        properties = FontProperties(family=family)
        try:
            font_manager.findfont(properties, fallback_to_default=False)
        except ValueError:
            continue
        return properties
    return FontProperties()


def _save(fig: plt.Figure, output_dir: Path, stem: str) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for suffix in ("png", "svg", "pdf"):
        path = output_dir / f"{stem}.{suffix}"
        fig.savefig(path, dpi=300 if suffix == "png" else None, bbox_inches="tight", facecolor="white")
        paths[suffix] = str(path)
    plt.close(fig)
    return paths


def _labels(ax, bars, font: FontProperties) -> None:
    for bar in bars:
        value = bar.get_height()
        ax.annotate(
            f"{value:.1%}",
            (bar.get_x() + bar.get_width() / 2, value),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=7.5,
            fontproperties=font,
        )


def render_plots(
    summary: dict[str, Any],
    baseline: dict[str, Any],
    output_dir: Path,
) -> dict[str, dict[str, str]]:
    font = _font()
    plt.rcParams["axes.unicode_minus"] = False
    formats = list(summary["by_format"])
    x = list(range(len(formats)))
    metrics = (
        ("cleaning_f1", "清洗 F1"),
        ("term_accuracy", "术语准确率"),
        ("field_accuracy", "字段准确率"),
        ("record_accuracy", "记录准确率"),
    )

    fig, ax = plt.subplots(figsize=(10.8, 5.9), constrained_layout=True)
    width = 0.19
    for index, (key, label) in enumerate(metrics):
        bars = ax.bar(
            [value + (index - 1.5) * width for value in x],
            [summary["by_format"][fmt][key] for fmt in formats],
            width,
            label=label,
            color=COLORS[index],
        )
        _labels(ax, bars, font)
    overall = summary["overall"]
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("比例", fontproperties=font)
    ax.set_title(
        f"任务一多格式算子清洗质量（{overall['files_total']} 个文件 / {overall['records_expected']} 条记录）",
        fontproperties=font,
        fontsize=14,
    )
    ax.set_xticks(x, [fmt.upper() for fmt in formats], fontproperties=font)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(prop=font, frameon=False, ncol=4, loc="lower center", bbox_to_anchor=(0.5, -0.18))
    quality = _save(fig, output_dir, "task1_operator_quality_v2")

    compare_metrics = (
        ("fixed_noise_recall", "固定噪声"),
        ("learned_noise_recall", "已学习噪声"),
        ("unseen_noise_recall", "未见噪声"),
        ("noise_recall", "全部噪声"),
    )
    labels = [f"{label}\n(n={summary['overall'][key.replace('_recall', '_expected')]})" for key, label in compare_metrics]
    positions = list(range(len(labels)))
    base = baseline["overall"]
    learned = summary["overall"]
    fig, ax = plt.subplots(figsize=(9.6, 5.6), constrained_layout=True)
    base_bars = ax.bar(
        [value - 0.19 for value in positions],
        [base[key] for key, _ in compare_metrics],
        0.38,
        label="基础规则",
        color="#8FAADC",
    )
    learned_bars = ax.bar(
        [value + 0.19 for value in positions],
        [learned[key] for key, _ in compare_metrics],
        0.38,
        label="加入噪声学习规则",
        color="#009E73",
    )
    _labels(ax, base_bars, font)
    _labels(ax, learned_bars, font)
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("召回率", fontproperties=font)
    ax.set_title("噪声学习效果", fontproperties=font, fontsize=14)
    ax.set_xticks(positions, labels, fontproperties=font)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(prop=font, frameon=False, loc="lower center", bbox_to_anchor=(0.5, -0.18), ncol=2)
    ablation = _save(fig, output_dir, "task1_noise_learning_ablation")

    return {"operator_quality": quality, "noise_learning_ablation": ablation}
