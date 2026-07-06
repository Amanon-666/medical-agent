# clients 模块说明

`clients/` 封装外部平台的 HTTP 访问逻辑，使业务代码不直接拼接 DataMate 或 Nexent 接口细节。

## 文件索引

| 文件 | 职责 |
| --- | --- |
| [`nexent_client.py`](nexent_client.py) | 封装 Nexent 登录、Agent 管理、MCP 注册、工具扫描和 SSE 流式对话接口。 |
| [`__init__.py`](__init__.py) | 包导出。 |

## 设计边界

- 本目录只负责平台通信、请求参数整理、响应解析和错误透传。
- 任务编排逻辑不放在这里：任务一编排位于 [`mcp_server/task1/`](../mcp_server/task1/)，任务二编排位于 [`mcp_server/task2/`](../mcp_server/task2/)。
- 账号、密码、服务地址从环境变量或配置文件读取，不在代码中硬编码。

## 与三项任务的关系

- 任务一通过 DataMate 客户端注册和查询混合格式数据集。
- 任务二通过客户端读取任务一输出数据，为知识图谱流水线提供来源文件。
- 任务三通过 Nexent 客户端确认智能体和 MCP 工具状态，并向用户返回可视化入口。

---

[← 返回项目首页](../README.md)
