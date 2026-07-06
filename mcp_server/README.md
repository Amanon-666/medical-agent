# MCP 服务说明

`mcp_server/` 是 Nexent 智能体调用本项目能力的主要入口。它把任务一、任务二、任务三封装成可发现、可调用、可返回结构化结果的 MCP 工具。

## 目录结构

| 目录或文件 | 职责 |
| --- | --- |
| `server.py` | MCP 服务启动入口，只负责注册工具和启动协议服务。 |
| `config.py` | 读取服务地址、数据库路径和运行参数。 |
| `tools/` | Nexent 直接调用的工具函数入口。 |
| `task1/` | 任务一混合数据集探查、清洗编排、状态查询和证据整理。 |
| `task2/` | 任务二文件解析、抽取流水线、记录选择和报告生成。 |
| `kg/` | 三元组入库、来源登记、分析库刷新和质量审计。 |
| `datamate/` | DataMate 数据集解析和 API 适配。 |
| `shared/` | 前端状态、SQLite 工具和通用解析函数。 |

## 工具分组

| 工具类别 | 典型工具 | 任务 |
| --- | --- | --- |
| 数据探查与清洗 | `inspect_dataset`、`run_task1_mixed_cleaning` | 任务一 |
| 知识图谱构建 | `run_task2_kg_pipeline`、`extract_medical_entities` | 任务二 |
| 分析问答 | `query_disease_analytics`、`execute_nl2sql` | 任务三 |
| 可视化平台 | `get_validation_frontend_status`、`get_medical_data_sources` | 任务三 |

## 设计边界

- `tools/` 只做参数校验、调用服务层和返回结构化结果。
- 业务编排放在 `task1/`、`task2/` 和 `kg/`。
- DataMate、数据库和文件系统访问通过适配模块完成。
- 工具返回必须基于真实 API、数据库或文件结果，不能在失败时补写成功结论。
