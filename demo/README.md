# demo 演示入口说明

`demo/` 提供两类演示入口：Notebook 流程演示和医学数据智能体可视化平台。

## 文件索引

| 文件/目录 | 用途 |
| --- | --- |
| [`start_notebook_demo.bat`](start_notebook_demo.bat) | Windows 一键启动 Notebook 演示。 |
| [`interactive_pipeline_demo.ipynb`](interactive_pipeline_demo.ipynb) | **主演示 Notebook**：交互式全链路演示（清洗→抽取→查询）。 |
| [`task3_interactive_demo/`](task3_interactive_demo/) | **可视化平台源码**（Python HTTP 服务 + JS 前端）。 |
| · [`server.py`](task3_interactive_demo/server.py) | 可视化平台 HTTP 服务入口。 |
| · [`query_service.py`](task3_interactive_demo/query_service.py) | 自然语言查询引擎。 |
| · [`dashboard_payloads.py`](task3_interactive_demo/dashboard_payloads.py) | 面板数据生成（KPI/图谱/图表/噪声）。 |
| · [`static/`](task3_interactive_demo/static/) | 前端静态文件（HTML/CSS/JS）。 |
| · [`task3_interactive_demo/README.md`](task3_interactive_demo/README.md) | 可视化平台详细说明。 |

## 在线服务

| 服务 | 地址 | 用途 |
| --- | --- | --- |
| 医学数据智能体可视化平台 | `https://demo.mashiro.xin/` | 查看图谱、图表、证据表、噪声拦截和疾病问答。 |
| Nexent 智能体平台 | `https://nexent.mashiro.xin/` | 通过任务一、任务二、任务三智能体执行流程。 |
| DataMate 数据处理平台 | `https://datamate.mashiro.xin/` | 查看数据集、算子和清洗结果。 |

演示账号：`suadmin@nexent.com` / `241002814`

---

[← 返回项目首页](../README.md)
