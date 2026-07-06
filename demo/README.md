# demo 演示入口说明

`demo/` 提供两类演示入口：Notebook 流程演示和医学数据智能体可视化平台。这里的演示默认基于已经部署好的在线服务和演示账号，用于快速展示比赛内容和端到端流程，不承担本地部署职责。

## 在线服务

| 服务 | 地址 | 用途 |
| --- | --- | --- |
| 医学数据智能体可视化平台 | `https://demo.mashiro.xin/` | 查看图谱、图表、证据表、噪声拦截和疾病问答。 |
| Nexent 智能体平台 | `https://nexent.mashiro.xin/` | 通过任务一、任务二、任务三智能体执行流程。 |
| DataMate 数据处理平台 | `https://datamate.mashiro.xin/` | 查看数据集、算子和清洗结果。 |

演示账号：`suadmin@nexent.com`  
演示密码：`241002814`

## Notebook 演示

双击：

```text
start_notebook_demo.bat
```

脚本会打开 `interactive_pipeline_demo.ipynb`，并默认使用在线服务和演示账号。Notebook 中不要求用户手工输入密码；如需在其他环境中复用，可通过环境变量覆盖服务地址和账号。

Notebook 展示内容：

1. 连接 Nexent 与在线可视化平台。
2. 调用任务一智能体执行混合格式清洗说明。
3. 调用任务二智能体构建知识图谱并展示入库指标。
4. 调用任务三智能体返回可视化平台入口、数据来源和 NL2SQL 指标。
5. 打开 `https://demo.mashiro.xin/` 查看图谱和图表结果。

## 可视化平台

目录 `task3_interactive_demo/` 是任务三的可视化平台源码。页面读取 `data/task2_medical_kg.db` 和 `data/task3_analytics.db`，提供：

- 数据来源与数据流展示；
- 疾病关系子图；
- 疾病、症状、药物、检查等统计图表；
- 查询证据表；
- 噪声拦截记录；
- 自然语言问答与 NL2SQL 结果展示。

详细说明见 `task3_interactive_demo/README.md`。
