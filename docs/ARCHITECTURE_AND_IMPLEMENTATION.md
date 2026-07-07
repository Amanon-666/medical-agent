# 架构与实现说明

本文说明医学数据智能体工程的模块边界、数据流、任务实现方法和部署关系。文档中的路径均对应本工程目录中的实际文件。

## 1. 总体架构

系统由四层组成：

```text
用户入口
├── Nexent 智能体对话页面
├── DataMate 数据处理页面
└── 医学数据智能体可视化平台

能力编排
├── MCP 工具服务
├── 任务一混合清洗编排
├── 任务二知识图谱构建编排
└── 任务三查询与可视化编排

领域能力
├── 医学实体识别
├── 医学关系抽取
├── 三元组生成
├── NL2SQL 查询
└── 质量审计

数据与平台
├── DataMate 数据集与算子任务
├── Nexent Agent 与 MCP 工具绑定
├── task2_medical_kg.db
└── task3_analytics.db
```

## 2. 目录职责

| 目录 | 职责 |
| --- | --- |
| `clients/` | DataMate 与 Nexent HTTP 客户端。 |
| `core/` | 医学文本抽取、标准化、问答和 NL2SQL 逻辑。 |
| `operators/` | DataMate 自定义算子。 |
| `mcp_server/` | MCP 服务、任务编排、DataMate 适配、知识图谱入库和任务三查询工具。 |
| `kg/` | 知识图谱与分析库构建脚本。 |
| `demo/` | Notebook 演示和任务三可视化平台。 |
| `deploy/` | 环境检查、算子部署、数据库构建、MCP 启动、Agent 发布和健康检查脚本。 |
| `data/` | 糖尿病混合格式数据、任务二知识图谱库、任务三分析库。 |
| `docs/` | 架构、部署、配置、数据资产和操作文档。 |

## 3. 任务一实现

任务一处理医学混合格式数据集，重点展示 DataMate 算子和数据治理能力。

### 处理流程

1. Nexent 智能体调用 `inspect_dataset` 解析 DataMate 数据集名称或 UUID。
2. MCP 服务读取数据集文件清单，识别 `txt/csv/json/jsonl` 类型。
3. `run_task1_mixed_cleaning` 为不同格式选择对应清洗链。
4. DataMate 执行算子任务。
5. MCP 服务查询任务状态，整理输出数据集、文件级质量证据、术语替换、噪声统计和吞吐量。
6. 输出数据集保留源格式和血缘，供任务二继续消费。

### 关键模块

| 模块 | 作用 |
| --- | --- |
| `operators/table_column_cleaner/` | 清洗 CSV 字段，保留表格结构。 |
| `operators/json_field_cleaner/` | 清洗 JSON / JSONL 字段，保留结构化字段。 |
| `operators/medical_term_normalizer/` | 医学术语和缩写标准化。 |
| `operators/llm_noise_filter/` | 噪声过滤和质量证据输出。 |
| `mcp_server/task1/mixed_cleaning_service.py` | 混合格式清洗主编排。 |
| `mcp_server/task1/evidence.py` | 清洗证据汇总。 |

### 结果边界

系统只展示工具真实返回的清洗证据。若某个算子没有返回逐文件语义噪声明细，报告会说明该项未提供，而不会补写“模型已确认无噪声”之类结论。

## 4. 任务二实现

任务二处理任务一输出数据集，重点展示 MCP 算子编排和知识图谱生成能力。

### 处理流程

1. 解析 DataMate 数据集，保留文件名、格式和记录编号。
2. 将 `txt/csv/json/jsonl` 统一转换为可抽取记录流。
3. 调用医学抽取服务生成实体、关系和三元组。
4. 过滤明显冲突或低质量三元组。
5. 写入 `data/task2_medical_kg.db`。
6. 登记 `kg_sources`，记录数据来源、数据集 ID、入库时间和三元组数量。
7. 刷新 `data/task3_analytics.db`，供任务三查询和图表展示。

### 关键模块

| 模块 | 作用 |
| --- | --- |
| `core/medical_extraction_service.py` | 医学抽取服务入口。 |
| `core/medical_offline_extraction.py` | 本地词典与规则增强抽取。 |
| `mcp_server/task2/pipeline_service.py` | 任务二端到端流水线。 |
| `mcp_server/task2/reporting.py` | 输出任务二结构化报告。 |
| `mcp_server/kg/persistence.py` | 三元组和来源入库。 |
| `mcp_server/kg/analytics_refresh.py` | 任务三分析库刷新。 |

### 指标输出

任务二返回：

- 输入文件数和格式分布；
- 解析记录数；
- 实体、关系、生成三元组、入库三元组数量；
- 被过滤三元组数量和原因；
- 抽取耗时、平均记录耗时、吞吐量；
- 分析库刷新状态。

## 5. 任务三实现

任务三读取任务二产物，重点展示图谱复用、自然语言查询和可视化效果。

### 查询能力

| 能力 | 数据来源 | 工具或模块 |
| --- | --- | --- |
| 疾病详情问答 | `task3_analytics.db` | `query_disease_analytics` |
| 关系子图 | `task2_medical_kg.db` | `query_knowledge_graph` |
| NL2SQL | `task3_analytics.db` | `execute_nl2sql` |
| 数据来源列表 | `kg_sources` | `get_medical_data_sources` |
| 可视化入口状态 | 服务健康检查 | `get_validation_frontend_status` |

### 可视化平台

`demo/task3_interactive_demo/` 提供统一页面，读取与 MCP 工具相同的数据库。页面包含：

- 数据流向；
- 疾病关系图；
- 统计图表；
- 证据表；
- 噪声拦截记录；
- 自然语言问答。

## 6. 数据流

```mermaid
flowchart LR
    A["糖尿病混合格式数据集"] --> B["任务一 DataMate 清洗"]
    B --> C["保留格式的清洗后数据集"]
    C --> D["任务二 MCP 知识抽取流水线"]
    D --> E["task2_medical_kg.db"]
    E --> F["task3_analytics.db"]
    E --> G["可视化平台关系子图"]
    F --> H["NL2SQL / 统计图表 / 疾病问答"]
```

## 7. 部署关系

在线环境通过固定域名访问：

| 服务 | 域名 |
| --- | --- |
| 可视化平台 | `https://demo.mashiro.xin/` |
| Nexent | `https://nexent.mashiro.xin/` |
| DataMate | `https://datamate.mashiro.xin/` |

本地或新服务器部署时，`deploy/` 目录负责把本项目能力接入已有 DataMate 与 Nexent 平台。详细步骤见 [`DEPLOY.md`](../DEPLOY.md)。

## 8. 质量边界

- 不修改 DataMate 与 Nexent 上游源码作为最终方案；必要改动通过算子、MCP、部署脚本或迁移脚本体现。
- 不把 Agent 自述当作成功依据；以 DataMate 任务、数据库记录、文件产物和接口返回为准。
- 不展示没有真实硬件支撑的 NPU 加速结论。

## 9. 当前规模与指标

下列指标用于说明当前工程的展示规模和评测口径，均来自本工程维护的数据产物或固定评测集。

| 类别 | 指标 | 当前值 | 说明 |
| --- | --- | --- | --- |
| 任务二 | 图谱规模 | 约 79,600 个实体、约 467,400 条三元组 | 写入 `data/task2_medical_kg.db`，供关系子图和疾病知识查询使用。 |
| 任务三 | 分析库规模 | 约 14,408 个疾病条目 | 刷新到 `data/task3_analytics.db`，供统计图表、证据表和 NL2SQL 使用。 |
| 任务二 | 实体识别基线 | CMeEE 样本 F1 16.5% | 本地词典与规则链的可复现基线，不作为医学权威模型分数。 |
| 任务二 | 关系抽取自检 | 100 条诊断样本通过 | 用于确认演示疾病域内的关系抽取稳定性。 |
| 任务三 | NL2SQL 指标 | 42 / 42，通过率 100.0% | 固定问题集规则化评测，展示阈值为 85%。 |
| 硬件 | NPU 状态 | 未启用 | 当前环境只展示 CPU 基线，不声明 NPU 优化效果。 |

---

[← 返回项目首页](../README.md)
