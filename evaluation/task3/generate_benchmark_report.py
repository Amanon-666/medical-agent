"""生成任务三 NL2SQL 中文表格与图表。"""
from __future__ import annotations
import csv, json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/"evaluation"/"task3"
DATA=BASE/"results"/"benchmark_metrics.json"
FIG=BASE/"figures"
def font():
    names={f.name for f in font_manager.fontManager.ttflist}
    for name in ("Microsoft YaHei","SimHei","Noto Sans CJK SC","Source Han Sans SC"):
        if name in names:
            plt.rcParams["font.sans-serif"]=[name]; break
    plt.rcParams["axes.unicode_minus"]=False
    plt.rcParams["svg.hashsalt"]="mediflow-task3"
def pct(v): return f"{v*100:.1f}%"
def save(fig,name):
    FIG.mkdir(parents=True,exist_ok=True)
    fig.savefig(FIG/f"{name}.png",dpi=220,bbox_inches="tight",facecolor="white")
    fig.savefig(FIG/f"{name}.svg",bbox_inches="tight",facecolor="white",metadata={"Date": None})
    plt.close(fig)
def main():
    m=json.loads(DATA.read_text(encoding="utf-8-sig")); out=BASE/"results"; font()
    with (out/"overall_accuracy.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f); w.writerow(["评测阶段","数据集","答对题数","总题数","执行准确率","是否盲测"])
        for r in m["runs"]: w.writerow([r["name"],r["split"],r["correct"],r["total"],pct(r["accuracy"]),"是" if r["blind"] else "否"])
    with (out/"test_accuracy_by_type.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f); w.writerow(["题型","题数","首次正确","首次准确率","回归正确","回归准确率"])
        for r in m["test_by_type"]: w.writerow([r["type"],r["total"],r["first_correct"],pct(r["first_correct"]/r["total"]),r["final_correct"],pct(r["final_correct"]/r["total"])])
    lines=["# 任务三 NL2SQL 评测结果表","","## 总体结果","","| 评测阶段 | 数据集 | 答对/总数 | 执行准确率 | 性质 |","|---|---:|---:|---:|---|"]
    for r in m["runs"]: lines.append(f"| {r['name']} | {r['split']} | {r['correct']}/{r['total']} | {pct(r['accuracy'])} | {'首次冻结运行（盲测）' if r['blind'] else '开发或迭代后回归'} |")
    lines += ["","## 测试集分题型结果","","| 题型 | 题数 | 首次准确率 | 回归准确率 |","|---|---:|---:|---:|"]
    for r in m["test_by_type"]: lines.append(f"| {r['type']} | {r['total']} | {pct(r['first_correct']/r['total'])} | {pct(r['final_correct']/r['total'])} |")
    lines += ["","注：测试集迭代后回归已使用首次失败信息，不属于盲测成绩。"]
    (out/"benchmark_results_zh.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    runs=m["runs"]; labels=[r["name"] for r in runs]; vals=[r["accuracy"]*100 for r in runs]
    fig,ax=plt.subplots(figsize=(11,6.2)); bars=ax.bar(labels,vals,color=["#94A3B8","#2563EB","#F59E0B","#16A34A"],width=.62)
    ax.axhline(85,color="#DC2626",ls="--",lw=1.6,label="目标线 85%"); ax.set_ylim(0,105); ax.set_ylabel("执行准确率（%）"); ax.set_title("任务三 NL2SQL 各阶段执行准确率"); ax.grid(axis="y",alpha=.22); ax.legend(); ax.tick_params(axis="x",rotation=12)
    for b,v in zip(bars,vals): ax.text(b.get_x()+b.get_width()/2,v+1.5,f"{v:.1f}%",ha="center",weight="bold")
    fig.tight_layout(); save(fig,"task3_nl2sql_overall_accuracy_zh")
    rows=m["test_by_type"]; labels=[r["type"] for r in rows]; first=[r["first_correct"]/r["total"]*100 for r in rows]; final=[r["final_correct"]/r["total"]*100 for r in rows]; x=list(range(len(rows))); width=.36
    fig,ax=plt.subplots(figsize=(11.5,6.4)); a=ax.bar([i-width/2 for i in x],first,width,label="首次冻结运行",color="#F59E0B"); b=ax.bar([i+width/2 for i in x],final,width,label="迭代后回归",color="#16A34A")
    ax.axhline(85,color="#DC2626",ls="--",lw=1.4,label="目标线 85%"); ax.set_xticks(x,labels); ax.set_ylim(0,108); ax.set_ylabel("执行准确率（%）"); ax.set_title("测试集各题型执行准确率对比"); ax.grid(axis="y",alpha=.22); ax.legend(ncol=3,loc="upper center")
    for bars in (a,b):
        for bar in bars: ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+1.2,f"{bar.get_height():.0f}%",ha="center",fontsize=8)
    fig.tight_layout(); save(fig,"task3_nl2sql_accuracy_by_type_zh")
    print(out); print(FIG)
if __name__=="__main__": main()
