from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter


OUTPUT = Path(__file__).with_name("runtime_relation_distribution.pdf")

LABELS = [
    "药物",
    "症状",
    "检查",
    "疾病分类",
    "治疗",
    "就诊科室",
    "并发症",
    "病因",
    "易感人群",
    "预防",
]
VALUES = [220_227, 63_110, 42_799, 25_587, 22_098, 16_796, 13_662, 10_864, 9_158, 9_129]


def main() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "font.size": 9,
        }
    )

    labels = list(reversed(LABELS))
    values = list(reversed(VALUES))
    fig, ax = plt.subplots(figsize=(7.1, 3.8), constrained_layout=True)
    bars = ax.barh(
        labels,
        values,
        color="white",
        edgecolor="black",
        linewidth=0.8,
    )
    for index, bar in enumerate(bars):
        bar.set_hatch("////" if index % 2 == 0 else "....")

    ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{int(value):,}"))
    ax.set_xlabel("三元组数量")
    ax.grid(axis="x", color="0.75", linewidth=0.5, linestyle="--")
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    limit = max(values) * 1.17
    ax.set_xlim(0, limit)
    for bar, value in zip(bars, values):
        ax.text(
            value + max(values) * 0.012,
            bar.get_y() + bar.get_height() / 2,
            f"{value:,}",
            va="center",
            ha="left",
            fontsize=8,
            color="black",
        )

    fig.savefig(OUTPUT, bbox_inches="tight")


if __name__ == "__main__":
    main()
