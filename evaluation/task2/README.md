# 任务二知识图谱评测

任务二的评测程序位于 `tests/`，本目录集中说明入口、数据边界和正式指标口径。

## 评测入口

- [`../../tests/eval_offline.py`](../../tests/eval_offline.py)：实体识别和关系抽取评测；
- [`../../tests/eval_task2_scenarios.py`](../../tests/eval_task2_scenarios.py)：多类医学场景、多后端和多格式真实输入评测；
- [`../../tests/task2/`](../../tests/task2/)：任务二回归测试；
- [`../../tests/EVAL_COMMANDS.md`](../../tests/EVAL_COMMANDS.md)：完整命令、输出目录和限制说明。

## 正式运行

CMeEE/CMeIE 标注集不是本仓库分发资产，需要通过参数传入本地文件。正式质量口径使用固定留出划分，未参与校准的样本计算 Precision、Recall 和 F1。

标注集的用途边界、获取原则和本地放置方式见 [`../../docs/任务二医学标注集使用说明.md`](../../docs/任务二医学标注集使用说明.md)。

```powershell
cd <project-root>
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

`offline` 不需要模型密钥；`hybrid` 和 `llm` 只有在当前进程显式提供 `CCF_LLM_API_KEY` 或 `--llm-key` 时才调用模型。评测器只读本地输入和知识图谱库，不写知识图谱、不刷新分析库、不连接 Nexent。无标签官方 test 集不能计算 F1。

多场景评测和四格式真实输入的完整参数见 [`../../tests/EVAL_COMMANDS.md`](../../tests/EVAL_COMMANDS.md)。场景统计用于检查覆盖范围，不等同于泛化能力分数。
