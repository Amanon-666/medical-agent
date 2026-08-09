# 任务三 NL2SQL 评测与复现

本目录使用真实 `task3_analytics.db` 评测自然语言转 SQL。评测比较 SQL 执行结果，不比较 SQL 字符串。

## 数据与指标

- `nl2sql_dev.jsonl`：40 道开发题。
- `nl2sql_test.jsonl`：93 道测试题。`r`n- `benchmark_manifest.json`：固定数据库大小、SHA-256、表和视图数量。
- 主指标：保留重复次数的执行结果一致率。
- 同时报告有序完全一致率和去重集合一致率。

2026-08-09 的测试集首次冻结运行后，失败题型已被查看。因此之后的测试集成绩只能称为“回归成绩”，不能称为盲测成绩。

## 运行评测

```powershell
python evaluation/task3/run_benchmark.py --split dev --engine nl2sql
python evaluation/task3/run_benchmark.py --split test --engine nl2sql
```

评测需要分析数据库和 `.env.runtime` 中的模型配置。脚本会先核对数据库 SHA-256；当前要求为 `157277244085a64cf5d953d89e2416eef969d5858435ff351682631fc591a757`。版本不匹配时评测会停止。自洽性检查可使用 `--engine gold`。

## 生成中文表格和图表

```powershell
python evaluation/task3/generate_benchmark_report.py
```

输出位于 `results/` 和 `figures/`，包含中文 Markdown、CSV、PNG 和 SVG。

## 当前结果

| 阶段 | 答对/总数 | 执行准确率 | 说明 |
|---|---:|---:|---|
| 开发集基线 | 25/40 | 62.5% | 优化前基线 |
| 开发集优化后 | 38/40 | 95.0% | 开发集验收 |
| 测试集首次冻结运行 | 57/93 | 61.3% | 查看失败前的盲测 |
| 测试集迭代后回归 | 89/93 | 95.7% | 不属于盲测 |

知识库解释能力不计入 NL2SQL 准确率，应另建召回和引用评测。
