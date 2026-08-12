# 三项任务评测入口

`evaluation/` 保存三项任务的正式评测入口、题集、金标准和可复现结果。评测脚本默认在本地运行，不连接 Nexent 或 DataMate；需要外部数据集、模型或运行环境的部分，会在对应说明中明确标出。

| 任务 | 正式入口 | 核心资产 | 结果口径 |
|---|---|---|---|
| 任务一：数据治理 | [`task1/README.md`](task1/README.md) | 多格式压力集、独立金标准、算子评测脚本 | 工程回归，不代表线上平台成绩 |
| 任务二：知识图谱 | [`task2/README.md`](task2/README.md) | CMeEE/CMeIE 外部标注集、离线/混合评测器、场景评测器 | 固定留出集计算 Precision、Recall、F1；无标签 test 不计算 F1 |
| 任务三：智能分析 | [`task3/README.md`](task3/README.md) | 40 道开发题、93 道测试题、Gold Result、数据库版本清单 | SQL 执行结果一致率；回归复核不等同独立盲测 |

统一命令索引见 [`../tests/EVAL_COMMANDS.md`](../tests/EVAL_COMMANDS.md)。所有命令均从项目根目录执行，输出优先写入 `tmp/` 或用户指定的临时目录，不把本机配置和密钥提交到仓库。
