"""生成任务三 NL2SQL 的 CSV 结果和可复现图表。"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "evaluation" / "task3"
DATA = BASE / "results" / "benchmark_metrics.json"
FIG = BASE / "figures"
TARGET_PERCENT = 85


def configure_font() -> None:
    """优先选择常见中文字体，保证本地生成的图表不出现方框。"""

    installed = {font.name for font in font_manager.fontManager.ttflist}
    for name in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC"):
        if name in installed:
            plt.rcParams["font.sans-serif"] = [name]
            break
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["svg.hashsalt"] = "mediflow-task3"


def format_percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def save_figure(fig: plt.Figure, name: str) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{name}.png", dpi=220, bbox_inches="tight", facecolor="white")
    svg_path = FIG / f"{name}.svg"
    fig.savefig(
        svg_path,
        bbox_inches="tight",
        facecolor="white",
        metadata={"Date": None},
    )
    # Matplotlib 会在 SVG 路径的换行处保留空格；清理后可通过仓库的空白检查，
    # 不改变图形内容，也让生成的 SVG 更适合进入版本库。
    svg_lines = svg_path.read_text(encoding="utf-8").splitlines()
    svg_path.write_text("\n".join(line.rstrip() for line in svg_lines) + "\n", encoding="utf-8")
    plt.close(fig)


def target_handle(target_percent: float) -> Line2D:
    return Line2D(
        [0],
        [0],
        color="#DC2626",
        linestyle="--",
        linewidth=1.8,
        label=f"达标线：{target_percent:.0f}%",
    )


def add_target_line(ax: plt.Axes, target_percent: float) -> None:
    """只在坐标轴内画线，图例统一放到坐标轴外。"""

    ax.axhline(target_percent, color="#DC2626", linestyle="--", linewidth=1.6, zorder=1)


def style_axes(ax: plt.Axes) -> None:
    ax.set_ylim(0, 108)
    ax.set_ylabel("执行准确率（%）", fontsize=12)
    ax.grid(axis="y", alpha=0.22, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def write_result_csv(metrics: dict) -> None:
    out = BASE / "results"
    out.mkdir(parents=True, exist_ok=True)

    with (out / "overall_accuracy.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["评测阶段", "数据集", "答对题数", "总题数", "执行准确率", "结果性质", "口径说明"])
        for run in metrics["runs"]:
            writer.writerow(
                [
                    run["name"],
                    run["split"],
                    run["correct"],
                    run["total"],
                    format_percent(run["accuracy"]),
                    run["stage"],
                    run["description"],
                ]
            )

    with (out / "test_accuracy_by_type.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["题型", "题数", "设计基线正确", "设计基线准确率", "回归复核正确", "回归复核准确率"])
        for row in metrics["test_by_type"]:
            writer.writerow(
                [
                    row["type"],
                    row["total"],
                    row["design_baseline_correct"],
                    format_percent(row["design_baseline_correct"] / row["total"]),
                    row["regression_correct"],
                    format_percent(row["regression_correct"] / row["total"]),
                ]
            )

def make_overall_chart(metrics: dict) -> None:
    runs = metrics["runs"]
    target_percent = metrics.get("target_accuracy", TARGET_PERCENT / 100) * 100
    labels = [run["chart_name"] for run in runs]
    values = [run["accuracy"] * 100 for run in runs]
    colors = ["#94A3B8", "#2563EB", "#F59E0B", "#16A34A"]
    positions = list(range(len(runs)))

    fig, ax = plt.subplots(figsize=(11.8, 6.8))
    fig.subplots_adjust(left=0.09, right=0.98, bottom=0.22, top=0.77)
    bars = ax.bar(positions, values, color=colors, width=0.62, zorder=2)
    add_target_line(ax, target_percent)
    style_axes(ax)
    ax.set_xticks(positions, labels, fontsize=12)
    ax.set_title("任务三 NL2SQL：能力建立与泛化检验", fontsize=17, pad=24)
    ax.axvline(1.5, color="#CBD5E1", linewidth=1.0, zorder=0)
    ax.text(
        0.5,
        -0.16,
        "开发集：能力建立",
        transform=ax.get_xaxis_transform(),
        ha="center",
        va="top",
        fontsize=11,
        color="#475569",
    )
    ax.text(
        2.5,
        -0.16,
        "测试集：泛化检验",
        transform=ax.get_xaxis_transform(),
        ha="center",
        va="top",
        fontsize=11,
        color="#475569",
    )
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + 1.5,
            f"{value:.1f}%",
            ha="center",
            va="bottom",
            fontsize=12,
            fontweight="bold",
        )
    fig.legend(
        handles=[target_handle(target_percent)],
        loc="upper center",
        bbox_to_anchor=(0.5, 0.93),
        frameon=False,
        fontsize=11,
    )
    save_figure(fig, "task3_nl2sql_overall_accuracy_zh")


def make_type_chart(metrics: dict) -> None:
    rows = metrics["test_by_type"]
    target_percent = metrics.get("target_accuracy", TARGET_PERCENT / 100) * 100
    labels = [row["type"] for row in rows]
    baseline = [row["design_baseline_correct"] / row["total"] * 100 for row in rows]
    regression = [row["regression_correct"] / row["total"] * 100 for row in rows]
    positions = list(range(len(rows)))
    width = 0.34

    fig, ax = plt.subplots(figsize=(12.2, 6.8))
    fig.subplots_adjust(left=0.08, right=0.99, bottom=0.24, top=0.76)
    baseline_bars = ax.bar(
        [position - width / 2 for position in positions],
        baseline,
        width,
        color="#F59E0B",
        zorder=2,
    )
    regression_bars = ax.bar(
        [position + width / 2 for position in positions],
        regression,
        width,
        color="#16A34A",
        zorder=2,
    )
    add_target_line(ax, target_percent)
    style_axes(ax)
    ax.set_xticks(positions, labels, fontsize=10)
    ax.set_title("任务三：不同题型的能力覆盖变化", fontsize=17, pad=24)
    for bars in (baseline_bars, regression_bars):
        for bar in bars:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1.2,
                f"{bar.get_height():.0f}%",
                ha="center",
                va="bottom",
                fontsize=8.5,
            )
    fig.legend(
        handles=[
            Patch(facecolor="#F59E0B", label="设计基线"),
            Patch(facecolor="#16A34A", label="回归复核"),
            target_handle(target_percent),
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, 0.93),
        ncol=3,
        frameon=False,
        fontsize=10.5,
    )
    save_figure(fig, "task3_nl2sql_accuracy_by_type_zh")


def main() -> None:
    metrics = json.loads(DATA.read_text(encoding="utf-8-sig"))
    configure_font()
    write_result_csv(metrics)
    make_overall_chart(metrics)
    make_type_chart(metrics)
    print(BASE / "results")
    print(FIG)


if __name__ == "__main__":
    main()
