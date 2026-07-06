# MCP 服务说明

`mcp_server/` 是 Nexent 智能体调用本项目能力的主要入口。它把任务一、任务二、任务三封装成可发现、可调用、可返回结构化结果的 MCP 工具。

## 目录索引

| 目录或文件 | 职责 | 详细说明 |
| --- | --- | --- |
| [`server.py`](server.py) | MCP 服务启动入口，只负责注册工具和启动协议服务。 | 入口文件 |
| [`config.py`](config.py) | 读取服务地址、数据库路径和运行参数。 | 配置加载 |
| [`tools/`](tools/) | Nexent 直接调用的工具函数入口。 | → [tools/__init__.py](tools/__init__.py) |
| · [`task1_data.py`](tools/task1_data.py) | 任务一 7 个 MCP 工具：上传、探查、清洗、状态查询。 | T1 |
| · [`task2_extract.py`](tools/task2_extract.py) | 任务二 3 个 MCP 工具：实体/关系/三元组抽取。 | T2 |
| · [`task2_pipeline.py`](tools/task2_pipeline.py) | 任务二 KG 流水线编排工具。 | T2 |
| · [`task3_query.py`](tools/task3_query.py) | 任务三 5 个查询工具：图谱、疾病、数据来源、前端状态。 | T3 |
| · [`task3_nl2sql.py`](tools/task3_nl2sql.py) | 任务三 NL2SQL 工具。 | T3 |
| [`task1/`](task1/) | 任务一混合数据集探查、清洗编排、状态查询和证据整理。 | → [task1/__init__.py](task1/__init__.py) |
| · [`mixed_cleaning_service.py`](task1/mixed_cleaning_service.py) | 混合格式清洗主编排器。 | T1 |
| · [`pipeline_service.py`](task1/pipeline_service.py) | DataMate 清洗任务创建与轮询。 | T1 |
| · [`chains.py`](task1/chains.py) | 三条清洗链定义（text/csv/json/jsonl）。 | T1 |
| · [`runtime_helpers/`](task1/runtime_helpers/) | 源格式保留清洗辅助模块。 | T1 |
| [`task2/`](task2/) | 任务二文件解析、抽取流水线、记录选择和报告生成。 | → [task2/__init__.py](task2/__init__.py) |
| · [`pipeline_service.py`](task2/pipeline_service.py) | KG 批量构建 7 阶段编排。 | T2 |
| · [`selection.py`](task2/selection.py) | 跨文件均衡抽样。 | T2 |
| · [`reporting.py`](task2/reporting.py) | KG 构建统计报告。 | T2 |
| [`kg/`](kg/) | 三元组入库、来源登记、分析库刷新和质量审计。 | → [kg/__init__.py](kg/__init__.py) |
| · [`persistence.py`](kg/persistence.py) | 实体/关系/三元组写入 SQLite。 | T2 |
| · [`analytics_refresh.py`](kg/analytics_refresh.py) | 从 KG 刷新任务三分析库。 | T2+T3 |
| · [`analytics.py`](kg/analytics.py) | 疾病分析查询辅助。 | T3 |
| [`datamate/`](datamate/) | DataMate 数据集解析和 API 适配。 | → [datamate/client.py](datamate/client.py) |
| [`shared/`](shared/) | 前端状态、SQLite 工具和通用解析函数。 | → [shared/__init__.py](shared/__init__.py) |

## 设计边界

- `tools/` 只做参数校验、调用服务层和返回结构化结果。
- 业务编排放在 `task1/`、`task2/` 和 `kg/`。
- DataMate、数据库和文件系统访问通过适配模块完成。
- 工具返回必须基于真实 API、数据库或文件结果，不能在失败时补写成功结论。

---

[← 返回项目首页](../README.md)
