# MediFlow 三项任务评测命令

详细入口见 [`../evaluation/README.md`](../evaluation/README.md)。以下命令均在项目根目录执行，外部数据集路径用占位符表示，不写入本机路径。

## 任务一：多格式清洗回归

```powershell
python -m evaluation.task1.run_benchmark
python -m pytest tests\task1\test_local_benchmark.py -q
```

结果默认写入 `evaluation/task1/runs/operator_v2_latest/`。这是本地算子压力集，不评价 DataMate/Nexent 服务或 PDF 解析质量。

## 任务二：知识图谱抽取

```powershell
$env:PYTHONPATH=(Get-Location).Path
$env:PYTHONIOENCODING='utf-8'

python tests\eval_offline.py `
  --cmeee <CMeEE-V2_dev.json> `
  --cmeie <CMeIE_dev.jsonl> `
  --kg-db data\task2_medical_kg.db `
  --split holdout --backend offline --offline-view gated --no-display `
  --output tmp\task2_formal_eval\report.json `
  --charts tmp\task2_formal_eval\charts
```

`holdout` 是正式质量口径；`hybrid`/`llm` 只有在当前进程显式提供模型密钥时才调用模型。评测器只读本地数据，不写知识图谱、不刷新分析库、不连接 Nexent。官方无标签 test 集不能计算 F1。

多场景和四格式真实输入统计：

```powershell
python tests\eval_task2_scenarios.py `
  --cmeee <CMeEE-V2_dev.json> `
  --cmeie <CMeIE_dev.jsonl> `
  --kg-db data\task2_medical_kg.db `
  --split full_dev --max-per-scenario 1 --backends offline `
  --output tmp\task2_scenarios\report.json `
  --charts tmp\task2_scenarios\assets --no-display
```

## 任务三：NL2SQL 执行评测

```powershell
# 先检查 Gold Result 自洽性
python evaluation/task3/run_benchmark.py --split dev --engine gold
python evaluation/task3/run_benchmark.py --split test --engine gold

# 运行语义层或模型 NL2SQL
python evaluation/task3/run_benchmark.py --split test --engine semantic
python evaluation/task3/run_benchmark.py --split test --engine nl2sql

# 生成中文 CSV、PNG、SVG 图表
python evaluation/task3/generate_benchmark_report.py
```

评测器会校验分析库与 `evaluation/task3/benchmark_manifest.json` 的版本信息。主指标是保留重复行的执行结果一致率；回归复核使用过失败题型信息，不等同独立盲测。

## 单元回归

```powershell
python -m pytest -q
```
