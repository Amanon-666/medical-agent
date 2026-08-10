# 任务三评测

本目录保存任务三 NL2SQL 的题集、Gold 结果和复现脚本。每道题包含自然语言问题、Gold SQL 与真实数据库执行结果；评测比较执行结果，不要求 SQL 字符串相同。

## 文件

- `nl2sql_dev.jsonl`：40 道开发题；
- `nl2sql_test.jsonl`：93 道测试题；
- `results_gold_dev.json`、`results_gold_test.json`：对应 Gold 结果；
- `benchmark_manifest.json`：数据库版本、题数和主指标记录；
- `schema_snapshot.json`：构建时的数据库结构快照；
- `run_benchmark.py`：执行评测；
- `build_nl2sql_benchmark.py`：从数据库重新构建题集；
- `generate_benchmark_report.py`：生成 CSV、PNG 和 SVG 结果图；
- `results/`、`figures/`：评测指标和图表输出。

## 使用

在项目根目录执行。评测数据库应放在 `data/task3_analytics.db`，并与 `benchmark_manifest.json` 中的版本一致。

```powershell
# 检查 Gold 结果和评测器
python evaluation/task3/run_benchmark.py --split dev --engine gold

# 运行稳定语义层
python evaluation/task3/run_benchmark.py --split test --engine semantic

# 运行模型 NL2SQL；模型配置由外部环境变量提供
python evaluation/task3/run_benchmark.py --split test --engine nl2sql

# 生成 CSV 和中文图表
python evaluation/task3/generate_benchmark_report.py
```

模型评测需要由运行环境提供 `CCF_LLM_API_KEY` 或 `CCF_LLM_API_KEY_FILE`，仓库不保存账号、密钥和本机配置。主指标是保留重复行的执行结果一致率；详细结果和限制统一写入技术报告。
