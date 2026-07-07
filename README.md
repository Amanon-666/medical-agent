# 医学数据智能体工程

本工程基于 DataMate 与 Nexent 构建医学数据智能体系统，形成“数据治理 → 知识图谱生成 → 分析问答与可视化”的端到端闭环。工程内容包括 DataMate 自定义算子、MCP 工具服务、Nexent 智能体编排、知识图谱库、分析库、可视化平台和部署说明。

## 在线服务入口

当前维护了一套可直接访问的在线环境。公网域名首次加载可能略有延迟，刷新后通常可以正常访问。

| 服务 | 地址 | 主要用途 |
| --- | --- | --- |
| 医学数据智能体可视化平台 | `https://demo.mashiro.xin/` | 查看数据流、疾病关系图、统计图表、证据表、噪声拦截记录，并进行疾病问答。 |
| Nexent 智能体平台 | `https://nexent.mashiro.xin/` | 与任务一、任务二、任务三智能体对话，观察 MCP 工具调用、执行指标和任务结果。 |
| DataMate 数据处理平台 | `https://datamate.mashiro.xin/` | 查看数据集、清洗算子、清洗任务、输出数据集和质量报告。 |

演示账号：`suadmin@nexent.com`  
演示密码：`241002814`

## 快速验证

1. 打开 `https://demo.mashiro.xin/`，确认页面标题为“医学数据智能体可视化平台”，页面可加载数据来源、统计指标、关系子图、图表、证据表和噪声拦截记录。
2. 打开 `https://nexent.mashiro.xin/`，使用演示账号登录，选择任务一、任务二或任务三智能体进行对话。
3. 打开 `https://datamate.mashiro.xin/`，使用演示账号登录，在数据管理中查看糖尿病混合格式数据集及其任务一清洗结果。
4. 如需 Notebook 演示，双击 `demo/start_notebook_demo.bat`。Notebook 默认连接已部署服务并使用演示账号。

可直接输入 Nexent 的示例指令：

```text
处理糖尿病全流程演示数据集，执行任务一混合清洗，并返回工具调用过程、输出数据集、质量报告和吞吐量。
```

```text
基于糖尿病任务一清洗后的最终数据集构建知识图谱，展示解析文件、实体数量、关系数量、三元组数量、入库数量、处理耗时和分析库刷新结果。
```

```text
给出医学数据智能体可视化平台入口，并说明本轮新接入数据来源、NL2SQL 指标和图表验证方式。
```

## 目录结构

| 目录 | 作用 | 详细说明 |
| --- | --- | --- |
| `clients/` | DataMate 与 Nexent HTTP 客户端封装。 | [`clients/README.md`](clients/README.md) |
| `core/` | 医学实体识别、关系抽取、三元组生成、疾病查询、NL2SQL 等领域能力。 | [`core/README.md`](core/README.md) |
| `operators/` | 注册到 DataMate 的自定义算子，包括医学术语标准化、结构化字段清洗、语义噪声过滤等。 | [`operators/README.md`](operators/README.md) |
| `mcp_server/` | 暴露给 Nexent 的 MCP 工具服务，负责任务一、二、三的工具入口和流程编排。 | [`mcp_server/README.md`](mcp_server/README.md) |
| `kg/` | 知识图谱库与分析库的构建脚本。 | [`kg/README.md`](kg/README.md) |
| `demo/` | Notebook 演示和医学数据智能体可视化平台。 | [`demo/README.md`](demo/README.md) |
| `data/` | 糖尿病混合格式数据、任务二知识图谱库、任务三分析库。 | [`data/README.md`](data/README.md) |
| `deploy/` | 环境检查、算子部署、数据库构建、MCP 启动、Agent 发布、可视化平台启动和健康检查。 | [`deploy/README.md`](deploy/README.md) |
| `docs/` | 架构、任务实现、部署、配置、演示和数据资产说明。 | [`docs/README.md`](docs/README.md) |
| `scripts/` | 部署流程调用的平台注册脚本。 | [`scripts/README.md`](scripts/README.md) |

## 三项任务实现方法

### 任务一：混合格式医学数据治理

任务一重点展示 DataMate 算子和 Nexent 智能体编排能力。系统支持 `txt/csv/json/jsonl` 混合数据集：智能体先调用 MCP 工具探查 DataMate 数据集，再按文件格式分派到不同清洗链，最后把清洗结果重新登记为一个最终数据集，并保留源格式、文件数、血缘和质量证据。

主要实现：

- `operators/medical_term_normalizer/`：医学术语和缩写标准化。
- `operators/table_column_cleaner/`：CSV 字段清洗，保留表格结构。
- `operators/json_field_cleaner/`：JSON / JSONL 字段清洗，保留对象结构。
- `operators/llm_noise_filter/`：语义噪声识别、规则库过滤和质量证据记录。
- `mcp_server/task1/`：混合格式清洗编排、输出数据集整理、质量证据汇总。
- `mcp_server/tools/task1_data.py`：Nexent 调用的任务一工具入口。

### 任务二：医学知识图谱生成

任务二重点展示 MCP 知识抽取算子和智能体自动编排能力。系统读取任务一输出数据集，将混合格式文件解析为统一记录流，执行实体识别、关系抽取、三元组生成、质量过滤、三元组入库和分析库刷新。

主要实现：

- `core/medical_extraction_service.py`：医学知识抽取服务入口。
- `core/medical_offline_extraction.py`：本地规则与词典增强抽取链，降低对模型接口的硬依赖。
- `mcp_server/task2/`：任务二流水线编排、记录选择、执行指标和结果报告。
- `mcp_server/kg/`：三元组入库、来源登记、质量审计和分析库刷新。
- `data/task2_medical_kg.db`：任务二知识图谱库。

任务二返回来源文件、格式分布、解析记录数、实体数、关系数、生成三元组数、入库三元组数、平均耗时、吞吐量和分析库刷新状态。

当前工程侧基线数据如下，数值来自本工程随附知识库、分析库和评测记录，用于说明系统规模与展示口径：

| 指标 | 当前值 | 说明 |
| --- | --- | --- |
| 知识图谱规模 | 约 79,600 个实体、约 467,400 条三元组 | 由医学公开数据和任务二新增来源构建，供任务三查询与图表使用。 |
| 疾病分析库规模 | 约 14,408 个疾病条目 | 来自 `data/task3_analytics.db`，用于疾病详情、统计图表和只读 SQL 查询。 |
| 实体识别评测 | CMeEE 样本基线 F1 16.5% | 当前为本地词典与规则链基线，用于展示无模型依赖时的可复现能力边界。 |
| 关系抽取自检 | 100 条诊断样本通过 | 用于检查关系抽取规则在演示疾病域内的稳定性。 |
| 任务三 NL2SQL | 42 / 42，通过率 100.0% | 固定问题集规则化评测，展示阈值为 85%。 |
| NPU 状态 | 未启用 | 当前在线环境未检测到真实 NPU，不声明 NPU 加速。 |

### 任务三：分析问答与可视化

任务三重点展示任务一、二产物复用。系统读取任务二知识图谱库和任务三分析库，提供疾病详情查询、关系子图、统计图表、证据表、噪声拦截记录、自然语言统计查询和 NL2SQL 指标。

主要实现：

- `mcp_server/tools/task3_query.py`：疾病详情、知识图谱、数据来源、前端状态等工具。
- `mcp_server/tools/task3_nl2sql.py`：自然语言统计查询和只读 SQL 执行。
- `demo/task3_interactive_demo/`：医学数据智能体可视化平台。
- `data/task3_analytics.db`：任务三分析库。

## 文档入口

| 文档 | 内容 |
| --- | --- |
| [`docs/README.md`](docs/README.md) | 文档目录索引，说明每份文档的用途和阅读顺序。 |
| [`docs/ARCHITECTURE_AND_IMPLEMENTATION.md`](docs/ARCHITECTURE_AND_IMPLEMENTATION.md) | 总体架构、三项任务数据流、模块职责、算子分工和工程边界。 |
| [`docs/DEMO_USAGE_GUIDE.md`](docs/DEMO_USAGE_GUIDE.md) | 在线服务、演示账号、Notebook 和对话式验证步骤。 |
| [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md) | 新环境复现部署步骤、脚本入口、健康检查和回滚方式。 |
| [`docs/CONFIGURATION_GUIDE.md`](docs/CONFIGURATION_GUIDE.md) | **配置总入口**：部署前速查清单 + 全部 33 个环境变量表 + 容器路径说明 + 修改入口。 |
| [`docs/DATA_ARTIFACTS.md`](docs/DATA_ARTIFACTS.md) | 演示数据、知识图谱库、分析库和数据来源管理策略。 |
| [`docs/TASK1_MIXED_ORCHESTRATION.md`](docs/TASK1_MIXED_ORCHESTRATION.md) | 任务一混合格式清洗编排、格式保留和质量证据。 |

## 部署复现

在线服务已部署完成，可直接验证。新环境复现请参阅 **[`DEPLOY.md`](DEPLOY.md)**（部署总指南，含 9 步清单、配置填写、文件索引和回滚方式）。

## 数据资产

| 文件或目录 | 说明 |
| --- | --- |
| `data/standard_diabetes_demo/datamate_upload/` | 糖尿病混合格式数据集，覆盖 `txt/csv/json/jsonl`，与在线 DataMate 演示数据保持同类结构。 |
| `data/task2_medical_kg.db` | 任务二知识图谱库，包含疾病、症状、药物、检查、科室等实体关系。 |
| `data/task3_analytics.db` | 任务三分析库，服务 NL2SQL、统计图表和疾病详情查询。 |
| `operators/llm_noise_filter/noise_kb.db` | 语义噪声规则与审计知识库，用于任务一噪声过滤与任务三质量展示。 |
| `operators/medical_term_normalizer/term_kb.db` | 医学术语标准化知识库，用于常见缩写、同义表达和术语替换。 |

数据库属于数据产物，可随工程目录提供；通常不纳入 Git 历史。

## 质量边界

- 清洗效果以工具返回的真实证据为准。
- 任务二以数据库写入和工具返回为成功依据，不把智能体自然语言自述当作成功依据。
- 当前环境无 NPU 加速。
- 对 DataMate / Nexent 源码的改动通过算子、MCP 工具、数据库产物、部署脚本和文档体现。

## 相关仓库

| 仓库 | 地址 | 说明 |
| --- | --- | --- |
| 本工程（提交侧） | [github.com/Amanon-666/medical-agent](https://github.com/Amanon-666/medical-agent) | 算子、MCP 工具、Agent 编排、部署脚本与文档 |
| DataMate（运行平台） | [github.com/ModelEngine-Group/DataMate](https://github.com/ModelEngine-Group/DataMate) | 数据处理平台，提供算子运行时与数据集管理 |
| Nexent（运行平台） | [github.com/ModelEngine-Group/nexent](https://github.com/ModelEngine-Group/nexent) | 智能体平台，提供 Agent 编排与 MCP 工具调度 |

