# docs 文档索引

`docs/` 保存工程说明、任务实现说明、部署说明、数据资产说明和演示说明。根目录 `README.md` 提供最快入口；本目录用于进一步了解实现细节、部署方式和数据资产边界。

## 阅读顺序

1. **[`ARCHITECTURE_AND_IMPLEMENTATION.md`](ARCHITECTURE_AND_IMPLEMENTATION.md)** — 系统架构、三项任务的数据流、DataMate 算子与 MCP 算子的分工。
2. **[`DEMO_USAGE_GUIDE.md`](DEMO_USAGE_GUIDE.md)** — 在线服务入口的功能验证。
3. **[`TASK1_MIXED_ORCHESTRATION.md`](TASK1_MIXED_ORCHESTRATION.md)** — 任务一混合格式清洗如何保留 `txt/csv/json/jsonl` 源格式和质量证据。
4. **[`CONFIGURATION_GUIDE.md`](CONFIGURATION_GUIDE.md)** — 配置总入口，含速查清单、全部环境变量表、字段说明和修改入口。

---

[← 返回项目首页](../README.md)

## 文档清单

| 文件 | 内容 |
| --- | --- |
| **[`ARCHITECTURE_AND_IMPLEMENTATION.md`](ARCHITECTURE_AND_IMPLEMENTATION.md)** | 总体架构、任务一/二/三实现流程、模块职责、算子分工 |
| **[`CONFIGURATION_GUIDE.md`](CONFIGURATION_GUIDE.md)** | 全部 33 个环境变量的字段含义、默认值与消费者 |
| **[`DEMO_USAGE_GUIDE.md`](DEMO_USAGE_GUIDE.md)** | 在线入口、演示账号、Notebook、Nexent 对话、DataMate 数据查看 |
| **[`TASK1_MIXED_ORCHESTRATION.md`](TASK1_MIXED_ORCHESTRATION.md)** | 混合格式识别、分链清洗、格式保留、血缘和质量证据 |

## 工作流追踪文档

`workflow/` 目录提供五条完整代码链路的逐文件追踪，用于理解数据如何在系统中流转：

| 文件 | 内容 |
| --- | --- |
| [`workflow/README.md`](workflow/README.md) | 工作流总索引与全局架构图 |
| [`workflow/workflow-1-data-cleaning.md`](workflow/workflow-1-data-cleaning.md) | 任务一：从用户文本到清洗结果的完整代码链路 |
| [`workflow/workflow-2-knowledge-graph.md`](workflow/workflow-2-knowledge-graph.md) | 任务二：实体识别→关系抽取→三元组生成→持久化 |
| [`workflow/workflow-3-analytics-visualization.md`](workflow/workflow-3-analytics-visualization.md) | 任务三：NL2SQL + 浏览器可视化平台双路径 |
| [`workflow/workflow-4-deployment.md`](workflow/workflow-4-deployment.md) | 部署流程：每一步执行什么、依赖什么 |
| [`workflow/workflow-5-notebook-demo.md`](workflow/workflow-5-notebook-demo.md) | Notebook 演示：5 个 Cell 逐一解析 |
| [`workflow/code-inventory.md`](workflow/code-inventory.md) | 完整代码清单：按链路归类 + 复用关系 |

