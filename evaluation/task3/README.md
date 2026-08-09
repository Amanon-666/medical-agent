# 任务三 NL2SQL 评测与复现

本目录使用固定版本的 `task3_analytics.db` 评测自然语言转 SQL。每道题都有自然语言问题、Gold SQL 和 Gold Result；评测比较 SQL 执行结果，不比较 SQL 字符串。

## 数据与指标

- `nl2sql_dev.jsonl`：40 道开发题，用于方案设计与迭代；
- `nl2sql_test.jsonl`：93 道预留测试题，先建立设计基线，再进行回归复核；
- `benchmark_manifest.json`：固定数据库大小、SHA-256、表和视图数量；
- `schema_snapshot.json`：构建时保存的结构快照；
- 主指标：保留重复行的执行结果一致率；
- 辅助指标：有序完全一致率和去重集合一致率；
- 达标线：执行准确率 ≥ 85%。

设计基线表示“方案分析前对预留测试题的首次测量”，用于记录系统从哪里起步。回归复核使用了设计基线暴露的失败题型，因此用于验证修正覆盖，不能替代独立泛化成绩。

## 运行评测

```powershell
python evaluation/task3/run_benchmark.py --split dev --engine nl2sql
python evaluation/task3/run_benchmark.py --split test --engine nl2sql
```

评测需要分析数据库和 `.env.runtime` 中的模型配置。脚本会先核对数据库 SHA-256；当前要求为：

`157277244085a64cf5d953d89e2416eef969d5858435ff351682631fc591a757`

版本不匹配时评测会停止。仅检查评测器和 Gold Result 自洽性时，可使用 `--engine gold`。

## 生成中文表格和图表

```powershell
python evaluation/task3/generate_benchmark_report.py
```

输出位于 `results/` 和 `figures/`，包括：

- 中文 Markdown 结果表；
- 可用 Excel 打开的 UTF-8 CSV；
- 中文 PNG 和 SVG 图表。

总体图将结果分成“开发集：能力建立”和“测试集：泛化检验”两组，达标线图例放在绘图区外，避免遮挡柱状图。

## 当前结果

| 阶段 | 答对/总数 | 执行准确率 | 说明 |
|---|---:|---:|---|
| 开发集基准 | 25/40 | 62.5% | 方案调整前的能力基准 |
| 开发集方案验证 | 38/40 | 95.0% | 完成语义路由与模型兜底后的开发集验证 |
| 测试集设计基线 | 57/93 | 61.3% | 方案分析前的首次测量 |
| 测试集回归复核 | 89/93 | 95.7% | 已使用设计基线暴露的失败题型，不是独立盲测 |

知识库解释能力不计入 NL2SQL 准确率，应另建召回、引用和解释一致性评测。统计查询的数量、排名和图表以分析库执行结果为准，疾病背景和来源解释由 Nexent 绑定的 `ccf_medical_kb` 提供。

## 可复现产物

| 文件 | 作用 |
|---|---|
| `build_nl2sql_benchmark.py` | 从真实数据库构建题目、Gold SQL 和 Gold Result |
| `run_benchmark.py` | 执行系统查询并计算准确率 |
| `generate_benchmark_report.py` | 生成中文结果表、CSV、PNG 和 SVG |
| `results/benchmark_metrics.json` | 阶段结果和分题型结果的单一数据源 |
| `figures/` | PPT 和技术报告使用的图表 |
